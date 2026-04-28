# Decisions Log

## Decision Template
**Date:** YYYY-MM-DD
**Decision:** [What was decided]
**Context:** [Why it was decided]
**Consequences:** [Impact on the system or workflow]

---

## Confirmed Decisions

**Date:** 2026-04-28
**Decision:** Use docs as shared agent memory.
**Context:** Context windows and chat memory often lose crucial details across sessions or when switching between agents (Codex, Antigravity, Gemini CLI).
**Consequences:** All agents MUST read `docs/` before starting and update `docs/` before finishing tasks. Chat history is not trusted as truth.

**Date:** 2026-04-28
**Decision:** Use one active editing agent at a time.
**Context:** Prevents race conditions, git conflicts, and divergent logic when multiple AI agents attempt to solve the same problem concurrently.
**Consequences:** Agents must wait for their turn and confirm they are the active editing agent.

**Date:** (Pre-existing)
**Decision:** Supabase Local History over Live API.
**Context:** YFinance frequently rate-limits and times out on Render free tiers.
**Consequences:** Local Supabase snapshots (`stock_history`, `mutual_fund_history`) are preferred for NIFTY history and baseline quant metrics over hitting Yahoo Finance directly.

**Date:** (Pre-existing)
**Decision:** Next.js API Proxy Pattern.
**Context:** Calling FastAPI directly from the browser exposes backend URLs and can trigger CORS issues.
**Consequences:** The frontend browser never communicates with FastAPI directly. All requests proxy through `frontend/app/api/`.

**Date:** (Pre-existing)
**Decision:** GitHub Actions for Scheduled Tasks.
**Context:** Vercel serverless environments do not support native Python runtimes required for our fetching scripts.
**Consequences:** Data fetching (`run_fetch.py`, `sync_mf.py`) is triggered via GitHub Actions cron, not Vercel cron.
