# Deployment

MarketMind utilizes a split deployment architecture due to the differing runtime requirements of the frontend and backend.

## Frontend (Vercel)
- **Status**: Active Auto-Deploy.
- **Root**: Deployed from the `frontend/` directory.
- **Runtime**: Next.js App Router; `/api/` handlers run as Node.js serverless functions.
- **Environment**: Configured via Vercel Dashboard. Depends on `NEXT_PUBLIC_API_URL` pointing to the Render backend URL.

## Backend (Render)
- **Status**: Active Auto-Deploy.
- **Root**: Deployed from the `backend/` directory.
- **Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (managed by `render.yaml`).
- **Keepalive**: The frontend pings `/api/keepalive` to prevent the free tier Render instance from spinning down. First-heavy-query latency may still occur.

## Scheduled Jobs (GitHub Actions)
- **Why**: Vercel serverless functions lack native Python runtime support, which is necessary for the EOD and MF syncing scripts.
- **Workflows**:
  - `fetch_stocks.yml`: Runs `scripts/run_fetch.py` daily at 16:30 IST (11:00 UTC).
  - `mf-sync.yml`: Triggers mutual fund metadata and NAV updates.
- **Secrets**: Handled via GitHub Repository Secrets.
