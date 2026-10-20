"""Controlled search, eligibility filtering, deterministic ranking, and grounded responses."""
from typing import List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from .agent_contracts import (
    NoMatchResponse,
    ProductOut,
    Recommendation,
    RecommendationResponse,
)
from .models import Product
from .schemas import Requirements


def format_inr(paise: int) -> str:
    """Format paise to INR currency string, e.g. 7000000 -> ₹70,000."""
    rupees = paise / 100
    if rupees.is_integer():
        return f"₹{int(rupees):,}"
    return f"₹{rupees:,.2f}"


def check_eligibility(product: Product, state: Requirements) -> Tuple[bool, str | None]:
    """
    Strict mandatory constraint check.
    Returns (True, None) if eligible, or (False, reason) if excluded.
    A missing required specification must not count as satisfying the constraint.
    """
    hard = state.hard_constraints
    specs = product.specifications or {}

    # Category check
    if state.category and product.category != state.category:
        return False, f"Category mismatch: expected {state.category}, got {product.category}"

    # Maximum price check (inclusive boundary)
    if hard.max_price_paise is not None and product.price_paise > hard.max_price_paise:
        return False, f"Price {format_inr(product.price_paise)} exceeds budget {format_inr(hard.max_price_paise)}"

    # Laptop constraints
    if product.category == "laptop":
        if hard.min_ram_gb is not None:
            ram = specs.get("ram_gb")
            if ram is None:
                return False, "RAM specification unknown in catalogue"
            if ram < hard.min_ram_gb:
                return False, f"RAM {ram} GB below required minimum {hard.min_ram_gb} GB"

        if hard.max_weight_kg is not None:
            weight = specs.get("weight_kg")
            if weight is None:
                # Missing required specification must not count as satisfying!
                return False, "Weight unknown in catalogue records"
            if weight > hard.max_weight_kg:
                return False, f"Weight {weight} kg exceeds maximum {hard.max_weight_kg} kg"

    # Headphone constraints
    elif product.category == "headphones":
        if hard.noise_cancellation is True:
            anc = specs.get("noise_cancellation")
            if not anc:
                return False, "Does not have active noise cancellation"

        if hard.connection is not None:
            conn = specs.get("connection")
            if conn != hard.connection and conn != "both":
                return False, f"Connection type is {conn}, required {hard.connection}"

        if hard.microphone is True:
            mic = specs.get("microphone")
            if not mic:
                return False, "Microphone not included"

        if hard.min_battery_hours is not None:
            bh = specs.get("battery_hours")
            if bh is None:
                return False, "Battery hours unknown or not applicable"
            if bh < hard.min_battery_hours:
                return False, f"Battery {bh}h below required {hard.min_battery_hours}h"

    # Required features
    if hard.required_features:
        product_features = set(product.features or [])
        for feat in hard.required_features:
            if feat not in product_features:
                return False, f"Missing required feature: {feat}"

    return True, None


def score_product(product: Product, state: Requirements) -> float:
    """
    Deterministic suitability score based on:
    - Intended-use fit
    - Stated preferences
    - Relevant capabilities
    - Price/value heuristic
    """
    score = 0.0
    specs = product.specifications or {}
    p_uses = set(product.intended_uses or [])

    # Intended uses
    for use in state.intended_uses:
        if use in p_uses:
            score += 35.0

    # Preferences
    pref = state.preferences

    # Lightweight preference
    if pref.lightweight is True:
        if product.category == "laptop":
            w = specs.get("weight_kg")
            if w is not None:
                if w <= 1.35:
                    score += 25.0
                elif w <= 1.6:
                    score += 15.0
                elif w <= 1.8:
                    score += 5.0
        elif product.category == "headphones":
            w = specs.get("weight_g")
            if w is not None:
                if w <= 200:
                    score += 20.0
                elif w <= 260:
                    score += 10.0

    # Brand preference
    if pref.brand:
        if pref.brand.lower() in product.name.lower():
            score += 30.0

    # Noise cancellation preference
    if pref.noise_cancellation is True:
        if specs.get("noise_cancellation") is True:
            score += 20.0

    # Category-specific capabilities
    if product.category == "laptop":
        ram = specs.get("ram_gb", 0)
        score += min(ram * 1.5, 24.0)

        # Dedicated GPU reward for demanding uses
        if any(u in ("gaming", "local_ml", "content_creation") for u in state.intended_uses):
            vram = specs.get("vram_gb")
            if vram and vram > 0:
                score += 30.0
                score += min(vram * 2.0, 16.0)

    elif product.category == "headphones":
        bh = specs.get("battery_hours")
        if bh and bh > 0:
            score += min(bh * 0.5, 20.0)

    # Budget efficiency / value bonus: reward staying within budget
    if state.hard_constraints.max_price_paise and state.hard_constraints.max_price_paise > 0:
        ratio = product.price_paise / state.hard_constraints.max_price_paise
        score += (1.0 - ratio) * 10.0

    return score


def generate_grounded_reasons(product: Product, state: Requirements) -> List[str]:
    reasons = []
    specs = product.specifications or {}
    p_uses = set(product.intended_uses or [])

    # Intended use reasons
    matching_uses = [u for u in state.intended_uses if u in p_uses]
    if matching_uses:
        use_labels = ", ".join(u.replace("_", " ") for u in matching_uses)
        if product.category == "laptop":
            reasons.append(f"Suitable for {use_labels} with {specs.get('cpu', 'CPU')} and {specs.get('ram_gb', 0)} GB RAM.")
        else:
            reasons.append(f"Designed for {use_labels}.")

    # Budget reason
    if state.hard_constraints.max_price_paise is not None:
        reasons.append(f"Priced at {format_inr(product.price_paise)}, within your budget ceiling of {format_inr(state.hard_constraints.max_price_paise)}.")
    else:
        reasons.append(f"Priced at {format_inr(product.price_paise)}.")

    # Lightweight reason
    if state.preferences.lightweight is True:
        if product.category == "laptop" and specs.get("weight_kg") is not None:
            reasons.append(f"Lightweight build at {specs['weight_kg']} kg matches your portability preference.")
        elif product.category == "headphones" and specs.get("weight_g") is not None:
            reasons.append(f"Comfortable lightweight build at {specs['weight_g']} g.")

    # ANC reason
    if (state.hard_constraints.noise_cancellation or state.preferences.noise_cancellation) and specs.get("noise_cancellation"):
        reasons.append("Equipped with Active Noise Cancellation.")

    # Default fallback reason if list is short
    if len(reasons) < 2:
        if product.category == "laptop":
            reasons.append(f"Includes {specs.get('storage_gb', 0)} GB fast SSD storage and {specs.get('operating_system', 'OS')}.")
        elif product.category == "headphones":
            conn = specs.get("connection", "wireless")
            reasons.append(f"Features {conn} connectivity and ergonomic fit.")

    return reasons


def generate_grounded_trade_offs(product: Product, state: Requirements) -> List[str]:
    trade_offs = []
    specs = product.specifications or {}

    if product.category == "laptop":
        vram = specs.get("vram_gb")
        if not vram:
            if any(u in ("gaming", "local_ml") for u in state.intended_uses):
                trade_offs.append("Uses integrated graphics without dedicated VRAM; demanding 3D games and local LLM training will be constrained.")
            else:
                trade_offs.append("Uses integrated graphics, which is great for battery life but unsuitable for heavy 3D workloads.")

        weight = specs.get("weight_kg")
        if weight is not None and weight > 1.8:
            trade_offs.append(f"At {weight} kg, it is heavier than ultraportable alternatives.")

    elif product.category == "headphones":
        conn = specs.get("connection")
        if conn == "wired":
            trade_offs.append("Wired connection provides zero-latency audio without battery limits, but requires a 3.5mm headphone jack.")
        elif conn == "wireless" and not specs.get("noise_cancellation"):
            trade_offs.append("Does not include active noise cancellation; isolation relies on passive ear-cup fit.")

    # Price proximity trade-off
    if state.hard_constraints.max_price_paise:
        ratio = product.price_paise / state.hard_constraints.max_price_paise
        if ratio > 0.95:
            trade_offs.append(f"Price is near the top of your {format_inr(state.hard_constraints.max_price_paise)} ceiling.")

    if not trade_offs:
        trade_offs.append("Balanced design with standard specifications for its price point.")

    return trade_offs


def identify_unknowns(product: Product) -> List[str]:
    unknowns = []
    specs = product.specifications or {}

    if product.category == "laptop":
        if specs.get("weight_kg") is None:
            unknowns.append("Weight is not specified in catalogue records.")
        if specs.get("vram_gb") is None:
            unknowns.append("Dedicated VRAM is not applicable (integrated GPU).")

    elif product.category == "headphones":
        if specs.get("battery_hours") is None and specs.get("battery_applicability") != "not_applicable":
            unknowns.append("Battery hours are not specified in catalogue records.")
        elif specs.get("battery_applicability") == "not_applicable":
            unknowns.append("Battery is not applicable for this wired model.")
        if specs.get("weight_g") is None:
            unknowns.append("Weight is not specified in catalogue records.")

    return unknowns


def search_and_rank(
    session: Session,
    state: Requirements,
) -> RecommendationResponse | NoMatchResponse:
    """
    Search database with allowlisted filters, strictly enforce constraints,
    rank eligible items, and return up to two grounded recommendations or a no-match explanation.
    """
    category = state.category or "laptop"
    stmt = select(Product).where(Product.category == category)

    if state.hard_constraints.max_price_paise is not None:
        stmt = stmt.where(Product.price_paise <= state.hard_constraints.max_price_paise)

    # Order by price ascending in SQL as base query
    stmt = stmt.order_by(Product.price_paise.asc(), Product.id.asc())
    candidates = list(session.scalars(stmt))

    # Strict in-memory eligibility check for allowlisted specifications
    eligible_products: List[Product] = []
    exclusion_reasons: List[str] = []

    for p in candidates:
        is_ok, reason = check_eligibility(p, state)
        if is_ok:
            eligible_products.append(p)
        elif reason:
            exclusion_reasons.append(reason)

    # If no eligible products found:
    if not eligible_products:
        return build_no_match_response(session, state)

    # Score and sort eligible products with stable tie-breaking:
    # Key: (-score, price_paise, id)
    scored_products = [
        (score_product(p, state), p) for p in eligible_products
    ]
    scored_products.sort(key=lambda item: (-item[0], item[1].price_paise, item[1].id))

    # Take up to 2 recommendations
    top_items = scored_products[:2]
    recommendations = []
    for _score, product in top_items:
        product_out = ProductOut.model_validate(product)
        reasons = generate_grounded_reasons(product, state)
        trade_offs = generate_grounded_trade_offs(product, state)
        unknowns = identify_unknowns(product)
        recommendations.append(
            Recommendation(
                product=product_out,
                reasons=reasons,
                trade_offs=trade_offs,
                unknowns=unknowns,
            )
        )

    return RecommendationResponse(
        requirements=state,
        products=recommendations,
    )


def build_no_match_response(session: Session, state: Requirements) -> NoMatchResponse:
    """
    Build an honest no-match response explaining which constraint caused exclusion,
    and proposing a concrete next step without silently relaxing any constraint.
    """
    category = state.category or "laptop"
    category_label = "laptops" if category == "laptop" else "headphones"

    # Query all products in category to find nearest options
    all_cat = list(session.scalars(
        select(Product).where(Product.category == category).order_by(Product.price_paise.asc())
    ))

    if not all_cat:
        return NoMatchResponse(
            requirements=state,
            explanation=f"No {category_label} exist in the catalogue.",
            proposed_adjustment_question="Would you like to explore another category?",
        )

    hard = state.hard_constraints
    explanation_parts = []
    adjustment_question = "Would you like to adjust any of these requirements?"

    # Check budget constraint
    if hard.max_price_paise is not None:
        cheapest = all_cat[0]
        if hard.max_price_paise < cheapest.price_paise:
            explanation_parts.append(
                f"Your budget ceiling of {format_inr(hard.max_price_paise)} is below our lowest-priced {category} "
                f"({cheapest.name} at {format_inr(cheapest.price_paise)})."
            )
            adjustment_question = f"Would you be open to adjusting your budget to {format_inr(cheapest.price_paise)}?"

    # Check RAM constraint
    if category == "laptop" and hard.min_ram_gb is not None:
        max_ram_available = max((p.specifications.get("ram_gb", 0) for p in all_cat), default=0)
        if hard.min_ram_gb > max_ram_available:
            explanation_parts.append(
                f"You requested at least {hard.min_ram_gb} GB RAM, but our highest capacity laptop has {max_ram_available} GB RAM."
            )
            adjustment_question = f"Would you like to consider a model with {max_ram_available} GB RAM instead?"

    # Check weight constraint
    if category == "laptop" and hard.max_weight_kg is not None:
        known_weights = [p.specifications.get("weight_kg") for p in all_cat if p.specifications.get("weight_kg") is not None]
        min_weight = min(known_weights, default=1.2)
        if hard.max_weight_kg < min_weight:
            explanation_parts.append(
                f"You requested a maximum weight of {hard.max_weight_kg} kg, but our lightest laptop weighs {min_weight} kg."
            )
            adjustment_question = f"Would {min_weight} kg be acceptable for your needs?"

    # Check features constraint
    if hard.required_features:
        explanation_parts.append(
            f"No {category_label} in our catalogue meet all your required features ({', '.join(hard.required_features)})."
        )

    if not explanation_parts:
        explanation_parts.append(f"No {category_label} match your combined set of mandatory constraints.")

    explanation = " ".join(explanation_parts)

    return NoMatchResponse(
        requirements=state,
        explanation=explanation,
        proposed_adjustment_question=adjustment_question,
    )
