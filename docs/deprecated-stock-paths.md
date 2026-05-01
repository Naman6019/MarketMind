# Deprecated Stock Paths

The following files contain deprecated legacy code (e.g., CSV imports, hardcoded screener workflows) that have been replaced by the new Provider Adapter layer and Repository-based background jobs.

- `backend/scripts/sync_stock_universe.py`: Replaced by `backend/app/jobs/sync_stock_universe.py` which uses the unified provider architecture and `StockRepository`.
- `backend/scripts/run_fetch.py`: Legacy script for EOD prices. Replaced by `backend/app/jobs/sync_latest_prices.py` and `backend/app/jobs/sync_price_history.py`.
- `backend/scripts/sync_fundamentals.py`: Legacy fundamentals sync. Replaced by `backend/app/jobs/sync_fundamentals.py` leveraging configured `FundamentalsProvider` adapters.
- `backend/scripts/calculate_ratios.py`: Legacy ratio calculation script. Replaced by `backend/app/jobs/calculate_ratios.py` leveraging the updated `ratio_engine.py` logic.
