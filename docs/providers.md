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
- `finedge`: fallback only. Free keys may be limited and should not be relied on for fundamentals.
- `indianapi`: active stock metadata/fundamentals provider (`INDIANAPI_KEY` or `INDIAN_API_KEY` required). Implemented: stock universe, `/stock` profile data, `/statement` fundamentals/ratios/shareholding, `/historical_data` price history, corporate actions, MF list + details.

FinEdge authenticates with `token=<apiKey>` in the URL query string.
FinEdge free-plan coverage is limited; do not use it as the stock fundamentals source.
NSE EOD history uses `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`.
IndianAPI historical prices use `/historical_data` with `stock_name`, `period`, and `filter`. Scheduled daily/history price workflows still prefer NSE CM-UDiFF bhavcopy.

If a selected paid provider is unavailable, backend code logs a warning and falls back to `manual`.

## Adding a Paid Provider
1. Implement the adapter in `backend/app/providers/`.
2. Normalize responses into `financial_statements`, `ratios_snapshot`, `shareholding_pattern`, and `corporate_events`.
3. Store provider name in `source`.
4. Leave unavailable fields as `null`.
5. Add provider-run logging in `data_provider_runs`.
