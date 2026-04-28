# API Contracts

## Frontend Proxy Routes (`frontend/app/api/`)
- `POST /api/chat`: Proxies user chat prompts to the backend.
- `GET /api/keepalive`: Calls the backend `/health` endpoint to keep the Render instance from sleeping.
- `GET /api/mf/[schemeCode]`: Fetches Supabase-backed mutual fund details and NAV history.
- `GET /api/search`: Supabase-backed search endpoint for stocks/funds.
- `GET /api/cron/sync-mf`: Protected route to trigger MF synchronization.

## Backend FastAPI Routes (`backend/app/main.py`)
- `POST /api/chat`: Accepts user prompts, routes to internal AI agents, fetches data, and returns synthesized markdown + structured `quant_data`.
- `GET /health`: Keepalive check.
- **TODO**: Add a dedicated `/api/quant` endpoint to separate stock lookup from chat synthesis.
- **TODO**: Add rate limiting for `/api/chat` and trigger routes.
