# Agent Workflow

The core intelligence of MarketMind resides in `backend/app/main.py`.

## Multi-Agent Pipeline
1. **Router Agent**: Analyzes user prompt and classifies intent into:
   - Quant
   - News
   - Screener
   - Comparison
2. **Execution Agents**:
   - **Quant Agent**: Gathers real-time/cached data via YFinance/Supabase.
   - **News Parser**: Scrapes Google News via RSS and assigns sentiment using Groq.
3. **Synthesis Core**: Combines inputs into a structured markdown response, highlighting "Trend Observations."
4. **Structured Output**: For comparisons, the backend also returns `system_action` and raw `quant_data` allowing the frontend Canvas to render interactive components.
