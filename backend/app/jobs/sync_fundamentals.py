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
from app.models.stock_models import ProviderRun, DataQualityIssue, FinancialStatement, ShareholdingPattern

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
        try:
            res = repo.supabase.table("stocks").select("symbol").eq("is_active", True).execute()
            symbols = [row["symbol"] for row in res.data] if res.data else []
        except Exception as e:
            logger.error(f"Failed to fetch active stocks: {e}")
            symbols = []

    limit = int(os.environ.get("STOCK_INFO_ENRICH_LIMIT", "0"))
    if limit > 0:
        symbols = symbols[:limit]

    run = ProviderRun(
        provider=provider.name,
        job_name="sync_fundamentals",
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
            statements = []
            if hasattr(provider, 'get_quarterly_results'):
                qr = provider.get_quarterly_results(symbol)
                for q in qr:
                    statements.append(FinancialStatement(**q))
            if hasattr(provider, 'get_annual_results'):
                ar = provider.get_annual_results(symbol)
                for a in ar:
                    statements.append(FinancialStatement(**a))
            if hasattr(provider, 'get_balance_sheet'):
                bs = provider.get_balance_sheet(symbol)
                for b in bs:
                    statements.append(FinancialStatement(**b))
            if hasattr(provider, 'get_cash_flow'):
                cf = provider.get_cash_flow(symbol)
                for c in cf:
                    statements.append(FinancialStatement(**c))
                    
            if statements:
                repo.upsert_financial_statements(statements)
                
            if hasattr(provider, 'get_shareholding'):
                sh = provider.get_shareholding(symbol)
                sh_patterns = [ShareholdingPattern(**s) for s in sh]
                if sh_patterns:
                    repo.upsert_shareholding_pattern(sh_patterns)
                
            run.symbols_succeeded += 1
        except Exception as e:
            run.symbols_failed += 1
            logger.error(f"Failed to sync fundamentals for {symbol}: {e}")
            repo.log_data_quality_issue(DataQualityIssue(
                symbol=symbol,
                table_name="financial_statements",
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
