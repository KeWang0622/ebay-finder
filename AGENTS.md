# AGENTS.md — context for AI agents working in this repo

**Project:** eBay Finder — turn a vague, plain-language wish ("a 1930–60
typewriter, has to work, high value-for-money", in any language) into a smart,
ranked hunt across eBay.

**Core principle:** the *intelligence is the agent running the skill*. Intent
parsing, photo/vision judgment, and price sanity are done by the host LLM via
`SKILL.md`. The Python package provides only **deterministic tools**: build search
URLs, optionally call the official Browse API, and score/rank listings with
transparent arithmetic. This is what lets the skill work with **no API key and no
LLM API key** — it rides the agent that invokes it.

## Tiers
- **Keyless (default):** build expertly-crafted public eBay search URLs; the host
  agent may fetch those public pages to preview/parse listings. Always available.
- **API (opt-in):** if `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` are set, use the
  Browse API for clean structured fan-out + richer ranking.

## Hard rules
- **Zero runtime dependencies.** Stdlib only (`urllib`, `json`, `base64`). Tests use
  `pytest` (dev-only).
- **Respect eBay.** Official Browse API for data when keyed; for keyless, generate
  URLs / do polite single-shot human-initiated fetches. Never build a high-volume
  scraper or anything that automates the eBay UI — eBay's user agreement forbids it.
- Follow `CONTRACT.md` exactly. All data structures live in `ebay_finder/contract.py`.
- Immutability everywhere (frozen dataclasses). Functions return new copies.
- Keep eBay codes (condition IDs, sort codes) only in `ebay_finder/ebay_grammar.py`.

## Layout
```
ebay_finder/
  contract.py     # data structures (DONE) — the API boundary
  ebay_grammar.py # condition/sort/buying-option codes (DONE)
  url_builder.py  # keyless: QueryPlan -> eBay /sch/ URLs  (Claude)
  browse_api.py   # API mode: OAuth + item_summary/search   (Codex)
  ranker.py       # transparent scoring/ranking             (Codex)
  report.py       # render ranked markdown report           (Claude)
  cli.py          # orchestrator                             (Claude)
tests/            # pytest, no network                       (Codex)
reference/        # human-readable eBay grammar cheat sheet
SKILL.md          # the agent-facing skill (the product)
```

## Verify
```
python -m pytest -q          # tests pass, no network
python -m ebay_finder.cli --help
```
