from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _normalize_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    return symbol.strip().upper()


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _validate_date(value: date, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a valid date object")


def _validate_datetime(value: datetime | None, field_name: str) -> None:
    if value is not None and not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a valid datetime object or None")


def _coerce_decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{field_name} must be Decimal-compatible or None") from exc


def _coerce_decimals(instance: object, fields: tuple[str, ...]) -> None:
    for field_name in fields:
        setattr(instance, field_name, _coerce_decimal(getattr(instance, field_name), field_name))


@dataclass
class StockProfile:
    symbol: str
    exchange: str
    company_name: str | None
    isin: str | None
    sector: str | None
    industry: str | None
    listing_status: str | None
    is_active: bool
    source: str

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        self.exchange = _require_text(self.exchange, "exchange").upper()
        self.source = _require_text(self.source, "source")


@dataclass
class StockPriceDaily:
    symbol: str
    date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    adj_close: Decimal | None
    volume: int | None
    value_traded: Decimal | None
    delivery_qty: int | None
    delivery_percent: Decimal | None
    source: str

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        _validate_date(self.date, "date")
        self.source = _require_text(self.source, "source")
        _coerce_decimals(self, ("open", "high", "low", "close", "adj_close", "value_traded", "delivery_percent"))


@dataclass
class FinancialStatement:
    symbol: str
    period_type: str
    period_end_date: date
    fiscal_year: int | None
    fiscal_quarter: int | None
    revenue: Decimal | None
    operating_profit: Decimal | None
    ebitda: Decimal | None
    ebit: Decimal | None
    profit_before_tax: Decimal | None
    net_profit: Decimal | None
    eps: Decimal | None
    total_assets: Decimal | None
    total_liabilities: Decimal | None
    total_equity: Decimal | None
    total_debt: Decimal | None
    cash_and_equivalents: Decimal | None
    cash_from_operations: Decimal | None
    cash_from_investing: Decimal | None
    cash_from_financing: Decimal | None
    source: str

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        self.period_type = _require_text(self.period_type, "period_type").lower()
        if self.period_type not in {"quarterly", "annual"}:
            raise ValueError("period_type must be 'quarterly' or 'annual'")
        _validate_date(self.period_end_date, "period_end_date")
        self.source = _require_text(self.source, "source")
        _coerce_decimals(
            self,
            (
                "revenue",
                "operating_profit",
                "ebitda",
                "ebit",
                "profit_before_tax",
                "net_profit",
                "eps",
                "total_assets",
                "total_liabilities",
                "total_equity",
                "total_debt",
                "cash_and_equivalents",
                "cash_from_operations",
                "cash_from_investing",
                "cash_from_financing",
            ),
        )


@dataclass
class RatioSnapshot:
    symbol: str
    snapshot_date: date
    market_cap: Decimal | None
    enterprise_value: Decimal | None
    pe: Decimal | None
    pb: Decimal | None
    ps: Decimal | None
    ev_ebitda: Decimal | None
    roe: Decimal | None
    roce: Decimal | None
    roa: Decimal | None
    debt_to_equity: Decimal | None
    current_ratio: Decimal | None
    interest_coverage: Decimal | None
    dividend_yield: Decimal | None
    sales_growth_1y: Decimal | None
    sales_growth_3y: Decimal | None
    profit_growth_1y: Decimal | None
    profit_growth_3y: Decimal | None
    eps_growth_1y: Decimal | None
    eps_growth_3y: Decimal | None
    source: str

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        _validate_date(self.snapshot_date, "snapshot_date")
        self.source = _require_text(self.source, "source")
        _coerce_decimals(
            self,
            (
                "market_cap",
                "enterprise_value",
                "pe",
                "pb",
                "ps",
                "ev_ebitda",
                "roe",
                "roce",
                "roa",
                "debt_to_equity",
                "current_ratio",
                "interest_coverage",
                "dividend_yield",
                "sales_growth_1y",
                "sales_growth_3y",
                "profit_growth_1y",
                "profit_growth_3y",
                "eps_growth_1y",
                "eps_growth_3y",
            ),
        )


@dataclass
class ShareholdingPattern:
    symbol: str
    period_end_date: date
    promoter_holding: Decimal | None
    promoter_pledge: Decimal | None
    fii_holding: Decimal | None
    dii_holding: Decimal | None
    public_holding: Decimal | None
    government_holding: Decimal | None
    source: str

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        _validate_date(self.period_end_date, "period_end_date")
        self.source = _require_text(self.source, "source")
        _coerce_decimals(
            self,
            (
                "promoter_holding",
                "promoter_pledge",
                "fii_holding",
                "dii_holding",
                "public_holding",
                "government_holding",
            ),
        )


@dataclass
class CorporateEvent:
    symbol: str
    event_date: date
    event_type: str
    title: str | None
    description: str | None
    source_url: str | None
    source: str

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        _validate_date(self.event_date, "event_date")
        self.event_type = _require_text(self.event_type, "event_type")
        self.source = _require_text(self.source, "source")


@dataclass
class ProviderRun:
    provider: str
    job_name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    symbols_attempted: int
    symbols_succeeded: int
    symbols_failed: int
    error_summary: str | None
    metadata: dict | None

    def __post_init__(self) -> None:
        self.provider = _require_text(self.provider, "provider")
        self.job_name = _require_text(self.job_name, "job_name")
        self.status = _require_text(self.status, "status")
        _validate_datetime(self.started_at, "started_at")
        _validate_datetime(self.finished_at, "finished_at")


@dataclass
class DataQualityIssue:
    symbol: str
    table_name: str | None
    field_name: str | None
    issue_type: str
    issue_message: str
    source: str | None
    metadata: dict | None

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        self.issue_type = _require_text(self.issue_type, "issue_type")
        self.issue_message = _require_text(self.issue_message, "issue_message")
        self.source = self.source.strip() if isinstance(self.source, str) and self.source.strip() else None
