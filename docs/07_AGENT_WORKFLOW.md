# Agent Workflow

This document outlines the workflow for using Codex, Antigravity, and Gemini CLI cooperatively on this repository.

## Rule: Single Active Editor
**Only ONE agent may edit files at a time.**
Do not ask multiple agents to generate or refactor code simultaneously to avoid conflicts.

## Which Tool to Use
- **Codex**: Use for architecture planning, backend Python implementation, refactors, unit tests, and core feature logic.
- **Antigravity**: Use for UI implementation, styling (Tailwind), layout changes, browser testing, and UX workflows.
- **Gemini CLI**: Use for repo-wide debugging, resolving build/test failures, reviewing PRs, and context compression/summarization.

## Start-of-Session Prompt
When starting a session with any agent, the user should provide or the agent should internally execute:
> "Please read `AGENTS.md` and the required files in `docs/` (specifically `CURRENT_STATE.md` and `10_TASKS.md`). Summarize your understanding of the current state, what we are working on, and ask for confirmation before proceeding."

## End-of-Session Prompt
When a task is completed, the user should prompt:
> "We are done with this task. Please update `CURRENT_STATE.md`, `10_TASKS.md`, and any other relevant docs to reflect our changes. Summarize what changed and what the next steps are."

## Review Workflow
1. Codex or Antigravity completes feature work.
2. The agent updates documentation.
3. (Optional) Gemini CLI is invoked to review the diffs, check for regressions, and ensure no secrets were exposed before committing.
