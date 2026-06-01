# Internal Contract

All modules speak the structures in `ebay_finder/contract.py`. Do not invent
parallel shapes. If a structure is insufficient, extend `contract.py` and update
this file in the same change.

## The three structures

| Structure | Produced by | Consumed by |
|-----------|-------------|-------------|
| `Criteria` | the **agent** (parses the user's vague request) | ranker, report |
| `QueryPlan` | the **agent** (search strategy) | url_builder, browse_api |
| `NormalizedListing` | url_builder/html preview **and** browse_api | ranker, report |
| `HuntResult` | cli orchestrator | report |

## Invariants

1. **Immutability.** Every dataclass is `frozen=True`. Never mutate; use
   `dataclasses.replace` / the provided `.scored()` / `.with_notes()` helpers.
2. **Money is float USD + currency string.** No Decimal-in-strings, no cents-as-int.
   `None` means unknown — never `0`.
3. **Source-agnostic listings.** A `NormalizedListing` from the keyless HTML path
   and from the Browse API must be indistinguishable to the ranker except for the
   `source` field and possibly missing optional fields.
4. **Ranker is pure.** `rank(listings, criteria) -> tuple[NormalizedListing, ...]`
   returns NEW scored copies, best-first. No I/O, no network, deterministic given
   inputs. All fuzzy "does this listing match the vibe" judgment is the agent's job,
   *not* the ranker's — the ranker does transparent, explainable arithmetic only.
5. **Browse API client never raises on empty results.** Network/auth failures raise
   typed errors (`BrowseAuthError`, `BrowseRateLimitError`); "0 items" is a normal
   empty tuple.

## Module ownership (initial build)

- `contract.py`, `ebay_grammar.py`, `url_builder.py`, `report.py`, `cli.py` — Claude
- `browse_api.py`, `ranker.py`, `tests/` — Codex

## browse_api.py — required surface

```python
class BrowseAuthError(RuntimeError): ...
class BrowseRateLimitError(RuntimeError): ...

def get_app_token(client_id: str, client_secret: str,
                  *, marketplace: str = "EBAY_US",
                  cache_path: str | None = None) -> str:
    """Client-credentials OAuth token. Cache to disk with expiry; refresh when stale.
    POST https://api.ebay.com/identity/v1/oauth2/token
      Authorization: Basic base64(client_id:client_secret)
      body: grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope
    """

def search(plan: QueryPlan, token: str) -> tuple[NormalizedListing, ...]:
    """GET https://api.ebay.com/buy/browse/v1/item_summary/search
       headers: Authorization: Bearer <token>, X-EBAY-C-MARKETPLACE-ID: <plan.marketplace_id>
       Build q, category_ids, filter, aspect_filter, sort, limit from the plan.
       Map each itemSummary -> NormalizedListing (source='browse_api')."""

def run_plans(plans: Iterable[QueryPlan], token: str) -> tuple[NormalizedListing, ...]:
    """Fan out, concatenate, DEDUPE by item_id (keep richest record)."""
```

Use only the Python stdlib (`urllib.request`, `json`, `base64`, `time`) — **no
third-party HTTP deps** so the package installs with zero dependencies. Keep the
filter/sort mapping in sync with `ebay_grammar.py` (import the constants from there;
do not hardcode condition IDs in two places).

## ranker.py — required surface

```python
def rank(listings: Sequence[NormalizedListing], criteria: Criteria,
         ) -> tuple[NormalizedListing, ...]:
    """Score 0..100 and return new copies sorted best-first.

    Scoring dimensions (document the weights as module constants):
      * value_ratio  -- price vs the cohort: cheaper-than-median is good, but
                        suspiciously-cheap is a mild flag, not a boost.
      * works_confidence -- keyword signals in title/condition:
                        +  'tested','works','working','fully functional','serviced'
                        -  'for parts','as-is','not working','repair','untested'
                        gate hard when criteria.must_work and signal is strongly negative.
      * condition fit, seller trust (feedback %/count), returns accepted,
        deal_breakers (zero out), nice_to_haves (boost).
    Every listing must come back with score_reasons explaining the number, and
    flags for anything a buyer should see ('for-parts', 'no-returns', 'low-feedback',
    'price-outlier-low')."""
```

`value_ratio`: compute the cohort median total price, then
`value_ratio = median_total / listing_total` (so >1 means cheaper than typical).
Guard against None prices and division by zero.

## Tests

`tests/test_ranker.py` and `tests/test_url_builder.py` with `pytest`. Cover:
must-work gating, value-ratio math, dedupe, price-band URL encoding, negative
keywords, condition-id mapping. Use small hand-built `NormalizedListing` fixtures —
**no network in tests.**
