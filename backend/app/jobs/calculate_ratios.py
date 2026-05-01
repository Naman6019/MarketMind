import logging
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))

from app.repositories.stock_repository import StockRepository
from app.services.ratio_engine import calculate_ratios
from app.models.stock_models import DataQualityIssue, ProviderRun

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    repo = StockRepository()
    
    try:
        res = repo.supabase.table("stocks").select("symbol").eq("is_active", True).execute()
        symbols = [row["symbol"] for row in res.data] if res.data else []
    except Exception as e:
        logger.error(f"Failed to fetch active stocks: {e}")
        symbols = []
        
    run = ProviderRun(
        provider="ratio_engine",
        job_name="calculate_ratios",
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
            statements = repo.get_financial_statements(symbol)
            prices = repo.get_price_history(symbol, limit=1)
            latest_price = prices[0].close if prices and prices[0].close is not None else None
            
            # Retrieve latest market cap if available
            market_cap = None
            if latest_price and statements:
                # Naive fallback for market cap if we have shares outstanding
                pass
                
            snapshot = calculate_ratios(symbol, statements, latest_price, market_cap)
            
            # Log data quality issues
            for field in snapshot.data_quality.get("missing_fields", []):
                repo.log_data_quality_issue(DataQualityIssue(
                    symbol=symbol,
                    table_name="ratios_snapshot",
                    issue_type="missing_data",
                    issue_message=f"Missing field for ratio calculation: {field}",
                    source="ratio_engine"
                ))
                
            repo.upsert_ratios_snapshot([snapshot])
            run.symbols_succeeded += 1
            
        except Exception as e:
            run.symbols_failed += 1
            logger.error(f"Failed to calculate ratios for {symbol}: {e}")
            repo.log_data_quality_issue(DataQualityIssue(
                symbol=symbol,
                table_name="ratios_snapshot",
                issue_type="calculation_error",
                issue_message=str(e),
                source="ratio_engine"
            ))

    run.status = "success" if run.symbols_failed == 0 else "partial"
    run.finished_at = datetime.now(timezone.utc)
    if run_id:
        repo.update_provider_run(run_id, run)
        
    print(f"Summary: Attempted: {run.symbols_attempted}, Succeeded: {run.symbols_succeeded}, Failed: {run.symbols_failed}")

if __name__ == "__main__":
    main()
