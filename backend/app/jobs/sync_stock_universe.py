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
from app.models.stock_models import ProviderRun, DataQualityIssue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    provider = get_fundamentals_provider()
    if not provider.is_available():
        logger.warning(f"Provider {provider.name} is not available. Exiting.")
        return

    repo = StockRepository()
    
    run = ProviderRun(
        provider=provider.name,
        job_name="sync_stock_universe",
        status="running",
        started_at=datetime.now(timezone.utc),
        symbols_attempted=0,
        symbols_succeeded=0,
        symbols_failed=0,
        finished_at=None,
        error_summary=None,
        metadata=None
    )
    run_id = repo.create_provider_run(run)
    
    try:
        if hasattr(provider, 'get_stock_universe'):
            universe = provider.get_stock_universe()
        else:
            logger.warning(f"Provider {provider.name} does not implement get_stock_universe(). Returning empty stub.")
            universe = []
            
        run.symbols_attempted = len(universe)
        
        for profile in universe:
            try:
                repo.upsert_stocks([profile])
                run.symbols_succeeded += 1
            except Exception as e:
                run.symbols_failed += 1
                logger.error(f"Failed to sync {profile.symbol}: {e}")
                repo.log_data_quality_issue(DataQualityIssue(
                    symbol=profile.symbol,
                    table_name="stocks",
                    issue_type="sync_error",
                    issue_message=str(e),
                    source=provider.name
                ))
                
        run.status = "success" if run.symbols_failed == 0 else "partial"
        
    except Exception as e:
        run.status = "failed"
        run.error_summary = str(e)
        logger.error(f"Job failed: {e}")
        
    run.finished_at = datetime.now(timezone.utc)
    if run_id:
        repo.update_provider_run(run_id, run)
        
    print(f"Summary: Attempted: {run.symbols_attempted}, Succeeded: {run.symbols_succeeded}, Failed: {run.symbols_failed}")

if __name__ == "__main__":
    main()
