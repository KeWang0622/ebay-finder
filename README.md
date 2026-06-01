<div align="center">

<img src="assets/logo.png" alt="eBay Finder" width="116" />

# eBay Finder

**Say what you want in plain words. Get a ranked hunt across eBay.**

*“a 1930–60 typewriter, has to actually **work**, best **bang for the buck** under $150”*
→ a shortlist of real listings, ranked, with the reasons shown.

<br/>

```bash
npx skills add KeWang0622/ebay-finder
```

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Runtime deps: 0](https://img.shields.io/badge/runtime%20deps-0-success)
![API key: optional](https://img.shields.io/badge/API%20key-optional-orange)
![Any language](https://img.shields.io/badge/works%20in-any%20language-8a2be2)
[![Star this repo](https://img.shields.io/github/stars/KeWang0622/ebay-finder?style=social)](https://github.com/KeWang0622/ebay-finder)

<img src="assets/hero.png" alt="" width="100%" />

</div>

---

## Keyword search can't do this

You know the feeling. You half-know what you want, with a few hard rules:

> *“a 1930–60 typewriter, has to work, best value for money”*

You can't type that into eBay's search box. And if you ask ChatGPT, it can't pull up **real, current, ranked** listings. eBay is building its own AI shopper — but it's **closed, US-only, and you can't script it.**

**eBay Finder is the open one, and it works for everyone.**

## See it work

For that exact wish, it fans out across the value brands, caps the budget near your anchor, and ranks — and the **cheapest** listing is *not* the winner, because you said it has to work:

```text
🏆 Top finds

1. Olympia SM3 — RESTORED & guaranteed working, ribbon included      score 70/100
   $110 + $18 ship = $128 · 99.9% positive (15,000 ratings) · New York, US
   works ~100% · value ×1.00
   ✓ working/tested language found  ✓ excellent seller

5. Underwood — FOR PARTS OR REPAIR, untested                          score  0/100
   $69 · ⚠ for-parts
   ✗ you said it must work — this listing strongly signals it doesn't
```

Every line tells you *why* it ranked there. No black box.

## How it works

<div align="center"><img src="assets/flow.png" alt="vague wish → search angles → ranked finds" width="100%" /></div>

The trick: **the AI agent running the skill is the brain.** It reads your wish, plans the strategy, and judges the photos and prices. The bundled, zero-dependency Python tool does only the boring, deterministic parts — so it needs **no API key and no LLM key.**

| | |
|--|--|
| **1 · Understand** | your wish → a structured goal (must-work, budget, era, deal-breakers) — *any language in, your language out* |
| **2 · Strategize** | one weak query becomes several smart angles: broad, per-brand, budget-capped, newest-first |
| **3 · Search** | get real listings via a fallback ladder: official Browse API *(free key)* → fetch the search pages → **eBay-restricted web search**. Always ends with actual `/itm/` listings, never just search pages |
| **4 · Inspect** | the agent looks at the listing **photos** to confirm condition and "working" claims |
| **5 · Rank** | transparent 0–100 score: value-vs-market, works-confidence, condition, seller trust, returns |

## Install & use

```bash
npx skills add KeWang0622/ebay-finder
```

Then just ask your agent, however you'd say it:

> *“find me a 1930–60 typewriter that actually works, best value under $150”*
> *“una máquina de escribir de los años 40 que funcione, buena relación calidad-precio”*

**No API key needed** — it returns a ranked list of real listings (via fetch, or an eBay-restricted web-search fallback when fetching is blocked), with fair-price bands and risk flags. Want fully-automatic structured fetch + ranking? Add a [free eBay key](SETUP.md) (~2 min).

<details>
<summary><b>Run the tool directly (optional)</b></summary>

```bash
# Keyless: build the search strategy + URLs for a wish
python -m ebay_finder.cli examples/typewriter.json

# Rank listings your agent fetched from those pages
python -m ebay_finder.cli examples/typewriter.json --listings listings.json --out report.md

# With a free eBay key set, it fetches + ranks automatically
export EBAY_CLIENT_ID=... EBAY_CLIENT_SECRET=...
python -m ebay_finder.cli examples/typewriter.json --out report.md
```
</details>

## It works for anything you'd hunt for

Not just typewriters — any category, any fuzzy wish:

| You say… | eBay Finder does… |
|----------|-------------------|
| *“a Pokémon card with the best value for money under $100”* | biases to graded slabs + vintage WOTC holos, hard-excludes proxies/fakes, ranks by collectible upside per dollar |
| *“a film camera that actually shoots, not a shelf prop”* | requires *tested/working*, kills *“for parts/display only”*, prefers sellers who post sample shots |
| *“a mechanical keyboard, quiet switches, under $80, like-new”* | open-box + used condition, budget cap, aspect on switch type, sorts by value |
| *“vintage Levi’s 501, made in USA, 32×32, honest fade”* | folds the spec into keywords, flags reproductions, rewards original-tag listings |

Run any of these via [`examples/`](examples/) or just ask your agent.

## Why it's different

| | eBay search | ChatGPT alone | eBay's AI agent | **eBay Finder** |
|--|:--:|:--:|:--:|:--:|
| Understands vague, multi-rule wishes | ❌ | ✅ | ✅ | ✅ |
| Returns **real, current** listings | ✅ | ❌ | ✅ | ✅ |
| Ranks on value / "must work", with reasons | ❌ | ❌ | ⚠️ | ✅ |
| Works in **any language** | ⚠️ | ✅ | ⚠️ | ✅ |
| **Open · scriptable · free** | — | — | ❌ | ✅ |
| Works with **no API key** | ✅ | — | — | ✅ |

## Plays fair with eBay

Uses eBay's **official Buy/Browse API** when you add a key, and otherwise builds standard search URLs for polite, human-initiated viewing. It does **not** scrape or automate the eBay UI — in line with eBay's developer and user agreements.

## Under the hood

```
SKILL.md                  the skill (the product) — what the agent follows
ebay_finder/
  contract.py             shared, immutable data model
  ebay_grammar.py         single source of truth for eBay codes
  url_builder.py          keyless: wish → eBay search URLs
  browse_api.py           official Browse API client (stdlib only)
  ranker.py               transparent 0–100 scoring
  report.py · cli.py      report + orchestrator
examples/ · reference/ · tests/
```

```bash
python -m pytest -q       # all green, zero network
```

Zero runtime dependencies. Pure standard library. Contributions welcome — category maps, more marketplaces, sharper ranking signals. See [`AGENTS.md`](AGENTS.md) and [`CONTRACT.md`](CONTRACT.md).

---

<div align="center">

**If this helps you find something good, [give it a ⭐](https://github.com/KeWang0622/ebay-finder) — it's how others discover it.**

<sub>MIT © 2026 Ke Wang · built with Claude + Codex · visuals by [Pika](https://pika.art)</sub><br/>
<sub>Prices and availability change fast — always verify on eBay before buying.</sub>

</div>
