import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.config import Settings
from app.database import Base, make_engine
from app.llm import FakeLLMAdapter
from app.main import create_app
from app.seed import seed


@pytest.fixture
def engine(tmp_path):
    url = os.getenv("TEST_DATABASE_URL")
    schema = None
    admin = None
    if url:
        parsed = make_url(url)
        if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
            pytest.fail("TEST_DATABASE_URL must use PostgreSQL and a database ending in _test")
        admin = make_engine(url)
        schema = "test_" + uuid.uuid4().hex
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        db = admin.execution_options(schema_translate_map={None: schema})
    else:
        db = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(db)
    with Session(db) as session:
        seed(session)
    yield db
    if schema:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
    else:
        db.dispose()


@pytest.fixture
def fake_llm():
    return FakeLLMAdapter()


@pytest.fixture
def app(engine, fake_llm):
    return create_app(engine=engine, settings=Settings(database_url="sqlite://"), llm_adapter=fake_llm)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
