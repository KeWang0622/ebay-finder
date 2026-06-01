"""Tests for the keyless eBay search URL builder."""

from urllib.parse import parse_qs, urlsplit

from ebay_finder.contract import BuyingOption, Condition, QueryPlan, Sort
from ebay_finder.url_builder import build_search_url, build_search_urls


def _params(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query)


def test_basic_url_encodes_keywords_and_host():
    plan = QueryPlan(label="x", keywords="vintage typewriter")
    url = build_search_url(plan)
    assert url.startswith("https://www.ebay.com/sch/i.html?")
    assert _params(url)["_nkw"] == ["vintage typewriter"]


def test_price_band_maps_to_udlo_udhi():
    plan = QueryPlan(label="x", keywords="k", price_min_usd=40, price_max_usd=180.5)
    p = _params(build_search_url(plan))
    assert p["_udlo"] == ["40"]      # integer prices render cleanly
    assert p["_udhi"] == ["180.50"]  # non-integers keep 2dp


def test_conditions_join_with_pipe():
    plan = QueryPlan(label="x", keywords="k", conditions=(Condition.OPEN_BOX, Condition.USED))
    p = _params(build_search_url(plan))
    assert p["LH_ItemCondition"] == ["1500|3000"]


def test_buying_options_and_location_and_sort():
    plan = QueryPlan(
        label="x", keywords="k",
        buying_options=(BuyingOption.FIXED_PRICE, BuyingOption.BEST_OFFER),
        item_location_country="US", sort=Sort.PRICE_LOW,
    )
    p = _params(build_search_url(plan))
    assert p["LH_BIN"] == ["1"] and p["LH_BO"] == ["1"]
    assert p["LH_PrefLoc"] == ["1"]
    assert p["_sop"] == ["15"]  # price + shipping lowest


def test_must_work_appends_negative_keywords():
    plan = QueryPlan(label="x", keywords="vintage typewriter")
    nkw = _params(build_search_url(plan, exclude_non_working=True))["_nkw"][0]
    assert '-"for parts"' in nkw
    assert "-as-is" in nkw


def test_must_work_does_not_duplicate_existing_negative():
    plan = QueryPlan(label="x", keywords='camera -"for parts"')
    nkw = _params(build_search_url(plan, exclude_non_working=True))["_nkw"][0]
    assert nkw.count('-"for parts"') == 1


def test_aspects_are_not_emitted_on_keyless_path():
    # Keyless deliberately ignores aspects (eBay public aspect params are unstable).
    plan = QueryPlan(label="x", keywords="k", aspects=(("Brand", ("Royal", "Remington")),))
    p = _params(build_search_url(plan))
    assert "Brand" not in p


def test_build_search_urls_is_parallel_to_plans():
    plans = (
        QueryPlan(label="a", keywords="alpha"),
        QueryPlan(label="b", keywords="alpha"),   # identical URL to plan a
        QueryPlan(label="c", keywords="gamma"),
    )
    urls = build_search_urls(plans)
    # One URL per plan, alignment preserved even when two plans coincide.
    assert len(urls) == len(plans)
    assert _params(urls[2])["_nkw"] == ["gamma"]
