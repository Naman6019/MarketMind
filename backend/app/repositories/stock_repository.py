from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, TypeVar

from app.database import supabase as default_supabase
from app.models.stock_models import (
    CorporateEvent,
    DataQualityIssue,
    FinancialStatement,
    ProviderRun,
    RatioSnapshot,
    ShareholdingPattern,
    StockPriceDaily,
    StockProfile,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class StockRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.supabase = client or default_supabase
        self._data_quality_issues_available = True

    def upsert_stocks(self, profiles: list[StockProfile]) -> None:
        rows = [self._with_updated_at(self._to_row(profile)) for profile in profiles]
        self._upsert("stocks", rows, "symbol")

    def upsert_stock_prices_daily(self, prices: list[StockPriceDaily]) -> None:
        rows = [self._with_updated_at(self._to_row(price)) for price in prices]
        self._upsert("stock_prices_daily", rows, "symbol,date,source")

    def upsert_financial_statements(self, statements: list[FinancialStatement]) -> None:
        rows = [self._with_updated_at(self._to_row(statement)) for statement in statements]
        self._upsert("financial_statements", rows, "symbol,period_type,period_end_date,source")

    def upsert_ratios_snapshot(self, ratios: list[RatioSnapshot]) -> None:
        rows = [self._with_updated_at(self._to_row(ratio)) for ratio in ratios]
        self._upsert("ratios_snapshot", rows, "symbol,snapshot_date,source")

    def upsert_shareholding_pattern(self, patterns: list[ShareholdingPattern]) -> None:
        rows = [self._with_updated_at(self._to_row(pattern)) for pattern in patterns]
        self._upsert("shareholding_pattern", rows, "symbol,period_end_date,source")

    def upsert_corporate_events(self, events: list[CorporateEvent]) -> None:
        rows = [self._with_updated_at(self._to_row(event)) for event in events]
        self._upsert("corporate_events", rows, "symbol,event_date,event_type,title,source")

    def create_provider_run(self, run: ProviderRun) -> str:
        if not self._has_client():
            return ""
        try:
            response = self.supabase.table("data_provider_runs").insert(self._to_row(run)).execute()
            return str((response.data or [{}])[0].get("id") or "")
        except Exception as exc:
            logger.warning("Provider run insert failed: %s", exc)
            return ""

    def update_provider_run(self, run_id: str, run: ProviderRun) -> None:
        if not self._has_client():
            return
        row = {
            "status": run.status,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "symbols_attempted": run.symbols_attempted,
            "symbols_succeeded": run.symbols_succeeded,
            "symbols_failed": run.symbols_failed,
            "error_summary": run.error_summary,
            "metadata": run.metadata or {},
        }
        try:
            self.supabase.table("data_provider_runs").update(row).eq("id", run_id).execute()
        except Exception as exc:
            logger.warning("Provider run update failed for %s: %s", run_id, exc)

    def log_data_quality_issue(self, issue: DataQualityIssue) -> None:
        if not self._has_client() or not self._data_quality_issues_available:
            return
        try:
            self.supabase.table("data_quality_issues").insert(self._to_row(issue)).execute()
        except Exception as exc:
            if _is_missing_table_error(exc, "data_quality_issues"):
                self._data_quality_issues_available = False
                logger.warning("Skipping data quality issue logging because data_quality_issues table is missing.")
                return
            logger.warning("Data quality issue insert failed for %s: %s", issue.symbol, exc)

    def get_stock_profile(self, symbol: str) -> StockProfile | None:
        clean = self._normalize_symbol(symbol)
        row = self._fetch_one("stocks", clean, order="updated_at")
        return self._map_one(row, self._profile_from_row, "stocks", clean)

    def get_price_history(self, symbol: str, start_date=None, end_date=None) -> list[StockPriceDaily]:
        clean = self._normalize_symbol(symbol)
        if not self._has_client():
            return []
        try:
            query = self.supabase.table("stock_prices_daily").select("*").eq("symbol", clean)
            if start_date:
                query = query.gte("date", self._date_filter(start_date))
            if end_date:
                query = query.lte("date", self._date_filter(end_date))
            response = query.order("date", desc=False).execute()
            return self._map_many(response.data or [], self._price_from_row, "stock_prices_daily", clean)
        except Exception as exc:
            logger.warning("Price history lookup failed for %s: %s", clean, exc)
            return []

    def get_latest_ratios(self, symbol: str) -> RatioSnapshot | None:
        clean = self._normalize_symbol(symbol)
        row = self._fetch_one("ratios_snapshot", clean, order="snapshot_date")
        return self._map_one(row, self._ratio_from_row, "ratios_snapshot", clean)

    def get_financial_statements(
        self,
        symbol: str,
        period_type: str | None = None,
        limit: int = 12,
    ) -> list[FinancialStatement]:
        clean = self._normalize_symbol(symbol)
        if not self._has_client():
            return []
        try:
            query = self.supabase.table("financial_statements").select("*").eq("symbol", clean)
            if period_type:
                query = query.eq("period_type", period_type.strip().lower())
            response = query.order("period_end_date", desc=True).limit(limit).execute()
            return self._map_many(response.data or [], self._financial_from_row, "financial_statements", clean)
        except Exception as exc:
            logger.warning("Financial statements lookup failed for %s: %s", clean, exc)
            return []

    def get_shareholding(self, symbol: str, limit: int = 4) -> list[ShareholdingPattern]:
        clean = self._normalize_symbol(symbol)
        if not self._has_client():
            return []
        try:
            response = (
                self.supabase.table("shareholding_pattern")
                .select("*")
                .eq("symbol", clean)
                .order("period_end_date", desc=True)
                .limit(limit)
                .execute()
            )
            return self._map_many(response.data or [], self._shareholding_from_row, "shareholding_pattern", clean)
        except Exception as exc:
            logger.warning("Shareholding lookup failed for %s: %s", clean, exc)
            return []

    def compare_stocks(self, symbols: list[str]) -> dict:
        comparison = {}
        for symbol in symbols:
            clean = self._normalize_symbol(symbol)
            comparison[clean] = {
                "profile": self.get_stock_profile(clean),
                "ratios": self.get_latest_ratios(clean),
                "financials": self.get_financial_statements(clean),
                "shareholding": self.get_shareholding(clean),
            }
        return comparison

    def _upsert(self, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
        if not rows or not self._has_client():
            return
        try:
            self.supabase.table(table).upsert(rows, on_conflict=on_conflict).execute()
        except Exception as exc:
            logger.warning("Batch upsert failed for %s: %s", table, exc)

    def _fetch_one(self, table: str, symbol: str, order: str | None = None) -> dict[str, Any] | None:
        if not self._has_client():
            return None
        try:
            query = self.supabase.table(table).select("*").eq("symbol", symbol)
            if order:
                query = query.order(order, desc=True)
            response = query.limit(1).execute()
            return (response.data or [None])[0]
        except Exception as exc:
            logger.warning("%s lookup failed for %s: %s", table, symbol, exc)
            return None

    def _has_client(self) -> bool:
        if self.supabase:
            return True
        logger.warning("Supabase client is not initialized.")
        return False

    @staticmethod
    def _to_row(model: Any) -> dict[str, Any]:
        row = {key: StockRepository._serialize(value) for key, value in asdict(model).items()}
        if "metadata" in row and row["metadata"] is None:
            row["metadata"] = {}
        return row

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    @staticmethod
    def _with_updated_at(row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "updated_at": datetime.now(timezone.utc).isoformat()}

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        return symbol.strip().upper()

    @staticmethod
    def _date_filter(value: Any) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _parse_date(value: Any, field_name: str) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise ValueError(f"{field_name} must be a valid date")

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        return Decimal(str(value))

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    @staticmethod
    def _profile_from_row(row: dict[str, Any]) -> StockProfile:
        return StockProfile(
            symbol=row.get("symbol"),
            exchange=row.get("exchange") or "NSE",
            company_name=row.get("company_name"),
            isin=row.get("isin"),
            sector=row.get("sector"),
            industry=row.get("industry"),
            listing_status=row.get("listing_status"),
            is_active=bool(row.get("is_active", True)),
            source=row.get("source") or "unknown",
        )

    @staticmethod
    def _price_from_row(row: dict[str, Any]) -> StockPriceDaily:
        return StockPriceDaily(
            symbol=row.get("symbol"),
            date=StockRepository._parse_date(row.get("date"), "date"),
            open=StockRepository._parse_decimal(row.get("open")),
            high=StockRepository._parse_decimal(row.get("high")),
            low=StockRepository._parse_decimal(row.get("low")),
            close=StockRepository._parse_decimal(row.get("close")),
            adj_close=StockRepository._parse_decimal(row.get("adj_close")),
            volume=StockRepository._parse_int(row.get("volume")),
            value_traded=StockRepository._parse_decimal(row.get("value_traded")),
            delivery_qty=StockRepository._parse_int(row.get("delivery_qty")),
            delivery_percent=StockRepository._parse_decimal(row.get("delivery_percent")),
            source=row.get("source") or "unknown",
        )

    @staticmethod
    def _financial_from_row(row: dict[str, Any]) -> FinancialStatement:
        return FinancialStatement(
            symbol=row.get("symbol"),
            period_type=row.get("period_type"),
            period_end_date=StockRepository._parse_date(row.get("period_end_date"), "period_end_date"),
            fiscal_year=StockRepository._parse_int(row.get("fiscal_year")),
            fiscal_quarter=StockRepository._parse_int(row.get("fiscal_quarter")),
            revenue=StockRepository._parse_decimal(row.get("revenue")),
            operating_profit=StockRepository._parse_decimal(row.get("operating_profit")),
            ebitda=StockRepository._parse_decimal(row.get("ebitda")),
            ebit=StockRepository._parse_decimal(row.get("ebit")),
            profit_before_tax=StockRepository._parse_decimal(row.get("profit_before_tax")),
            net_profit=StockRepository._parse_decimal(row.get("net_profit")),
            eps=StockRepository._parse_decimal(row.get("eps")),
            total_assets=StockRepository._parse_decimal(row.get("total_assets")),
            total_liabilities=StockRepository._parse_decimal(row.get("total_liabilities")),
            total_equity=StockRepository._parse_decimal(row.get("total_equity")),
            total_debt=StockRepository._parse_decimal(row.get("total_debt")),
            cash_and_equivalents=StockRepository._parse_decimal(row.get("cash_and_equivalents")),
            cash_from_operations=StockRepository._parse_decimal(row.get("cash_from_operations")),
            cash_from_investing=StockRepository._parse_decimal(row.get("cash_from_investing")),
            cash_from_financing=StockRepository._parse_decimal(row.get("cash_from_financing")),
            source=row.get("source") or "unknown",
        )

    @staticmethod
    def _ratio_from_row(row: dict[str, Any]) -> RatioSnapshot:
        return RatioSnapshot(
            symbol=row.get("symbol"),
            snapshot_date=StockRepository._parse_date(row.get("snapshot_date"), "snapshot_date"),
            market_cap=StockRepository._parse_decimal(row.get("market_cap")),
            enterprise_value=StockRepository._parse_decimal(row.get("enterprise_value")),
            pe=StockRepository._parse_decimal(row.get("pe")),
            pb=StockRepository._parse_decimal(row.get("pb")),
            ps=StockRepository._parse_decimal(row.get("ps")),
            ev_ebitda=StockRepository._parse_decimal(row.get("ev_ebitda")),
            roe=StockRepository._parse_decimal(row.get("roe")),
            roce=StockRepository._parse_decimal(row.get("roce")),
            roa=StockRepository._parse_decimal(row.get("roa")),
            debt_to_equity=StockRepository._parse_decimal(row.get("debt_to_equity")),
            current_ratio=StockRepository._parse_decimal(row.get("current_ratio")),
            interest_coverage=StockRepository._parse_decimal(row.get("interest_coverage")),
            dividend_yield=StockRepository._parse_decimal(row.get("dividend_yield")),
            sales_growth_1y=StockRepository._parse_decimal(row.get("sales_growth_1y")),
            sales_growth_3y=StockRepository._parse_decimal(row.get("sales_growth_3y")),
            profit_growth_1y=StockRepository._parse_decimal(row.get("profit_growth_1y")),
            profit_growth_3y=StockRepository._parse_decimal(row.get("profit_growth_3y")),
            eps_growth_1y=StockRepository._parse_decimal(row.get("eps_growth_1y")),
            eps_growth_3y=StockRepository._parse_decimal(row.get("eps_growth_3y")),
            source=row.get("source") or "unknown",
        )

    @staticmethod
    def _shareholding_from_row(row: dict[str, Any]) -> ShareholdingPattern:
        return ShareholdingPattern(
            symbol=row.get("symbol"),
            period_end_date=StockRepository._parse_date(row.get("period_end_date"), "period_end_date"),
            promoter_holding=StockRepository._parse_decimal(row.get("promoter_holding")),
            promoter_pledge=StockRepository._parse_decimal(row.get("promoter_pledge")),
            fii_holding=StockRepository._parse_decimal(row.get("fii_holding")),
            dii_holding=StockRepository._parse_decimal(row.get("dii_holding")),
            public_holding=StockRepository._parse_decimal(row.get("public_holding")),
            government_holding=StockRepository._parse_decimal(row.get("government_holding")),
            source=row.get("source") or "unknown",
        )

    @staticmethod
    def _map_one(
        row: dict[str, Any] | None,
        mapper: Callable[[dict[str, Any]], T],
        table: str,
        symbol: str,
    ) -> T | None:
        if not row:
            return None
        try:
            return mapper(row)
        except Exception as exc:
            logger.warning("Failed to map %s row for %s: %s", table, symbol, exc)
            return None

    @staticmethod
    def _map_many(
        rows: list[dict[str, Any]],
        mapper: Callable[[dict[str, Any]], T],
        table: str,
        symbol: str,
    ) -> list[T]:
        mapped = []
        for row in rows:
            item = StockRepository._map_one(row, mapper, table, symbol)
            if item is not None:
                mapped.append(item)
        return mapped


def _is_missing_table_error(exc: Exception, table_name: str) -> bool:
    text = str(exc)
    return table_name in text and ("PGRST205" in text or "Could not find the table" in text)
