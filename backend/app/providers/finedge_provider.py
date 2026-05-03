from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any

import httpx

from app.models.stock_models import StockProfile
from app.providers.base import FundamentalsProvider

logger = logging.getLogger(__name__)


class FinEdgeProvider(FundamentalsProvider):
    name = "finedge"
    base_url = "https://data.finedgeapi.com"

    def __init__(self) -> None:
        self.api_key = os.environ.get("FINEDGE_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        query = dict(params or {})
        query["token"] = self.api_key
        return httpx.get(f"{self.base_url}{path}", params=query, timeout=20.0)

    def get_stock_universe(self) -> list[StockProfile]:
        try:
            res = self._get("/api/v1/stock-symbols")
            if res.status_code != 200:
                logger.warning("FinEdge get_stock_universe failed with %s", res.status_code)
                return []

            profiles = []
            for item in _as_list(res.json()):
                symbol = item.get("nse_code") or item.get("symbol") or item.get("bse_code")
                if not symbol:
                    continue
                profiles.append(StockProfile(
                    symbol=str(symbol).upper(),
                    exchange="NSE" if item.get("nse_code") else "BSE",
                    company_name=item.get("name"),
                    isin=None,
                    sector=None,
                    industry=None,
                    listing_status="Active",
                    is_active=True,
                    source=self.name,
                ))
            return profiles
        except Exception as exc:
            logger.error("FinEdge get_stock_universe error: %s", exc)
            return []

    def get_eod_prices(self, symbol: str) -> list[dict]:
        try:
            current_year = datetime.now().year
            res = self._get(
                f"/api/v1/daily-quotes/{symbol}",
                params={"from": current_year - 1, "to": current_year},
            )
            if res.status_code != 200:
                logger.warning("FinEdge get_eod_prices failed for %s with %s", symbol, res.status_code)
                return []

            data = res.json()
            rows = data.get("price", []) if isinstance(data, dict) else []
            prices = []
            for row in rows:
                quote_date = row.get("quote_date")
                if not quote_date:
                    continue
                try:
                    parsed_date = datetime.fromisoformat(str(quote_date)[:10]).date()
                except ValueError:
                    continue

                close = _safe_float(row.get("close_price"))
                prices.append({
                    "symbol": symbol,
                    "date": parsed_date,
                    "open": _safe_float(row.get("open_price")),
                    "high": _safe_float(row.get("high_price")),
                    "low": _safe_float(row.get("low_price")),
                    "close": close,
                    "adj_close": close,
                    "volume": _safe_int(row.get("volume")),
                    "value_traded": None,
                    "delivery_qty": None,
                    "delivery_percent": None,
                    "source": self.name,
                })
            return sorted(prices, key=lambda item: item["date"])
        except Exception as exc:
            logger.error("FinEdge get_eod_prices error for %s: %s", symbol, exc)
            return []

    def get_corporate_actions(self, symbol: str) -> list[dict]:
        try:
            res = self._get("/api/v1/corporate-actions/all", params={"symbol": symbol})
            if res.status_code != 200:
                logger.warning("FinEdge get_corporate_actions failed for %s with %s", symbol, res.status_code)
                return []

            events = []
            for item in _as_list(res.json()):
                event_date = _parse_finedge_date(item.get("ex_date"))
                if not event_date:
                    continue
                event_type = str(item.get("action") or "unknown").lower()
                events.append({
                    "symbol": symbol,
                    "event_date": event_date,
                    "event_type": event_type,
                    "title": item.get("subject") or event_type.title(),
                    "description": item.get("dividend_type") or item.get("subject"),
                    "source_url": None,
                    "source": self.name,
                })
            return events
        except Exception as exc:
            logger.error("FinEdge get_corporate_actions error for %s: %s", symbol, exc)
            return []

    def get_annual_results(self, symbol: str) -> list[dict]:
        try:
            res = self._get(
                f"/api/v1/basic-financials/{symbol}",
                params={"statement_type": "s", "statement_code": "pl"},
            )
            if res.status_code != 200:
                logger.warning("FinEdge get_annual_results failed for %s with %s", symbol, res.status_code)
                return []

            data = res.json()
            rows = data.get("basic_financials", []) if isinstance(data, dict) else []
            statements = []
            for row in rows:
                year = _safe_int(row.get("year"))
                if not year:
                    continue
                statements.append({
                    "symbol": symbol,
                    "period_type": "annual",
                    "period_end_date": date(year, 3, 31),
                    "fiscal_year": year,
                    "fiscal_quarter": None,
                    "revenue": _safe_float(row.get("operatingRevenue")),
                    "operating_profit": _safe_float(row.get("operatingProfit")),
                    "ebitda": _safe_float(row.get("ebitda")),
                    "ebit": _safe_float(row.get("ebit")),
                    "profit_before_tax": None,
                    "net_profit": None,
                    "eps": None,
                    "total_assets": None,
                    "total_liabilities": None,
                    "total_equity": None,
                    "total_debt": None,
                    "cash_and_equivalents": None,
                    "cash_from_operations": None,
                    "cash_from_investing": None,
                    "cash_from_financing": None,
                    "source": self.name,
                })
            return statements
        except Exception as exc:
            logger.error("FinEdge get_annual_results error for %s: %s", symbol, exc)
            return []


def _as_list(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_finedge_date(value: Any):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(text[:11], fmt).date()
        except ValueError:
            continue
    return None
