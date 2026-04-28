# Backend Guide

## Tech Stack
FastAPI, Python 3.x, Supabase-py, YFinance, Feedparser.

## Conventions
- **Indentation**: 4 spaces.
- **Async**: Use `async def` for route handlers.
- **Environment Vars**: Access via `os.getenv()`. Never hardcode secrets.
- **Organization**:
  - Agent logic lives in `app/main.py`.
  - Data fetching logic lives in `app/fetcher.py`.
  - Standalone scripts live in `scripts/` and should not blindly import from `app/` without path guards.

## Running Locally
```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
