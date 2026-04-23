"""
Standalone AMFI Mutual Fund NAV Sync script for GitHub Actions.
Downloads the full NAVAll.txt from AMFI and upserts to Supabase.
"""
import os
import logging
import requests
import time
from datetime import datetime, timezone
from supabase import create_client
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
BATCH_SIZE = 500

def fetch_amfi_nav():
    """
    Downloads NAVAll.txt with retries and exponential backoff.
    Parses pipe-delimited lines.
    """
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    try:
        logger.info(f"Fetching AMFI NAV data from {AMFI_URL}...")
        response = session.get(AMFI_URL, timeout=30)
        response.raise_for_status()
        
        # Handle encoding issues
        text = response.content.decode('utf-8', errors='replace')
        lines = text.split('\n')
        
        updates = []
        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            
            # User specified pipe-delimited format:
            # Scheme Code|ISIN Div Payout/IDCW|ISIN Div Reinvestment|Scheme Name|Net Asset Value|Date
            cols = trimmed.split('|')
            if len(cols) != 6:
                # Fallback to semicolon if pipe fails (AMFI often uses semicolon)
                cols = trimmed.split(';')
            
            if len(cols) == 6:
                try:
                    scheme_code = int(cols[0])
                    nav = float(cols[4])
                    isin = cols[1] if cols[1] and cols[1] != '-' else cols[2]
                    scheme_name = cols[3]
                    date_str = cols[5].strip()
                    
                    try:
                        nav_date = datetime.strptime(date_str, "%d-%b-%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        nav_date = datetime.now().strftime("%Y-%m-%d")

                    updates.append({
                        "scheme_code": scheme_code,
                        "scheme_name": scheme_name,
                        "isin": isin,
                        "nav": nav,
                        "nav_date": nav_date,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })
                except (ValueError, IndexError):
                    continue

        return updates
    except Exception as e:
        logger.error(f"Failed to fetch AMFI NAV: {e}")
        return []

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    updates = fetch_amfi_nav()
    if not updates:
        logger.error("No updates found or fetch failed.")
        return

    logger.info(f"Parsed {len(updates)} fund schemes.")

    success = 0
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i + BATCH_SIZE]
        try:
            # 1. Update main table
            supabase.table('mutual_funds').upsert(batch, on_conflict='scheme_code').execute()
            
            # 2. Append to history table
            history_batch = [{
                "scheme_code": u["scheme_code"],
                "nav": u["nav"],
                "nav_date": u["nav_date"]
            } for u in batch]
            supabase.table('mutual_fund_history').upsert(history_batch, on_conflict='scheme_code,nav_date').execute()
            
            success += len(batch)
            logger.info(f"Upserted batch {i//BATCH_SIZE + 1}: {success}/{len(updates)} schemes done.")
        except Exception as e:
            logger.error(f"Batch upsert failed at offset {i}: {e}")

    logger.info(f"Finished. {success}/{len(updates)} schemes synced to Supabase.")

if __name__ == "__main__":
    main()
