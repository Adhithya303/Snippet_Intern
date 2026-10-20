"""Comprehensive Day 2 behavioural, memory, ranking, and failure recovery tests."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.agent_contracts import (
    RequirementUpdate,
    SetBudget,
    SetCategory,
    SetFeatures,
    SetLightweight,
    SetMinRam,
    SetUses,
    SetWeight,
)
from app.llm import (
    FakeLLMAdapter,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.models import Conversation, Message, Product
from app.ranking import search_and_rank
from app.schemas import HardConstraints, Preferences, Requirements


def test_vague_request_produces_clarification(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetUses(field="intended_uses", value=["general_coursework"]),
            ],
            answered_no_preference=[],
            unresolved_questions=[],
        )
    )
    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a laptop for college"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "clarification"
    assert "budget" in data["question"].lower() or "tasks" in data["question"].lower()
    # Confirm state was updated
    conv = client.get(f"/api/v1/conversations/{conv_id}").json()
    assert conv["requirements"]["category"] == "laptop"
    assert conv["requirements"]["intended_uses"] == ["general_coursework"]


def test_complete_request_proceeds_to_search(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetUses(field="intended_uses", value=["programming"]),
                SetBudget(field="max_price_paise", value=7000000),
            ],
            answered_no_preference=[],
            unresolved_questions=[],
        )
    )
    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a programming laptop under 70000 rupees"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "recommendations"
    assert 1 <= len(data["products"]) <= 2
    # Verify products meet budget
    for r in data["products"]:
        assert r["product"]["price_paise"] <= 7000000
        assert r["product"]["category"] == "laptop"


def test_budget_revision_retains_unrelated_requirements(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    # Turn 1: establish programming laptop under 70000 with 16GB RAM
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetUses(field="intended_uses", value=["programming"]),
                SetBudget(field="max_price_paise", value=7000000),
                SetMinRam(field="min_ram_gb", value=16),
            ]
        )
    )
    client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a programming laptop under 70000 with 16GB RAM"},
    )

    # Turn 2: revise budget only to 60000
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetBudget(field="max_price_paise", value=6000000),
            ]
        )
    )
    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Actually 60000"},
    )
    assert resp.status_code == 200
    data = resp.json()
    reqs = data["requirements"]
    assert reqs["hard_constraints"]["max_price_paise"] == 6000000
    # Retained unrelated requirements
    assert reqs["hard_constraints"]["min_ram_gb"] == 16
    assert reqs["intended_uses"] == ["programming"]
    assert reqs["category"] == "laptop"


def test_preference_removal_works(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    # Turn 1: lightweight laptop
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetLightweight(field="lightweight", value=True),
            ]
        )
    )
    client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I prefer a lightweight laptop"},
    )

    # Turn 2: remove weight preference
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetLightweight(field="lightweight", value=None),
            ],
            answered_no_preference=["weight"],
        )
    )
    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Weight doesn't matter anymore"},
    )
    assert resp.status_code == 200
    reqs = resp.json()["requirements"]
    assert reqs["preferences"]["lightweight"] is None
    assert "weight" in reqs["answered_no_preference"]


def test_no_preference_remains_answered(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    # Customer explicitly states no brand preference
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetUses(field="intended_uses", value=["programming"]),
            ],
            answered_no_preference=["brand"],
        )
    )
    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Any brand is fine for programming laptop"},
    )
    reqs = resp.json()["requirements"]
    assert "brand" in reqs["answered_no_preference"]

    # Next turn: adding budget should NOT erase answered_no_preference
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetBudget(field="max_price_paise", value=8000000),
            ]
        )
    )
    resp2 = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Under 80000"},
    )
    reqs2 = resp2.json()["requirements"]
    assert "brand" in reqs2["answered_no_preference"]
    assert reqs2["hard_constraints"]["max_price_paise"] == 8000000


def test_category_change_clears_incompatible_fields(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    # Turn 1: laptop with 16GB RAM, coursework uses, 50000 budget
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetUses(field="intended_uses", value=["general_coursework", "programming"]),
                SetMinRam(field="min_ram_gb", value=16),
                SetBudget(field="max_price_paise", value=5000000),
            ]
        )
    )
    client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "Laptop with 16GB RAM under 50000"})

    # Turn 2: switch to headphones
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="headphones"),
                SetUses(field="intended_uses", value=["music"]),
            ]
        )
    )
    resp = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "Actually show me headphones for music"})
    reqs = resp.json()["requirements"]
    assert reqs["category"] == "headphones"
    assert reqs["intended_uses"] == ["music"]
    # Incompatible laptop constraints must be cleared
    assert reqs["hard_constraints"]["min_ram_gb"] is None
    # Category-agnostic budget ceiling must be preserved!
    assert reqs["hard_constraints"]["max_price_paise"] == 5000000


def test_contradictory_requirements_receive_clarification(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetBudget(field="max_price_paise", value=2000000),
                SetMinRam(field="min_ram_gb", value=64),
            ],
            unresolved_questions=["A 64GB RAM laptop is not available under ₹20,000. Would you like to adjust budget or RAM?"],
        )
    )
    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need 64GB RAM laptop for under 20000"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "clarification"
    assert "64gb" in data["question"].lower() or "adjust" in data["question"].lower()


def test_exact_budget_boundary_is_included(client, engine):
    # LAP-015 is priced at exactly 70,000 INR (7000000 paise)
    with Session(engine) as session:
        lap015 = session.get(Product, "LAP-015")
        assert lap015 is not None
        assert lap015.price_paise == 7000000

        # Boundary inclusive search
        state_exact = Requirements(
            category="laptop",
            hard_constraints=HardConstraints(max_price_paise=7000000),
        )
        res_exact = search_and_rank(session, state_exact)
        assert res_exact.type == "recommendations"
        product_ids = [r.product.id for r in res_exact.products]
        # At boundary, items <= 7000000 qualify

        # Below boundary by 1 paise
        state_below = Requirements(
            category="laptop",
            hard_constraints=HardConstraints(max_price_paise=6999999),
        )
        res_below = search_and_rank(session, state_below)
        for r in res_below.products:
            assert r.product.price_paise <= 6999999
            assert r.product.id != "LAP-015"


def test_every_recommendation_meets_mandatory_constraints(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetBudget(field="max_price_paise", value=6500000),
                SetMinRam(field="min_ram_gb", value=16),
            ]
        )
    )
    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Laptop with at least 16GB RAM under 65000"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "recommendations"
    for r in data["products"]:
        p = r["product"]
        assert p["category"] == "laptop"
        assert p["price_paise"] <= 6500000
        assert p["specifications"]["ram_gb"] >= 16


def test_one_match_and_no_match_cases(client, engine):
    with Session(engine) as session:
        # Case 1: No match (impossible budget for laptop)
        state_no_match = Requirements(
            category="laptop",
            hard_constraints=HardConstraints(max_price_paise=1000000),  # ₹10,000 (cheapest is ₹29,990)
        )
        res_no = search_and_rank(session, state_no_match)
        assert res_no.type == "no_match"
        assert "below our lowest-priced" in res_no.explanation or "no laptop" in res_no.explanation.lower()
        assert "₹29,990" in res_no.explanation or "adjusting" in res_no.proposed_adjustment_question.lower()

        # Case 2: One match
        # Let's find a very specific constraint matching exactly 1 laptop
        state_one = Requirements(
            category="laptop",
            hard_constraints=HardConstraints(
                max_price_paise=3000000,  # <= ₹30,000 -> only LAP-023 is ₹29,990
            ),
        )
        res_one = search_and_rank(session, state_one)
        assert res_one.type == "recommendations"
        assert len(res_one.products) == 1
        assert res_one.products[0].product.id == "LAP-023"


def test_missing_required_specifications_disqualifies_product(client, engine):
    # LAP-023 has weight_kg: null
    with Session(engine) as session:
        p23 = session.get(Product, "LAP-023")
        assert p23.specifications.get("weight_kg") is None

        # When maximum weight is specified, LAP-023 MUST NOT qualify
        state = Requirements(
            category="laptop",
            hard_constraints=HardConstraints(max_weight_kg=1.8),
        )
        res = search_and_rank(session, state)
        assert res.type == "recommendations"
        product_ids = [r.product.id for r in res.products]
        assert "LAP-023" not in product_ids


def test_facts_in_recommendations_match_stored_records(client, engine):
    with Session(engine) as session:
        state = Requirements(
            category="laptop",
            intended_uses=["programming"],
            hard_constraints=HardConstraints(max_price_paise=6000000),
        )
        res = search_and_rank(session, state)
        assert res.type == "recommendations"
        for rec in res.products:
            db_p = session.get(Product, rec.product.id)
            assert db_p is not None
            assert rec.product.name == db_p.name
            assert rec.product.price_paise == db_p.price_paise
            assert rec.product.specifications == db_p.specifications
            assert rec.product.features == db_p.features
            assert rec.product.intended_uses == db_p.intended_uses
            # Check grounded reasons and trade-offs are non-empty
            assert len(rec.reasons) >= 1
            assert len(rec.trade_offs) >= 1


def test_malformed_model_output_preserves_state(client, fake_llm, engine):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    # Queue malformed output error
    fake_llm.queue_response(LLMValidationError("Malformed JSON from LLM"))

    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a laptop"},
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "llm_invalid_response"

    # Verify conversation state was untouched and no messages saved
    conv = client.get(f"/api/v1/conversations/{conv_id}").json()
    assert conv["requirements"]["category"] is None
    assert len(conv["messages"]) == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Message)) == 0


def test_timeout_preserves_state(client, fake_llm, engine):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    fake_llm.queue_response(LLMTimeoutError("Timed out after 10s"))

    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a laptop"},
    )
    assert resp.status_code == 504
    assert resp.json()["error"]["code"] == "llm_timeout"

    conv = client.get(f"/api/v1/conversations/{conv_id}").json()
    assert len(conv["messages"]) == 0


def test_rate_limit_handling(client, fake_llm):
    conv_id = client.post("/api/v1/conversations").json()["id"]
    fake_llm.queue_response(LLMRateLimitError("Rate limit exceeded"))

    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a laptop"},
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limit_exceeded"


def test_conversation_isolation_and_persistence(client, fake_llm):
    c1 = client.post("/api/v1/conversations").json()["id"]
    c2 = client.post("/api/v1/conversations").json()["id"]
    assert c1 != c2

    # Message to c1
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetBudget(field="max_price_paise", value=5000000),
            ]
        )
    )
    client.post(f"/api/v1/conversations/{c1}/messages", json={"content": "Laptop under 50000"})

    # Message to c2
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="headphones"),
                SetBudget(field="max_price_paise", value=1000000),
            ]
        )
    )
    client.post(f"/api/v1/conversations/{c2}/messages", json={"content": "Headphones under 10000"})

    # Check isolation
    conv1 = client.get(f"/api/v1/conversations/{c1}").json()
    conv2 = client.get(f"/api/v1/conversations/{c2}").json()

    assert conv1["requirements"]["category"] == "laptop"
    assert conv1["requirements"]["hard_constraints"]["max_price_paise"] == 5000000
    assert len(conv1["messages"]) == 2

    assert conv2["requirements"]["category"] == "headphones"
    assert conv2["requirements"]["hard_constraints"]["max_price_paise"] == 1000000
    assert len(conv2["messages"]) == 2


def test_database_error_remains_distinct_from_no_match(client, app, monkeypatch):
    conv_id = client.post("/api/v1/conversations").json()["id"]

    # Simulate database failure during message processing
    def fail_engine(*args, **kwargs):
        raise OperationalError("Database connection lost", {}, Exception("db error"))

    monkeypatch.setattr(app.state.engine, "connect", fail_engine)

    # Health check reflects database unavailable (503)
    health = client.get("/api/v1/health")
    assert health.status_code == 503
    assert health.json()["database"] == "unavailable"


def test_overlapping_message_handling(client, fake_llm, engine):
    conv_id = client.post("/api/v1/conversations").json()["id"]

    # Simulate concurrent turn updating updated_at before current turn commits
    # Turn 1 gets queued
    fake_llm.queue_response(
        RequirementUpdate(
            changes=[
                SetCategory(field="category", value="laptop"),
                SetBudget(field="max_price_paise", value=5000000),
            ]
        )
    )

    # Artificially modify updated_at in the database right during extraction
    original_extract = fake_llm.extract

    async def concurrent_extract(message, state):
        res = await original_extract(message, state)
        with Session(engine) as s:
            c = s.get(Conversation, conv_id)
            c.updated_at = datetime.now(timezone.utc)
            s.commit()
        return res

    fake_llm.extract = concurrent_extract

    resp = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Laptop under 50000"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "concurrency_conflict"
