"""
Sync mutual fund metadata (AUM, NAV, returns) from IndianAPI /mutual_funds endpoint
into the Supabase mutual_funds table, keyed by scheme_name fuzzy match.
"""
import logging
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.providers.indianapi_provider import IndianAPIProvider
from app.database import supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 200


def main():
    provider = IndianAPIProvider()
    if not provider.is_available():
        logger.error("INDIANAPI_KEY not set. Exiting.")
        return

    if not supabase:
        logger.error("Supabase client not initialized. Exiting.")
        return

    logger.info("Fetching mutual fund list from IndianAPI...")
    funds = provider.get_mf_list()
    if not funds:
        logger.warning("No mutual fund data returned. Exiting.")
        return

    logger.info("Fetched %d funds. Matching against Supabase mutual_funds table...", len(funds))

    # Load existing mutual_funds rows indexed by normalized scheme_name
    existing_res = supabase.table("mutual_funds").select("scheme_code,scheme_name").execute()
    existing = existing_res.data or []

    # Build a lookup: lower-stripped scheme_name → scheme_code
    name_to_code: dict[str, int] = {}
    for row in existing:
        name_to_code[row["scheme_name"].lower().strip()] = int(row["scheme_code"])

    updates: list[dict] = []
    unmatched = 0

    for fund in funds:
        raw_name = (fund.get("scheme_name") or "").strip()
        if not raw_name:
            continue

        code = name_to_code.get(raw_name.lower())
        if not code:
            unmatched += 1
            continue

        update: dict = {
            "scheme_code": code,
            "scheme_name": raw_name,
            "category": fund.get("category") or "Unknown",
            "sub_category": fund.get("sub_category") or "Unknown",
            "fund_house": "Unknown",
            "nav": fund.get("nav") or 0,
            "nav_date": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if fund.get("aum") is not None:
            update["aum"] = fund["aum"]
        if fund.get("star_rating") is not None:
            update["star_rating"] = fund["star_rating"]

        updates.append(update)

    logger.info("Matched %d funds, %d unmatched.", len(updates), unmatched)

    written = 0
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i : i + BATCH_SIZE]
        try:
            supabase.table("mutual_funds").upsert(batch, on_conflict="scheme_code").execute()
            written += len(batch)
            logger.info("Upserted batch %d/%d (%d records)", i // BATCH_SIZE + 1, -(-len(updates) // BATCH_SIZE), len(batch))
        except Exception as e:
            logger.error("Upsert failed for batch starting at %d: %s", i, e)

    logger.info("Done. Written: %d, Unmatched: %d", written, unmatched)


if __name__ == "__main__":
    main()
