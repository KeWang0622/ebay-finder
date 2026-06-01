<div align="center">

<img src="assets/logo.png" alt="Treasure Hunter logo" width="120" />

# 🔭 Treasure Hunter for eBay

### Describe what you want in plain words — in *any* language — and get a ranked hunt across eBay.

<em>“a <strong>1930–60</strong> typewriter, has to <strong>work</strong>, high <strong>性价比</strong>”</em> → a shortlist of real listings, ranked, with reasons.

[![Install with skills](https://img.shields.io/badge/install-npx%20skills%20add-000?style=for-the-badge)](https://github.com/vercel-labs/skills)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
![Zero dependencies](https://img.shields.io/badge/runtime%20deps-0-success?style=for-the-badge)
![Works without an API key](https://img.shields.io/badge/API%20key-optional-orange?style=for-the-badge)

<img src="assets/hero.png" alt="Treasure Hunter hero" width="100%" />

</div>

---

## The problem

Keyword search breaks the moment your wish has **soft constraints**:

> *"a 1930–60 typewriter, **has to work**, **high value-for-money**"*

You can't type that into eBay. You can't even type it into ChatGPT and get real, current, ranked listings back. eBay is building its own AI shopper — but it's **closed, US-only, and not scriptable.**

**Treasure Hunter is the open one that works for everyone.** It turns a fuzzy wish into expert eBay searches, fans out across angles, inspects the listings (including the photos), and hands you a ranked shortlist with the reasoning shown.

## How it works

<div align="center">
<img src="assets/flow.png" alt="Vague wish → search angles → ranked finds" width="100%" />
</div>

The trick: **the intelligence is the AI agent that runs the skill.** Your assistant (Claude, etc.) reads the wish, designs the strategy, and judges the photos and prices. The bundled, zero-dependency Python tool does only the deterministic parts:

1. **Understand** the wish → a structured goal (`must_work`, budget, era, deal-breakers, nice-to-haves) — *any language in, your language out.*
2. **Strategize** → several search angles (broad, per-brand, budget-capped, newest-first) instead of one weak query.
3. **Search** → build precise eBay search URLs *(keyless)* or call the official Browse API *(with a free key)*.
4. **Inspect** → the agent looks at listing photos to confirm condition, model, and "working" claims.
5. **Rank & report** → transparent 0–100 scoring on value-vs-market, working-confidence, condition, seller trust, returns — with a reason on every line and ⚠ flags for risks.

## Quick start

Install the skill into any agent that supports the [skills](https://github.com/vercel-labs/skills) format:

```bash
npx skills add KeWang0622/ebay-treasure-hunter
```

Then just ask your agent, in plain language:

> *“find me a 1930–60 typewriter that actually works, best bang for the buck under $150”*
> *“想要一台能用的老式打字机，1930到1960年代，高性价比”*

That's it. **No API key required** — you get expertly-built, fully-filtered eBay search links plus a ranked read of the listings. Want richer, automatic results? Add a [free eBay API key](SETUP.md) (~2 minutes) and it fetches and ranks listings for you.

### Run the tool directly (optional)

```bash
# Keyless: build the search strategy + URLs for a wish
python -m treasure_hunter.cli examples/typewriter.json

# Rank listings your agent fetched from those pages
python -m treasure_hunter.cli examples/typewriter.json --listings listings.json --out report.md

# With a free eBay key set, it fetches + ranks automatically
export EBAY_CLIENT_ID=... EBAY_CLIENT_SECRET=...
python -m treasure_hunter.cli examples/typewriter.json --out report.md
```

## Example output

For the flagship wish — *“1930–60 typewriter, has to work, high 性价比”* — Treasure Hunter fans out across the value brands (Royal, Remington, Underwood, Smith-Corona, Olympia), caps the budget near your anchor, and ranks:

```
🏆 Top finds

1. Olympia SM3 — RESTORED & guaranteed working, ribbon included   · score 70/100
   $110.00 + $18.00 ship = $128.00 · 99.9% positive (15,000 ratings) · New York, US
   works~100% · value×1.00
   - working/tested language found
   - seller feedback 99.9% over 15000 ratings

…

5. Underwood — FOR PARTS OR REPAIR, untested                      · score 0/100
   $69.00 · ⚠ for-parts
   - must work, but listing strongly signals non-working   ← hard-gated, even though cheapest
```

The cheapest listing is *not* the winner when you said "has to work" — and the report tells you exactly why.

## Why it's different

| | Plain eBay search | ChatGPT/Claude alone | eBay's own AI agent | **Treasure Hunter** |
|---|:---:|:---:|:---:|:---:|
| Understands vague, multi-constraint wishes | ❌ | ✅ | ✅ | ✅ |
| Returns **real, current** listings | ✅ | ❌ | ✅ | ✅ |
| Ranks on value / "must work" with reasons | ❌ | ❌ | ⚠️ | ✅ |
| Works in **any language** | ⚠️ | ✅ | ⚠️ | ✅ |
| **Open + scriptable + free** | — | — | ❌ | ✅ |
| Works with **no API key** | ✅ | — | — | ✅ |

## Plays fair with eBay

Treasure Hunter uses eBay's **official Buy/Browse API** when you add a key, and otherwise builds standard search URLs for polite, human-initiated viewing. It does **not** scrape or automate the eBay UI, and it does not impersonate a shopper bot — in line with eBay's developer and user agreements.

## Project layout

```
SKILL.md                     the skill (the product) — agent-facing flow
treasure_hunter/
  contract.py                shared, immutable data model
  ebay_grammar.py            single source of truth for eBay codes
  url_builder.py             keyless: QueryPlan → eBay search URLs
  browse_api.py              official Browse API client (stdlib only)
  ranker.py                  transparent 0–100 scoring
  report.py                  Markdown report
  cli.py                     orchestrator
reference/ebay-search-grammar.md   the URL + API cheat sheet
examples/                    runnable plan specs
tests/                       pytest, no network
```

## Develop

```bash
python -m pytest -q          # all green, zero network
python -m treasure_hunter.cli examples/typewriter.json --json
```

Contributions welcome — new category maps, marketplace support, and ranking signals especially. See [`AGENTS.md`](AGENTS.md) and [`CONTRACT.md`](CONTRACT.md).

## License

MIT © 2026 Ke Wang. Built with Claude + Codex. Visuals by [Pika](https://pika.art).

<div align="center"><sub>Prices and availability change fast — always verify on eBay before buying.</sub></div>
