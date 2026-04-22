# Project: MarketMind

## Overview

MarketMind is an **AI-orchestrated financial research platform** for the Indian stock and mutual fund markets. It uses a multi-agent pipeline to synthesize quantitative metrics, news sentiment, and historical trends into retail-investor-friendly insights. The system is split into a **Next.js 15 frontend** (deployed on Vercel) and a **Python FastAPI backend** (deployed separately on Render), with **Supabase** as the primary database and **GitHub Actions** handling all scheduled data fetching.

---

## Tech Stack

### Frontend
- **Framework:** Next.js 15 (App Router), TypeScript
- **Styling:** Tailwind CSS
- **Charts:** Recharts
- **Icons:** Lucide Icons
- **State Management:** Zustand
- **Deployment:** Vercel

### Backend
- **Framework:** Python, FastAPI
- **AI/LLM:** Groq API (Llama 3.1 8b / 70b)
- **Market Data:** YFinance (on-demand), mfapi.in (Mutual Fund NAV)
- **News:** Feedparser (Google News RSS)
- **Deployment:** Render (or equivalent Python host)

### Data & Automation
- **Database:** Supabase (PostgreSQL + Realtime)
- **Scheduling:** GitHub Actions (cron-based, NOT Vercel crons)
  - `fetch_stocks.yml` — EOD stock data at 16:30 IST (11:00 UTC)
  - `mf-sync.yml` — Mutual fund metadata sync

---

## Directory Structure

```
MarketMind/
├── .github/workflows/
│   ├── fetch_stocks.yml      # Daily EOD stock data fetch (16:30 IST)
│   └── mf-sync.yml           # MF metadata sync
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point + AI Agent Router
│   │   ├── database.py       # Supabase client initialization
│   │   └── fetcher.py        # On-demand YFinance logic for agents
│   ├── scripts/
│   │   ├── run_fetch.py      # Standalone EOD script (used by GitHub Actions)
│   │   └── sync_mf.py        # Mutual Fund metadata sync script
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── api/              # Next.js API Routes (proxy to backend/Supabase)
│   │   └── page.tsx          # Main dashboard entry point
│   ├── components/
│   │   ├── canvas/           # Deep-dive UI (Comparison, Stock/MF views)
│   │   ├── chat/             # AI chat interaction window
│   │   ├── funds/            # MF-specific charts and detail panels
│   │   └── layout/           # Dashboard & Sidebar structure
│   ├── hooks/                # Custom data-fetching hooks (SWR-like pattern)
│   ├── lib/                  # Quant utilities (Alpha, Beta, Sharpe, CAGR, etc.)
│   └── store/                # Zustand global state (canvas visibility, selections)
└── README.md
```

---

## Key Functional Modules

### A. AI Agent Pipeline (Backend)
The core of MarketMind — a multi-agent router in `backend/app/main.py`:
- **Router Agent:** Classifies user intent into Quant, News, Screener, or Comparison.
- **Quant Agent:** Fetches real-time or cached EOD data via YFinance.
- **News Parser:** Scrapes Google News RSS per ticker; assigns AI-driven sentiment via Groq.
- **Synthesis Core:** Combines quant data + news into a structured Markdown response with "Trend Observations."

### B. Interactive Canvas (Frontend)
- The dashboard splits into a **Chat Area** (left) and a **Canvas** (right).
- Canvas views live in `frontend/components/canvas/`.
- **Head-to-Head MF Comparison:** Two mutual funds compared with normalized (rebased to 100) NAV charts.
- **Risk Analysis:** Auto-computed Alpha, Beta, Sharpe Ratio, Standard Deviation — quant logic in `frontend/lib/`.
- **Portfolio Overlap:** Common holdings + stock concentration across two funds — logic exists in the canvas components but is currently limited by real-time AMFI data availability.

### C. Data Engine
- **Stock Universe:** Nifty 50 (Large Cap), Nifty Midcap 100, Nifty Smallcap 250 (~110 tickers total).
- **MF Engine:** mfapi.in for historical NAV; metadata synced to Supabase for fast searching.
- **EOD Pipeline:** GitHub Actions runs `backend/scripts/run_fetch.py` daily at 16:30 IST.

---

## How to Approach Every Task

Always follow this sequence — no shortcuts:

### 1. Understand First
- Use `grep_search` **extensively** before writing a single line of code.
- Use `grep_search` to locate relevant functions, routes, component names, and hook patterns.
- Use `find_files` (glob) to map the structure before reading specific files.
- Use `read_file` or `read_many_files` to validate assumptions.
- Do **not** guess file locations or function signatures — always verify.

### 2. Plan Before Acting
- Articulate the plan clearly before making any edits.
- Identify which files will be touched, what changes, and any downstream side effects.
- For multi-file changes (e.g. backend route + frontend hook + component), sequence edits with dependencies first.

### 3. Execute Precisely
- Make **targeted, minimal edits** — do not rewrite working code unnecessarily.
- Preserve existing code style, naming conventions, and patterns (e.g. SWR-like hooks, Zustand store patterns).
- After editing, **read the file back** to verify the change is correct.

### 4. Verify
- For backend: run `uvicorn backend.app.main:app --reload` and test the affected route.
- For frontend: run `npm run dev` inside `frontend/` and check the relevant component/page.
- Check for TypeScript errors (`npx tsc --noEmit`) after frontend edits.

---

## Using `grep_search` Effectively

`grep_search` is the single most important tool for navigating this codebase — use it before every non-trivial edit.

**What it does:** Searches for a regex pattern across files, returning matching lines with file path and line number. Uses `git grep` in a Git repo (fast).

**When to use it:**
- Before touching any backend route: find where it's defined and where it's called
- Before editing a component: find all places it's imported and used
- Before adding a new utility to `lib/`: check if a similar one already exists
- Before editing Zustand store: find all consumers of that slice of state

**Key patterns for this codebase:**

```bash
# --- BACKEND ---
# Find all FastAPI route definitions
grep_search("@app\.(get|post|put|delete)|@router\.")

# Find all Supabase operations
grep_search("supabase\.", include="*.py")

# Find env var usage
grep_search("os\.getenv|SUPABASE|GROQ|MFAPI", include="*.py")

# Find Groq/LLM call sites
grep_search("groq|chat\.completions|Groq\(", include="*.py")

# Find YFinance usage
grep_search("yfinance|yf\.download|Ticker\(", include="*.py")

# --- FRONTEND ---
# Find all Next.js API route handlers
grep_search("export.*GET|export.*POST", include="*.ts")

# Find Zustand store usage
grep_search("useStore|useCanvasStore|create\(", include="*.tsx")

# Find canvas view components
grep_search("Canvas|CanvasView|canvasType", include="*.tsx")

# Find MF overlap / common holdings logic
grep_search("overlap|commonHolding|concentration", include="*.tsx")
grep_search("overlap|commonHolding|concentration", include="*.ts")

# Find Recharts usage (chart components)
grep_search("LineChart|AreaChart|BarChart|ResponsiveContainer", include="*.tsx")

# Find quant utility functions in lib/
grep_search("sharpe|alpha|beta|cagr|drawdown", include="*.ts")

# Find hook definitions
grep_search("export.*function use|export const use", include="*.ts")
```

Use the `include` filter to narrow scope:
- Python only: `include="*.py"`
- TypeScript/React: `include="*.tsx"` or `include="*.ts"`

---

## Coding Conventions

### Python / FastAPI (`backend/`)
- **4 spaces** indentation — never tabs
- All route handlers use `async def` with full type annotations
- Environment variables via `os.getenv()` — never hardcode secrets
- Errors via FastAPI's `HTTPException` with correct status codes
- Agent logic stays in `main.py`; pure data fetching stays in `fetcher.py`
- Scripts in `backend/scripts/` are standalone — they must not import from `app/` without a relative path guard

### TypeScript / Next.js (`frontend/`)
- **2 spaces** indentation
- Use the App Router pattern — pages in `app/`, shared UI in `components/`
- Data fetching via custom hooks in `hooks/` — do not fetch directly inside components
- Zustand store in `store/` — keep slices focused (canvas state, selection state, etc.)
- Quant math lives in `lib/` — keep it pure (no React, no side effects)
- API calls from the frontend always go through `app/api/` proxy routes — never call the FastAPI backend directly from the browser (CORS + key safety)
- Use Recharts for all charts — do not introduce a second chart library
- TypeScript strict mode is on — fix type errors, do not use `any` as a crutch

### General
- Never commit `.env` or `.env.local` — use `.env.example` for documentation
- Do not add dependencies (pip or npm) without updating the relevant lockfile/requirements
- GitHub Actions workflows in `.github/workflows/` are critical infrastructure — edit carefully and always verify cron times in UTC (IST = UTC+5:30)

---

## Deployment Notes

### Frontend (Vercel)
- Deployed as a standard Next.js 15 app — `frontend/` is the project root on Vercel
- `app/api/` routes become Vercel serverless functions (Node.js runtime)
- Environment variables set in the Vercel dashboard
- **Vercel does NOT run the Python backend** — it only hosts Next.js and the proxy API routes

### Backend (Render)
- FastAPI app in `backend/app/main.py`, started with `uvicorn`
- The frontend's `app/api/` routes proxy requests to this backend URL
- Backend URL is stored as an environment variable — never hardcode it in frontend code

### GitHub Actions (Data Pipeline)
- `fetch_stocks.yml`: runs `backend/scripts/run_fetch.py` at 16:30 IST (11:00 UTC) on weekdays
- `mf-sync.yml`: syncs MF metadata to Supabase
- Secrets (Supabase keys, etc.) stored in GitHub repo secrets — not in code
- Do **not** move cron logic into Vercel — the scripts require a Python runtime

---

## Supabase Notes

- Python client (`supabase-py`) used in backend; JS client (`@supabase/supabase-js`) used in frontend proxy routes
- Always handle errors explicitly — never silently swallow exceptions
- Stock EOD data, MF metadata, and cached results live in Supabase
- Use `grep_search("\.table\(", include="*.py")` to discover existing table names before writing new queries
- RLS may be enabled — verify policies if queries return empty unexpectedly

---

## Known Limitations (Do Not Regress These)

- **Portfolio Overlap:** Logic exists in `frontend/components/canvas/` but is limited by real-time AMFI data availability — do not remove or break existing overlap code while making other changes.
- **Stock-to-Stock Comparison:** Canvas is currently optimized for MF comparison; stock comparison is in development.
- **News Latency:** News is fetched via RSS (Feedparser) — not real-time exchange filings; moving toward direct scraping in future.

---

## Do Not

- Do **not** run `pip install` or `npm install` without confirming with the user
- Do **not** call the FastAPI backend directly from browser-side code — always go through `app/api/` proxy
- Do **not** use `console.log` for debugging in components — remove before committing
- Do **not** use `any` in TypeScript without clear justification
- Do **not** add print statements in Python — use `logging`
- Do **not** make assumptions about Supabase table schemas — search first
- Do **not** expose Supabase service keys or Groq API keys in any committed file
- Do **not** move scheduled jobs to Vercel crons — they require the Python runtime in GitHub Actions

---

## Quick Reference: Shell Commands

```bash
# --- Frontend ---
cd frontend
npm run dev              # Start Next.js dev server
npx tsc --noEmit         # Check TypeScript errors without building
npm run build            # Production build (mirrors Vercel)

# --- Backend ---
cd backend
uvicorn app.main:app --reload --port 8000   # Start FastAPI dev server
python scripts/run_fetch.py                  # Run EOD stock fetch manually
python scripts/sync_mf.py                    # Run MF metadata sync manually
pip list                                     # Check installed packages

# --- General ---
printenv | grep -i supabase    # Check Supabase env vars
printenv | grep -i groq        # Check Groq env vars
```

---

## Memory Tip

Use `/memory add <note>` during sessions to persist discoveries — Supabase table names, env var names, component locations, tricky routing rules — so context survives across sessions.