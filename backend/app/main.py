import logging
from math import ceil
from typing import Annotated
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .agent_contracts import AgentResponse
from .catalogue import list_products
from .config import Settings
from .controller import handle_message
from .database import make_engine
from .llm import FakeLLMAdapter, GeminiLLMAdapter
from .models import Conversation, Message, Product
from .schemas import (
    Category,
    ConversationOut,
    ErrorEnvelope,
    HealthOut,
    MessageInput,
    MessageOut,
    ProductOut,
    ProductPage,
    Requirements,
)

logger = logging.getLogger(__name__)


def get_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


def create_app(engine=None, settings=None, llm_adapter=None):
    settings = settings or Settings()
    app = FastAPI(
        title="Electronics Sales Assistant",
        version="0.2.0",
        description="Grounded AI sales assistant for laptops and headphones with structured conversation memory and requirement tracking. Prices use integer paise (100 paise = INR 1).",
    )
    app.state.engine = engine if engine is not None else make_engine(settings.database_url)
    app.state.settings = settings

    if llm_adapter is not None:
        app.state.llm_adapter = llm_adapter
    elif settings.gemini_api_key:
        app.state.llm_adapter = GeminiLLMAdapter(settings=settings)
    else:
        app.state.llm_adapter = FakeLLMAdapter()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request. Check the documented field types, bounds and required values.",
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request, exc):
        # Log the error class only: connection strings and SQL parameters may contain sensitive data.
        logger.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "The database is unavailable. Please retry later.",
                }
            },
        )

    SessionDep = Annotated[Session, Depends(get_session)]
    errors = {
        422: {"model": ErrorEnvelope},
        503: {"model": ErrorEnvelope},
    }

    @app.get("/api/v1/products", response_model=ProductPage, tags=["Catalogue"], responses=errors)
    def products(
        session: SessionDep,
        category: Category | None = None,
        max_price_paise: Annotated[int | None, Query(ge=0, le=2_000_000_000)] = None,
        page: Annotated[int, Query(ge=1, le=100000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 12,
    ):
        """Filter stored records. Stable order: price ascending, then product ID."""
        items, total = list_products(session, category, max_price_paise, page, page_size)
        return ProductPage(
            items=[ProductOut.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total > 0 else 0,
        )

    @app.get(
        "/api/v1/products/{product_id}",
        response_model=ProductOut,
        tags=["Catalogue"],
        responses={**errors, 404: {"model": ErrorEnvelope}},
    )
    def product(product_id: str, session: SessionDep):
        item = session.get(Product, product_id)
        if item is None:
            raise HTTPException(404, {"code": "product_not_found", "message": "Product not found."})
        return ProductOut.model_validate(item)

    def conversation_record(conversation_id, session):
        item = session.get(Conversation, str(conversation_id))
        if item is None:
            raise HTTPException(404, {"code": "conversation_not_found", "message": "Conversation not found."})
        return item

    def conversation_output(item, session):
        history = session.scalars(
            select(Message)
            .where(Message.conversation_id == item.id)
            .order_by(Message.created_at, Message.id)
        ).all()
        return ConversationOut(
            id=item.id,
            requirements=Requirements.model_validate(item.requirements),
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
            messages=[MessageOut.model_validate(m) for m in history],
        )

    @app.post(
        "/api/v1/conversations",
        response_model=ConversationOut,
        status_code=201,
        tags=["Conversations"],
        responses=errors,
    )
    def new_conversation(session: SessionDep):
        item = Conversation(requirements=Requirements().model_dump())
        session.add(item)
        session.commit()
        session.refresh(item)
        return conversation_output(item, session)

    @app.get(
        "/api/v1/conversations/{conversation_id}",
        response_model=ConversationOut,
        tags=["Conversations"],
        responses={**errors, 404: {"model": ErrorEnvelope}},
    )
    def conversation(conversation_id: UUID, session: SessionDep):
        return conversation_output(conversation_record(conversation_id, session), session)

    @app.post(
        "/api/v1/conversations/{conversation_id}/messages",
        response_model=AgentResponse,
        status_code=200,
        tags=["Conversations"],
        responses={
            **errors,
            404: {"model": ErrorEnvelope},
            409: {"model": ErrorEnvelope},
            429: {"model": ErrorEnvelope},
            502: {"model": ErrorEnvelope},
            504: {"model": ErrorEnvelope},
        },
        summary="AI message processing and grounded recommendations",
    )
    async def message(conversation_id: UUID, payload: MessageInput, request: Request):
        """Process customer message, update structured requirements, clarify or return grounded recommendations."""
        return await handle_message(
            conversation_id=conversation_id,
            payload=payload,
            engine=request.app.state.engine,
            llm_adapter=request.app.state.llm_adapter,
        )

    @app.get(
        "/api/v1/health",
        response_model=HealthOut,
        tags=["System"],
        responses={503: {"model": HealthOut}},
    )
    def health():
        name = app.state.engine.dialect.name
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return HealthOut(
                status="ok",
                database="connected",
                database_engine=name,
                agent="active",
                build_stage="day2",
            )
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503,
                content=HealthOut(
                    status="unavailable",
                    database="unavailable",
                    database_engine=name,
                    agent="active",
                    build_stage="day2",
                ).model_dump(),
            )

    return app


app = create_app()
