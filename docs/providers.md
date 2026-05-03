# Providers

Provider selection is controlled by environment variables.

```env
STOCK_DATA_PROVIDER=manual
FINEDGE_API_KEY=
INDIANAPI_KEY=
GLOBALDATAFEEDS_API_KEY=
STOCK_INFO_ENRICH_LIMIT=120
STOCK_YFINANCE_FALLBACK_LIMIT=150
```

## Active Providers
- `manual`: reads local Supabase source-neutral tables.
- `nse`: official NSE bhavcopy EOD price data and historical backfill.
- `yfinance`: fallback for price/history only, not a primary fundamentals provider.
- `finedge`: active stock metadata/fundamentals provider (`FINEDGE_API_KEY` required). Implemented: stock universe, corporate actions, and partial annual P&L fundamentals.
- `indianapi`: active provider (`INDIANAPI_KEY` required). Implemented: stock universe, EOD price history, corporate actions, MF list + details. Financial statement methods (`get_quarterly_results`, `get_balance_sheet`, etc.) are **stubs** pending `/historical_stats` expansion.

FinEdge authenticates with `token=<apiKey>` in the URL query string.
FinEdge free keys may allow `/api/v1/stock-symbols` while rejecting paid price endpoints like `/api/v1/daily-quotes/{symbol}`.
NSE EOD history uses `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`.
IndianAPI EOD history uses `/historical_data` with `symbol`, `period`, and `filter` query params.

If a selected paid provider is unavailable, backend code logs a warning and falls back to `manual`.

## Adding a Paid Provider
1. Implement the adapter in `backend/app/providers/`.
2. Normalize responses into `financial_statements`, `ratios_snapshot`, `shareholding_pattern`, and `corporate_events`.
3. Store provider name in `source`.
4. Leave unavailable fields as `null`.
5. Add provider-run logging in `data_provider_runs`.
