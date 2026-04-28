# MarketMind Codex Guide

This file is the working guide for Codex agents operating in this repository.
It captures project structure, commands, data flow, and known implementation
constraints that matter when making changes.

## Project Overview

MarketMind is a market research app for Indian equities, indices, and mutual
funds. It has two deployable parts:

- `frontend/`: Next.js app deployed on Vercel.
- `backend/`: FastAPI service deployed on Render.

The app uses Supabase as the durable data store, Groq for LLM routing and
synthesis, and multiple market-data fallbacks for stocks, indices, and mutual
funds.

## Important Rule

This project uses Next.js `16.2.4`. Do not assume older Next.js APIs or file
conventions. Before changing Next.js route handlers, app router behavior,
caching, or config, read the relevant local docs under:

```text
frontend/node_modules/next/dist/docs/
```

The root `AGENTS.md` explicitly warns that this is not the Next.js version most
models were trained on.

## Repository Map

```text
backend/
  app/
    main.py              FastAPI app, chat endpoint, routing, quant fetch logic
    database.py          Supabase client setup
    fetcher.py           EOD/on-demand stock fetch compatibility layer
    nse_client.py        NSE/BSE/live quote helpers
  scripts/
    run_fetch.py         Scheduled stock/EOD sync
    sync_mf.py           Mutual fund NAV/history sync
    sync_mf_metadata.py  Mutual fund metadata sync
  requirements.txt
  render.yaml

frontend/
  app/
    api/
      chat/route.ts              Proxy to backend `/api/chat`
      keepalive/route.ts         Calls backend `/health`
      mf/[schemeCode]/route.ts   Supabase-backed mutual fund details endpoint
      search/route.ts            Supabase search endpoint
      cron/sync-mf/route.ts      Protected MF sync route
  components/
    chat/ChatWindow.tsx
    canvas/
    funds/
  hooks/
  lib/
  store/
  package.json

.github/workflows/
  fetch_stocks.yml
  mf-sync.yml
  keepalive.yml
```

## Local Development

Run backend:

```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run frontend:

```powershell
cd frontend
npm run dev
```

The frontend development proxy expects the backend at:

```text
http://127.0.0.1:8000/api/chat
```

Production frontend requests use:

```text
NEXT_PUBLIC_API_URL
```

## Verification Commands

Backend syntax check:

```powershell
python -m py_compile backend/app/main.py
```

Frontend type check:

```powershell
cd frontend
node node_modules/typescript/bin/tsc --noEmit
```

Frontend build:

```powershell
cd frontend
npm run build
```

Lint:

```powershell
cd frontend
npm run lint
```

Note: in this local environment, `npm` may be misconfigured if it points to a
missing global `npm-cli.js`. Use the bundled project tooling directly when
possible, or fix the local Node/npm installation before relying on `npm` output.

## Environment Variables

Do not commit real secrets. The app expects these environment variables in the
appropriate deployment environments:

```text
Backend / Render:
SUPABASE_URL
SUPABASE_KEY
GROQ_API_KEY

Frontend / Vercel:
NEXT_PUBLIC_API_URL
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
CRON_SECRET

GitHub Actions:
SUPABASE_URL
SUPABASE_KEY
```

## Runtime Data Flow

### Chat

1. `frontend/components/chat/ChatWindow.tsx` sends user input to `/api/chat`.
2. `frontend/app/api/chat/route.ts` proxies to the FastAPI backend.
3. `backend/app/main.py` classifies intent through Groq.
4. Backend gathers quant/news/screener/comparison data.
5. Backend synthesizes a markdown answer through Groq.
6. For compare actions, backend also returns `system_action` and structured
   `quant_data`.
7. Frontend opens the canvas using Zustand state in `frontend/store/useCanvasStore.ts`.

### Mutual Fund Comparison

Structured comparison data should come from backend `quant_data.comparison`.
The comparison canvas must not rely only on the markdown answer, because the
LLM may omit fields that exist in structured data.

Known fields used by the frontend include:

```text
name
nav
nav_date
category
fund_house
expense_ratio
aum
beta
alpha_vs_nifty
risk_period
source
```

Backend risk metrics for mutual funds should prefer local Supabase
`mutual_fund_history` plus local NIFTY history from `stock_history`. Use
YFinance only as a fallback.

### Stock / NIFTY Quant Data

`backend/app/main.py::fetch_quant_data` should prefer:

- market-hours live stock quotes through `fetch_live_quote`
- market-hours live NIFTY snapshot for `^NSEI` / `NIFTY`
- Supabase local snapshots/history as fallback
- YFinance as a fallback, not the sole source of truth

This is important because YFinance regularly rate-limits or fails on Render.

### Mutual Fund Details Canvas

`frontend/app/api/mf/[schemeCode]/route.ts` fetches fund details and history
from Supabase. Avoid calling a helper from this route that fetches `/api/mf`
again, because that can recurse back into the same route.

## Market Data Tables

Common Supabase tables referenced by code:

```text
nifty_stocks
stock_history
mutual_funds
mutual_fund_history
```

`stock_history` is used for local NIFTY history and EOD stock calculations.
`mutual_fund_history` is used for mutual fund charting, returns, Alpha, and Beta.

## Deployment Notes

Frontend deploys to Vercel. Backend deploys to Render.

Render free tier can spin down after inactivity. A keepalive endpoint exists,
but keepalive requests to `/health` only warm the service process. They do not
warm heavy routes, Groq, Supabase, YFinance, or NSE/BSE network paths.

For perceived latency:

- keep critical data in Supabase
- prefer local snapshots before live APIs
- keep short in-memory caches for hot quant lookups
- avoid doing multiple YFinance calls in a single request when local data is enough

## Coding Guidelines

- Use `rg` for search and `rg --files` for file discovery.
- Keep changes scoped to the affected feature path.
- Do not revert unrelated user changes.
- Use `apply_patch` for manual edits.
- Avoid broad `except: pass` blocks; log failures with enough context.
- Preserve structured response payloads separately from LLM markdown answers.
- Avoid putting generated secrets or `.env.local` content into docs or commits.
- TypeScript is strict. Explicitly type callback parameters when inference is weak.
- For Next.js route handlers, check local Next docs before changing signatures,
  caching, dynamic config, or route conventions.

## Known Fragile Areas

- YFinance can rate-limit or return empty data on Render.
- The LLM markdown answer may omit fields available in `quant_data`.
- NIFTY values can be stale if only EOD sync is used during market hours.
- Render `/health` keepalive does not eliminate first-heavy-query latency.
- Frontend direct benchmark fetches from Yahoo can fail in user browsers.
- Supabase service role keys must stay server-side only.

## Recommended Future Improvements

- Add a dedicated backend `/api/quant` endpoint for structured stock/index data.
- Move benchmark data fetching fully server-side.
- Store short-lived live quotes in Supabase or another cache during market hours.
- Add explicit tests for compare payload shape and MF Alpha/Beta visibility.
- Replace broad LLM-driven table rendering with deterministic tables when
  structured data is available.

