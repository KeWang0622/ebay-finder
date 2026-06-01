# Optional: free eBay API key (≈2 minutes)

Treasure Hunter works **with no key at all** — it builds expert eBay search URLs and
ranks any listings you hand it. Adding a free eBay developer key unlocks **API mode**:
it fetches structured listings itself, dedupes across search angles, and ranks them
automatically.

## Get the key
1. Go to <https://developer.ebay.com/> and sign in (or create a free account).
2. Open **Developer Account → Application Keys**.
3. Create / use a **Production** keyset. You need the **App ID (Client ID)** and
   **Cert ID (Client Secret)**.

## Use the key
Set two environment variables before running the tool:
```bash
export EBAY_CLIENT_ID="YourAppId-xxxx-PRD-xxxxxxxxx-xxxxxxxx"
export EBAY_CLIENT_SECRET="PRD-xxxxxxxxxxxx-xxxx-xxxx-xxxx-xxxx"
```
That's it — the next run uses API mode automatically. The OAuth token is cached at
`~/.cache/treasure_hunter/token.json` (override with `EBAY_TOKEN_CACHE`).

## Limits & etiquette
- The client-credentials (application) tier is free, ~1,000–5,000 calls/day — plenty
  for personal hunting.
- Treasure Hunter uses the **official Buy/Browse API** only. It never scrapes or
  automates the eBay website, in line with eBay's developer and user agreements.

## No key? You still get everything that matters
Run without the variables set and the tool prints clickable, fully-filtered search
URLs. Open them (or let your agent fetch them), then rank what you found:
```bash
python -m treasure_hunter.cli plan.json --listings listings.json --out report.md
```
