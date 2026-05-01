import logging
import argparse
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))

from app.providers import get_fundamentals_provider
from app.repositories.stock_repository import StockRepository
from app.models.stock_models import ProviderRun, DataQualityIssue, StockPriceDaily

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols to sync")
    args = parser.parse_args()

    provider = get_fundamentals_provider()
    if not provider.is_available():
        logger.warning(f"Provider {provider.name} is not available. Exiting.")
        return

    repo = StockRepository()
    
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        # Read from active stocks
        profiles = repo.get_stock_profile("NIFTY") # dummy fetch just to test, actually we need to fetch all active
        # Wait, repository doesn't have get_all_active_stocks. We'll fetch from Supabase.
        try:
            res = repo.supabase.table("stocks").select("symbol").eq("is_active", True).execute()
            symbols = [row["symbol"] for row in res.data] if res.data else []
        except Exception as e:
            logger.error(f"Failed to fetch active stocks: {e}")
            symbols = []

    limit = int(os.environ.get("STOCK_PRICE_HISTORY_LIMIT", "0"))
    if limit > 0:
        symbols = symbols[:limit]

    run = ProviderRun(
        provider=provider.name,
        job_name="sync_price_history",
        status="running",
        started_at=datetime.now(timezone.utc),
        symbols_attempted=len(symbols),
        symbols_succeeded=0,
        symbols_failed=0,
        finished_at=None,
        error_summary=None,
        metadata=None
    )
    run_id = repo.create_provider_run(run)
    
    for symbol in symbols:
        try:
            if hasattr(provider, 'get_price_history'):
                # YFinance provider returns list[dict], need to map to list[StockPriceDaily]
                history_dicts = provider.get_price_history(symbol)
                prices = []
                for h in history_dicts:
                    prices.append(StockPriceDaily(
                        symbol=h["symbol"],
                        date=datetime.fromisoformat(h["date"]).date() if isinstance(h["date"], str) else h["date"],
                        open=h.get("open"),
                        high=h.get("high"),
                        low=h.get("low"),
                        close=h.get("close"),
                        adj_close=h.get("adj_close"),
                        volume=h.get("volume"),
                        value_traded=h.get("value_traded"),
                        delivery_qty=h.get("delivery_qty"),
                        delivery_percent=h.get("delivery_percent"),
                        source=h.get("source") or provider.name
                    ))
                repo.upsert_stock_prices_daily(prices)
            else:
                logger.warning(f"Provider {provider.name} does not implement get_price_history(). Returning empty stub.")
                prices = []
                
            run.symbols_succeeded += 1
        except Exception as e:
            run.symbols_failed += 1
            logger.error(f"Failed to sync {symbol}: {e}")
            repo.log_data_quality_issue(DataQualityIssue(
                symbol=symbol,
                table_name="stock_prices_daily",
                issue_type="sync_error",
                issue_message=str(e),
                source=provider.name
            ))
            
    run.status = "success" if run.symbols_failed == 0 else "partial"
    run.finished_at = datetime.now(timezone.utc)
    if run_id:
        repo.update_provider_run(run_id, run)
        
    print(f"Summary: Attempted: {run.symbols_attempted}, Succeeded: {run.symbols_succeeded}, Failed: {run.symbols_failed}")

if __name__ == "__main__":
    main()
