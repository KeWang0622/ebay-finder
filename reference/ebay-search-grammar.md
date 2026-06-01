# eBay Search Grammar Cheat Sheet

The keyless backbone of Treasure Hunter is precise eBay URL construction. This is
the reference both the code (`treasure_hunter/ebay_grammar.py`) and the agent use.

## Public search URL — `https://www.ebay.com/sch/i.html`

| Param | Meaning | Example |
|-------|---------|---------|
| `_nkw` | keywords (query) | `vintage typewriter` |
| `_sacat` | category id | `159923` (Typewriters) |
| `_udlo` / `_udhi` | price low / high (site currency) | `_udlo=40&_udhi=180` |
| `LH_ItemCondition` | condition ID(s), pipe-joined | `3000` or `1500\|3000` |
| `LH_BIN` | Buy It Now only | `1` |
| `LH_Auction` | Auctions only | `1` |
| `LH_BO` | Best Offer only | `1` |
| `LH_FS` | free shipping | `1` |
| `LH_PrefLoc` | location: 1=US, 2=N.America, 3=Worldwide | `1` |
| `LH_TopRatedSeller` | top-rated sellers only | `1` |
| `LH_RPB` | returns accepted | `1` |
| `_sop` | sort code (see below) | `15` |
| `_ipg` | results per page (60/120/240) | `60` |

### Keyword operators (in `_nkw`)
- **Exclude a word:** `typewriter -electric`
- **Exclude a phrase:** `typewriter -"for parts"`
- **OR group:** `(royal,remington,underwood) typewriter`
- **Exact phrase:** quote it — `"in working order"`

### Condition IDs (same numbers for web & API)
| ID | Meaning |
|----|---------|
| 1000 | New |
| 1500 | New other / open box |
| 2000 | Certified refurbished |
| 2500 | Seller refurbished |
| 3000 | Used |
| 7000 | For parts or not working |

### Sort codes (`_sop`)
| Code | Sort |
|------|------|
| 12 | Best Match (default) |
| 15 | Price + shipping: lowest first |
| 16 | Price + shipping: highest first |
| 10 | Newly listed |
| 1 | Ending soonest |

## Official Browse API — `GET /buy/browse/v1/item_summary/search`

Headers: `Authorization: Bearer <app_token>`, `X-EBAY-C-MARKETPLACE-ID: EBAY_US`.

| Param | Example |
|-------|---------|
| `q` | `vintage typewriter` |
| `category_ids` | `159923` |
| `sort` | `price`, `-price`, `newlyListed`, `endingSoonest` (omit for Best Match) |
| `limit` / `offset` | `limit=50` (max 200) |
| `aspect_filter` | `categoryId:159923,Brand:{Royal\|Remington}` |
| `filter` | comma-separated, see below |

### `filter=` field grammar
```
price:[40..180],priceCurrency:USD,
conditions:{3000|1500},
buyingOptions:{FIXED_PRICE|BEST_OFFER},
itemLocationCountry:US,
returnsAccepted:true,
sellerAccountTypes:{INDIVIDUAL}
```
Ranges use `[min..max]`, `[min..]`, or `[..max]`. Sets use `{A|B|C}`.

### OAuth (client-credentials)
```
POST https://api.ebay.com/identity/v1/oauth2/token
Authorization: Basic base64(client_id:client_secret)
Content-Type: application/x-www-form-urlencoded
grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope
```
Token lifetime ~7200s. Cache it; refresh ~60s before expiry.
Default client-credentials rate limit: ~1,000–5,000 calls/day (free dev tier).

## Handy category IDs (US)
| Category | id |
|----------|----|
| Typewriters | 159923 |
| Vintage Cameras | 15230 |
| Wristwatches | 31387 |
| Vinyl Records | 176985 |
| Vintage Computing | 162075 |
| Mechanical Keyboards | 33963 |
| Fountain Pens | 14894 |

(Use the website's "category" sidebar or the API `category_ids` to confirm — eBay
occasionally re-numbers leaf categories.)
