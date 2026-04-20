"""
Standalone AMFI Mutual Fund NAV Sync script for GitHub Actions.
Downloads the full NAVAll.txt from AMFI and upserts to Supabase.
No serverless timeout limitations.
"""
import os
import logging
import requests
from datetime import datetime
from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
BATCH_SIZE = 500

def parse_amfi_data(text: str) -> list:
    lines = text.split('\n')
    updates = []
    current_category = 'Unknown Category'
    current_fund_house = 'Unknown Fund House'

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        if ';' not in trimmed:
            current_category = trimmed
            if 'mutual fund' in trimmed.lower():
                current_fund_house = trimmed
            continue

        parts = trimmed.split(';')
        if len(parts) < 6:
            continue

        try:
            scheme_code = int(parts[0])
        except ValueError:
            continue

        scheme_name = parts[3]
        try:
            nav = float(parts[4])
        except ValueError:
            continue

        date_str = parts[5].strip()
        nav_date = None
        try:
            nav_date = datetime.strptime(date_str, "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            nav_date = datetime.now().strftime("%Y-%m-%d")

        category_parts = current_category.split('(')
        category = category_parts[0].strip() if category_parts else 'General'
        sub_category = category_parts[1].replace(')', '').strip() if len(category_parts) > 1 else 'General'

        updates.append({
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "fund_house": current_fund_house,
            "category": category,
            "sub_category": sub_category,
            "nav": nav,
            "nav_date": nav_date,
            "updated_at": datetime.utcnow().isoformat()
        })

    return updates

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    logger.info(f"Fetching AMFI NAV data from {AMFI_URL}...")
    response = requests.get(AMFI_URL, timeout=60)
    response.raise_for_status()
    logger.info(f"Downloaded {len(response.text)} bytes.")

    updates = parse_amfi_data(response.text)
    logger.info(f"Parsed {len(updates)} fund schemes.")

    success = 0
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i + BATCH_SIZE]
        try:
            supabase.table('mutual_funds').upsert(batch, on_conflict='scheme_code').execute()
            success += len(batch)
            logger.info(f"Upserted batch {i//BATCH_SIZE + 1}: {success}/{len(updates)} schemes done.")
        except Exception as e:
            logger.error(f"Batch upsert failed at offset {i}: {e}")

    logger.info(f"Finished. {success}/{len(updates)} schemes synced to Supabase.")

if __name__ == "__main__":
    main()
