# Frontend Guide

## Tech Stack
Next.js 15 (App Router), TypeScript, Tailwind CSS, Zustand, Recharts.

## Conventions
- **Indentation**: 2 spaces.
- **Proxy Pattern**: Never call FastAPI directly from the browser. Always route through `frontend/app/api/`.
- **State Management**: Keep Zustand slices focused (`store/useCanvasStore.ts`).
- **Data Logic**: Keep pure math and quant utilities in `lib/` without React side-effects.
- **Charts**: Use only Recharts. Avoid adding new chart libraries.
- **TypeScript**: Strict mode is enabled. Do not use `any` as a crutch.

## Key Directories
- `app/api/`: Next.js Serverless functions proxying to backend.
- `components/canvas/`: Canvas views for deep-dives (MF comparison).
- `components/chat/`: Chat window UI.
