import logging
import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone

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
    parser.add_argument("--date", type=str, help="Trade date in YYYY-MM-DD format")
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

    limit = int(os.environ.get("STOCK_PRICE_HISTORY_LIMIT", "0"))
    if limit > 0:
        symbols = symbols[:limit]

    symbol_set = set(symbols)

    run = ProviderRun(
        provider=provider.name,
        job_name="sync_latest_prices",
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

    if hasattr(provider, "get_eod_prices_for_date"):
        sync_date = date.fromisoformat(args.date) if args.date else _latest_candidate_trade_date()
        history_dicts = []
        for candidate in _candidate_trade_dates(sync_date):
            history_dicts = provider.get_eod_prices_for_date(candidate)
            if history_dicts:
                sync_date = candidate
                break

        rows = [row for row in history_dicts if row.get("symbol") in symbol_set] if symbol_set else history_dicts
        if not symbol_set:
            run.symbols_attempted = len({row.get("symbol") for row in rows if row.get("symbol")})
        prices = [_to_stock_price(row, provider.name) for row in rows]
        repo.upsert_stock_prices_daily(prices)

        run.symbols_succeeded = len({price.symbol for price in prices})
        run.symbols_failed = max(run.symbols_attempted - run.symbols_succeeded, 0)
        run.status = "success" if prices and run.symbols_failed == 0 else "partial"
        run.finished_at = datetime.now(timezone.utc)
        run.metadata = {"trade_date": sync_date.isoformat(), "rows_upserted": len(prices)}
        if run_id:
            repo.update_provider_run(run_id, run)
        print(f"Summary: Date: {sync_date}, Attempted: {run.symbols_attempted}, Succeeded: {run.symbols_succeeded}, Failed: {run.symbols_failed}, Rows: {len(prices)}")
        return

    for symbol in symbols:
        try:
            if hasattr(provider, 'get_eod_prices'):
                history_dicts = provider.get_eod_prices(symbol)
                if not history_dicts:
                    raise ValueError("No price history returned by provider")

                prices = []
                for h in history_dicts:
                    prices.append(_to_stock_price(h, provider.name))
                repo.upsert_stock_prices_daily(prices)
                run.symbols_succeeded += 1
            else:
                logger.warning(f"Provider {provider.name} does not implement get_eod_prices(). Returning empty stub.")
                raise ValueError("Provider does not implement get_eod_prices")
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


def _latest_candidate_trade_date() -> date:
    today = datetime.now().date()
    return today if today.weekday() < 5 else today - timedelta(days=today.weekday() - 4)


def _candidate_trade_dates(start_date: date, lookback_days: int = 5):
    current = start_date
    checked = 0
    while checked < lookback_days:
        if current.weekday() < 5:
            yield current
            checked += 1
        current -= timedelta(days=1)


def _to_stock_price(row: dict, default_source: str) -> StockPriceDaily:
    return StockPriceDaily(
        symbol=row["symbol"],
        date=datetime.fromisoformat(row["date"]).date() if isinstance(row["date"], str) else row["date"],
        open=row.get("open"),
        high=row.get("high"),
        low=row.get("low"),
        close=row.get("close"),
        adj_close=row.get("adj_close"),
        volume=row.get("volume"),
        value_traded=row.get("value_traded"),
        delivery_qty=row.get("delivery_qty"),
        delivery_percent=row.get("delivery_percent"),
        source=row.get("source") or default_source
    )


if __name__ == "__main__":
    main()
