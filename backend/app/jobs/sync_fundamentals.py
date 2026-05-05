import logging
import argparse
import os
import sys
import time
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))

from app.providers import get_fundamentals_provider
from app.repositories.stock_repository import StockRepository
from app.models.stock_models import ProviderRun, DataQualityIssue, FinancialStatement, RatioSnapshot, ShareholdingPattern
from app.stock_universe import load_stock_universe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols to sync")
    parser.add_argument("--scope", choices=["watchlist", "full", "all-active", "symbols"], default=os.environ.get("FUNDAMENTALS_REFRESH_SCOPE", "watchlist"))
    parser.add_argument("--universe", default=os.environ.get("FUNDAMENTALS_UNIVERSE", "NIFTY500"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=float(os.environ.get("FUNDAMENTALS_SYMBOL_SLEEP_SECONDS", "0")))
    args = parser.parse_args()

    provider = get_fundamentals_provider()
    if not provider.is_available():
        logger.warning(f"Provider {provider.name} is not available. Exiting.")
        return

    repo = StockRepository()
    symbols = _select_symbols(repo, args)

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
        metadata={
            "scope": "symbols" if args.symbols else args.scope,
            "universe": args.universe,
            "limit": _effective_limit(args),
            "sleep_seconds": args.sleep_seconds,
        }
    )
    run_id = repo.create_provider_run(run)
    
    for symbol in symbols:
        try:
            statement_rows = []
            sh_patterns = []
            ratio = None
            if hasattr(provider, 'get_quarterly_results'):
                statement_rows.extend(provider.get_quarterly_results(symbol))
            if hasattr(provider, 'get_annual_results'):
                statement_rows.extend(provider.get_annual_results(symbol))
            if hasattr(provider, 'get_balance_sheet'):
                statement_rows.extend(provider.get_balance_sheet(symbol))
            if hasattr(provider, 'get_cash_flow'):
                statement_rows.extend(provider.get_cash_flow(symbol))

            statements = [FinancialStatement(**row) for row in _merge_statement_rows(statement_rows)]
                    
            if statements:
                repo.upsert_financial_statements(statements)
                
            if hasattr(provider, 'get_shareholding'):
                sh = provider.get_shareholding(symbol)
                sh_patterns = [ShareholdingPattern(**s) for s in sh]
                if sh_patterns:
                    repo.upsert_shareholding_pattern(sh_patterns)

            if hasattr(provider, 'get_ratios_snapshot'):
                ratio = provider.get_ratios_snapshot(symbol)
                if ratio:
                    repo.upsert_ratios_snapshot([RatioSnapshot(**ratio)])

            if statements or sh_patterns or ratio:
                run.symbols_succeeded += 1
            else:
                run.symbols_failed += 1
                message = "No fundamentals returned by provider."
                logger.warning("No fundamentals synced for %s via %s.", symbol, provider.name)
                repo.log_data_quality_issue(DataQualityIssue(
                    symbol=symbol,
                    table_name="financial_statements",
                    issue_type="empty_provider_response",
                    issue_message=message,
                    source=provider.name
                ))
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
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
            
    run.status = "success" if run.symbols_failed == 0 else "partial"
    run.finished_at = datetime.now(timezone.utc)
    if run_id:
        repo.update_provider_run(run_id, run)
        
    print(f"Summary: Attempted: {run.symbols_attempted}, Succeeded: {run.symbols_succeeded}, Failed: {run.symbols_failed}")

def _merge_statement_rows(rows: list[dict]) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row.get("symbol"),
            row.get("period_type"),
            row.get("period_end_date"),
            row.get("source"),
        )
        existing = merged.setdefault(key, dict(row))
        for field, value in row.items():
            if existing.get(field) is None and value is not None:
                existing[field] = value
    return list(merged.values())


def _select_symbols(repo: StockRepository, args: argparse.Namespace) -> list[str]:
    if args.symbols or args.scope == "symbols":
        symbols = _parse_symbols(args.symbols)
    elif args.scope == "full":
        symbols = list(load_stock_universe(args.universe).keys())
    elif args.scope == "all-active":
        symbols = _load_active_symbols(repo)
    else:
        symbols = _watchlist_symbols()

    limit = _effective_limit(args)
    if limit > 0:
        symbols = symbols[:limit]
    return symbols


def _parse_symbols(raw: str | None) -> list[str]:
    seen = set()
    symbols = []
    for item in (raw or "").split(","):
        symbol = item.strip().upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    return symbols


def _watchlist_symbols() -> list[str]:
    configured = (
        os.environ.get("FUNDAMENTALS_WATCHLIST_SYMBOLS")
        or os.environ.get("WATCHED_STOCK_SYMBOLS")
    )
    if configured:
        return _parse_symbols(configured)
    return list(load_stock_universe("NIFTY100").keys())


def _load_active_symbols(repo: StockRepository) -> list[str]:
    try:
        res = repo.supabase.table("stocks").select("symbol").eq("is_active", True).execute()
        return _parse_symbols(",".join(row["symbol"] for row in res.data)) if res.data else []
    except Exception as e:
        logger.error(f"Failed to fetch active stocks: {e}")
        return []


def _effective_limit(args: argparse.Namespace) -> int:
    if args.limit is not None:
        return args.limit
    legacy_limit = int(os.environ.get("STOCK_INFO_ENRICH_LIMIT", "0"))
    if legacy_limit > 0:
        return legacy_limit
    if args.symbols:
        return 0
    if args.scope == "full":
        return int(os.environ.get("FUNDAMENTALS_MONTHLY_LIMIT", "500"))
    if args.scope == "watchlist":
        return int(os.environ.get("FUNDAMENTALS_WEEKLY_LIMIT", "100"))
    return 0


if __name__ == "__main__":
    main()
