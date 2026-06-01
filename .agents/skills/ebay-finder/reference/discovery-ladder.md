# Discovery Ladder — always end with real listings

The non-negotiable rule: **every hunt returns a ranked list of real eBay listings
(`ebay.com/itm/<id>` links) that satisfy the user's inputs.** Search-page URLs are a
browsing bonus, never the final answer. Walk down this ladder and stop at the first
rung that yields listings.

### Rung 1 — Official Browse API (best)
If `EBAY_CLIENT_ID` + `EBAY_CLIENT_SECRET` are set, the tool fetches, dedupes, and
ranks structured listings automatically. Free 2-minute key: see `SETUP.md`.

```bash
export EBAY_CLIENT_ID=... EBAY_CLIENT_SECRET=...
python -m ebay_finder.cli plan.json --out report.md
```

### Rung 2 — Fetch the search pages
Open each generated `/sch/` URL with a browser/fetch tool, read the listing cards, and
write them into `listings.json` (array of `{title, url, price_usd, shipping_usd,
condition_raw, seller_feedback_pct, item_location, image_url}` — partial is fine).

### Rung 3 — eBay-restricted web search (universal fallback)
Datacenter IPs are frequently challenged by eBay, so fetching may fail. In that case use
your web-search tool **restricted to `ebay.com`**, one query per plan:

```
query="Olympia SM3 typewriter serviced working"  allowed_domains=["ebay.com"]
```

Keep the `https://www.ebay.com/itm/<id>` results — these are real, current listings.
Build `listings.json` from them (title + url at minimum) and rank:

```bash
python -m ebay_finder.cli plan.json --listings listings.json --out report.md
```

When only titles + links are available, still return a ranked shortlist using the
working/condition signals in the titles, add fair-price bands, and tell the user to
confirm price ≤ budget on each item. **Never stop at search-page URLs only.**
