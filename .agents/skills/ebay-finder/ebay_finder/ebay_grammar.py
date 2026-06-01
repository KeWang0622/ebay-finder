"""Single source of truth for eBay's search vocabulary.

Two surfaces use this:
  * the keyless path -> builds public ``/sch/i.html`` URLs (LH_* params, _sop, _udlo).
  * the API path     -> builds Browse API ``filter=`` / ``sort=`` strings.

Both must agree on what "USED" or "PRICE_LOW" means, so the mappings live here and
nowhere else. See reference/ebay-search-grammar.md for the human-readable cheat sheet.
"""

from __future__ import annotations

from .contract import BuyingOption, Condition, Sort

# --------------------------------------------------------------------------- #
# Condition: canonical bucket -> (eBay condition ID, web LH_ItemCondition code)
# eBay uses the same numeric IDs for both the API ``conditions`` filter and the
# website ``LH_ItemCondition`` param, which is convenient.
# --------------------------------------------------------------------------- #
CONDITION_ID: dict[Condition, str] = {
    Condition.NEW: "1000",
    Condition.OPEN_BOX: "1500",          # "New other (see details)"
    Condition.CERTIFIED_REFURB: "2000",  # "Certified - Refurbished"
    Condition.SELLER_REFURB: "2500",     # "Seller refurbished" / excellent-good refurb
    Condition.USED: "3000",
    Condition.FOR_PARTS: "7000",         # "For parts or not working"
}

# Browse API ``conditions`` filter accepts enum names too, but IDs are the most
# precise and portable, so we use IDs everywhere.

# --------------------------------------------------------------------------- #
# Sort: canonical -> (Browse API sort value, website _sop code)
# Browse API supports: price, -price, newlyListed, endingSoonest, bestMatch(default).
# Website _sop: 12=Best Match, 15=Price+Shipping Lowest, 16=Price+Shipping Highest,
#               10=Newly Listed, 1=Ending Soonest.
# --------------------------------------------------------------------------- #
SORT_API: dict[Sort, str | None] = {
    Sort.BEST_MATCH: None,          # omit -> API default is Best Match
    Sort.PRICE_LOW: "price",
    Sort.PRICE_HIGH: "-price",
    Sort.NEWLY_LISTED: "newlyListed",
    Sort.ENDING_SOONEST: "endingSoonest",
}

SORT_WEB: dict[Sort, str] = {
    Sort.BEST_MATCH: "12",
    Sort.PRICE_LOW: "15",
    Sort.PRICE_HIGH: "16",
    Sort.NEWLY_LISTED: "10",
    Sort.ENDING_SOONEST: "1",
}

# --------------------------------------------------------------------------- #
# Buying options: canonical -> Browse API enum / website LH_* flag param
# --------------------------------------------------------------------------- #
BUYING_OPTION_API: dict[BuyingOption, str] = {
    BuyingOption.FIXED_PRICE: "FIXED_PRICE",
    BuyingOption.AUCTION: "AUCTION",
    BuyingOption.BEST_OFFER: "BEST_OFFER",
}

BUYING_OPTION_WEB_FLAG: dict[BuyingOption, str] = {
    BuyingOption.FIXED_PRICE: "LH_BIN",   # Buy It Now
    BuyingOption.AUCTION: "LH_Auction",
    BuyingOption.BEST_OFFER: "LH_BO",
}

# --------------------------------------------------------------------------- #
# Preferred-location codes for the website (LH_PrefLoc).
# 1 = located in <site country> (e.g. US), 2 = North America, 3 = Worldwide.
# --------------------------------------------------------------------------- #
PREF_LOC_US = "1"
PREF_LOC_NORTH_AMERICA = "2"
PREF_LOC_WORLDWIDE = "3"

# --------------------------------------------------------------------------- #
# Marketplace -> default website host. Browse API uses X-EBAY-C-MARKETPLACE-ID.
# --------------------------------------------------------------------------- #
MARKETPLACE_HOST: dict[str, str] = {
    "EBAY_US": "www.ebay.com",
    "EBAY_GB": "www.ebay.co.uk",
    "EBAY_DE": "www.ebay.de",
    "EBAY_AU": "www.ebay.com.au",
    "EBAY_CA": "www.ebay.ca",
    "EBAY_FR": "www.ebay.fr",
    "EBAY_IT": "www.ebay.it",
    "EBAY_ES": "www.ebay.es",
}

BROWSE_SEARCH_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"
OAUTH_TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"

# Words that, in a title/condition, strongly suggest the item is NOT functional.
# Shared so the URL builder can inject them as negative keywords AND the ranker
# can penalize them — same vocabulary, two uses.
NON_WORKING_SIGNALS: tuple[str, ...] = (
    "for parts", "not working", "parts only", "as-is", "as is",
    "untested", "repair", "broken", "damaged", "spares or repair",
)

WORKING_SIGNALS: tuple[str, ...] = (
    "tested", "works", "working", "fully functional", "fully working",
    "serviced", "refurbished", "restored", "guaranteed", "in working order",
)


def web_host(marketplace_id: str) -> str:
    """Website host for a marketplace id, defaulting to the US site."""
    return MARKETPLACE_HOST.get(marketplace_id, "www.ebay.com")
