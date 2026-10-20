"""Conversation controller orchestrating message validation, LLM extraction, memory merge, clarification, search, and atomic persistence."""
import logging
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .agent_contracts import (
    AgentResponse,
    ClarificationResponse,
    LLMAdapter,
    NoMatchResponse,
    RecommendationResponse,
)
from .llm import (
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMValidationError,
)
from .memory import merge_requirements
from .models import Conversation, Message, utcnow
from .ranking import format_inr, search_and_rank
from .schemas import MessageInput, Requirements

logger = logging.getLogger(__name__)


def decide_clarification(state: Requirements) -> str | None:
    """
    Decide if a focused question is required before searching.
    Ask only questions that materially affect recommendations.
    Do not ask if customer has already given explicit no-preference.
    """
    # 1. Unresolved questions / contradictions
    if state.unresolved_questions:
        return state.unresolved_questions[0]

    # 2. Missing category
    if state.category is None:
        return "Are you looking for a laptop or headphones?"

    # 3. Vague laptop request: only college/coursework with no budget and no answered no-preference
    if state.category == "laptop":
        is_vague_use = len(state.intended_uses) == 0 or state.intended_uses == ["general_coursework"]
        no_budget = state.hard_constraints.max_price_paise is None and "budget" not in state.answered_no_preference
        if is_vague_use and no_budget:
            return "What primary tasks will you use the laptop for (such as general coursework, programming, or gaming), and do you have a target budget?"

    # 4. Vague headphones request
    if state.category == "headphones":
        if len(state.intended_uses) == 0 and state.hard_constraints.max_price_paise is None and "budget" not in state.answered_no_preference:
            return "What will you primarily use the headphones for (such as music, calls, study focus, or travel), and do you have a target budget?"

    return None


async def handle_message(
    conversation_id: UUID,
    payload: MessageInput,
    engine,
    llm_adapter: LLMAdapter,
) -> AgentResponse:
    """
    Orchestrate full message handling:
    1. Read conversation state outside long-lived transaction.
    2. Extract proposed updates with external LLM adapter (no DB transaction held).
    3. Merge state deterministically.
    4. Clarify or search & rank.
    5. Save state and message turn atomically with concurrency check.
    """
    conv_id_str = str(conversation_id)

    # 1. Load conversation record
    with Session(engine) as session:
        conv = session.get(Conversation, conv_id_str)
        if conv is None:
            raise HTTPException(404, {"code": "conversation_not_found", "message": "Conversation not found."})
        current_state = Requirements.model_validate(conv.requirements)
        version_timestamp = conv.updated_at

    # 2. Extract proposed updates via LLM adapter outside of DB transaction
    try:
        update = await llm_adapter.extract(payload.content, current_state)
    except LLMTimeoutError as exc:
        logger.warning("LLM request timed out for conversation %s: %s", conv_id_str, exc)
        raise HTTPException(504, {"code": "llm_timeout", "message": "The AI service timed out. Your message was not saved. Please retry."})
    except LLMRateLimitError as exc:
        logger.warning("LLM rate limit reached for conversation %s: %s", conv_id_str, exc)
        raise HTTPException(429, {"code": "rate_limit_exceeded", "message": "AI service quota or rate limit exceeded. Please wait a moment and retry."})
    except LLMConfigurationError as exc:
        logger.error("LLM configuration error: %s", exc)
        raise HTTPException(503, {"code": "llm_unavailable", "message": "AI service is not configured. Please verify GEMINI_API_KEY."})
    except LLMUnavailableError as exc:
        logger.error("LLM service unavailable: %s", exc)
        raise HTTPException(503, {"code": "llm_unavailable", "message": "The AI service is temporarily unavailable. Please retry later."})
    except LLMValidationError as exc:
        logger.warning("LLM validation error: %s", exc)
        raise HTTPException(502, {"code": "llm_invalid_response", "message": "The AI service returned an unreadable response. Please retry."})
    except Exception as exc:
        logger.error("Unexpected error in LLM extraction: %s", exc)
        raise HTTPException(500, {"code": "agent_error", "message": "An unexpected error occurred while processing your message."})

    # 3. Merge requirements state
    new_state = merge_requirements(current_state, update)

    # 4. Check clarification policy or search catalogue
    clarification_question = decide_clarification(new_state)
    if clarification_question:
        agent_response = ClarificationResponse(
            question=clarification_question,
            requirements=new_state,
        )
        assistant_text = clarification_question
    else:
        with Session(engine) as session:
            agent_response = search_and_rank(session, new_state)

        if agent_response.type == "recommendations":
            products_summary = ", ".join(f"{r.product.name} ({format_inr(r.product.price_paise)})" for r in agent_response.products)
            assistant_text = f"Here are my top recommendations matching your requirements: {products_summary}."
        else:
            assistant_text = f"{agent_response.explanation} {agent_response.proposed_adjustment_question}"

    # 5. Persist atomically with optimistic concurrency check
    with Session(engine) as session:
        # Check if conversation still exists and version matches
        conv_record = session.get(Conversation, conv_id_str)
        if conv_record is None:
            raise HTTPException(404, {"code": "conversation_not_found", "message": "Conversation not found."})

        if conv_record.updated_at != version_timestamp:
            logger.warning("Concurrency conflict on conversation %s (stale timestamp)", conv_id_str)
            raise HTTPException(409, {"code": "concurrency_conflict", "message": "Another message is being processed in this conversation. Please retry."})

        now = utcnow()
        from datetime import timedelta
        user_message = Message(
            conversation_id=conv_id_str,
            role="user",
            content=payload.content,
            created_at=now,
        )
        assistant_message = Message(
            conversation_id=conv_id_str,
            role="assistant",
            content=assistant_text,
            created_at=now + timedelta(milliseconds=10),
        )
        session.add(user_message)
        session.add(assistant_message)

        conv_record.requirements = new_state.model_dump()
        conv_record.status = agent_response.type
        conv_record.updated_at = utcnow()
        session.commit()

    return agent_response
