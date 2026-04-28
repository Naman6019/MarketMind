# Database Schema

MarketMind uses Supabase (PostgreSQL) as its primary data store. 
*(Note: Writes are kept server-side only via backend scripts or service-role environments).*

## Known Tables
- `nifty_stocks`: Universe of supported Nifty Large/Mid/Small cap and Total Market stocks.
- `stock_history`: Historical price and volume data. Used for EOD calculations and local NIFTY performance baselines.
- `mutual_funds`: Metadata for mutual funds (scheme codes, names, categories, TER, AUM).
- `mutual_fund_history`: Historical NAV data used for MF charting, returns, Alpha, and Beta computations.

## TODOs
- **Holdings/Overlap**: Schema details for portfolio overlap features are incomplete or rely on partial AMFI disclosures.
