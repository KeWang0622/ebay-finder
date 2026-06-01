"""Render a HuntResult as a clean, skimmable Markdown report.

The report is the thing a human actually reads, so it leads with the verdict
(the best finds), shows *why* each was ranked where it is, and ends with the
clickable search URLs so they can keep hunting themselves.
"""

from __future__ import annotations

from .contract import HuntResult, NormalizedListing


def _price(listing: NormalizedListing) -> str:
    total = listing.total_price_usd
    if total is None:
        return "price n/a"
    base = f"${listing.price_usd:,.2f}" if listing.price_usd is not None else "?"
    if listing.shipping_usd:
        return f"{base} + ${listing.shipping_usd:,.2f} ship = **${total:,.2f}**"
    return f"**${total:,.2f}**"


def _seller(listing: NormalizedListing) -> str:
    if listing.seller_feedback_pct is None:
        return ""
    count = listing.seller_feedback_count
    tail = f" ({count:,} ratings)" if count else ""
    return f"{listing.seller_feedback_pct:.1f}% positive{tail}"


def _badges(listing: NormalizedListing) -> str:
    parts: list[str] = []
    if listing.works_confidence is not None:
        pct = int(round(listing.works_confidence * 100))
        parts.append(f"works~{pct}%")
    if listing.value_ratio is not None:
        parts.append(f"value×{listing.value_ratio:.2f}")
    for flag in listing.flags:
        parts.append(f"⚠ {flag}")
    return "  ·  ".join(parts)


def render(result: HuntResult, *, top: int = 8) -> str:
    c = result.criteria
    lines: list[str] = []
    mode = "keyless (search-strategist)" if result.keyless else "API (Browse API)"

    lines.append(f"# 🔭 Treasure Hunt — {c.item_summary}")
    lines.append("")
    lines.append(f"> _“{c.raw_request.strip()}”_")
    lines.append("")
    goal_bits = []
    if c.must_work:
        goal_bits.append("**must work**")
    if c.value_focused:
        goal_bits.append("**best value-for-money**")
    if c.era:
        goal_bits.append(f"era **{c.era}**")
    if c.target_price_usd:
        goal_bits.append(f"~**${c.target_price_usd:,.0f}** target")
    if goal_bits:
        lines.append("Goal: " + " · ".join(goal_bits))
        lines.append("")
    lines.append(f"Mode: {mode} · {len(result.plans)} search angles · "
                 f"{len(result.listings)} candidates found")
    lines.append("")

    if c.notes:
        lines.append(f"**Strategy.** {c.notes}")
        lines.append("")

    # ---- Top finds ------------------------------------------------------- #
    if result.listings:
        lines.append("## 🏆 Top finds")
        lines.append("")
        for i, item in enumerate(result.listings[:top], 1):
            score = f"{item.score:.0f}" if item.score is not None else "—"
            lines.append(f"### {i}. [{item.title}]({item.url})  ·  score {score}/100")
            meta = [_price(item)]
            if item.condition_raw:
                meta.append(item.condition_raw)
            seller = _seller(item)
            if seller:
                meta.append(seller)
            if item.item_location:
                meta.append(item.item_location)
            lines.append("  " + "  ·  ".join(m for m in meta if m))
            badges = _badges(item)
            if badges:
                lines.append("  " + badges)
            for reason in item.score_reasons[:4]:
                lines.append(f"  - {reason}")
            lines.append("")
    else:
        lines.append("## No candidates fetched")
        lines.append("")
        lines.append("Use the search URLs below — they encode the full strategy and "
                     "open directly on eBay. (Add an eBay API key for inline ranked results.)")
        lines.append("")

    # ---- Search strategy / URLs ------------------------------------------ #
    if result.search_urls:
        lines.append("## 🔗 Run these searches on eBay")
        lines.append("")
        for plan, url in zip(result.plans, result.search_urls):
            lines.append(f"- **{plan.label}** — [open on eBay]({url})")
        lines.append("")

    lines.append("---")
    lines.append("_Built by 🔭 Treasure Hunter. Prices and availability change fast — "
                 "verify on eBay before buying._")
    return "\n".join(lines)
