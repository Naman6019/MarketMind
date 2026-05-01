# Tasks

## Todo
- [ ] Add a dedicated `/api/quant` backend endpoint to separate stock lookup from chat synthesis.
- [ ] Add stock comparison charts/history beyond the current metric-only canvas.
- [ ] Add rate limiting for frontend proxy routes (`/api/chat`, `/api/cron/sync-mf`).

## In Progress
- [ ] Expanding stock coverage beyond the current Nifty-focused list.
- [ ] Testing `NIFTY500` vs `NIFTYTOTALMARKET`.
- [ ] Tuning `STOCK_INFO_ENRICH_LIMIT` and `STOCK_YFINANCE_FALLBACK_LIMIT`.
- [ ] Building a premium Landing Page at `/` and moving app to `/dashboard` (UI layout fixes ongoing).

## Done
- [x] AI chat with asset mode toggle: `Auto`, `Stocks`, `Mutual Funds`.
- [x] Mutual fund comparison canvas with NAV charts, returns, alpha, beta, Sharpe.
- [x] MF sync for NAV, TER, and AUM.
- [x] Stock EOD fetch pipeline using NSE CSVs and Supabase.
- [x] Stock name resolver for broader NSE names and typo tolerance.
- [x] Fixed MF/NIFTY timezone mismatch in risk metrics.
- [x] Fixed MF comparison routing so it does not fall back to stock tickers.
- [x] Added deterministic `/api/chat` response tables with missing-entity notes, news fallback text, and safer research wording.
- [x] Added metric-only stock-to-stock comparison canvas.
- [x] Next.js `/api/*` proxy pattern enforced as frontend/backend boundary.
- [x] GitHub Actions handles scheduled fetch jobs, not Vercel cron.

## Blocked
- None currently.

## Known Issues
- YFinance rate limits often on Render deployments.
- [ ] Portfolio overlap is partial because AMFI holdings API often returns `Nil`.
- News uses Google News RSS and can be slow.
- Landing page has an empty black space on the right side. This persists because the root background container isn't stretching fully to 100% viewport width on wide screens, likely due to a conflict between Windows scrollbar width calculations and Tailwind's w-full/overflow-x-hidden properties.
