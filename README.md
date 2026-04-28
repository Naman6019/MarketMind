# MarketMind

MarketMind is an AI-orchestrated financial research platform for the Indian stock and mutual fund markets. It provides retail-investor-friendly insights by synthesizing quantitative metrics, news sentiment, and historical trends through a multi-agent pipeline.

## Features
- **AI Chat & Intent Routing**: Routes queries to Quant, News, Screener, or Comparison pipelines.
- **Interactive Canvas**: Deep-dive UI for side-by-side Mutual Fund comparisons (NAV charts, returns, alpha, beta, Sharpe).
- **Automated Data Pipelines**: Daily EOD stock data fetches and mutual fund syncs.

## Tech Stack
- **Frontend**: Next.js 15, TypeScript, Tailwind CSS, Zustand, Recharts (Deployed on Vercel)
- **Backend**: Python FastAPI, YFinance, Groq API, Feedparser (Deployed on Render)
- **Database**: Supabase (PostgreSQL)
- **Automation**: GitHub Actions

## Project Structure
```
MarketMind/
├── .github/workflows/      # Data synchronization cron jobs
├── backend/                # FastAPI application & fetching scripts
├── frontend/               # Next.js web application
├── docs/                   # Shared agent memory & architectural docs
└── prompts/                # AI Agent instructions
```

## Setup & Development

### 1. Environment Variables
Copy the `.env.example` file to create your local environments:
- `.env` (or `.env.local` inside `frontend/`)
- Backend `.env` inside `backend/`
See `.env.example` for required keys.

### 2. Run the Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Run the Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Documentation
For agents and contributors, read the `AGENTS.md` file and the `docs/` folder. The primary source of truth is `docs/CURRENT_STATE.md`.
