# System Architecture

The application is a decoupled monorepo containing a frontend Next.js app and a backend FastAPI service.

## Frontend (`frontend/`)
- **Framework**: Next.js 15 (App Router)
- **UI/Styling**: Tailwind CSS, Lucide Icons, Recharts for charting.
- **State**: Zustand (Canvas visibility, selections).
- **Data Fetching**: Custom SWR-like hooks communicating with Next.js `/api/` proxy routes.

## Backend (`backend/`)
- **Framework**: Python FastAPI
- **AI Core**: Groq API (Llama 3.1 8b/70b)
- **Market Data**: YFinance (fallback), mfapi.in, local Supabase caching.
- **News**: Feedparser (Google News RSS).

## Database & Cron
- **Supabase**: Primary store for stock history, MF history, and metadata.
- **GitHub Actions**: Runs `backend/scripts/run_fetch.py` and `sync_mf.py` independently.
