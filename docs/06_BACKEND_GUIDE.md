# Backend Guide

## Framework & Tooling
- **Framework**: FastAPI (Python 3.x).
- **Server**: Uvicorn.
- **Market Libraries**: `yfinance` (fallback), `feedparser` (news).
- **Database Client**: `supabase-py`.

## Directory Structure
- `app/main.py`: FastAPI entry point, endpoint definitions, and AI Agent Router logic.
- `app/database.py`: Supabase client initialization.
- `app/fetcher.py`: Data fetching logic (YFinance, Supabase lookups).
- `app/nse_client.py`: Client for NSE bhavcopy/live data.
- `app/stock_universe.py`: Logic for loading NSE constituent CSVs.
- `scripts/`: Standalone cron scripts (`run_fetch.py`, `sync_mf.py`, `sync_mf_metadata.py`).

## Conventions
- **Indentation**: 4 spaces.
- **Async**: Use `async def` for all route handlers.
- **Env Vars**: Use `os.getenv()`. Never hardcode secrets.
- **Dependencies**: Do not add dependencies without updating `requirements.txt`.
- **Scripts**: Scripts in `scripts/` are standalone. They must handle their own paths and not blindly import from `app/` without guards.

## Running Locally
```bash
cd backend
# Or use python -m uvicorn ...
uvicorn app.main:app --reload --port 8000
```
