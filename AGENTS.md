# MarketMind Agents Guide

## Project Summary
MarketMind is an AI-orchestrated financial research platform for the Indian stock and mutual fund markets, utilizing a Next.js frontend, a FastAPI backend, and Supabase for persistent storage.

## Core Rule
**Docs are the source of truth, not chat history.** 
Never rely on previous chat context. Always refer to the `docs/` directory.

## Required Reading
Before starting any task, you MUST read:
- `docs/CURRENT_STATE.md` (Always)
- `docs/10_TASKS.md` (Always)
- `docs/09_DECISIONS.md` (Always)
- `docs/02_ARCHITECTURE.md` (When architecture/backend is involved)
- `docs/05_FRONTEND_GUIDE.md` (When frontend/UI is involved)

## Agent Responsibilities
- **Codex**: Architecture, backend logic, refactoring, tests, and feature implementation.
- **Antigravity**: UI/UX, layouts, browser testing, visual aesthetics, responsiveness, and frontend user flows.
- **Gemini CLI**: Debugging, build/test failures, repo-wide reviews, and context compression.

## Editing Rules
- Keep changes minimal and incremental.
- Do NOT modify unrelated files.
- Do NOT commit unless explicitly asked by the user.
- **Never expose secrets** in code or responses.
- **Never commit `.env` files**.

## Documentation Rules
- Update `docs/CURRENT_STATE.md` after meaningful changes.
- Update `docs/10_TASKS.md` after task progress or completion.
- Update `docs/09_DECISIONS.md` after major design or architectural decisions.
- Update API (`docs/03_API_CONTRACTS.md`) and database (`docs/04_DATABASE_SCHEMA.md`) docs if those areas change.

## Safety Rules
- ALWAYS ask the user before running destructive commands such as:
  - `rm -rf`
  - `git reset --hard`
  - `git clean -fd`
  - `git push --force`
  - Dropping databases or deleting migrations.