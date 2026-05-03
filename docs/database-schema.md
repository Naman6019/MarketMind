# Database Schema

Run:

```bash
psql "$DATABASE_URL" -f backend/migrations/20260501_source_neutral_stock_data.sql
psql "$DATABASE_URL" -f backend/migrations/20260503_add_data_quality_issues.sql
```

## Source-Neutral Stock Tables
- `stocks`
- `stock_prices_daily`
- `financial_statements`
- `ratios_snapshot`
- `shareholding_pattern`
- `corporate_events`
- `data_provider_runs`
- `data_quality_issues`

All financial values use `numeric` columns. Unique constraints prevent duplicate symbol/date/source rows.

Legacy tables such as `nifty_stocks` and `stock_history` are kept as fallbacks during migration. New app paths read the source-neutral tables first.

Old CSV import helpers are isolated under `backend/scripts/deprecated/` and are not part of the active migration or production jobs.
