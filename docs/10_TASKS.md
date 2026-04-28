# Ongoing Tasks & Limitations

## 1. Architecture Tasks

- Keep frontend API routes as thin proxies to the FastAPI backend.
- Keep Supabase writes server-side only through backend scripts or service-role environments.
- Keep GitHub Actions focused on scheduled data syncs, not deployment, because Vercel and Render already auto-deploy on commit.
- Keep stock universe loading shared between `backend/app/fetcher.py` and `backend/scripts/run_fetch.py`.

## 2. Completed Features

- Mutual fund mode and stock mode toggle added to chat.
- Mutual fund data sync now fills NAV, NAV history, TER, and AUM from public/non-commercial sources.
- MF chart/risk calculations now normalize timezone handling.
- Stock universe now loads from official NSE CSVs instead of small hardcoded arrays.
- Nifty 500 is the default stock universe.
- Stock resolver handles company-name prompts and common typo cases.

## 3. Current Task

Expand stock coverage safely while keeping GitHub Actions reliable.

Current settings:

```yaml
STOCK_UNIVERSE_INDEX: NIFTY500
STOCK_INFO_ENRICH_LIMIT: "120"
STOCK_YFINANCE_FALLBACK_LIMIT: "150"
```

Do not blindly enrich all 500 stocks with YFinance `info`; it can slow down or throttle the action.

## 4. Next Steps

- Run the stock fetch workflow manually after pushing.
- Check that `nifty_stocks` contains expanded symbols, especially `WAAREEENER`.
- Check that `stock_history` receives rows for expanded symbols.
- Tune `STOCK_INFO_ENRICH_LIMIT` based on action runtime.
- If Nifty 500 works reliably, test `NIFTYTOTALMARKET`.
- Add a dedicated `/api/quant` endpoint to separate stock lookup from chat synthesis.
- Build stock-to-stock comparison canvas; current comparison canvas is MF-first.
- Move benchmark fetching fully server-side.
- Add rate limiting for `/api/chat` and `/api/trigger-fetch`.

## Known Limitations

- Portfolio overlap depends on usable AMFI/AMC holdings disclosures and is still partial.
- AMFI holdings API currently returns `Nil` for many AMC/quarter combinations.
- Stock comparison canvas still shows a placeholder for direct stock-to-stock comparisons.
- News fetching relies on Google News RSS and may have latency or coverage gaps.
- YFinance should remain a fallback/enrichment source, not the main EOD price source.
