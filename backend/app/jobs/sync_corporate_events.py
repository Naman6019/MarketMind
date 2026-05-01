import logging
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
from app.models.stock_models import ProviderRun, DataQualityIssue, CorporateEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    provider = get_fundamentals_provider()
    if not provider.is_available():
        logger.warning(f"Provider {provider.name} is not available. Exiting.")
        return

    repo = StockRepository()
    
    try:
        res = (
            repo.supabase.table("stocks")
            .select("symbol")
            .eq("is_active", True)
            .eq("exchange", "NSE")
            .execute()
        )
        symbols = [row["symbol"] for row in res.data] if res.data else []
    except Exception as e:
        logger.error(f"Failed to fetch active stocks: {e}")
        symbols = []

    run = ProviderRun(
        provider=provider.name,
        job_name="sync_corporate_events",
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
            if hasattr(provider, 'get_corporate_actions'):
                events_dicts = provider.get_corporate_actions(symbol)
                events = [CorporateEvent(**e) for e in events_dicts]
                if events:
                    repo.upsert_corporate_events(events)
            else:
                logger.warning(f"Provider {provider.name} does not implement get_corporate_actions(). Returning empty stub.")
                
            run.symbols_succeeded += 1
        except Exception as e:
            run.symbols_failed += 1
            logger.error(f"Failed to sync corporate events for {symbol}: {e}")
            repo.log_data_quality_issue(DataQualityIssue(
                symbol=symbol,
                table_name="corporate_events",
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
