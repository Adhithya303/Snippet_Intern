"""Structured conversation memory and requirement state merge logic."""
from typing import Any
from .agent_contracts import RequirementUpdate
from .schemas import HardConstraints, Preferences, Requirements

LAPTOP_SPECIFIC_USES = {"general_coursework", "programming", "gaming", "local_ml", "content_creation"}
HEADPHONE_SPECIFIC_USES = {"music", "calls", "focus_study", "travel", "sports_workouts", "studio_production"}
LAPTOP_SPECIFIC_FEATURES = {"SSD storage", "Dedicated GPU", "Portable design", "High refresh rate"}
HEADPHONE_SPECIFIC_FEATURES = {"Active Noise Cancellation", "Multipoint connection", "Microphone", "Foldable design"}


def merge_requirements(current: Requirements, update: RequirementUpdate) -> Requirements:
    """
    Merge proposed updates into current requirements according to Day 2 rules:
    - Omission retains existing state.
    - Non-null value sets or replaces a requirement.
    - Explicit None or empty list clears a requirement.
    - Switching category clears incompatible category-specific fields while preserving budget and brand.
    - Tracks explicit no-preference answers.
    """
    # Start with a copy of current state
    category = current.category
    intended_uses = list(current.intended_uses)
    hard_dict = current.hard_constraints.model_dump()
    pref_dict = current.preferences.model_dump()
    answered_no_pref = list(current.answered_no_preference)

    # 1. Check if category is being changed
    new_category_change = next((c for c in update.changes if c.field == "category"), None)
    if new_category_change is not None:
        new_category = new_category_change.value
        if new_category != category and new_category is not None:
            if new_category == "headphones":
                # Clear laptop-specific fields
                hard_dict["min_ram_gb"] = None
                hard_dict["max_weight_kg"] = None
                intended_uses = [u for u in intended_uses if u not in LAPTOP_SPECIFIC_USES]
                hard_dict["required_features"] = [f for f in hard_dict.get("required_features", []) if f not in LAPTOP_SPECIFIC_FEATURES]
                if "weight" in answered_no_pref:
                    answered_no_pref.remove("weight")
            elif new_category == "laptop":
                # Clear headphone-specific fields
                hard_dict["noise_cancellation"] = None
                hard_dict["connection"] = None
                hard_dict["microphone"] = None
                hard_dict["min_battery_hours"] = None
                pref_dict["noise_cancellation"] = None
                intended_uses = [u for u in intended_uses if u not in HEADPHONE_SPECIFIC_USES]
                hard_dict["required_features"] = [f for f in hard_dict.get("required_features", []) if f not in HEADPHONE_SPECIFIC_FEATURES]

    # 2. Apply explicit changes
    for change in update.changes:
        field = change.field
        val = change.value

        if field == "category":
            category = val

        elif field == "intended_uses":
            if val is None or len(val) == 0:
                intended_uses = []
            else:
                # Deduplicate while preserving order
                intended_uses = list(dict.fromkeys(val))

        elif field == "max_price_paise":
            hard_dict["max_price_paise"] = val
            if val is not None and "budget" in answered_no_pref:
                answered_no_pref.remove("budget")

        elif field == "min_ram_gb":
            hard_dict["min_ram_gb"] = val

        elif field == "max_weight_kg":
            hard_dict["max_weight_kg"] = val
            if val is not None and "weight" in answered_no_pref:
                answered_no_pref.remove("weight")

        elif field == "required_features":
            if val is None or len(val) == 0:
                hard_dict["required_features"] = []
            else:
                hard_dict["required_features"] = list(dict.fromkeys(val))

        elif field == "lightweight":
            pref_dict["lightweight"] = val
            if val is not None and "weight" in answered_no_pref:
                answered_no_pref.remove("weight")

        elif field == "brand":
            pref_dict["brand"] = val
            if val is not None and "brand" in answered_no_pref:
                answered_no_pref.remove("brand")

        elif field == "noise_cancellation":
            hard_dict["noise_cancellation"] = val

        elif field == "connection":
            hard_dict["connection"] = val

        elif field == "microphone":
            hard_dict["microphone"] = val

        elif field == "min_battery_hours":
            hard_dict["min_battery_hours"] = val

    # 3. Merge answered_no_preference
    for no_pref in update.answered_no_preference:
        if no_pref not in answered_no_pref:
            answered_no_pref.append(no_pref)
        if no_pref == "budget":
            hard_dict["max_price_paise"] = None
        elif no_pref == "brand":
            pref_dict["brand"] = None
        elif no_pref == "weight":
            pref_dict["lightweight"] = None
            hard_dict["max_weight_kg"] = None

    # 4. Unresolved questions
    unresolved = list(update.unresolved_questions)

    return Requirements(
        category=category,
        intended_uses=intended_uses,
        hard_constraints=HardConstraints.model_validate(hard_dict),
        preferences=Preferences.model_validate(pref_dict),
        answered_no_preference=answered_no_pref,
        unresolved_questions=unresolved,
    )
