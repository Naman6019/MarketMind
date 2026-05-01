# API Contracts

## Frontend Proxy Routes (`frontend/app/api/`)
- `POST /api/chat`: Proxies user chat prompts to the backend.
- `GET /api/keepalive`: Calls the backend `/health` endpoint to keep the Render instance from sleeping.
- `GET /api/mf/[schemeCode]`: Fetches Supabase-backed mutual fund details and NAV history.
- `GET /api/search`: Supabase-backed search endpoint for stocks/funds.
- `GET /api/cron/sync-mf`: Protected route to trigger MF synchronization.
- `GET /api/quant/stocks/compare?symbols=RELIANCE,TCS`: Proxies source-neutral stock comparison data.
- `GET /api/quant/stocks/[symbol]/profile`: Proxies stock metadata, latest price, ratios, and source summary.
- `GET /api/quant/stocks/[symbol]/financials`: Proxies recent quarterly and annual statements.
- `GET /api/quant/stocks/[symbol]/price-history`: Proxies source-neutral daily price history.

## Backend FastAPI Routes (`backend/app/main.py`)
- `POST /api/chat`: Accepts user prompts, routes to internal AI agents, fetches data, and returns synthesized markdown + structured `quant_data`.
  - Comparison responses include every requested entity in the markdown table. Entities that cannot be resolved are marked as `Data Unavailable`.
  - `system_action: { type: "COMPARE", ids: [...] }` is returned only when at least two comparison entities resolve to valid canvas IDs.
  - News sections use explicit fallback text when configured news sources return no recent items.
- `GET /api/quant/stocks/compare`: Returns source-neutral stock comparison data:
  - `asset_type`, `symbols`, `available`, `unavailable`, `metrics`, `price_history`, `fundamentals`, `ratios`, `data_quality`, `source_summary`, and compatibility `comparison`.
- `GET /api/quant/stocks/{symbol}/profile`: Returns metadata, latest price, ratios, shareholding, and source summary.
- `GET /api/quant/stocks/{symbol}/financials`: Returns recent quarterly and annual `financial_statements`.
- `GET /api/quant/stocks/{symbol}/price-history`: Returns daily price history from `stock_prices_daily` with safe fallbacks.
- `GET /health`: Keepalive check.
- **TODO**: Add rate limiting for `/api/chat` and trigger routes.
