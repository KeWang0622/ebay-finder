"""Shared data contract for eBay Finder.

Every module in this package speaks these three structures:

    Criteria      -- the soft, human goal ("must work", "high value-for-money")
    QueryPlan     -- one concrete search (keywords + hard filters + sort)
    NormalizedListing -- one item, identical shape whether it came from the
                         keyless URL/HTML path or the official Browse API.

Keeping the shapes here (and *only* here) lets the URL builder, the Browse API
client, the ranker, and the report renderer evolve independently. Treat this
file as the API boundary: change it deliberately, never casually.

Design rules (see CONTRACT.md):
  * All structures are immutable: use dataclasses(frozen=True) and return
    new copies instead of mutating in place.
  * Money is always stored as float USD plus an explicit currency string.
  * Optional/unknown values are None, never "" or 0 sentinels.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------- #
# eBay vocabulary (mirrors reference/ebay-search-grammar.md)
# --------------------------------------------------------------------------- #
class Condition(str, Enum):
    """Canonical condition buckets, mapped to eBay condition IDs elsewhere."""

    NEW = "NEW"
    OPEN_BOX = "OPEN_BOX"          # 1500 "New other"
    CERTIFIED_REFURB = "CERTIFIED_REFURB"  # 2000
    SELLER_REFURB = "SELLER_REFURB"        # 2500
    USED = "USED"                 # 3000
    FOR_PARTS = "FOR_PARTS"       # 7000


class BuyingOption(str, Enum):
    FIXED_PRICE = "FIXED_PRICE"
    AUCTION = "AUCTION"
    BEST_OFFER = "BEST_OFFER"


class Sort(str, Enum):
    BEST_MATCH = "BEST_MATCH"
    PRICE_LOW = "PRICE_LOW"          # price + shipping, lowest first
    PRICE_HIGH = "PRICE_HIGH"
    NEWLY_LISTED = "NEWLY_LISTED"
    ENDING_SOONEST = "ENDING_SOONEST"


# --------------------------------------------------------------------------- #
# Criteria -- the human's vague goal, made explicit by the agent
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Criteria:
    """The soft goal behind a hunt. Filled by the *agent* reading the request.

    These drive ranking, not hard filtering. ``must_work`` for example does not
    forbid "for parts" listings at the API layer (sellers mislabel constantly);
    it strongly penalizes them and rewards "tested/working" language in scoring.
    """

    raw_request: str                       # verbatim user text, any language
    item_summary: str                      # short normalized description, English
    must_work: bool = False                # functional/tested requirement
    value_focused: bool = True             # optimize price-for-quality (best bang for the buck)
    target_price_usd: Optional[float] = None   # the user's mental anchor, if any
    deal_breakers: tuple[str, ...] = ()    # phrases that disqualify (e.g. "repaint")
    nice_to_haves: tuple[str, ...] = ()    # phrases that boost score
    era: Optional[str] = None              # e.g. "1930-1960"
    notes: Optional[str] = None            # free-form agent reasoning

    def with_notes(self, notes: str) -> "Criteria":
        return replace(self, notes=notes)


# --------------------------------------------------------------------------- #
# QueryPlan -- one concrete, executable search
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class QueryPlan:
    """One search angle. A hunt fans out into several of these.

    ``label`` explains *why* this angle exists ("Underwood, working, budget")
    so the final report can show the strategy, not just results.
    """

    label: str
    keywords: str                          # goes into _nkw / q, may contain -negatives
    category_id: Optional[str] = None      # eBay leaf/L1 category id as string
    conditions: tuple[Condition, ...] = ()
    buying_options: tuple[BuyingOption, ...] = ()
    price_min_usd: Optional[float] = None
    price_max_usd: Optional[float] = None
    sort: Sort = Sort.BEST_MATCH
    sellers_top_rated_only: bool = False
    returns_accepted: Optional[bool] = None
    item_location_country: Optional[str] = None   # ISO-2, e.g. "US"
    aspects: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (("Brand", ("Royal","Remington")),)
    marketplace_id: str = "EBAY_US"
    limit: int = 50

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 200:
            raise ValueError("limit must be in 1..200 (eBay Browse API max)")
        if (
            self.price_min_usd is not None
            and self.price_max_usd is not None
            and self.price_min_usd > self.price_max_usd
        ):
            raise ValueError("price_min_usd cannot exceed price_max_usd")


# --------------------------------------------------------------------------- #
# NormalizedListing -- one result, source-agnostic
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class NormalizedListing:
    """A single item. Identical whether sourced from Browse API or HTML preview.

    ``score`` / ``score_reasons`` / ``value_ratio`` start as None and are filled
    by the ranker. Keep the listing immutable: the ranker returns new copies.
    """

    item_id: str
    title: str
    url: str
    price_usd: Optional[float] = None
    shipping_usd: Optional[float] = None
    currency: str = "USD"
    condition: Optional[Condition] = None
    condition_raw: Optional[str] = None       # seller's literal condition text
    buying_options: tuple[BuyingOption, ...] = ()
    seller_feedback_pct: Optional[float] = None
    seller_feedback_count: Optional[int] = None
    item_location: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_urls: tuple[str, ...] = ()
    returns_accepted: Optional[bool] = None
    source: str = "browse_api"                # "browse_api" | "html_preview"
    raw: Optional[dict] = field(default=None, compare=False, repr=False)

    # --- filled by the ranker -------------------------------------------- #
    score: Optional[float] = None             # 0..100 composite
    value_ratio: Optional[float] = None       # quality-per-dollar, higher better
    works_confidence: Optional[float] = None  # 0..1 from "tested/working" signals
    score_reasons: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()               # e.g. "for-parts", "no-returns"

    @property
    def total_price_usd(self) -> Optional[float]:
        if self.price_usd is None:
            return None
        return round(self.price_usd + (self.shipping_usd or 0.0), 2)

    def scored(
        self,
        *,
        score: float,
        value_ratio: Optional[float] = None,
        works_confidence: Optional[float] = None,
        reasons: tuple[str, ...] = (),
        flags: tuple[str, ...] = (),
    ) -> "NormalizedListing":
        """Return a new listing carrying ranking output (no mutation)."""
        return replace(
            self,
            score=score,
            value_ratio=value_ratio,
            works_confidence=works_confidence,
            score_reasons=reasons,
            flags=flags,
        )


@dataclass(frozen=True)
class HuntResult:
    """The full output of a hunt: the plans we ran and the ranked findings."""

    criteria: Criteria
    plans: tuple[QueryPlan, ...]
    listings: tuple[NormalizedListing, ...]   # ranked best-first
    keyless: bool                             # True if no API key was used
    search_urls: tuple[str, ...] = ()         # human-clickable eBay URLs
    notes: Optional[str] = None
