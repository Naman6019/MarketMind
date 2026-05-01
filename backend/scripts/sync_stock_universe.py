"""
# DEPRECATED: Replaced by provider adapter layer. Do not use in new code.
Sync NSE stock universe metadata into the source-neutral stocks table.
"""
import logging
import os
import sys
from datetime import datetime, timezone

from supabase import create_client

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.stock_universe import load_stock_universe
from scripts.run_fetch import build_stock_metadata_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(url, key)
    universe = load_stock_universe()
    run_row = {
        "provider": "nse",
        "job_name": "sync_stock_universe",
        "status": "running",
        "symbols_attempted": len(universe),
    }
    run = supabase.table("data_provider_runs").insert(run_row).execute()
    run_id = (run.data or [{}])[0].get("id")

    succeeded = 0
    failed = 0
    for symbol, meta in universe.items():
        try:
            supabase.table("stocks").upsert(
                build_stock_metadata_payload(symbol, meta),
                on_conflict="symbol",
            ).execute()
            succeeded += 1
        except Exception as exc:
            failed += 1
            logger.warning("Universe upsert failed for %s: %s", symbol, exc)

    if run_id:
        supabase.table("data_provider_runs").update({
            "status": "success" if failed == 0 else "partial",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "symbols_succeeded": succeeded,
            "symbols_failed": failed,
        }).eq("id", run_id).execute()

    logger.info("Synced %s stock metadata rows; %s failed.", succeeded, failed)


if __name__ == "__main__":
    main()
