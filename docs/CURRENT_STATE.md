# Current State

MarketMind is an actively developed repository split between a Next.js frontend and a FastAPI backend.
- The repository was recently reorganized to standardise documentation inside the `docs/` and `prompts/` folders.
- Agents (Codex, Gemini, Antigravity) are supported with dedicated prompt guidelines.
- Continuous deployment is functioning via Vercel (frontend) and Render (backend).
- EOD scripts successfully run via GitHub Actions.
- Focus is currently on polishing the comparison canvas, refining stock comparisons, and ensuring YFinance rate-limits are mitigated using Supabase caching.
