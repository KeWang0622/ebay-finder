"""eBay Finder — vague wish -> ranked eBay hunt.

Public surface kept small on purpose; see contract.py for the data model.
"""

from .contract import (
    BuyingOption,
    Condition,
    Criteria,
    HuntResult,
    NormalizedListing,
    QueryPlan,
    Sort,
)
from .url_builder import build_search_url, build_search_urls

__all__ = [
    "BuyingOption",
    "Condition",
    "Criteria",
    "HuntResult",
    "NormalizedListing",
    "QueryPlan",
    "Sort",
    "build_search_url",
    "build_search_urls",
]

__version__ = "0.2.0"
