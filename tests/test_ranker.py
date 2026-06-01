import pytest

from ebay_finder.contract import Condition, Criteria, NormalizedListing
from ebay_finder.ranker import rank


def listing(
    item_id,
    *,
    title="Royal Quiet De Luxe typewriter tested working",
    price=100,
    shipping=0,
    condition=Condition.USED,
    returns=True,
    feedback_pct=99.5,
    feedback_count=500,
):
    return NormalizedListing(
        item_id=item_id,
        title=title,
        url=f"https://example.test/{item_id}",
        price_usd=price,
        shipping_usd=shipping,
        condition=condition,
        condition_raw=condition.value if condition else None,
        seller_feedback_pct=feedback_pct,
        seller_feedback_count=feedback_count,
        returns_accepted=returns,
        source="browse_api",
    )


def test_must_work_hard_gates_for_parts_listing():
    criteria = Criteria(
        raw_request="working typewriter",
        item_summary="typewriter",
        must_work=True,
    )
    candidate = listing(
        "parts",
        title="Royal typewriter for parts not working",
        price=25,
        condition=Condition.FOR_PARTS,
    )

    (scored,) = rank((candidate,), criteria)

    assert scored is not candidate
    assert scored.score == 0.0
    assert scored.works_confidence == 0.0
    assert "for-parts" in scored.flags
    assert any("must work" in reason for reason in scored.score_reasons)


def test_value_ratio_uses_cohort_median_total_price_and_sorts_best_first():
    criteria = Criteria(raw_request="value typewriter", item_summary="typewriter")
    low = listing("low", price=50)
    middle = listing("middle", price=100)
    high = listing("high", price=200)

    ranked = rank((high, low, middle), criteria)
    by_id = {item.item_id: item for item in ranked}

    assert by_id["low"].value_ratio == pytest.approx(2.0)
    assert by_id["middle"].value_ratio == pytest.approx(1.0)
    assert by_id["high"].value_ratio == pytest.approx(0.5)
    assert ranked[0].item_id == "low"
    assert ranked[-1].item_id == "high"
    assert all(item.score_reasons for item in ranked)


def test_ranker_flags_returns_feedback_and_price_outlier():
    criteria = Criteria(raw_request="cheap working typewriter", item_summary="typewriter")
    too_cheap = listing(
        "too-cheap",
        price=10,
        returns=False,
        feedback_pct=96.5,
        feedback_count=8,
    )
    normal = listing("normal", price=100)
    expensive = listing("expensive", price=190)

    ranked = rank((too_cheap, normal, expensive), criteria)
    flagged = next(item for item in ranked if item.item_id == "too-cheap")

    assert flagged.value_ratio == pytest.approx(10.0)
    assert "price-outlier-low" in flagged.flags
    assert "no-returns" in flagged.flags
    assert "low-feedback" in flagged.flags


def test_deal_breakers_zero_score_and_nice_to_haves_boost():
    criteria = Criteria(
        raw_request="serviced typewriter, no repaint",
        item_summary="typewriter",
        deal_breakers=("repaint",),
        nice_to_haves=("serviced",),
    )
    deal_breaker = listing("bad", title="Serviced Royal typewriter repaint project")
    nice = listing("nice", title="Serviced Royal typewriter working")

    ranked = rank((deal_breaker, nice), criteria)
    by_id = {item.item_id: item for item in ranked}

    assert by_id["bad"].score == 0.0
    assert "deal-breaker" in by_id["bad"].flags
    assert by_id["nice"].score > by_id["bad"].score
