from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid4())


json_type = JSON().with_variant(JSONB(), "postgresql")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price_paise >= 0", name="ck_positive_price"),
        CheckConstraint("category IN ('laptop', 'headphones')", name="ck_category"),
        CheckConstraint("currency = 'INR'", name="ck_currency"),
        Index("ix_product_category_price_id", "category", "price_paise", "id"),
    )
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20))
    price_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    specifications: Mapped[dict] = mapped_column(json_type)
    intended_uses: Mapped[list] = mapped_column(json_type)
    features: Mapped[list] = mapped_column(json_type)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    requirements: Mapped[dict] = mapped_column(json_type, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="awaiting_agent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_message_role"),
        Index("ix_message_conversation_time", "conversation_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
