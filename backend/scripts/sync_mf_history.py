"""
Backfill mutual fund NAV history from public mfapi.in.

AMFI NAVAll.txt only gives the latest NAV. This script fills
mutual_fund_history with older NAV rows so 3Y/5Y metrics work.
"""
import logging
import os
import time
from datetime import datetime

from supabase import create_client

from mf_ingest_utils import create_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BATCH_SIZE = int(os.environ.get("MF_HISTORY_BATCH_SIZE", "500"))
SCHEME_LIMIT = int(os.environ.get("MF_HISTORY_SCHEME_LIMIT", "200"))
MIN_HISTORY_ROWS = int(os.environ.get("MF_HISTORY_MIN_ROWS", "500"))
REQUEST_SLEEP_SECONDS = float(os.environ.get("MF_HISTORY_SLEEP_SECONDS", "0.2"))


def fetch_history(session, scheme_code: int) -> list[dict]:
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    try:
        res = session.get(url, timeout=45)
        res.raise_for_status()
        payload = res.json()
    except Exception as e:
        logger.warning("History fetch failed for %s: %s", scheme_code, e)
        return []

    rows = []
    for item in payload.get("data", []):
        try:
            nav_date = datetime.strptime(item["date"], "%d-%m-%Y").strftime("%Y-%m-%d")
            rows.append({
                "scheme_code": int(scheme_code),
                "nav": float(item["nav"]),
                "nav_date": nav_date,
            })
        except (KeyError, TypeError, ValueError):
            continue

    return rows


def upsert_history(supabase, rows: list[dict]) -> int:
    written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        try:
            supabase.table("mutual_fund_history").upsert(
                batch,
                on_conflict="scheme_code,nav_date",
            ).execute()
            written += len(batch)
        except Exception as e:
            logger.error("History batch upsert failed: %s", e)
    return written


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    session = create_session()

    funds_res = supabase.table("mutual_funds").select("scheme_code, scheme_name").limit(SCHEME_LIMIT).execute()
    funds = funds_res.data or []
    logger.info("Checking history coverage for %s schemes.", len(funds))

    total_written = 0
    for fund in funds:
        scheme_code = int(fund["scheme_code"])
        count_res = (
            supabase.table("mutual_fund_history")
            .select("scheme_code", count="exact")
            .eq("scheme_code", scheme_code)
            .limit(1)
            .execute()
        )
        existing_count = count_res.count or 0
        if existing_count >= MIN_HISTORY_ROWS:
            continue

        logger.info("Backfilling %s (%s existing rows).", fund["scheme_name"], existing_count)
        rows = fetch_history(session, scheme_code)
        if rows:
            total_written += upsert_history(supabase, rows)
        time.sleep(REQUEST_SLEEP_SECONDS)

    logger.info("History sync finished. Upserted %s rows.", total_written)


if __name__ == "__main__":
    main()
