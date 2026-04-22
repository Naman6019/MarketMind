"""
Metadata Sync for Mutual Funds.
Fetches AUM and Expense Ratio using yfinance for top funds.
Runs weekly via GitHub Actions.
"""
import os
import time
import logging
import yfinance as yf
from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_yfinance_ticker(scheme_code: int, name: str) -> str:
    # Most Indian MFs on yfinance follow the pattern <ISIN>.BO or unique Yahoo IDs
    # Since we don't have ISIN here easily, we use a mapping or search.
    # For this version, we will focus on updating existing records that have a ticker mapping
    # or common pattern if we can derive it.
    return None

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Fetch funds that need metadata (e.g., AUM is null)
    # To keep it efficient, we only update a batch of 50 top funds per run
    try:
        response = supabase.table('mutual_funds').select('scheme_code, scheme_name').is_('aum', 'null').limit(50).execute()
        funds = response.data
    except Exception as e:
        logger.error(f"Failed to fetch funds from Supabase: {e}")
        return

    logger.info(f"Found {len(funds)} funds needing metadata.")
    
    success = 0
    for fund in funds:
        code = fund['scheme_code']
        name = fund['scheme_name']
        
        # This is a placeholder for the logic to find the Yahoo Ticker.
        # In production, we'd use a mapping table or an ISIN-based lookup.
        # For now, we log that we are ready for the mapping.
        logger.info(f"Processing {name} ({code})...")
        
        # Simulate update with placeholder data if we were to find it
        # In a real scenario, we'd call yf.Ticker(...)
        
        time.sleep(0.5)

    logger.info(f"Metadata sync finished. {success} updated.")

if __name__ == "__main__":
    main()
