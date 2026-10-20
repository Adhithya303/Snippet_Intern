"""LLM adapter interfaces, Gemini Developer API client, and Fake test adapter."""
import asyncio
import json
import logging
import re
from typing import Any, Protocol
import httpx
from pydantic import ValidationError

from .agent_contracts import (
    Change,
    RequirementUpdate,
    SetBudget,
    SetCategory,
    SetConnection,
    SetFeatures,
    SetLightweight,
    SetMicrophone,
    SetMinBatteryHours,
    SetMinRam,
    SetNoiseCancellation,
    SetUses,
    SetWeight,
    SetBrand,
)
from .config import Settings
from .schemas import Requirements

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM adapter errors."""
    pass


class LLMConfigurationError(LLMError):
    """Missing or invalid LLM configuration."""
    pass


class LLMTimeoutError(LLMError):
    """Provider request timed out."""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit or quota exhausted."""
    pass


class LLMUnavailableError(LLMError):
    """LLM provider service unavailable."""
    pass


class LLMValidationError(LLMError):
    """Malformed or invalid structured output from LLM."""
    pass


GEMINI_EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "changes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "field": {
                        "type": "STRING",
                        "enum": [
                            "category",
                            "intended_uses",
                            "max_price_paise",
                            "lightweight",
                            "min_ram_gb",
                            "max_weight_kg",
                            "brand",
                            "required_features",
                            "noise_cancellation",
                            "connection",
                            "microphone",
                            "min_battery_hours",
                        ],
                    },
                    "string_value": {"type": "STRING"},
                    "int_value": {"type": "INTEGER"},
                    "float_value": {"type": "NUMBER"},
                    "bool_value": {"type": "BOOLEAN"},
                    "list_value": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "is_null": {"type": "BOOLEAN"},
                },
                "required": ["field"],
            },
        },
        "answered_no_preference": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "unresolved_questions": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": ["changes", "answered_no_preference", "unresolved_questions"],
}

SYSTEM_INSTRUCTION = """You are an AI electronics sales assistant requirement extractor for a store with laptops and headphones.
Your task is to analyze the customer's message and their current requirement state, then propose structured updates.
Rules:
1. Prices in INR must be converted to integer paise (1 INR = 100 paise; e.g. Rs 70,000 = 7,000,000 paise).
2. Approximate prices like "around 70,000" are soft guidelines, NOT strict maximum ceilings unless stated as maximum, budget, under, or ceiling.
3. If the user revises a budget (e.g. "Actually 60000"), propose a change for max_price_paise with the new amount.
4. If the user removes a preference (e.g. "Weight doesn't matter anymore"), set is_null=true for lightweight/max_weight_kg and add "weight" to answered_no_preference.
5. If the user says they have no budget limit or don't care about brand/weight, add "budget", "brand", or "weight" to answered_no_preference.
6. If the user switches category (e.g. to headphones or laptops), propose setting category.
7. Only propose changes for fields the customer explicitly mentioned or revised. Do not propose changes for omitted fields.
8. If the request is contradictory (e.g. asking for conflicting specs), add a clear question to unresolved_questions.
9. Do not invent products or generate SQL.
"""


class GeminiLLMAdapter:
    """Google Gemini Developer API adapter using structured JSON output on the free tier."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.api_key = self.settings.gemini_api_key
        self.model = self.settings.gemini_model
        self.timeout_seconds = self.settings.llm_timeout_seconds

    async def extract(self, message: str, state: Requirements) -> RequirementUpdate:
        if not self.api_key:
            raise LLMConfigurationError("Gemini API key is not configured in GEMINI_API_KEY")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        prompt = f"""Current requirement state:
Category: {state.category}
Intended uses: {state.intended_uses}
Hard constraints: {state.hard_constraints.model_dump()}
Preferences: {state.preferences.model_dump()}
Answered no preference: {state.answered_no_preference}

Customer message:
{message}
"""

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_EXTRACTION_SCHEMA,
                "temperature": 0.1,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("Gemini API request timed out after %s seconds", self.timeout_seconds)
            raise LLMTimeoutError(f"Gemini API timed out after {self.timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            logger.error("Gemini network error: %s", type(exc).__name__)
            raise LLMUnavailableError(f"Gemini network request failed: {type(exc).__name__}") from exc

        if response.status_code == 429:
            raise LLMRateLimitError("Gemini rate limit or quota exceeded. Please wait and retry.")
        if response.status_code in (500, 502, 503, 504):
            raise LLMUnavailableError(f"Gemini service unavailable (HTTP {response.status_code})")
        if response.status_code != 200:
            raise LLMError(f"Gemini API returned HTTP {response.status_code}")

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMValidationError("Gemini returned empty candidates")
            part_text = candidates[0]["content"]["parts"][0]["text"]
            parsed_raw = json.loads(part_text)
            return self._build_requirement_update(parsed_raw)
        except (KeyError, IndexError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.error("Failed to parse Gemini output: %s", exc)
            raise LLMValidationError(f"Invalid structured output from Gemini: {exc}") from exc

    def _build_requirement_update(self, raw: dict[str, Any]) -> RequirementUpdate:
        changes = []
        raw_changes = raw.get("changes", [])
        for item in raw_changes:
            field = item.get("field")
            is_null = item.get("is_null", False)
            if field == "category":
                val = None if is_null else item.get("string_value")
                changes.append(SetCategory(field="category", value=val))
            elif field == "intended_uses":
                val = [] if is_null else item.get("list_value", [])
                changes.append(SetUses(field="intended_uses", value=val))
            elif field == "max_price_paise":
                val = None if is_null else item.get("int_value")
                changes.append(SetBudget(field="max_price_paise", value=val))
            elif field == "min_ram_gb":
                val = None if is_null else item.get("int_value")
                changes.append(SetMinRam(field="min_ram_gb", value=val))
            elif field == "max_weight_kg":
                val = None if is_null else (item.get("float_value") or item.get("int_value"))
                changes.append(SetWeight(field="max_weight_kg", value=val))
            elif field == "lightweight":
                val = None if is_null else item.get("bool_value")
                changes.append(SetLightweight(field="lightweight", value=val))
            elif field == "brand":
                val = None if is_null else item.get("string_value")
                changes.append(SetBrand(field="brand", value=val))
            elif field == "required_features":
                val = [] if is_null else item.get("list_value", [])
                changes.append(SetFeatures(field="required_features", value=val))
            elif field == "noise_cancellation":
                val = None if is_null else item.get("bool_value")
                changes.append(SetNoiseCancellation(field="noise_cancellation", value=val))
            elif field == "connection":
                val = None if is_null else item.get("string_value")
                changes.append(SetConnection(field="connection", value=val))
            elif field == "microphone":
                val = None if is_null else item.get("bool_value")
                changes.append(SetMicrophone(field="microphone", value=val))
            elif field == "min_battery_hours":
                val = None if is_null else item.get("int_value")
                changes.append(SetMinBatteryHours(field="min_battery_hours", value=val))

        return RequirementUpdate(
            changes=changes,
            answered_no_preference=raw.get("answered_no_preference", []),
            unresolved_questions=raw.get("unresolved_questions", []),
        )


class FakeLLMAdapter:
    """Deterministic fake LLM adapter for automated testing and offline development."""

    def __init__(self, responses: list[RequirementUpdate | Exception] | None = None):
        self.responses = list(responses or [])
        self.call_history: list[dict[str, Any]] = []

    def queue_response(self, response: RequirementUpdate | Exception):
        self.responses.append(response)

    async def extract(self, message: str, state: Requirements) -> RequirementUpdate:
        self.call_history.append({"message": message, "state": state.model_dump()})

        if self.responses:
            next_resp = self.responses.pop(0)
            if isinstance(next_resp, Exception):
                raise next_resp
            return next_resp

        # Default rule-based mock extractor for realistic natural language testing
        return self._rule_based_extract(message, state)

    def _rule_based_extract(self, message: str, state: Requirements) -> RequirementUpdate:
        msg = message.lower()
        changes: list[Change] = []
        answered_no_pref: list[str] = []
        unresolved: list[str] = []

        # Category detection
        if "laptop" in msg and "headphone" not in msg:
            changes.append(SetCategory(field="category", value="laptop"))
        elif "headphone" in msg or "earphone" in msg:
            changes.append(SetCategory(field="category", value="headphones"))

        # Budget extraction (INR to paise)
        # Match "around 70000" vs "under 70000" or "maximum 70,000" or "actually 60000"
        is_approximate = bool(re.search(r'\baround\s+₹?\s*\d+', msg))
        budget_match = re.search(r'(?:maximum|max|under|budget|below|actually|around|to)?\s*(?:rs\.?|inr|₹)?\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\s*(?:rupees|paise|k)?', msg)
        
        # Check explicit no budget limit
        if "no budget limit" in msg or "no budget" in msg or "budget doesn't matter" in msg or "budget does not matter" in msg:
            answered_no_pref.append("budget")
            changes.append(SetBudget(field="max_price_paise", value=None))
        elif not is_approximate:
            # Look for explicit numbers
            num_match = re.search(r'(?:max(?:imum)?|under|budget|below|actually|at most)?\s*(?:rs\.?|inr|₹)?\s*([0-9]+(?:,[0-9]+)?)\s*(?:rupees)?', msg)
            if num_match:
                raw_num = num_match.group(1).replace(",", "")
                try:
                    num_val = int(raw_num)
                    # If user typed e.g. 70000 -> 70000 * 100 = 7000000
                    if num_val > 1000:
                        paise = num_val * 100
                        changes.append(SetBudget(field="max_price_paise", value=paise))
                except ValueError:
                    pass

        # Intended uses
        uses = []
        if "program" in msg or "coding" in msg or "developer" in msg:
            uses.append("programming")
        if "gaming" in msg or "game" in msg:
            uses.append("gaming")
        if "college" in msg or "school" in msg or "study" in msg or "coursework" in msg:
            uses.append("general_coursework")
        if "music" in msg or "song" in msg:
            uses.append("music")
        if "call" in msg or "meeting" in msg:
            uses.append("calls")
        if "travel" in msg or "flight" in msg:
            uses.append("travel")
        if "ml" in msg or "machine learning" in msg or "ai" in msg:
            uses.append("local_ml")
        if uses:
            # If state already has uses, combine or replace
            changes.append(SetUses(field="intended_uses", value=uses))

        # RAM extraction
        ram_match = re.search(r'([0-9]+)\s*gb\s*ram', msg)
        if ram_match:
            changes.append(SetMinRam(field="min_ram_gb", value=int(ram_match.group(1))))

        # Weight preference / removal
        if "weight doesn't matter" in msg or "weight does not matter" in msg or "don't care about weight" in msg:
            answered_no_pref.append("weight")
            changes.append(SetLightweight(field="lightweight", value=None))
            changes.append(SetWeight(field="max_weight_kg", value=None))
        elif "lightweight" in msg or "light" in msg or "portable" in msg:
            changes.append(SetLightweight(field="lightweight", value=True))

        # Brand preference / removal
        if "no brand preference" in msg or "any brand" in msg or "brand doesn't matter" in msg:
            answered_no_pref.append("brand")
            changes.append(SetBrand(field="brand", value=None))

        # Noise cancellation (headphones)
        if "anc" in msg or "noise cancel" in msg or "noise cancelling" in msg:
            changes.append(SetNoiseCancellation(field="noise_cancellation", value=True))

        # Detect contradictions (e.g. impossible budget for ML laptop or conflicting requirements)
        if "local_ml" in uses and any(c.field == "max_price_paise" and c.value is not None and c.value < 4000000 for c in changes):
            unresolved.append("Local ML workstations typically require dedicated GPUs which start above ₹50,000. Your budget is under ₹40,000.")

        # Check duplicate fields inside changes to keep contract valid
        seen_fields = set()
        deduped_changes = []
        for c in changes:
            if c.field not in seen_fields:
                seen_fields.add(c.field)
                deduped_changes.append(c)

        return RequirementUpdate(
            changes=deduped_changes,
            answered_no_preference=answered_no_pref,
            unresolved_questions=unresolved,
        )
