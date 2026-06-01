"""Keyless core: turn a QueryPlan into a real, clickable eBay search URL.

This is what makes eBay Finder useful to *everyone*, no API key required.
The agent designs the search strategy (a handful of QueryPlans); this module
encodes each one into a ``https://www.ebay.com/sch/i.html?...`` URL with the
right price band, condition filter, buying options, sort, location preference,
and negative keywords. A human clicks it and lands on exactly the right results;
the host agent can also fetch the page to preview listings.

All knowledge of eBay's URL parameter codes lives in ``ebay_grammar`` — this
module only assembles them.
"""

from __future__ import annotations

from urllib.parse import urlencode

from . import ebay_grammar as g
from .contract import Condition, QueryPlan


def _condition_param(conditions: tuple[Condition, ...]) -> str | None:
    """LH_ItemCondition is a pipe-joined list of condition IDs (web uses '|')."""
    if not conditions:
        return None
    ids = [g.CONDITION_ID[c] for c in conditions]
    return "|".join(ids)


def _keywords_with_negatives(keywords: str, must_work: bool) -> str:
    """Optionally append non-working negative keywords.

    eBay search treats ``-word`` as exclude and ``-"two words"`` as exclude-phrase.
    We only add the strongest, least-ambiguous exclusions so we don't accidentally
    filter out a genuinely working item whose description happens to mention a word.
    """
    kw = keywords.strip()
    if not must_work:
        return kw
    # A conservative subset: phrases that almost always mean "not functional".
    strong_excludes = ('for parts', 'not working', 'as-is', 'as is', 'parts only', 'spares or repair')
    existing = kw.lower()
    additions: list[str] = []
    for phrase in strong_excludes:
        if phrase in existing:
            continue  # the user/agent already addressed it
        token = f'-"{phrase}"' if " " in phrase else f"-{phrase}"
        additions.append(token)
    if additions:
        return f"{kw} {' '.join(additions)}"
    return kw


def build_search_url(plan: QueryPlan, *, exclude_non_working: bool = False) -> str:
    """Encode one QueryPlan as a public eBay search URL.

    ``exclude_non_working`` injects negative keywords for non-functional items;
    the CLI sets this from ``Criteria.must_work``.
    """
    host = g.web_host(plan.marketplace_id)
    params: list[tuple[str, str]] = []

    params.append(("_nkw", _keywords_with_negatives(plan.keywords, exclude_non_working)))

    if plan.category_id:
        params.append(("_sacat", plan.category_id))

    cond = _condition_param(plan.conditions)
    if cond:
        params.append(("LH_ItemCondition", cond))

    # Price band -> _udlo / _udhi (USD on the .com site).
    if plan.price_min_usd is not None:
        params.append(("_udlo", _money(plan.price_min_usd)))
    if plan.price_max_usd is not None:
        params.append(("_udhi", _money(plan.price_max_usd)))

    # Buying options are independent boolean flags on the website.
    for opt in plan.buying_options:
        flag = g.BUYING_OPTION_WEB_FLAG.get(opt)
        if flag:
            params.append((flag, "1"))

    if plan.item_location_country == "US":
        params.append(("LH_PrefLoc", g.PREF_LOC_US))

    if plan.sellers_top_rated_only:
        params.append(("LH_TopRatedSeller", "1"))

    if plan.returns_accepted:
        params.append(("LH_RPB", "1"))  # returns accepted refinement

    # NOTE: aspect refinements (e.g. Brand) are intentionally NOT emitted on the
    # keyless /sch/ path — eBay's public aspect params are opaque/unstable. Fold
    # brands into `keywords` instead (e.g. "(royal,remington) typewriter"). Aspects
    # are honored only on the official Browse API path (browse_api.py).

    params.append(("_sop", g.SORT_WEB[plan.sort]))
    params.append(("_ipg", "60"))  # 60 results per page — more to scan per fetch

    return f"https://{host}/sch/i.html?" + urlencode(params, safe="|")


def _money(value: float) -> str:
    """eBay price params accept plain numbers; emit ints cleanly, else 2dp."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def build_search_urls(
    plans: tuple[QueryPlan, ...], *, exclude_non_working: bool = False
) -> tuple[str, ...]:
    """Encode a fan-out of plans into exactly one URL per plan, in order.

    The result is parallel to ``plans`` (``urls[i]`` is ``plans[i]``'s URL), so
    callers can safely ``zip(plans, urls)`` for labelling. We do NOT de-duplicate
    here — dropping a duplicate would shift every later URL out of alignment with
    its plan. Distinct plans almost always yield distinct URLs anyway.
    """
    return tuple(
        build_search_url(plan, exclude_non_working=exclude_non_working)
        for plan in plans
    )
