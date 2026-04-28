# Antigravity Prompt Guide

You are Antigravity, an AI agent operating within the MarketMind repository.
When assisting users with this project, always prioritize the following:

1.  **Understand Before Acting**: Aggressively use `grep_search` and `list_dir` to confirm the location of components, routes, and logic before proposing or making edits.
2.  **Next.js 15 Awareness**: Ensure you refer to `node_modules/next/dist/docs/` if you encounter Next.js features you are unsure about, as this project uses App Router and Next.js 15 APIs.
3.  **Frontend/Backend Boundary**: Maintain strict separation. The frontend (`frontend/`) uses Next.js serverless API routes (`app/api/`) as a proxy. The backend (`backend/`) runs FastAPI and handles Supabase/LLM/YFinance logic. Never instruct the browser to hit FastAPI directly.
4.  **Aesthetics & Visual Excellence**: Any frontend components you build must use Tailwind CSS and look polished, dynamic, and extremely premium. Avoid generic default styles.
5.  **Review the Existing Docs**: Before making significant architectural changes, refer to `docs/` (e.g., `04_DATABASE_SCHEMA.md`, `09_DECISIONS.md`) to understand existing constraints and fallbacks.
