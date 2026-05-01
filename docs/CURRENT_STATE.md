# Current State

**Last Updated**: 2026-05-01

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
- Stock-to-stock comparison has a metric-only canvas panel driven by `/api/chat` `system_action` data.
- Stock fundamentals now use a source-neutral provider architecture with `/api/quant/stocks/*` endpoints. CSV fundamentals are no longer required for active app paths.
- Legacy CSV tooling is isolated under `backend/scripts/deprecated/` and is not used by routes or GitHub Actions.
- Stock price-history comparison charts render when `stock_prices_daily` or fallback history exists.
- Next.js `/api/*` proxy pattern is the required frontend/backend boundary.
- GitHub Actions handles scheduled fetch jobs, not Vercel cron.
- Mobile dashboard layout now uses a single active workspace for chat or comparison, with the chat header fixed at the top and input fixed at the bottom on phones.

## In Progress
- Expanding stock coverage beyond the current Nifty-focused list.
- Testing `NIFTY500` vs `NIFTYTOTALMARKET`.
- Tuning `STOCK_INFO_ENRICH_LIMIT` and `STOCK_YFINANCE_FALLBACK_LIMIT`.
- **Premium Landing Page (`/`) with Framer Motion animations and Dashboard moved to (`/dashboard`)**.

## Known Gaps
- Paid fundamentals provider mappings are not implemented yet.
- Frontend proxy route rate limiting still pending.
- YFinance rate limits often on Render.
- Portfolio overlap is partial because AMFI holdings often returns `Nil`.
- News uses Google News RSS and can be slow.
- Landing page wide-screen overflow has been clipped and the hero/features shell now uses a wider responsive container.

## Stock Data Architecture
- Source-neutral tables are defined in `backend/migrations/20260501_source_neutral_stock_data.sql`.
- Provider adapters live in `backend/app/providers/`.
- Ratio calculation lives in `backend/app/services/ratio_engine.py`.
- GitHub Actions runs stock universe, EOD price, fundamentals, and ratio jobs.
