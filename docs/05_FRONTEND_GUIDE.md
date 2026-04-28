# Frontend Guide

## Framework & Tooling
- **Framework**: Next.js 15 (App Router).
- **Language**: TypeScript (Strict mode enabled. Avoid `any`).
- **Styling**: Tailwind CSS.
- **Icons**: Lucide React.
- **State Management**: Zustand (slices located in `store/`, e.g., `useCanvasStore.ts`).
- **Charting**: Recharts. (Do NOT add new charting libraries).
- **Data Fetching**: Custom hooks in `hooks/` using SWR-like patterns.

## Directory Structure
- `app/`: Next.js pages and API proxy routes (`app/api/`).
- `components/layout/`: Dashboard and Sidebar structures.
- `components/chat/`: The AI chat interaction window.
- `components/canvas/`: Deep-dive UI components (e.g., side-by-side Head-to-Head MF comparison).
- `components/funds/`: MF-specific charts and detail panels.
- `lib/`: Pure quantitative utilities (Alpha, Beta, Sharpe, CAGR, etc.) with no React side effects.

## Conventions
- **Indentation**: 2 spaces.
- **Backend Communication**: Never call the FastAPI backend directly from the browser. Always route through `frontend/app/api/` proxies to prevent CORS and key leaks.
