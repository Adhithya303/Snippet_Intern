from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Category = Literal["laptop", "headphones"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class LaptopSpecs(StrictModel):
    ram_gb: int = Field(gt=0)
    storage_gb: int = Field(gt=0)
    cpu: str
    gpu: str
    vram_gb: int | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, gt=0)
    operating_system: str


class HeadphoneSpecs(StrictModel):
    connection: Literal["wired", "wireless", "both"]
    microphone: bool | None
    noise_cancellation: bool | None
    weight_g: int | None = Field(default=None, gt=0)
    battery_hours: int | None = Field(default=None, gt=0)
    battery_applicability: Literal["applicable", "not_applicable"]

    @model_validator(mode="after")
    def battery_consistency(self):
        if self.connection == "wired" and self.battery_applicability != "not_applicable":
            raise ValueError("Wired-only sample products have no battery")
        if self.connection != "wired" and self.battery_applicability != "applicable":
            raise ValueError("Wireless products need a battery applicability flag")
        if self.battery_applicability == "not_applicable" and self.battery_hours is not None:
            raise ValueError("Not-applicable battery cannot have hours")
        return self


class ProductOut(StrictModel):
    id: str
    name: str
    category: Category
    price_paise: int = Field(ge=0)
    currency: Literal["INR"]
    specifications: dict
    intended_uses: list[str]
    features: list[str]

    @model_validator(mode="after")
    def category_specs(self):
        schema = LaptopSpecs if self.category == "laptop" else HeadphoneSpecs
        self.specifications = schema.model_validate(self.specifications).model_dump()
        return self


class ProductPage(StrictModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class HardConstraints(StrictModel):
    max_price_paise: int | None = Field(default=None, ge=0)
    min_ram_gb: int | None = Field(default=None, gt=0)
    max_weight_kg: float | None = Field(default=None, gt=0)
    required_features: list[str] = Field(default_factory=list)
    noise_cancellation: bool | None = None
    connection: Literal["wired", "wireless", "both"] | None = None
    microphone: bool | None = None
    min_battery_hours: int | None = Field(default=None, gt=0)


class Preferences(StrictModel):
    lightweight: bool | None = None
    brand: str | None = None
    noise_cancellation: bool | None = None


class Requirements(StrictModel):
    category: Category | None = None
    intended_uses: list[str] = Field(default_factory=list)
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    preferences: Preferences = Field(default_factory=Preferences)
    answered_no_preference: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class MessageInput(StrictModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class MessageOut(StrictModel):
    id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class ConversationOut(StrictModel):
    id: UUID
    requirements: Requirements
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = Field(default_factory=list)


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorEnvelope(StrictModel):
    error: ErrorBody


class HealthOut(StrictModel):
    status: Literal["ok", "unavailable"]
    database: Literal["connected", "unavailable"]
    database_engine: Literal["sqlite", "postgresql"]
    agent: Literal["not_implemented", "active"] = "active"
    build_stage: Literal["day1", "day2"] = "day2"
