# Database Schema (Supabase)

The core data store uses PostgreSQL (via Supabase).

## Known Tables
- `nifty_stocks`: Universe of supported Nifty Large/Mid/Small cap stocks.
- `stock_history`: Historical price and volume data used for EOD calculations and local NIFTY history.
- `mutual_funds`: Metadata for mutual funds (scheme codes, names, categories).
- `mutual_fund_history`: Historical NAV data used for MF charting, Alpha, and Beta computations.

## Notes
- `stock_history` is used to build NIFTY performance baselines locally.
- Use `grep_search("\.table\(", include="*.py")` to discover precise queries before interacting with Supabase tables.
