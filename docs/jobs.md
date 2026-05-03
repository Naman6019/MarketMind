# Jobs

GitHub Actions runs stock and MF jobs from `.github/workflows/`. Jobs are Python modules under `backend/app/jobs/`.

## Stock Workflows

| Workflow file | Schedule (UTC) | Job module invoked |
|---|---|---|
| `sync-stock-universe.yml` | Daily `0 1 * * *` | `python -m backend.app.jobs.sync_stock_universe` |
| `sync-prices-daily.yml` | Weekdays `30 10 * * 1-5` | `python -m backend.app.jobs.sync_latest_prices` |
| `sync-fundamentals-weekly.yml` | Saturdays `0 2 * * 6` | `python -m backend.app.jobs.sync_fundamentals` + `calculate_ratios` |
| `sync-corporate-events.yml` | Daily `0 3 * * *` | `python -m backend.app.jobs.sync_corporate_events` |
| `fetch_stocks.yml` | Daily `0 11 * * *` | `python backend/scripts/run_fetch.py` (legacy EOD fetch) |

## MF Workflows

| Workflow file | Schedule (UTC) | Steps |
|---|---|---|
| `mf-sync.yml` | Weekdays `30 13 * * 1-5` | `scripts/sync_mf.py` → `sync_mf_history.py` → `sync_mf_metadata.py` → `python -m backend.app.jobs.sync_mf_from_indianapi` |
| `keepalive.yml` | Scheduled ping | Pings Render `/api/keepalive` to prevent free-tier spin-down |

## Behavior
- Jobs use upserts and are safe to rerun.
- NSE universe sync writes `stocks`.
- EOD price jobs write `stock_prices_daily`.
- EOD price jobs count an empty provider response as a failed symbol, not a successful insert.
- Stock universe, EOD price, fundamentals, and corporate event workflows select FinEdge with `STOCK_DATA_PROVIDER=finedge`.
- YFinance is used only when NSE bhavcopy returns empty or local price history is unavailable.
- Fundamentals sync is skipped when no external provider is configured.
- Ratio calculation writes `ratios_snapshot` only when enough statement data exists.
- Every provider job writes `data_provider_runs` where possible.
- Deprecated CSV scripts under `backend/scripts/deprecated/` are not scheduled.
- Stock job secrets are stored as GitHub Repository Secrets: `SUPABASE_URL`, `SUPABASE_KEY`, `FINEDGE_API_KEY`.
- MF sync still uses `INDIAN_API_KEY` for IndianAPI mutual fund data.
