# Architecture

MarketMind is a decoupled monorepo containing a frontend Next.js application and a backend FastAPI service.

## Frontend (`frontend/`)
- **Framework**: Next.js 15 (App Router).
- **Core Loop**: Users interact with the AI Chat UI. The app proxies these requests through Next.js serverless functions (`/api/*`) to prevent CORS and hide backend secrets.
- **State & UI**: Zustand manages canvas visibility and selections. Recharts handles charting.

## Backend (`backend/`)
- **Framework**: Python FastAPI.
- **Core Loop**: `main.py` receives proxied requests. An LLM (Groq) acts as a router, classifying intent into Quant, News, Screener, or Comparison.
- **Data Fetchers**: `fetcher.py` and `nse_client.py` pull live quotes or local Supabase data.
- **Synthesis**: The LLM synthesizes a markdown answer, while structured `quant_data` is returned alongside it for precise frontend rendering.

## Data Flow
1. User types in chat -> `frontend/app/api/chat` -> `backend/api/chat`.
2. Backend LLM routes intent -> fetches from Supabase / NSE / YFinance / News RSS.
3. Backend LLM synthesizes response -> returns JSON (Markdown + structured data).
4. Frontend displays Markdown in chat and opens Canvas with structured data.

## External APIs
- **Supabase**: Primary persistent data store (PostgreSQL + Realtime).
- **Groq API**: Hosts Llama models for intent routing and response synthesis.
- **YFinance**: Fallback/supplemental stock market data (often rate-limited on Render).
- **NSE Bhavcopy / Indices**: Daily EOD stock data and constituent lists.
- **mfapi.in & AMFI**: Mutual fund NAV and metadata.
- **Google News RSS**: Market news via Feedparser.

## Auth
- TODO: Investigate frontend user authentication (if any exists). Currently, Supabase uses Anon Keys for client reads and Service Role Keys for backend writes.
