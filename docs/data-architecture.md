# Data Architecture

MarketMind stock data is source-neutral. App code reads normalized tables and does not depend on CSV exports.

## Stock Data Layers
- `stocks`: NSE/BSE metadata and identifiers.
- `stock_prices_daily`: daily OHLCV price history.
- `financial_statements`: quarterly and annual statement rows.
- `ratios_snapshot`: calculated and provider-supplied ratios.
- `shareholding_pattern`: promoter, FII, DII, public holdings.
- `corporate_events`: splits, dividends, bonuses, and other events.
- `data_provider_runs`: job run audit log.

## Rules
- Missing data stays `null`.
- Providers must write their `source`.
- Paid provider adapters must be disabled unless API keys exist.
- Scheduled jobs run in GitHub Actions, not Vercel cron.
- Stock EOD history is populated from NSE CM-UDiFF bhavcopy zip files with source `nse_bhavcopy`.
- Mutual fund tables and jobs remain separate.
