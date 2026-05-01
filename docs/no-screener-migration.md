# No-Screener Migration

MarketMind no longer requires Screener CSV exports for active stock comparison or AI chat quant data.

## Changed
- Active stock comparison reads `/api/quant/stocks/compare`.
- Chat stock comparison uses source-neutral quant data.
- Production jobs do not import CSV fundamentals.
- Legacy CSV tooling lives only in `backend/scripts/deprecated/` and is not used by routes or scheduled jobs.
- The active source-neutral migration does not read old CSV tables. Optional bridge tooling is isolated under `backend/scripts/deprecated/`.

## Data Quality
- Missing fundamentals are returned explicitly.
- The UI shows `Unavailable` instead of zero.
- The LLM is instructed through structured data to avoid inventing missing fundamentals.

## Limitation
Until a paid fundamentals provider is configured, many statement, ratio, and shareholding fields can remain unavailable.
