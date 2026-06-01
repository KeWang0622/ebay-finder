import json
import urllib.parse

from ebay_finder import browse_api
from ebay_finder.contract import BuyingOption, Condition, NormalizedListing, QueryPlan, Sort


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def close(self):
        pass


def test_build_filter_uses_ebay_grammar_codes():
    plan = QueryPlan(
        label="working used",
        keywords="vintage typewriter",
        conditions=(Condition.USED, Condition.OPEN_BOX),
        buying_options=(BuyingOption.FIXED_PRICE, BuyingOption.BEST_OFFER),
        price_min_usd=40,
        price_max_usd=180,
        item_location_country="US",
        returns_accepted=True,
    )

    # Numeric eBay condition IDs must go in `conditionIds` (the `conditions`
    # filter only accepts enum names like NEW|USED). See ref-buy-browse-filters.
    assert (
        browse_api._build_filter(plan)
        == "price:[40..180],priceCurrency:USD,"
        "conditionIds:{3000|1500},"
        "buyingOptions:{FIXED_PRICE|BEST_OFFER},"
        "itemLocationCountry:US,returnsAccepted:true"
    )


def test_aspect_and_location_operands_are_sanitized():
    # Agent-supplied aspect values must not be able to inject filter grammar
    # ({ } | , : [ ]) that survives eBay's server-side percent-decoding.
    plan = QueryPlan(
        label="x",
        keywords="k",
        category_id="159923",
        item_location_country="US},conditionIds:{7000",
        aspects=(("Brand", ("Royal|Remington", "Under{wood}")),),
    )
    filt = browse_api._build_filter(plan)
    aspect = browse_api._build_aspect_filter(plan)
    # No injected grammar leaks through.
    assert "conditionIds:{7000" not in filt
    assert "itemLocationCountry:US" in filt
    assert "Royal|Remington" not in aspect
    assert "RoyalRemington" in aspect and "Underwood" in aspect


def test_search_builds_request_and_maps_item_summary(monkeypatch):
    captured = {}

    def fake_urlopen(request):
        captured["request"] = request
        return FakeResponse(
            {
                "itemSummaries": [
                    {
                        "itemId": "v1|123|0",
                        "title": "Royal Quiet De Luxe typewriter tested working",
                        "itemWebUrl": "https://www.ebay.com/itm/123",
                        "price": {"value": "99.50", "currency": "USD"},
                        "shippingOptions": [
                            {"shippingCost": {"value": "15.25", "currency": "USD"}}
                        ],
                        "conditionId": "3000",
                        "condition": "Used",
                        "buyingOptions": ["FIXED_PRICE", "BEST_OFFER"],
                        "seller": {
                            "feedbackPercentage": "99.8",
                            "feedbackScore": 1200,
                        },
                        "itemLocation": {"city": "Austin", "stateOrProvince": "TX", "country": "US"},
                        "image": {"imageUrl": "https://img.example/main.jpg"},
                        "thumbnailImages": [{"imageUrl": "https://img.example/thumb.jpg"}],
                        "returnTerms": {"returnsAccepted": True},
                    }
                ]
            }
        )

    monkeypatch.setattr(browse_api.urllib.request, "urlopen", fake_urlopen)
    plan = QueryPlan(
        label="royal",
        keywords="royal typewriter",
        category_id="159923",
        aspects=(("Brand", ("Royal", "Remington")),),
        sort=Sort.PRICE_LOW,
        limit=25,
    )

    (listing,) = browse_api.search(plan, "TOKEN")

    request = captured["request"]
    query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
    assert query["q"] == ["royal typewriter"]
    assert query["category_ids"] == ["159923"]
    assert query["aspect_filter"] == ["categoryId:159923,Brand:{Royal|Remington}"]
    assert query["sort"] == ["price"]
    assert query["limit"] == ["25"]
    assert request.get_header("Authorization") == "Bearer TOKEN"
    assert request.get_header("X-ebay-c-marketplace-id") == "EBAY_US"

    assert listing.item_id == "v1|123|0"
    assert listing.condition is Condition.USED
    assert listing.price_usd == 99.5
    assert listing.shipping_usd == 15.25
    assert listing.buying_options == (BuyingOption.FIXED_PRICE, BuyingOption.BEST_OFFER)
    assert listing.seller_feedback_pct == 99.8
    assert listing.seller_feedback_count == 1200
    assert listing.returns_accepted is True
    assert listing.source == "browse_api"


def test_condition_text_mapping_without_condition_id():
    assert (
        browse_api._condition_from_item({"condition": "For parts or not working"})
        is Condition.FOR_PARTS
    )
    assert browse_api._condition_from_item({"condition": "Open box"}) is Condition.OPEN_BOX
    assert (
        browse_api._condition_from_item({"condition": "Certified - Refurbished"})
        is Condition.CERTIFIED_REFURB
    )


def test_run_plans_dedupes_by_item_id_and_keeps_richest(monkeypatch):
    sparse = NormalizedListing(
        item_id="same",
        title="Sparse listing",
        url="https://example.test/1",
        price_usd=100,
        source="browse_api",
    )
    rich = NormalizedListing(
        item_id="same",
        title="Rich listing",
        url="https://example.test/1",
        price_usd=100,
        shipping_usd=12,
        condition=Condition.USED,
        seller_feedback_pct=99.9,
        image_url="https://img.example/item.jpg",
        thumbnail_urls=("https://img.example/item.jpg",),
        source="browse_api",
    )

    calls = iter(((sparse,), (rich,)))
    monkeypatch.setattr(browse_api, "search", lambda plan, token: next(calls))
    plans = (
        QueryPlan(label="one", keywords="typewriter"),
        QueryPlan(label="two", keywords="typewriter used"),
    )

    assert browse_api.run_plans(plans, "TOKEN") == (rich,)
