"""Official eBay Browse API client for structured Treasure Hunter searches.

This module intentionally stays small and deterministic: it only performs
OAuth, one Browse search endpoint, and normalization into the shared contract.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
import urllib.request

from . import ebay_grammar as g
from .contract import BuyingOption, Condition, NormalizedListing, QueryPlan


class BrowseAuthError(RuntimeError):
    """Authentication or non-retriable Browse API request failure."""


class BrowseRateLimitError(RuntimeError):
    """eBay rejected the request because the app is rate limited."""


_TOKEN_REFRESH_SKEW_SECONDS = 60
_CONDITION_BY_ID = {value: key for key, value in g.CONDITION_ID.items()}
_BUYING_OPTION_BY_API = {value: key for key, value in g.BUYING_OPTION_API.items()}


def get_app_token(
    client_id: str,
    client_secret: str,
    *,
    marketplace: str = "EBAY_US",
    cache_path: str | None = None,
) -> str:
    """Return a client-credentials OAuth token, using a disk cache when fresh."""
    if not client_id or not client_secret:
        raise BrowseAuthError("eBay client id and client secret are required")

    path = cache_path or _default_cache_path(marketplace)
    cached = _read_cached_token(path, client_id, marketplace)
    if cached:
        return cached

    token = _fetch_app_token(client_id, client_secret)
    _write_cached_token(path, token, client_id, marketplace)
    return str(token["access_token"])


def search(plan: QueryPlan, token: str) -> tuple[NormalizedListing, ...]:
    """Run one QueryPlan against the Browse item_summary/search endpoint."""
    params = _build_search_params(plan)
    url = f"{g.BROWSE_SEARCH_ENDPOINT}?{urllib.parse.urlencode(params, safe='{}[]|:,.')}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": plan.marketplace_id,
        },
    )

    payload = _open_json(request, error_context="Browse API search failed")
    summaries = payload.get("itemSummaries") or ()
    listings: list[NormalizedListing] = []
    for item in summaries:
        if not isinstance(item, dict):
            continue
        listing = _item_to_listing(item)
        if listing is not None:
            listings.append(listing)
    return tuple(listings)


def run_plans(plans, token: str) -> tuple[NormalizedListing, ...]:
    """Fan out a set of plans and de-dupe listings by item_id."""
    by_item_id: dict[str, NormalizedListing] = {}
    for plan in plans:
        for listing in search(plan, token):
            existing = by_item_id.get(listing.item_id)
            if existing is None or _richness(listing) > _richness(existing):
                by_item_id[listing.item_id] = listing
    return tuple(by_item_id.values())


def _fetch_app_token(client_id: str, client_secret: str) -> dict:
    credentials = f"{client_id}:{client_secret}".encode("utf-8")
    encoded_credentials = base64.b64encode(credentials).decode("ascii")
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "scope": g.OAUTH_SCOPE,
        }
    ).encode("ascii")
    request = urllib.request.Request(
        g.OAUTH_TOKEN_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    payload = _open_json(request, error_context="eBay OAuth failed")
    access_token = payload.get("access_token")
    expires_in = _to_float(payload.get("expires_in"))
    if not access_token or expires_in is None:
        raise BrowseAuthError("eBay OAuth response did not include a usable token")
    return {
        "access_token": access_token,
        "expires_at": time.time() + expires_in,
    }


def _open_json(request: urllib.request.Request, *, error_context: str) -> dict:
    try:
        response = urllib.request.urlopen(request)
        try:
            body = response.read()
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
    except Exception as exc:
        code = getattr(exc, "code", None)
        body_text = _error_body(exc)
        message = f"{error_context}: {code or exc}"
        if body_text:
            message = f"{message}: {body_text}"
        if code == 429:
            raise BrowseRateLimitError(message) from exc
        raise BrowseAuthError(message) from exc

    if not body:
        return {}
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrowseAuthError(f"{error_context}: invalid JSON response") from exc
    if isinstance(decoded, dict):
        return decoded
    raise BrowseAuthError(f"{error_context}: response was not a JSON object")


def _error_body(exc: BaseException) -> str:
    read = getattr(exc, "read", None)
    if read is None:
        return ""
    try:
        data = read()
    except Exception:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace").strip()
    return str(data).strip()


def _default_cache_path(marketplace: str) -> str:
    safe_marketplace = "".join(ch for ch in marketplace if ch.isalnum() or ch in ("-", "_"))
    return os.path.expanduser(
        os.path.join("~", ".cache", "treasure_hunter", f"ebay_token_{safe_marketplace}.json")
    )


def _read_cached_token(path: str, client_id: str, marketplace: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cached = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(cached, dict):
        return None
    if cached.get("client_id") != client_id or cached.get("marketplace") != marketplace:
        return None
    token = cached.get("access_token")
    expires_at = _to_float(cached.get("expires_at"))
    if not token or expires_at is None:
        return None
    if expires_at <= time.time() + _TOKEN_REFRESH_SKEW_SECONDS:
        return None
    return str(token)


def _write_cached_token(path: str, token: dict, client_id: str, marketplace: str) -> None:
    data = {
        "access_token": token["access_token"],
        "expires_at": token["expires_at"],
        "client_id": client_id,
        "marketplace": marketplace,
    }
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        # A cache write failure should not prevent a valid in-memory token.
        return


def _build_search_params(plan: QueryPlan) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [("q", plan.keywords), ("limit", str(plan.limit))]
    if plan.category_id:
        params.append(("category_ids", plan.category_id))

    filter_value = _build_filter(plan)
    if filter_value:
        params.append(("filter", filter_value))

    aspect_filter = _build_aspect_filter(plan)
    if aspect_filter:
        params.append(("aspect_filter", aspect_filter))

    sort = g.SORT_API[plan.sort]
    if sort:
        params.append(("sort", sort))
    return params


def _build_filter(plan: QueryPlan) -> str | None:
    parts: list[str] = []

    price = _price_filter(plan.price_min_usd, plan.price_max_usd)
    if price:
        parts.append(price)
        parts.append("priceCurrency:USD")

    if plan.conditions:
        ids = "|".join(g.CONDITION_ID[condition] for condition in plan.conditions)
        parts.append(f"conditions:{{{ids}}}")

    if plan.buying_options:
        options = "|".join(g.BUYING_OPTION_API[option] for option in plan.buying_options)
        parts.append(f"buyingOptions:{{{options}}}")

    if plan.item_location_country:
        parts.append(f"itemLocationCountry:{plan.item_location_country}")

    if plan.returns_accepted is not None:
        parts.append(f"returnsAccepted:{str(plan.returns_accepted).lower()}")

    return ",".join(parts) if parts else None


def _price_filter(min_usd: float | None, max_usd: float | None) -> str | None:
    if min_usd is None and max_usd is None:
        return None
    lower = _money(min_usd) if min_usd is not None else ""
    upper = _money(max_usd) if max_usd is not None else ""
    return f"price:[{lower}..{upper}]"


def _build_aspect_filter(plan: QueryPlan) -> str | None:
    if not plan.category_id or not plan.aspects:
        return None
    parts = [f"categoryId:{plan.category_id}"]
    for name, values in plan.aspects:
        clean_values = tuple(value for value in values if value)
        if clean_values:
            parts.append(f"{name}:{{{'|'.join(clean_values)}}}")
    if len(parts) == 1:
        return None
    return ",".join(parts)


def _item_to_listing(item: dict) -> NormalizedListing | None:
    item_id = _first_text(item, "itemId", "legacyItemId")
    title = _first_text(item, "title") or ""
    url = _first_text(item, "itemWebUrl", "itemAffiliateWebUrl", "itemHref") or ""
    if not item_id or not title or not url:
        return None

    price, currency = _money_value(item.get("price") or item.get("currentBidPrice"))
    shipping, shipping_currency = _shipping_cost(item.get("shippingOptions"))
    if currency == "USD" and shipping_currency:
        currency = shipping_currency

    return NormalizedListing(
        item_id=item_id,
        title=title,
        url=url,
        price_usd=price,
        shipping_usd=shipping,
        currency=currency,
        condition=_condition_from_item(item),
        condition_raw=_first_text(item, "condition"),
        buying_options=_buying_options(item.get("buyingOptions")),
        seller_feedback_pct=_seller_feedback_pct(item.get("seller")),
        seller_feedback_count=_seller_feedback_count(item.get("seller")),
        item_location=_location_text(item.get("itemLocation")),
        image_url=_image_url(item.get("image")),
        thumbnail_urls=_thumbnail_urls(item),
        returns_accepted=_returns_accepted(item),
        source="browse_api",
        raw=item,
    )


def _condition_from_item(item: dict) -> Condition | None:
    condition_id = item.get("conditionId")
    if condition_id is not None:
        mapped = _CONDITION_BY_ID.get(str(condition_id))
        if mapped is not None:
            return mapped

    text = (_first_text(item, "condition") or "").lower()
    if not text:
        return None
    if "for parts" in text or "not working" in text:
        return Condition.FOR_PARTS
    if "certified" in text and "refurb" in text:
        return Condition.CERTIFIED_REFURB
    if "seller" in text and "refurb" in text:
        return Condition.SELLER_REFURB
    if "new other" in text or "open box" in text:
        return Condition.OPEN_BOX
    if text.startswith("new"):
        return Condition.NEW
    if "used" in text or "pre-owned" in text or "preowned" in text:
        return Condition.USED
    if "refurb" in text:
        return Condition.SELLER_REFURB
    return None


def _buying_options(raw_options) -> tuple[BuyingOption, ...]:
    if not isinstance(raw_options, list):
        return ()
    options: list[BuyingOption] = []
    for raw in raw_options:
        option = _BUYING_OPTION_BY_API.get(str(raw))
        if option is not None:
            options.append(option)
    return tuple(options)


def _shipping_cost(raw_options) -> tuple[float | None, str | None]:
    if not isinstance(raw_options, list):
        return None, None

    costs: list[tuple[float, str]] = []
    free_shipping = False
    for option in raw_options:
        if not isinstance(option, dict):
            continue
        cost, currency = _money_value(option.get("shippingCost"))
        if cost is not None:
            costs.append((cost, currency))
        elif str(option.get("shippingCostType", "")).upper() == "FREE":
            free_shipping = True

    if free_shipping:
        costs.append((0.0, "USD"))
    if costs:
        return min(costs, key=lambda entry: entry[0])
    return None, None


def _money_value(raw) -> tuple[float | None, str]:
    if not isinstance(raw, dict):
        return None, "USD"
    value = _to_float(raw.get("value"))
    currency = str(raw.get("currency") or "USD")
    return value, currency


def _seller_feedback_pct(seller) -> float | None:
    if not isinstance(seller, dict):
        return None
    return _to_float(seller.get("feedbackPercentage"))


def _seller_feedback_count(seller) -> int | None:
    if not isinstance(seller, dict):
        return None
    raw = seller.get("feedbackScore")
    try:
        if raw is None:
            return None
        return int(raw)
    except (TypeError, ValueError):
        return None


def _location_text(location) -> str | None:
    if isinstance(location, str):
        return location or None
    if not isinstance(location, dict):
        return None
    pieces = [
        location.get("city"),
        location.get("stateOrProvince"),
        location.get("postalCode"),
        location.get("country"),
    ]
    text = ", ".join(str(piece) for piece in pieces if piece)
    return text or None


def _image_url(image) -> str | None:
    if isinstance(image, dict):
        url = image.get("imageUrl")
        return str(url) if url else None
    if isinstance(image, str):
        return image or None
    return None


def _thumbnail_urls(item: dict) -> tuple[str, ...]:
    urls: list[str] = []
    primary = _image_url(item.get("image"))
    if primary:
        urls.append(primary)

    raw_thumbnails = item.get("thumbnailImages")
    if isinstance(raw_thumbnails, list):
        for thumbnail in raw_thumbnails:
            url = _image_url(thumbnail)
            if url and url not in urls:
                urls.append(url)
    return tuple(urls)


def _returns_accepted(item: dict) -> bool | None:
    raw = item.get("returnsAccepted")
    if isinstance(raw, bool):
        return raw
    terms = item.get("returnTerms")
    if isinstance(terms, dict) and isinstance(terms.get("returnsAccepted"), bool):
        return terms["returnsAccepted"]
    return None


def _first_text(mapping: dict, *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            text = str(value)
            if text:
                return text
    return None


def _to_float(raw) -> float | None:
    try:
        if raw is None:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _money(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _richness(listing: NormalizedListing) -> int:
    fields = (
        listing.price_usd,
        listing.shipping_usd,
        listing.condition,
        listing.condition_raw,
        listing.buying_options,
        listing.seller_feedback_pct,
        listing.seller_feedback_count,
        listing.item_location,
        listing.image_url,
        listing.returns_accepted,
    )
    score = sum(1 for value in fields if value not in (None, "", ()))
    score += len(listing.thumbnail_urls)
    if listing.raw:
        score += 1
    return score
