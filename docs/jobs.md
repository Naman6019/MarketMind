# Jobs

GitHub Actions runs stock jobs from `.github/workflows/fetch_stocks.yml`.

## Stock Jobs
```bash
python backend/scripts/sync_stock_universe.py
python backend/scripts/run_fetch.py
python backend/scripts/sync_fundamentals.py
python backend/scripts/calculate_ratios.py
```

## Behavior
- Jobs use upserts and are safe to rerun.
- NSE universe sync writes `stocks`.
- EOD fetch writes `stock_prices_daily` and legacy fallback tables.
- YFinance is used only when NSE bhavcopy returns empty or local price history is unavailable.
- Fundamentals sync is skipped when no external provider is configured.
- Ratio calculation writes `ratios_snapshot` only when enough statement data exists.
- Every provider job writes `data_provider_runs` where possible.
- Deprecated CSV scripts under `backend/scripts/deprecated/` are not scheduled.
