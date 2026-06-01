"""Deterministic listing ranker for eBay Finder.

The host agent handles taste and intent. This module only applies transparent,
auditable arithmetic to already-normalized listings.
"""

from __future__ import annotations

from collections.abc import Sequence

from . import ebay_grammar as g
from .contract import Condition, Criteria, NormalizedListing


VALUE_WEIGHT = 30.0
WORKS_WEIGHT = 25.0
CONDITION_WEIGHT = 15.0
SELLER_WEIGHT = 15.0
RETURNS_WEIGHT = 5.0
NICE_TO_HAVE_WEIGHT = 10.0

LOW_PRICE_OUTLIER_RATIO = 2.5
LOW_FEEDBACK_PCT = 97.0
LOW_FEEDBACK_COUNT = 25

_STRONG_NON_WORKING_SIGNALS = (
    "for parts",
    "not working",
    "parts only",
    "as-is",
    "as is",
    "broken",
    "spares or repair",
)


def rank(
    listings: Sequence[NormalizedListing],
    criteria: Criteria,
) -> tuple[NormalizedListing, ...]:
    """Score listings 0..100 and return new scored copies, best first."""
    median_total = _median(
        listing.total_price_usd
        for listing in listings
        if listing.total_price_usd is not None and listing.total_price_usd > 0
    )

    scored = tuple(_score_listing(listing, criteria, median_total) for listing in listings)
    return tuple(
        sorted(
            scored,
            key=lambda listing: (
                -(listing.score if listing.score is not None else -1.0),
                -(listing.value_ratio if listing.value_ratio is not None else -1.0),
                listing.total_price_usd or 10**12,
                listing.item_id,
            ),
        )
    )


def _score_listing(
    listing: NormalizedListing,
    criteria: Criteria,
    median_total: float | None,
) -> NormalizedListing:
    text = _listing_text(listing)
    reasons: list[str] = []
    flags: list[str] = []

    deal_breaker = _matched_phrase(text, criteria.deal_breakers)
    if deal_breaker:
        reasons.append(f"deal breaker matched: {deal_breaker}")
        return listing.scored(
            score=0.0,
            value_ratio=_value_ratio(listing, median_total),
            works_confidence=_works_confidence(listing, text),
            reasons=tuple(reasons),
            flags=("deal-breaker",),
        )

    value_ratio = _value_ratio(listing, median_total)
    value_component = _value_component(value_ratio)
    if value_ratio is None:
        reasons.append("price unknown; value score neutral-low")
    else:
        reasons.append(f"value ratio {value_ratio:.2f} vs cohort median")
        if value_ratio >= LOW_PRICE_OUTLIER_RATIO:
            flags.append("price-outlier-low")
            reasons.append("price is unusually low for the cohort")

    works_confidence = _works_confidence(listing, text)
    if works_confidence >= 0.75:
        reasons.append("working/tested language found")
    elif works_confidence <= 0.25:
        reasons.append("non-working language found")
    else:
        reasons.append("working status unclear")

    if listing.condition is Condition.FOR_PARTS:
        flags.append("for-parts")

    if criteria.must_work and _strongly_non_working(listing, text):
        reasons.append("must work, but listing strongly signals non-working")
        return listing.scored(
            score=0.0,
            value_ratio=value_ratio,
            works_confidence=works_confidence,
            reasons=tuple(reasons),
            flags=tuple(_dedupe(flags + ["for-parts"])),
        )

    condition_component = _condition_component(listing.condition)
    reasons.append(_condition_reason(listing.condition, condition_component))

    seller_component, seller_reason, seller_flags = _seller_component(listing)
    reasons.append(seller_reason)
    flags.extend(seller_flags)

    returns_component = _returns_component(listing.returns_accepted)
    if listing.returns_accepted is True:
        reasons.append("returns accepted")
    elif listing.returns_accepted is False:
        reasons.append("seller does not accept returns")
        flags.append("no-returns")
    else:
        reasons.append("returns policy unknown")

    nice_matches = _matched_phrases(text, criteria.nice_to_haves)
    nice_boost = _nice_boost(nice_matches, criteria.nice_to_haves)
    if nice_matches:
        reasons.append("nice-to-have matched: " + ", ".join(nice_matches))

    score = (
        VALUE_WEIGHT * value_component
        + WORKS_WEIGHT * works_confidence
        + CONDITION_WEIGHT * condition_component
        + SELLER_WEIGHT * seller_component
        + RETURNS_WEIGHT * returns_component
        + nice_boost
    )
    return listing.scored(
        score=round(_clamp(score, 0.0, 100.0), 2),
        value_ratio=value_ratio,
        works_confidence=works_confidence,
        reasons=tuple(reasons),
        flags=tuple(_dedupe(flags)),
    )


def _value_ratio(listing: NormalizedListing, median_total: float | None) -> float | None:
    total = listing.total_price_usd
    if median_total is None or total is None or total <= 0:
        return None
    return median_total / total


def _value_component(value_ratio: float | None) -> float:
    if value_ratio is None:
        return 0.45
    if value_ratio >= LOW_PRICE_OUTLIER_RATIO:
        return 0.55
    if value_ratio >= 1.0:
        return _clamp(0.60 + (value_ratio - 1.0) * 0.25, 0.60, 0.90)
    return _clamp(0.60 * value_ratio, 0.05, 0.60)


def _works_confidence(listing: NormalizedListing, text: str) -> float:
    positive = sum(1 for signal in g.WORKING_SIGNALS if signal in text)
    negative = sum(1 for signal in g.NON_WORKING_SIGNALS if signal in text)
    if listing.condition is Condition.FOR_PARTS:
        negative += 2
    confidence = 0.5 + positive * 0.18 - negative * 0.28
    return round(_clamp(confidence, 0.0, 1.0), 2)


def _strongly_non_working(listing: NormalizedListing, text: str) -> bool:
    return listing.condition is Condition.FOR_PARTS or any(
        signal in text for signal in _STRONG_NON_WORKING_SIGNALS
    )


def _condition_component(condition: Condition | None) -> float:
    if condition is Condition.NEW:
        return 0.95
    if condition is Condition.OPEN_BOX:
        return 0.9
    if condition in (Condition.CERTIFIED_REFURB, Condition.SELLER_REFURB):
        return 0.85
    if condition is Condition.USED:
        return 0.75
    if condition is Condition.FOR_PARTS:
        return 0.0
    return 0.5


def _condition_reason(condition: Condition | None, component: float) -> str:
    if condition is None:
        return "condition unknown"
    return f"condition fit: {condition.value.lower()} ({component:.2f})"


def _seller_component(listing: NormalizedListing) -> tuple[float, str, tuple[str, ...]]:
    pct = listing.seller_feedback_pct
    count = listing.seller_feedback_count
    flags: list[str] = []

    if pct is None and count is None:
        return 0.5, "seller feedback unknown", ()

    pct_component = 0.5 if pct is None else _clamp((pct - 95.0) / 5.0, 0.0, 1.0)
    count_component = _feedback_count_component(count)
    component = pct_component * 0.65 + count_component * 0.35

    if (pct is not None and pct < LOW_FEEDBACK_PCT) or (
        count is not None and count < LOW_FEEDBACK_COUNT
    ):
        flags.append("low-feedback")

    pct_text = "unknown" if pct is None else f"{pct:.1f}%"
    count_text = "unknown" if count is None else str(count)
    return component, f"seller feedback {pct_text} over {count_text} ratings", tuple(flags)


def _feedback_count_component(count: int | None) -> float:
    if count is None:
        return 0.5
    if count >= 500:
        return 1.0
    if count >= 100:
        return 0.8
    if count >= 25:
        return 0.55
    if count >= 10:
        return 0.35
    return 0.2


def _returns_component(returns_accepted: bool | None) -> float:
    if returns_accepted is True:
        return 1.0
    if returns_accepted is False:
        return 0.0
    return 0.45


def _nice_boost(matches: tuple[str, ...], nice_to_haves: tuple[str, ...]) -> float:
    if not matches or not nice_to_haves:
        return 0.0
    return NICE_TO_HAVE_WEIGHT * min(len(matches) / len(nice_to_haves), 1.0)


def _listing_text(listing: NormalizedListing) -> str:
    return " ".join(
        text.lower()
        for text in (listing.title, listing.condition_raw)
        if text
    )


def _matched_phrase(text: str, phrases: tuple[str, ...]) -> str | None:
    for phrase in phrases:
        normalized = phrase.lower().strip()
        if normalized and normalized in text:
            return phrase
    return None


def _matched_phrases(text: str, phrases: tuple[str, ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for phrase in phrases:
        normalized = phrase.lower().strip()
        if normalized and normalized in text and phrase not in matches:
            matches.append(phrase)
    return tuple(matches)


def _median(values) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
