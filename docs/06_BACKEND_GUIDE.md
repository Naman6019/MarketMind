# Backend Guide

## Framework & Tooling
- **Framework**: FastAPI (Python 3.x).
- **Server**: Uvicorn.
- **Market Libraries**: `yfinance` (fallback), `feedparser` (news).
- **Database Client**: `supabase-py`.

## Directory Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point, endpoint definitions, AI Agent Router
│   ├── database.py          # Supabase client initialization
│   ├── fetcher.py           # On-demand stock fetching (NSE/Supabase first, YFinance fallback)
│   ├── nse_client.py        # NSE bhavcopy/live data client
│   ├── stock_universe.py    # NSE constituent CSV loader
│   ├── models/
│   │   └── stock_models.py  # StockProfile, StockPriceDaily, and other DTOs
│   ├── providers/           # Source-neutral provider adapters
│   │   ├── base.py          # Abstract FundamentalsProvider interface
│   │   ├── indianapi_provider.py  # IndianAPI adapter (stock universe, EOD, corp actions, MF)
│   │   ├── yfinance_provider.py   # YFinance fallback adapter
│   │   ├── manual_provider.py     # Reads from Supabase source-neutral tables
│   │   ├── nse_provider.py        # NSE bhavcopy adapter
│   │   └── finedge_provider.py    # FinEdge adapter (stock universe, EOD, corp actions, partial P&L)
│   ├── repositories/
│   │   └── stock_repository.py    # All CRUD for source-neutral stock tables
│   ├── services/
│   │   ├── quant_service.py       # Assembles /api/quant responses
│   │   └── ratio_engine.py        # Calculates financial ratios from statement data
│   └── jobs/                # Scheduled job modules (run by GitHub Actions)
│       ├── sync_stock_universe.py   # Writes stock metadata to `stocks`
│       ├── sync_latest_prices.py    # Writes EOD prices to `stock_prices_daily`
│       ├── sync_price_history.py    # Backfills historical price data
│       ├── sync_fundamentals.py     # Fetches financial statements from active provider
│       ├── calculate_ratios.py      # Computes and writes `ratios_snapshot`
│       ├── sync_corporate_events.py # Fetches dividends, splits, bonuses
│       └── sync_mf_from_indianapi.py # Syncs MF AUM/returns from IndianAPI
├── scripts/                 # Legacy standalone scripts (AMFI MF sync, run_fetch.py)
│   ├── run_fetch.py
│   ├── sync_mf.py
│   ├── sync_mf_history.py
│   ├── sync_mf_metadata.py
│   └── deprecated/          # Retired CSV scripts, not scheduled
├── migrations/              # SQL migration files
└── requirements.txt
```

## Conventions
- **Indentation**: 4 spaces.
- **Async**: Use `async def` for all route handlers.
- **Env Vars**: Use `os.getenv()`. Never hardcode secrets.
- **Dependencies**: Do not add dependencies without updating `requirements.txt`.
- **Scripts**: Scripts in `scripts/` are standalone. They must handle their own paths and not blindly import from `app/` without guards.
- **Jobs**: Modules under `app/jobs/` are invoked as `python -m backend.app.jobs.<name>` by GitHub Actions.

## Running Locally
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
