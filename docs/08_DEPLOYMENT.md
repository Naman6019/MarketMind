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

| Workflow file | Schedule (UTC) | Description |
|---|---|---|
| `fetch_stocks.yml` | Daily `0 11 * * *` | Runs `scripts/run_fetch.py` for legacy EOD stock fetch |
| `mf-sync.yml` | Weekdays `30 13 * * 1-5` | AMFI NAV → NAV history → MF metadata (TER/AUM) → IndianAPI MF AUM/returns |
| `sync-stock-universe.yml` | Daily `0 1 * * *` | Syncs all NSE/BSE stock metadata via IndianAPI |
| `sync-prices-daily.yml` | Weekdays `30 10 * * 1-5` | Syncs latest EOD prices via IndianAPI |
| `sync-fundamentals-weekly.yml` | Saturdays `0 2 * * 6` | Fetches financial statements + recalculates ratios |
| `sync-corporate-events.yml` | Daily `0 3 * * *` | Fetches dividends, splits, bonuses via IndianAPI |
| `keepalive.yml` | Scheduled | Pings Render to prevent free-tier spin-down |

- **Secrets**: Handled via GitHub Repository Secrets (`SUPABASE_URL`, `SUPABASE_KEY`, `INDIAN_API_KEY`).
