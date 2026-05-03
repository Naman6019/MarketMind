# Providers

Provider selection is controlled by environment variables.

```env
FUNDAMENTALS_PROVIDER=manual
FINEDGE_API_KEY=
INDIANAPI_KEY=
GLOBALDATAFEEDS_API_KEY=
STOCK_INFO_ENRICH_LIMIT=120
STOCK_YFINANCE_FALLBACK_LIMIT=150
```

## Active Providers
- `manual`: reads local Supabase source-neutral tables.
- `nse`: stock universe and EOD price data.
- `yfinance`: fallback for price/history only, not a primary fundamentals provider.
- `finedge`: adapter stub, disabled without `FINEDGE_API_KEY`.
- `indianapi`: active provider (`INDIANAPI_KEY` required). Implemented: stock universe, EOD price history, corporate actions, MF list + details. Financial statement methods (`get_quarterly_results`, `get_balance_sheet`, etc.) are **stubs** pending `/historical_stats` expansion.

If a selected paid provider is unavailable, backend code logs a warning and falls back to `manual`.

## Adding a Paid Provider
1. Implement the adapter in `backend/app/providers/`.
2. Normalize responses into `financial_statements`, `ratios_snapshot`, `shareholding_pattern`, and `corporate_events`.
3. Store provider name in `source`.
4. Leave unavailable fields as `null`.
5. Add provider-run logging in `data_provider_runs`.
