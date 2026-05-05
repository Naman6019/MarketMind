# Providers

Provider selection is controlled by environment variables.

```env
STOCK_DATA_PROVIDER=manual
FINEDGE_API_KEY=
INDIANAPI_BASE_URL=https://stock.indianapi.in
INDIANAPI_KEY=
GLOBALDATAFEEDS_API_KEY=
STOCK_INFO_ENRICH_LIMIT=120
FUNDAMENTALS_WATCHLIST_SYMBOLS=TCS,RELIANCE,HDFCBANK
FUNDAMENTALS_WEEKLY_LIMIT=100
FUNDAMENTALS_MONTHLY_LIMIT=500
INDIANAPI_REQUEST_SLEEP_SECONDS=1.05
STOCK_YFINANCE_FALLBACK_LIMIT=150
```

## Active Providers
- `manual`: reads local Supabase source-neutral tables.
- `nse`: official NSE bhavcopy EOD price data and historical backfill.
- `yfinance`: fallback for price/history only, not a primary fundamentals provider.
- `finedge`: fallback only. Free keys may be limited and should not be relied on for fundamentals.
- `indianapi`: supplementary server-side provider (`INDIANAPI_KEY` required). Implemented v1 client/service methods: `/industry_search`, `/stock`, `/historical_stats`, `/mutual_fund_search`, `/mutual_funds`, `/mutual_funds_details`, `/corporate_actions`, `/recent_announcements`; optional enrichment: `/historical_data`, `/stock_target_price`, `/stock_forecasts`.

IndianAPI v1 base URL defaults to `https://stock.indianapi.in` and can be overridden with `INDIANAPI_BASE_URL`.
Fundamentals refresh uses `sync_fundamentals --scope watchlist|full|all-active` or `--symbols TCS,RELIANCE`. Weekly watchlist refresh defaults to 100 symbols; monthly full refresh defaults to `NIFTY500` and 500 symbols.
FinEdge authenticates with `token=<apiKey>` in the URL query string.
FinEdge free-plan coverage is limited; do not use it as the stock fundamentals source.
NSE EOD history uses `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`.
IndianAPI historical data uses `/historical_data` with `stock_name`, `period`, and `filter` only as optional enrichment. Scheduled daily/history price workflows still prefer NSE CM-UDiFF bhavcopy. A 403 disables only that endpoint in `provider_endpoint_health`.

If a selected paid provider is unavailable, backend code logs a warning and falls back to `manual`.

## Adding a Paid Provider
1. Implement the adapter in `backend/app/providers/`.
2. Normalize responses into `financial_statements`, `ratios_snapshot`, `shareholding_pattern`, and `corporate_events`.
3. Store provider name in `source`.
4. Leave unavailable fields as `null`.
5. Add provider-run logging in `data_provider_runs`.
