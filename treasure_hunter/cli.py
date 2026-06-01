"""Orchestrator CLI — the deterministic tool the skill drives.

The *agent* writes a plan spec (criteria + a fan-out of QueryPlans) as JSON; this
CLI turns it into a hunt:

    python -m treasure_hunter.cli plan.json --out report.md

What it does, in order:
  1. Always builds clickable eBay search URLs from the plans (keyless backbone).
  2. If EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are set, calls the Browse API, ranks
     the results, and embeds them in the report.
  3. Otherwise (keyless) it emits the URLs + strategy. The host agent can fetch
     those pages, hand the listings back via --listings listings.json, and this
     CLI will rank those instead — same ranking either way.

The plan spec schema is documented in reference/plan-spec.md and validated here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from typing import Any

from .contract import (
    BuyingOption,
    Condition,
    Criteria,
    HuntResult,
    NormalizedListing,
    QueryPlan,
    Sort,
)
from .url_builder import build_search_urls
from . import report as report_mod


# --------------------------------------------------------------------------- #
# Spec parsing (JSON -> frozen dataclasses), with friendly validation errors
# --------------------------------------------------------------------------- #
def _enum(enum_cls, value, field_name):
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise SystemExit(f"Invalid {field_name}: {value!r}. Allowed: {allowed}")


def parse_criteria(d: dict[str, Any]) -> Criteria:
    return Criteria(
        raw_request=d.get("raw_request", ""),
        item_summary=d.get("item_summary", d.get("raw_request", "search")),
        must_work=bool(d.get("must_work", False)),
        value_focused=bool(d.get("value_focused", True)),
        target_price_usd=_opt_float(d.get("target_price_usd")),
        deal_breakers=tuple(d.get("deal_breakers", [])),
        nice_to_haves=tuple(d.get("nice_to_haves", [])),
        era=d.get("era"),
        notes=d.get("notes"),
    )


def parse_plan(d: dict[str, Any]) -> QueryPlan:
    aspects = tuple(
        (name, tuple(values)) for name, values in (d.get("aspects") or [])
    )
    return QueryPlan(
        label=d.get("label", "search"),
        keywords=d["keywords"],
        category_id=_opt_str(d.get("category_id")),
        conditions=tuple(_enum(Condition, c, "condition") for c in d.get("conditions", [])),
        buying_options=tuple(
            _enum(BuyingOption, b, "buying_option") for b in d.get("buying_options", [])
        ),
        price_min_usd=_opt_float(d.get("price_min_usd")),
        price_max_usd=_opt_float(d.get("price_max_usd")),
        sort=_enum(Sort, d.get("sort", "BEST_MATCH"), "sort"),
        sellers_top_rated_only=bool(d.get("sellers_top_rated_only", False)),
        returns_accepted=d.get("returns_accepted"),
        item_location_country=_opt_str(d.get("item_location_country")),
        aspects=aspects,
        marketplace_id=d.get("marketplace_id", "EBAY_US"),
        limit=int(d.get("limit", 50)),
    )


# Map free-text seller condition labels -> canonical Condition. Keyless listings
# (scraped from the page) carry text like "Used" / "For parts" rather than the enum,
# so we infer it here to give the ranker the condition-fit signal it expects.
_CONDITION_TEXT: tuple[tuple[str, Condition], ...] = (
    ("for parts", Condition.FOR_PARTS),
    ("not working", Condition.FOR_PARTS),
    ("certified", Condition.CERTIFIED_REFURB),
    ("seller refurbished", Condition.SELLER_REFURB),
    ("refurbished", Condition.CERTIFIED_REFURB),
    ("open box", Condition.OPEN_BOX),
    ("new other", Condition.OPEN_BOX),
    ("new", Condition.NEW),
    ("used", Condition.USED),
    ("pre-owned", Condition.USED),
    ("preowned", Condition.USED),
)


def _infer_condition(raw: str | None) -> Condition | None:
    if not raw:
        return None
    low = raw.lower()
    for needle, cond in _CONDITION_TEXT:
        if needle in low:
            return cond
    return None


def parse_listing(d: dict[str, Any]) -> NormalizedListing:
    """Parse a listing the agent fetched itself (keyless HTML preview path)."""
    cond = d.get("condition")
    condition = _enum(Condition, cond, "condition") if cond else _infer_condition(d.get("condition_raw"))
    return NormalizedListing(
        item_id=str(d.get("item_id") or d.get("url") or d.get("title", "")),
        title=d.get("title", ""),
        url=d.get("url", ""),
        price_usd=_opt_float(d.get("price_usd")),
        shipping_usd=_opt_float(d.get("shipping_usd")),
        currency=d.get("currency", "USD"),
        condition=condition,
        condition_raw=d.get("condition_raw"),
        buying_options=tuple(
            _enum(BuyingOption, b, "buying_option") for b in d.get("buying_options", [])
        ),
        seller_feedback_pct=_opt_float(d.get("seller_feedback_pct")),
        seller_feedback_count=_opt_int(d.get("seller_feedback_count")),
        item_location=d.get("item_location"),
        image_url=d.get("image_url"),
        returns_accepted=d.get("returns_accepted"),
        source=d.get("source", "html_preview"),
    )


def _opt_float(v):
    return None if v is None else float(v)


def _opt_int(v):
    return None if v is None else int(v)


def _opt_str(v):
    return None if v is None else str(v)


# --------------------------------------------------------------------------- #
# Optional modules (Browse API + ranker). Imported lazily so the keyless path
# works even in a minimal checkout.
# --------------------------------------------------------------------------- #
def _try_rank(listings, criteria):
    try:
        from .ranker import rank
    except Exception:
        return tuple(listings)  # ranking unavailable: return unranked
    return rank(listings, criteria)


def _try_browse(plans, criteria):
    cid = os.environ.get("EBAY_CLIENT_ID")
    secret = os.environ.get("EBAY_CLIENT_SECRET")
    if not (cid and secret):
        return None  # signal: keyless
    from .browse_api import get_app_token, run_plans  # raises if missing -> surfaced

    cache = os.environ.get("EBAY_TOKEN_CACHE", os.path.expanduser("~/.cache/treasure_hunter/token.json"))
    token = get_app_token(cid, secret, cache_path=cache)
    return run_plans(plans, token)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run(spec: dict[str, Any], listings_override: list[dict] | None) -> HuntResult:
    criteria = parse_criteria(spec.get("criteria", {}))
    plans = tuple(parse_plan(p) for p in spec.get("plans", []))
    if not plans:
        raise SystemExit("Plan spec has no 'plans'. The agent must supply at least one QueryPlan.")

    urls = build_search_urls(plans, exclude_non_working=criteria.must_work)

    listings: tuple[NormalizedListing, ...] = ()
    keyless = True

    if listings_override is not None:
        listings = tuple(parse_listing(d) for d in listings_override)
        keyless = True  # these came from the agent's own fetch
    else:
        fetched = _try_browse(plans, criteria)
        if fetched is not None:
            listings = tuple(fetched)
            keyless = False

    if listings:
        listings = _try_rank(listings, criteria)

    return HuntResult(
        criteria=criteria,
        plans=plans,
        listings=listings,
        keyless=keyless,
        search_urls=urls,
        notes=criteria.notes,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="treasure_hunter",
        description="Vague wish -> ranked eBay hunt. Keyless by default; richer with an eBay API key.",
    )
    ap.add_argument("spec", help="Path to plan spec JSON (criteria + plans). '-' for stdin.")
    ap.add_argument("--listings", help="JSON file of listings the agent fetched (keyless ranking).")
    ap.add_argument("--out", help="Write the Markdown report here (default: stdout).")
    ap.add_argument("--json", action="store_true", help="Emit the HuntResult as JSON instead of Markdown.")
    ap.add_argument("--top", type=int, default=8, help="How many top finds to show (default 8).")
    args = ap.parse_args(argv)

    spec_text = sys.stdin.read() if args.spec == "-" else _read(args.spec)
    spec = json.loads(spec_text)
    listings_override = json.loads(_read(args.listings)) if args.listings else None

    result = run(spec, listings_override)

    if args.json:
        output = json.dumps(_result_to_dict(result), indent=2)
    else:
        output = report_mod.render(result, top=args.top)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"Wrote {args.out} ({len(result.listings)} ranked listings, "
              f"{len(result.search_urls)} search URLs).", file=sys.stderr)
    else:
        print(output)
    return 0


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _result_to_dict(r: HuntResult) -> dict:
    def listing(l: NormalizedListing) -> dict:
        return {
            "item_id": l.item_id, "title": l.title, "url": l.url,
            "price_usd": l.price_usd, "shipping_usd": l.shipping_usd,
            "total_price_usd": l.total_price_usd, "currency": l.currency,
            "condition": l.condition.value if l.condition else None,
            "condition_raw": l.condition_raw,
            "seller_feedback_pct": l.seller_feedback_pct,
            "seller_feedback_count": l.seller_feedback_count,
            "item_location": l.item_location, "image_url": l.image_url,
            "score": l.score, "value_ratio": l.value_ratio,
            "works_confidence": l.works_confidence,
            "score_reasons": list(l.score_reasons), "flags": list(l.flags),
            "source": l.source,
        }
    return {
        "item_summary": r.criteria.item_summary,
        "keyless": r.keyless,
        "search_urls": list(r.search_urls),
        "plans": [p.label for p in r.plans],
        "listings": [listing(l) for l in r.listings],
    }


if __name__ == "__main__":
    raise SystemExit(main())
