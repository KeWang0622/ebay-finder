---
name: ebay-finder
description: >-
  Find anything on eBay from a vague, plain-language wish — in ANY language —
  even with fuzzy constraints like "must actually work", "best value for money",
  a date range ("1930–60"), or a vibe ("looks well-loved, not beat up").
  Translates the wish into expert eBay searches, fans out across angles, inspects
  listings (incl. photos), and returns a ranked shortlist with reasons. Works with
  NO API key; richer with a free eBay developer key. Use whenever someone wants to
  buy, find, price-check, or hunt for something on eBay and plain keyword search
  isn't enough.
license: MIT
---

# 🔭 eBay Finder

Plain keyword search fails the moment a wish has *soft* constraints — "a **1930–60**
typewriter, **has to work**, **best value for money**". eBay's own AI shopper is closed/US-only.
This skill is the open one that works for everyone: **you are the intelligence** —
you read the wish, design the search strategy, judge the photos and prices — and the
bundled Python tool does the deterministic parts (build precise eBay URLs, optionally
call the official Browse API, and score listings transparently).

## When to use
- "Find me a …", "help me buy …", "what's a good … on eBay", "is this a fair price"
- Any wish with fuzzy criteria: condition/working state, era, budget, brand vibe,
  value-for-money, "not a project / not for parts", "with original box", etc.
- Requests in any language (translate the *intent*, keep the user's language in the report).

## The method (follow in order)

### 1 — Understand the wish → `Criteria`
Read the request and extract the soft goal. Build a `criteria` object:
- `raw_request`: the user's exact words (any language).
- `item_summary`: a short English description.
- `must_work`: true if functional/tested matters.
- `value_focused`: true for "best value / cheap but good / bang for the buck".
- `target_price_usd`: their mental anchor if any (convert currency).
- `era`: e.g. `"1930-1960"`. `deal_breakers`: phrases that disqualify
  (e.g. "repainted", "reproduction"). `nice_to_haves`: phrases that boost
  (e.g. "original case", "new ribbon", "serviced").
- `notes`: 1–2 sentences explaining your search strategy (shown in the report).

If the wish is genuinely ambiguous in a way that changes the search (budget unknown
AND no anchor, or item type unclear), ask **one** crisp question. Otherwise proceed —
don't interrogate the user.

### 2 — Strategize → several `QueryPlan`s
Vague wishes need **multiple search angles**, not one query. Typical fan-out:
- A **broad** angle (category + era keywords).
- One angle **per likely brand / synonym** (e.g. typewriters → Royal, Remington,
  Underwood, Smith-Corona, Olympia). Brands are where the value hides.
- A **budget** angle (tight price band, sorted by price).
- A **fresh** angle (`NEWLY_LISTED`) to catch underpriced new listings.

For each plan set: `label` (why this angle), `keywords`, `category_id` (see
`reference/ebay-search-grammar.md`), `conditions`, `buying_options`,
`price_min_usd`/`price_max_usd`, `sort`, `item_location_country`, `aspects`
(e.g. `[["Brand", ["Royal","Remington"]]]`).

Encode `must_work` as **ranking** intent, not a hard filter — sellers mislabel
constantly. The tool adds conservative negative keywords (`-"for parts"`) for you.

### 3 — Search
Write the spec to `plan.json` and run the tool:
```bash
python -m ebay_finder.cli plan.json --out report.md
```
- **Keyless (default):** the tool prints clickable, fully-filtered eBay search URLs.
  Open / fetch them, then read the listings. To rank what you fetched, hand them back:
  ```bash
  python -m ebay_finder.cli plan.json --listings listings.json --out report.md
  ```
  (`listings.json` = a JSON array of items you scraped from the page: `title`, `url`,
  `price_usd`, `shipping_usd`, `condition_raw`, `seller_feedback_pct`, `image_url`, …)
- **API mode (richer):** if `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` are set, the
  tool calls the official Browse API, fetches structured listings, dedupes, and ranks
  automatically. See `SETUP.md` for the 2-minute free key.

### 4 — Inspect (use your eyes)
For the top candidates, **look at the photos** (`image_url`): confirm the era/model,
spot cracks/rust/missing keys/repaints, sanity-check that "working" claims are
plausible. Read the seller's condition text. This visual judgment is *your* job and is
exactly what keyword search can't do — it's the skill's superpower.

### 5 — Rank & report
The ranker scores 0–100 on value-vs-cohort, working-confidence, condition fit, seller
trust, returns, deal-breakers and nice-to-haves, with a reason on every line. Present
the **top finds** with: total price (incl. shipping), why it ranked, any ⚠ flags
("for-parts", "no-returns", "low-feedback", "price-outlier-low"), and the link. Then
list the search URLs so the user can keep hunting. Add your own one-line verdict and a
fair-price band. **Reply in the user's language.**

## Plan spec example (flagship: the typewriter)
See `examples/typewriter.json` for a full, runnable spec. The shape:
```json
{
  "criteria": {
    "raw_request": "1930-60 type writer, has to work, high value for money",
    "item_summary": "working vintage typewriter, 1930s–1960s, best value",
    "must_work": true, "value_focused": true,
    "target_price_usd": 120, "era": "1930-1960",
    "deal_breakers": ["repaint", "reproduction"],
    "nice_to_haves": ["serviced", "new ribbon", "original case"],
    "notes": "Fan out across the value brands; cap budget; reward tested/serviced."
  },
  "plans": [
    {"label": "Value brands, working, budget", "keywords": "vintage typewriter (royal,remington,underwood,smith-corona,olympia)",
     "category_id": "159923", "conditions": ["USED"], "buying_options": ["FIXED_PRICE","BEST_OFFER"],
     "price_min_usd": 40, "price_max_usd": 180, "sort": "BEST_MATCH", "item_location_country": "US"},
    {"label": "Newly listed underpriced", "keywords": "vintage typewriter working", "category_id": "159923",
     "conditions": ["USED"], "price_max_usd": 150, "sort": "NEWLY_LISTED"}
  ]
}
```

## Principles
- **Respect eBay.** Use the official Browse API when keyed; keyless = build URLs and do
  polite, human-initiated fetches. Never build a high-volume scraper or automate the
  eBay UI — eBay's user agreement forbids agentic bots.
- **Be honest.** Prices/availability change fast; tell the user to verify before buying.
  Surface risk flags, don't hide them to make a result look good.
- **Multi-language by default.** Understand any language; answer in theirs.

## Files
- `ebay_finder/` — the tool (zero runtime deps, stdlib only).
- `reference/ebay-search-grammar.md` — eBay URL + Browse API cheat sheet.
- `examples/` — runnable plan specs.
- `SETUP.md` — optional free eBay API key in ~2 minutes.
