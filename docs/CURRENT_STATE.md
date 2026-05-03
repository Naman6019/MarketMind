# Current State

**Last Updated**: 2026-05-03

## Project Summary
MarketMind is a research-only Indian equities and mutual fund app.

**Tech Stack**: 
- Next.js 15 frontend
- FastAPI backend
- Supabase (PostgreSQL)
- Groq API (LLM)
- YFinance & NSE data
- GitHub Actions cron jobs

## Implemented
- AI chat with asset mode toggle: `Auto`, `Stocks`, `Mutual Funds`.
- Mutual fund comparison canvas with NAV charts, returns, alpha, beta, Sharpe.
- MF sync for NAV, TER, and AUM.
- Stock EOD fetch pipeline using NSE CSVs and Supabase.
- Stock name resolver for broader NSE names and typo tolerance.
- Fixed MF/NIFTY timezone mismatch in risk metrics.
- Fixed MF comparison routing so it does not fall back to stock tickers.
- Chat responses now render deterministic data tables from structured `quant_data`, including unavailable comparison entities and news fallback text.
- `/api/chat` stock comparisons reuse the source-neutral stock comparison payload and tolerate missing risk periods in deterministic tables.
- Stock-to-stock comparison has a metric-only canvas panel driven by `/api/chat` `system_action` data.
- Stock fundamentals now use a source-neutral provider architecture with `/api/quant/stocks/*` endpoints. CSV fundamentals are no longer required for active app paths.
- Legacy CSV tooling is isolated under `backend/scripts/deprecated/` and is not used by routes or GitHub Actions.
- Stock price-history comparison charts render when `stock_prices_daily` or fallback history exists.
- Next.js `/api/*` proxy pattern is the required frontend/backend boundary.
- GitHub Actions handles scheduled fetch jobs, not Vercel cron.
- Mobile dashboard layout keeps chat mounted behind comparison overlays, and chat state lives in a shared store so query/messages survive canvas-to-chat switches.
- `IndianAPIProvider` is fully implemented for stock universe, EOD prices, corporate actions, and MF data (AUM, NAV, returns). Financial statement methods are stubs pending expansion.
- `FinEdgeProvider` supports stock universe, corporate actions, and partial annual P&L fundamentals using `FINEDGE_API_KEY`.
- `sync_corporate_events.py` is FinEdge-only and does not use IndianAPI fallback, avoiding IndianAPI 403 failures for stock corporate actions.
- Stock EOD and historical price backfill use NSE CM-UDiFF bhavcopy zip files and write `stock_prices_daily` with source `nse_bhavcopy`.
- IndianAPI EOD price history follows the documented `/historical_data?symbol=...&period=1yr&filter=price` request shape.
- `sync_mf_from_indianapi.py` job syncs MF AUM and returns from IndianAPI into the `mutual_funds` Supabase table, running as part of the `mf-sync.yml` workflow.

## In Progress
- Expanding stock coverage beyond the current Nifty-focused list.
- Testing `NIFTY500` vs `NIFTYTOTALMARKET`.
- Tuning `STOCK_INFO_ENRICH_LIMIT` and `STOCK_YFINANCE_FALLBACK_LIMIT`.
- **Premium Landing Page (`/`) with Framer Motion animations and Dashboard moved to (`/dashboard`)**.
- Mutual fund missing data cleanup after stock historical backfill.

## Known Gaps
- IndianAPI financial statement endpoints (`get_quarterly_results`, `get_balance_sheet`, etc.) are stubs; `STOCK_DATA_PROVIDER=manual` remains the active local fallback path.
- Frontend proxy route rate limiting still pending.
- YFinance rate limits often on Render.
- Portfolio overlap is partial because AMFI holdings often returns `Nil`.
- News uses Google News RSS and can be slow.
- Landing page wide-screen layout now uses full-width hero/features sections, and the hero preview fills the right side instead of stopping at a fixed card width.

## Stock Data Architecture
- Source-neutral tables are defined in `backend/migrations/20260501_source_neutral_stock_data.sql`.
- Stock data DTOs live in `backend/app/models/stock_models.py`.
- Supabase stock repository access lives in `backend/app/repositories/stock_repository.py`.
- Provider adapters live in `backend/app/providers/`.
- Ratio calculation lives in `backend/app/services/ratio_engine.py`.
- Provider sync issue logging uses optional `data_quality_issues`; apply `backend/migrations/20260503_add_data_quality_issues.sql` if the table is missing.
- NSE bhavcopy value traded needs `backend/migrations/20260503_add_stock_price_value_traded.sql` on older Supabase schemas.
- GitHub Actions runs 8 workflows: stock universe, daily EOD prices, historical price backfill, fundamentals + ratios (weekly), corporate events, legacy EOD fetch, MF sync, and keepalive. See `docs/jobs.md` for the full schedule.
