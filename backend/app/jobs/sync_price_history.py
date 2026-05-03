import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.models.stock_models import DataQualityIssue, ProviderRun, StockPriceDaily
from app.providers import get_fundamentals_provider
from app.repositories.stock_repository import StockRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols to sync")
    parser.add_argument("--start-date", type=str, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", type=str, help="End date in YYYY-MM-DD format")
    parser.add_argument("--days", type=int, default=int(os.environ.get("STOCK_PRICE_BACKFILL_DAYS", "365")))
    args = parser.parse_args()

    provider = get_fundamentals_provider()
    if not provider.is_available():
        logger.warning("Provider %s is not available. Exiting.", provider.name)
        return
    if not hasattr(provider, "get_eod_prices_for_date"):
        raise RuntimeError(f"Provider {provider.name} does not support date-based EOD backfill")

    repo = StockRepository()
    symbols = _load_symbols(repo, args.symbols)
    symbol_set = set(symbols)
    start_date, end_date = _resolve_date_window(args.start_date, args.end_date, args.days)
    trade_dates = list(_trading_dates(start_date, end_date))

    run = ProviderRun(
        provider=provider.name,
        job_name="sync_price_history",
        status="running",
        started_at=datetime.now(timezone.utc),
        symbols_attempted=len(symbols) * len(trade_dates),
        symbols_succeeded=0,
        symbols_failed=0,
        finished_at=None,
        error_summary=None,
        metadata={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trade_dates": len(trade_dates),
        },
    )
    run_id = repo.create_provider_run(run)

    rows_upserted = 0
    dates_failed = 0
    for trade_date in trade_dates:
        try:
            rows = provider.get_eod_prices_for_date(trade_date)
            if not rows:
                raise ValueError("No bhavcopy rows returned")

            filtered_rows = [row for row in rows if row.get("symbol") in symbol_set] if symbol_set else rows
            prices = [_to_stock_price(row, provider.name) for row in filtered_rows]
            repo.upsert_stock_prices_daily(prices)
            rows_upserted += len(prices)
            run.symbols_succeeded += len({price.symbol for price in prices})
            logger.info("Synced %s rows for %s", len(prices), trade_date)
        except Exception as exc:
            dates_failed += 1
            run.symbols_failed += len(symbols)
            logger.error("Failed to sync bhavcopy for %s: %s", trade_date, exc)
            repo.log_data_quality_issue(DataQualityIssue(
                symbol="NSE",
                table_name="stock_prices_daily",
                issue_type="sync_error",
                issue_message=f"{trade_date}: {exc}",
                source=provider.name,
            ))

    if not symbol_set:
        run.symbols_attempted = rows_upserted + run.symbols_failed
    run.status = "success" if dates_failed == 0 else "partial"
    run.finished_at = datetime.now(timezone.utc)
    run.metadata = {
        **(run.metadata or {}),
        "dates_failed": dates_failed,
        "rows_upserted": rows_upserted,
    }
    if run_id:
        repo.update_provider_run(run_id, run)

    print(
        "Summary: "
        f"Dates: {len(trade_dates)}, Failed dates: {dates_failed}, "
        f"Rows upserted: {rows_upserted}, Symbols: {len(symbols)}"
    )


def _load_symbols(repo: StockRepository, symbols_arg: str | None) -> list[str]:
    if symbols_arg:
        return [symbol.strip().upper() for symbol in symbols_arg.split(",") if symbol.strip()]
    try:
        res = (
            repo.supabase.table("stocks")
            .select("symbol")
            .eq("is_active", True)
            .eq("exchange", "NSE")
            .execute()
        )
        return [row["symbol"] for row in res.data] if res.data else []
    except Exception as exc:
        logger.error("Failed to fetch active stocks: %s", exc)
        return []


def _resolve_date_window(start: str | None, end: str | None, days: int) -> tuple[date, date]:
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=max(days - 1, 0))
    if start_date > end_date:
        raise ValueError("start-date cannot be after end-date")
    return start_date, end_date


def _trading_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


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
        source=row.get("source") or default_source,
    )


if __name__ == "__main__":
    main()
