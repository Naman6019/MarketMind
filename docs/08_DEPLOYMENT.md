# Deployment

## Frontend (Vercel)
- Deployed from the `frontend/` directory.
- `app/api/` handlers run as Node.js serverless functions.
- Uses `NEXT_PUBLIC_API_URL` to route requests to the backend.

## Backend (Render)
- Runs `backend/app/main.py` using Uvicorn.
- Can spin down on free tiers. The frontend `/api/keepalive` ping helps mitigate this, but first-heavy-query latency remains an issue.

## GitHub Actions
- `fetch_stocks.yml`: Runs `scripts/run_fetch.py` daily at 16:30 IST.
- `mf-sync.yml`: Runs MF metadata synchronization.
- **Rule**: Do not move cron logic to Vercel crons. Scripts require a Python runtime.
