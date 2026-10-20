from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from app.main import get_session
from app.models import Conversation, Message, Product
from app.seed import seed


def test_catalogue_total(client):
    result = client.get('/api/v1/products').json()
    assert result['total'] == 36
    assert len(result['items']) == 12
    assert result['total_pages'] == 3


@pytest.mark.parametrize('category,count', [('laptop',24),('headphones',12)])
def test_category(client,category,count):
    result = client.get('/api/v1/products',params={'category':category,'page_size':100}).json()
    assert result['total'] == count
    assert all(p['category']==category for p in result['items'])


def test_budget_boundary(client):
    boundary = 7000000
    result = client.get('/api/v1/products',params={'category':'laptop','max_price_paise':boundary,'page_size':100}).json()
    assert all(p['price_paise']<=boundary for p in result['items'])
    assert 'LAP-015' in [p['id'] for p in result['items']]
    below = client.get('/api/v1/products',params={'category':'laptop','max_price_paise':boundary-1,'page_size':100}).json()
    assert 'LAP-015' not in [p['id'] for p in below['items']]


def test_empty_budget(client):
    result = client.get('/api/v1/products?max_price_paise=0').json()
    assert result['items']==[] and result['total']==0 and result['total_pages']==0


def test_pagination_stable(client):
    all_items = client.get('/api/v1/products?page_size=100').json()['items']
    pages = [client.get(f'/api/v1/products?page={i}&page_size=7').json()['items'] for i in range(1,7)]
    flattened = [p for page in pages for p in page]
    assert flattened == all_items
    assert [(p['price_paise'],p['id']) for p in all_items] == sorted((p['price_paise'],p['id']) for p in all_items)


@pytest.mark.parametrize('query', ['page=0','page=-1','page_size=0','page_size=101','category=phone',
                                 'max_price_paise=-1','max_price_paise=12.5','page=hello','max_price_paise=3000000000'])
def test_invalid_filters(client,query):
    response=client.get('/api/v1/products?'+query)
    assert response.status_code==422
    assert response.json()['error']['code']=='validation_error'


def test_product_detail_and_missing(client):
    response=client.get('/api/v1/products/LAP-001')
    assert response.status_code==200
    assert response.json()['price_paise']==3299000
    assert client.get('/api/v1/products/not-real').status_code==404


def test_page_beyond_end(client):
    response=client.get('/api/v1/products?page=10').json()
    assert response['items']==[] and response['total']==36


def test_persistent_conversation(client,engine):
    response=client.post('/api/v1/conversations')
    assert response.status_code==201
    record=response.json()
    assert record['status']=='awaiting_agent' and record['messages']==[]
    assert record['requirements']['hard_constraints']['max_price_paise'] is None
    assert client.get('/api/v1/conversations/'+record['id']).json()==record
    with Session(engine) as session:
        assert session.get(Conversation,record['id']) is not None


def test_history_order_and_isolation(client,engine):
    a=client.post('/api/v1/conversations').json()['id']
    b=client.post('/api/v1/conversations').json()['id']
    assert a!=b
    now=datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add_all([Message(conversation_id=a,role='assistant',content='Second',created_at=now),
                         Message(conversation_id=a,role='user',content='First',created_at=now-timedelta(seconds=1)),
                         Message(conversation_id=b,role='user',content='Separate')])
        session.commit()
    assert [m['content'] for m in client.get('/api/v1/conversations/'+a).json()['messages']]==['First','Second']
    assert [m['content'] for m in client.get('/api/v1/conversations/'+b).json()['messages']]==['Separate']


def test_unknown_conversation(client):
    unknown=str(uuid4())
    assert client.get('/api/v1/conversations/'+unknown).status_code==404
    assert client.post('/api/v1/conversations/'+unknown+'/messages',json={'content':'hello'}).status_code==404
    assert client.get('/api/v1/conversations/not-a-uuid').status_code==422


def test_agent_message_processing_saves_turn(client,engine):
    original=client.post('/api/v1/conversations').json()
    url='/api/v1/conversations/'+original['id']
    response=client.post(url+'/messages',json={'content':'I need a programming laptop under 70000 rupees'})
    assert response.status_code==200
    data=response.json()
    assert data['type'] in ('clarification', 'recommendations', 'no_match')
    updated=client.get(url).json()
    assert len(updated['messages'])==2
    assert updated['messages'][0]['role']=='user'
    assert updated['messages'][1]['role']=='assistant'
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Message))==2


@pytest.mark.parametrize('payload',[{}, {'content':''},{'content':'   '},{'content':'a'*4001},
                                  {'content':42},{'content':'hello','unexpected':True}])
def test_invalid_messages(client,payload):
    cid=client.post('/api/v1/conversations').json()['id']
    assert client.post(f'/api/v1/conversations/{cid}/messages',json=payload).status_code==422


def test_health(client):
    response=client.get('/api/v1/health')
    assert response.status_code==200
    assert response.json()['agent']=='active'


def test_health_database_failure(client,engine,monkeypatch):
    def fail(*args,**kwargs):
        raise OperationalError('private connection detail',{},Exception('secret'))
    monkeypatch.setattr(engine,'connect',fail)
    response=client.get('/api/v1/health')
    assert response.status_code==503
    assert response.json()['database']=='unavailable'
    assert 'secret' not in response.text


def test_catalogue_database_failure(client,app):
    def fail_session():
        raise OperationalError('private SQL',{},Exception('secret'))
        yield
    app.dependency_overrides[get_session]=fail_session
    response=client.get('/api/v1/products')
    assert response.status_code==503
    assert response.json()['error']['code']=='database_unavailable'
    assert 'secret' not in response.text


def test_seed_is_idempotent_and_preserves_edits(engine):
    with Session(engine) as session:
        item=session.get(Product,'LAP-001')
        item.name='User-edited name'
        session.commit()
        assert seed(session)==0
        assert session.scalar(select(func.count()).select_from(Product))==36
        assert session.get(Product,'LAP-001').name=='User-edited name'


def test_openapi_exposes_all_required_paths(client):
    paths=client.get('/openapi.json').json()['paths']
    assert len(paths)==6
    assert '200' in paths['/api/v1/conversations/{conversation_id}/messages']['post']['responses']
