# Current State

## 1. Architecture

MarketMind is a full-stack market research platform.

- Frontend: Next.js app on Vercel with chat, canvas views, stock/MF search, and comparison UI.
- Backend: FastAPI service on Render with routing, data lookup, risk metrics, synthesis, and fetch triggers.
- Database: Supabase stores stock snapshots/history, mutual fund metadata, NAV history, and holdings placeholders.
- Data jobs: GitHub Actions run scheduled stock and mutual fund sync scripts.
- Data sources: NSE bhavcopy and NSE index constituent CSVs for stocks; AMFI NAV, AMFI public APIs, and mfapi.in for mutual funds.
- AI layer: Groq-hosted LLM routes user queries and generates research-only summaries.

## 2. Completed Features

- Research-only chat experience with disclaimer language.
- Asset mode toggle: `Auto`, `Stocks`, `Mutual Funds`.
- Mutual fund comparison canvas with NAV charts, AUM, expense ratio, returns, alpha, beta, Sharpe, and volatility where data exists.
- Mutual fund sync workflow for latest NAV, NAV history, TER, AUM, and partial holdings support.
- Fixed mutual fund comparison routing so MF mode does not fall back to stock tickers.
- Fixed timezone mismatch in MF/NIFTY risk metric calculations.
- Stock EOD fetch pipeline via NSE bhavcopy and Supabase.
- Expanded stock universe from hardcoded lists to official NSE index CSVs, defaulting to Nifty 500.
- Stock name resolver for broad NSE names, including typo-tolerant resolution like `Waree Energies` to `WAAREEENER`.
- Vercel and Render auto-deploy are enabled; duplicate GitHub deploy workflow is no longer needed.

## 3. Current Task

The current work is broadening stock coverage from a small Nifty-focused list to a larger official NSE universe.

Current default:

```text
STOCK_UNIVERSE_INDEX=NIFTY500
```

This covers roughly 500 NSE stocks. The broader supported option is:

```text
STOCK_UNIVERSE_INDEX=NIFTYTOTALMARKET
```

That uses NSE's broader total market constituent list, around 750 stocks.

## 4. Next Steps

- Push the current stock-universe changes and let Render/Vercel redeploy.
- Run `EOD Stock Data Fetch` manually from GitHub Actions.
- Verify Supabase has rows for expanded symbols such as `WAAREEENER`.
- Test Stocks mode with prompts like `How is Waaree Energies performing?`.
- Watch GitHub Action duration and adjust `STOCK_INFO_ENRICH_LIMIT` if runtime or YFinance throttling becomes an issue.
- Decide whether to keep `NIFTY500` or switch to `NIFTYTOTALMARKET`.
- Add direct stock comparison canvas later; current canvas is still optimized for mutual funds.
