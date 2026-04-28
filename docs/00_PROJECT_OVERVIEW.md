# Project Overview

MarketMind is an **AI-orchestrated financial research platform** for the Indian stock and mutual fund markets.

## Goal
To synthesize quantitative metrics, news sentiment, and historical trends into retail-investor-friendly insights using a multi-agent pipeline.

## System Architecture
- **Frontend**: Next.js 15 (App Router) deployed on Vercel.
- **Backend**: Python FastAPI service deployed on Render.
- **Data Engine**: Supabase (PostgreSQL + Realtime).
- **Automation**: GitHub Actions handling scheduled EOD data fetching and syncing.
