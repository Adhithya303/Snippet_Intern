import pytest
from pydantic import ValidationError
from app.agent_contracts import RequirementUpdate
from app.schemas import HeadphoneSpecs, Requirements
from app.seed import read_seed


def test_seed_category_schemas():
    assert len(read_seed())==36


def test_omitted_and_explicit_remove_are_distinct():
    assert RequirementUpdate().changes==[]
    update=RequirementUpdate.model_validate({'changes':[{'field':'max_price_paise','value':None}]})
    assert len(update.changes)==1 and update.changes[0].value is None


@pytest.mark.parametrize('change', [{'field':'max_price_paise','value':-1},
                                   {'field':'category','value':'car'},
                                   {'field':'run_sql','value':'DROP TABLE products'},
                                   {'field':'min_ram_gb','value':0}])
def test_invalid_update(change):
    with pytest.raises(ValidationError):
        RequirementUpdate.model_validate({'changes':[change]})


def test_explicit_no_preference():
    state=Requirements(answered_no_preference=['budget'])
    assert state.hard_constraints.max_price_paise is None
    assert 'budget' in state.answered_no_preference


def test_unknown_battery_and_not_applicable_are_distinct():
    wireless=HeadphoneSpecs(connection='wireless',microphone=None,noise_cancellation=None,
                           weight_g=None,battery_hours=None,battery_applicability='applicable')
    assert wireless.battery_hours is None
    with pytest.raises(ValidationError):
        HeadphoneSpecs(connection='wired',microphone=True,noise_cancellation=False,
                       weight_g=100,battery_hours=20,battery_applicability='not_applicable')
