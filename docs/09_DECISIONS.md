# Architectural Decisions

- **Supabase Local History over Live API**: Due to frequent YFinance rate-limiting and timeouts on Render, local Supabase snapshots are preferred for NIFTY history and baseline quant metrics over hitting Yahoo Finance directly.
- **Next.js API Proxy**: To avoid CORS and leaking the backend URL or secrets, the frontend browser never communicates with FastAPI directly. All data requests go through `frontend/app/api/`.
- **Separation of LLM text and Data payloads**: LLMs can drop structured data. Therefore, `quant_data` is sent as a discrete JSON payload alongside the LLM's markdown answer for precise Canvas rendering.
- **GitHub Actions for Cron**: Vercel does not support running our Python fetching scripts natively in a cron environment, so Actions are used instead.
