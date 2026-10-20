"""Day 2 contracts: LLM adapter protocol, updates and response interfaces."""
from typing import Annotated, Literal, Protocol
from pydantic import Field, model_validator
from .schemas import Category, ProductOut, Requirements, StrictModel


class SetCategory(StrictModel):
    field: Literal["category"]
    value: Category | None


class SetUses(StrictModel):
    field: Literal["intended_uses"]
    value: list[str]


class SetBudget(StrictModel):
    field: Literal["max_price_paise"]
    value: int | None = Field(default=None, ge=0)


class SetLightweight(StrictModel):
    field: Literal["lightweight"]
    value: bool | None = None


class SetMinRam(StrictModel):
    field: Literal["min_ram_gb"]
    value: int | None = Field(default=None, gt=0)


class SetWeight(StrictModel):
    field: Literal["max_weight_kg"]
    value: float | None = Field(default=None, gt=0)


class SetBrand(StrictModel):
    field: Literal["brand"]
    value: str | None = None


class SetFeatures(StrictModel):
    field: Literal["required_features"]
    value: list[str] = Field(default_factory=list)


class SetNoiseCancellation(StrictModel):
    field: Literal["noise_cancellation"]
    value: bool | None = None


class SetConnection(StrictModel):
    field: Literal["connection"]
    value: Literal["wired", "wireless", "both"] | None = None


class SetMicrophone(StrictModel):
    field: Literal["microphone"]
    value: bool | None = None


class SetMinBatteryHours(StrictModel):
    field: Literal["min_battery_hours"]
    value: int | None = Field(default=None, gt=0)


Change = Annotated[
    SetCategory
    | SetUses
    | SetBudget
    | SetLightweight
    | SetMinRam
    | SetWeight
    | SetBrand
    | SetFeatures
    | SetNoiseCancellation
    | SetConnection
    | SetMicrophone
    | SetMinBatteryHours,
    Field(discriminator="field"),
]


class RequirementUpdate(StrictModel):
    # No change object => preserve current value. null/[] => explicitly clear it.
    # A non-null value sets/replaces that one field.
    changes: list[Change] = Field(default_factory=list)
    answered_no_preference: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_duplicate_fields(self):
        fields = [c.field for c in self.changes]
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicate field update in single turn")
        return self


class LLMAdapter(Protocol):
    async def extract(self, message: str, state: Requirements) -> RequirementUpdate: ...


class ClarificationResponse(StrictModel):
    type: Literal["clarification"] = "clarification"
    question: str
    requirements: Requirements


class Recommendation(StrictModel):
    product: ProductOut
    reasons: list[str]
    trade_offs: list[str]
    unknowns: list[str]


class RecommendationResponse(StrictModel):
    type: Literal["recommendations"] = "recommendations"
    requirements: Requirements
    products: list[Recommendation] = Field(min_length=1, max_length=2)


class NoMatchResponse(StrictModel):
    type: Literal["no_match"] = "no_match"
    requirements: Requirements
    explanation: str
    proposed_adjustment_question: str


AgentResponse = Annotated[
    ClarificationResponse | RecommendationResponse | NoMatchResponse,
    Field(discriminator="type"),
]
