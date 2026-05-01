"""
Calculate ratios_snapshot rows from source-neutral financial_statements.
"""
# DEPRECATED: Replaced by provider adapter layer. Do not use in new code.
import logging
import os
import sys
from datetime import date, datetime, timezone

from supabase import create_client

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.services.ratio_engine import calculate_ratio_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(url, key)
    symbols = [
        row["symbol"]
        for row in (supabase.table("stocks").select("symbol").eq("is_active", True).execute().data or [])
    ]
    run = supabase.table("data_provider_runs").insert({
        "provider": "marketmind",
        "job_name": "calculate_ratios",
        "status": "running",
        "symbols_attempted": len(symbols),
    }).execute()
    run_id = (run.data or [{}])[0].get("id")

    succeeded = 0
    failed = 0
    for symbol in symbols:
        try:
            rows = supabase.table("financial_statements").select("*").eq("symbol", symbol).order("period_end_date", desc=True).limit(16).execute().data or []
            annual = [row for row in rows if row.get("period_type") == "annual"]
            quarterly = [row for row in rows if row.get("period_type") == "quarterly"]
            result = calculate_ratio_snapshot(annual, quarterly)
            if not any(value is not None for value in result.ratios.values()):
                continue
            payload = {
                "symbol": symbol,
                "snapshot_date": date.today().isoformat(),
                "source": "marketmind_ratio_engine",
                **result.ratios,
            }
            supabase.table("ratios_snapshot").upsert(payload, on_conflict="symbol,snapshot_date,source").execute()
            succeeded += 1
        except Exception as exc:
            failed += 1
            logger.warning("Ratio calculation failed for %s: %s", symbol, exc)

    if run_id:
        supabase.table("data_provider_runs").update({
            "status": "success" if failed == 0 else "partial",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "symbols_succeeded": succeeded,
            "symbols_failed": failed,
        }).eq("id", run_id).execute()

    logger.info("Calculated ratios for %s symbols; %s failed.", succeeded, failed)


if __name__ == "__main__":
    main()
