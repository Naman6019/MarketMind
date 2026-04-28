# API Contracts

## Frontend Proxy Routes (`frontend/app/api/`)
- `/api/chat`: Proxies chat requests to the backend.
- `/api/keepalive`: Calls the backend `/health` to keep Render instances warm.
- `/api/mf/[schemeCode]`: Fetches Supabase-backed mutual fund details.
- `/api/search`: Supabase-backed search endpoint.
- `/api/cron/sync-mf`: Protected route for MF synchronization.

## Backend FastAPI Routes (`backend/app/main.py`)
- `/api/chat` (POST): Accepts user prompts, routes to internal AI agents, and returns synthesized markdown and structured `quant_data`.
- `/health` (GET): Simple keepalive check.
- (TODO: Extract a dedicated `/api/quant` endpoint for structured data)
