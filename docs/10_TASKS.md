# Tasks

## Todo
- [x] Add a dedicated `/api/quant` backend endpoint to separate stock lookup from chat synthesis.
- [ ] Add rate limiting for frontend proxy routes (`/api/chat`, `/api/cron/sync-mf`).

## Future Features
- [ ] Advanced charting: add richer stock/fund chart controls, date ranges, indicators, and mobile-friendly comparison views before considering WebGL.
- [ ] Document analysis: support annual report/PDF upload, extraction, summaries, and cited answers.
- [ ] Basic strategy backtesting: simulate simple rules against clean historical EOD data with fees, slippage, benchmark comparison, and result charts.
- [ ] Historical anomaly detection: flag unusual price, volume, valuation, or fundamentals changes with evidence; avoid predictive wording until models are validated.

## In Progress
- [ ] Expanding stock coverage beyond the current Nifty-focused list.
- [ ] Testing `NIFTY500` vs `NIFTYTOTALMARKET`.
- [ ] Tuning `STOCK_INFO_ENRICH_LIMIT` and `STOCK_YFINANCE_FALLBACK_LIMIT`.
- [ ] Building a premium Landing Page at `/` and moving app to `/dashboard`.
- [ ] Fill mutual fund missing data gaps after stock historical backfill.

## Done
- [x] Quota-aware fundamentals cadence: monthly NIFTY500, weekly watched stocks, and on-demand compared symbols.
- [x] AI chat with asset mode toggle: `Auto`, `Stocks`, `Mutual Funds`.
- [x] Mutual fund comparison canvas with NAV charts, returns, alpha, beta, Sharpe.
- [x] MF sync for NAV, TER, and AUM.
- [x] Stock EOD fetch pipeline using NSE CSVs and Supabase.
- [x] Stock name resolver for broader NSE names and typo tolerance.
- [x] Fixed MF/NIFTY timezone mismatch in risk metrics.
- [x] Fixed MF comparison routing so it does not fall back to stock tickers.
- [x] Added deterministic `/api/chat` response tables with missing-entity notes, news fallback text, and safer research wording.
- [x] Fixed `/api/chat` stock comparison table crash when risk period data is missing.
- [x] Added metric-only stock-to-stock comparison canvas.
- [x] Added legacy CSV import foundation and premium fundamental comparison charts.
- [x] Replaced active CSV dependency with source-neutral stock provider architecture.
- [x] Moved legacy CSV tooling under `backend/scripts/deprecated/`.
- [x] Added stock price-history comparison charts for source-neutral quant data.
- [x] Next.js `/api/*` proxy pattern enforced as frontend/backend boundary.
- [x] GitHub Actions handles scheduled fetch jobs, not Vercel cron.
- [x] Fixed mobile dashboard clipping by using a single active chat/comparison workspace and compact comparison chart spacing.
- [x] Fixed mobile chat positioning so the header stays visible and the input stays at the bottom.
- [x] Fixed mobile comparison canvas state loss by keeping chat mounted behind the canvas overlay and moving chat state into a shared store.
- [x] Fixed landing page wide-screen right-side void by removing fixed hero width caps and using full-width sections.
- [x] Added internal stock DTOs and a Supabase repository layer for source-neutral stock data.
- [x] Added NSE CM-UDiFF bhavcopy daily price sync and manual historical backfill into `stock_prices_daily`.

## Blocked
- None currently.

## Known Issues
- YFinance rate limits often on Render deployments.
- [ ] Portfolio overlap is partial because AMFI holdings API often returns `Nil`.
- News uses Google News RSS and can be slow.
- Landing page wide-screen void was fixed by removing fixed hero width caps and using full-width sections.
