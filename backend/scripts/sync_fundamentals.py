"""
Sync fundamentals from the configured provider.

Manual provider is a no-op because local rows are already in Supabase. Paid
providers are intentionally disabled until their API keys and mapping code exist.
"""
# DEPRECATED: Replaced by provider adapter layer. Do not use in new code.
import logging
import os
import sys
from datetime import datetime, timezone

from supabase import create_client

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.providers import get_fundamentals_provider
from app.stock_universe import load_stock_universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(url, key)
    provider = get_fundamentals_provider()
    limit = int(os.environ.get("STOCK_INFO_ENRICH_LIMIT", "120"))
    symbols = list(load_stock_universe().keys())[:limit]
    run = supabase.table("data_provider_runs").insert({
        "provider": provider.name,
        "job_name": "sync_fundamentals",
        "status": "running",
        "symbols_attempted": len(symbols),
        "metadata": {"mode": "noop" if provider.name in {"manual", "nse", "yfinance"} else "adapter"},
    }).execute()
    run_id = (run.data or [{}])[0].get("id")

    message = "No external fundamentals provider configured; leaving missing values null."
    logger.warning(message)
    if run_id:
        supabase.table("data_provider_runs").update({
            "status": "skipped",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "symbols_succeeded": 0,
            "symbols_failed": 0,
            "error_summary": message,
        }).eq("id", run_id).execute()


if __name__ == "__main__":
    main()
