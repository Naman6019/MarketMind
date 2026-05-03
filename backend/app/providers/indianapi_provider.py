from __future__ import annotations

import os
import logging
from datetime import date, datetime
from typing import Any

import httpx

from app.providers.base import FundamentalsProvider
from app.models.stock_models import StockProfile

logger = logging.getLogger(__name__)


class IndianAPIProvider(FundamentalsProvider):
    name = "indianapi"
    base_url = "https://analyst.indianapi.in"

    def __init__(self) -> None:
        self.api_key = os.environ.get("INDIANAPI_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    # ------------------------------------------------------------------ #
    #  Stock Universe                                                       #
    # ------------------------------------------------------------------ #

    def get_stock_universe(self) -> list[StockProfile]:
        try:
            res = httpx.get(f"{self.base_url}/static/all_stocks.json", timeout=15.0)
            if res.status_code != 200:
                logger.error("IndianAPI get_stock_universe failed with status %s", res.status_code)
                return []

            data = res.json()
            profiles = []
            for item in data:
                symbol = item.get("nse-code") or item.get("bse-code") or item.get("name")
                if not symbol or symbol == "null":
                    continue
                profiles.append(StockProfile(
                    symbol=symbol.upper(),
                    exchange="NSE" if item.get("nse-code") else "BSE",
                    company_name=item.get("name"),
                    isin=None,
                    sector=None,
                    industry=None,
                    listing_status="Active",
                    is_active=True,
                    source=self.name
                ))
            return profiles
        except Exception as exc:
            logger.error("IndianAPI get_stock_universe error: %s", exc)
            return []

    # ------------------------------------------------------------------ #
    #  Price History — uses /historical_data                               #
    # ------------------------------------------------------------------ #

    def get_eod_prices(self, symbol: str) -> list[dict]:
        """
        Fetch historical daily price data using /historical_data endpoint.
        Returns list of dicts compatible with StockPriceDaily.
        """
        try:
            res = httpx.get(
                f"{self.base_url}/historical_data",
                params={"symbol": symbol, "period": "1yr", "filter": "price"},
                headers=self._get_headers(),
                timeout=15.0,
            )
            if res.status_code != 200:
                logger.warning("IndianAPI get_eod_prices failed for %s with %s", symbol, res.status_code)
                return []

            data = res.json()
            datasets = data.get("datasets", [])

            # Extract price and volume series by metric name
            price_map: dict[str, float] = {}
            volume_map: dict[str, Any] = {}

            for ds in datasets:
                metric = ds.get("metric", "")
                values = ds.get("values", [])
                if metric == "Price":
                    for row in values:
                        if len(row) >= 2:
                            price_map[row[0]] = float(row[1])
                elif metric == "Volume":
                    for row in values:
                        if len(row) >= 2:
                            vol_val = row[1]
                            delivery = row[2].get("delivery") if len(row) > 2 and isinstance(row[2], dict) else None
                            volume_map[row[0]] = {"volume": int(vol_val) if vol_val else None, "delivery": delivery}

            results = []
            for date_str, close_price in price_map.items():
                try:
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue

                vol_data = volume_map.get(date_str, {})
                volume = vol_data.get("volume")
                delivery_pct = vol_data.get("delivery")

                results.append({
                    "symbol": symbol,
                    "date": parsed_date,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": close_price,
                    "adj_close": close_price,
                    "volume": volume,
                    "value_traded": None,
                    "delivery_qty": None,
                    "delivery_percent": delivery_pct,
                    "source": self.name,
                })

            return sorted(results, key=lambda x: x["date"])

        except Exception as exc:
            logger.error("IndianAPI get_eod_prices error for %s: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------ #
    #  Corporate Actions — uses /corporate_actions                          #
    # ------------------------------------------------------------------ #

    def get_corporate_actions(self, symbol: str) -> list[dict]:
        """
        Fetch corporate actions (dividends, splits, bonuses) via /corporate_actions.
        Returns list of dicts compatible with CorporateEvent model.
        """
        try:
            res = httpx.get(
                f"{self.base_url}/corporate_actions",
                params={"stock_name": symbol},
                headers=self._get_headers(),
                timeout=10.0,
            )
            if res.status_code != 200:
                logger.warning("IndianAPI get_corporate_actions failed for %s with %s", symbol, res.status_code)
                return []

            data = res.json()
            events = []

            # API returns a list or a dict with categorised events
            raw_events = data if isinstance(data, list) else data.get("corporate_actions", [])

            for item in raw_events:
                raw_date = item.get("ex_date") or item.get("date") or item.get("record_date")
                if not raw_date:
                    continue
                try:
                    event_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                except ValueError:
                    continue

                event_type = (
                    item.get("action_type")
                    or item.get("type")
                    or item.get("purpose")
                    or "unknown"
                ).lower()

                events.append({
                    "symbol": symbol,
                    "event_date": event_date,
                    "event_type": event_type,
                    "title": item.get("subject") or item.get("title") or event_type.title(),
                    "description": item.get("details") or item.get("description"),
                    "source_url": None,
                    "source": self.name,
                })

            return events

        except Exception as exc:
            logger.error("IndianAPI get_corporate_actions error for %s: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------ #
    #  Financial Statements — stub (use /historical_stats for expansion)   #
    # ------------------------------------------------------------------ #

    def get_quarterly_results(self, symbol: str) -> list[dict]:
        return []

    def get_annual_results(self, symbol: str) -> list[dict]:
        return []

    def get_balance_sheet(self, symbol: str) -> list[dict]:
        return []

    def get_cash_flow(self, symbol: str) -> list[dict]:
        return []

    def get_shareholding(self, symbol: str) -> list[dict]:
        return []

    # ------------------------------------------------------------------ #
    #  Mutual Fund Details — uses /mutual_funds_details                    #
    # ------------------------------------------------------------------ #

    def get_mutual_fund_details(self, fund_id: str) -> dict | None:
        """
        Fetch detailed mutual fund metadata including AUM, expense ratio, NAV.
        fund_id is the IndianAPI internal MF ID (e.g. 'MF000063').
        Returns a flat dict with keys: aum, expense_ratio, nav, category, fund_house, etc.
        """
        try:
            res = httpx.get(
                f"{self.base_url}/mutual_funds_details",
                params={"fund_id": fund_id},
                headers=self._get_headers(),
                timeout=10.0,
            )
            if res.status_code != 200:
                logger.warning("IndianAPI get_mutual_fund_details failed for %s with %s", fund_id, res.status_code)
                return None

            data = res.json()
            if not data:
                return None

            # Normalize key fields — actual field names depend on live response
            return {
                "fund_id": fund_id,
                "scheme_name": data.get("schemeName") or data.get("scheme_name"),
                "aum": _safe_float(data.get("aum") or data.get("asset_size")),
                "expense_ratio": _safe_float(data.get("expenseRatio") or data.get("expense_ratio")),
                "nav": _safe_float(data.get("nav") or data.get("latest_nav")),
                "category": data.get("category") or data.get("schemeType"),
                "fund_house": data.get("fundHouse") or data.get("amc"),
                "star_rating": data.get("starRating") or data.get("star_rating"),
                "returns_1y": _safe_float(data.get("returns_1y") or data.get("1_year_return")),
                "returns_3y": _safe_float(data.get("returns_3y") or data.get("3_year_return")),
                "returns_5y": _safe_float(data.get("returns_5y") or data.get("5_year_return")),
            }

        except Exception as exc:
            logger.error("IndianAPI get_mutual_fund_details error for %s: %s", fund_id, exc)
            return None

    def get_mf_list(self) -> list[dict]:
        """
        Fetch the full mutual funds list with AUM, NAV, returns.
        Uses /mutual_funds endpoint which returns categorized data.
        """
        try:
            res = httpx.get(
                f"{self.base_url}/mutual_funds",
                headers=self._get_headers(),
                timeout=20.0,
            )
            if res.status_code != 200:
                logger.warning("IndianAPI get_mf_list failed with %s", res.status_code)
                return []

            data = res.json()
            funds = []

            # Response is nested: { "Equity": { "Large Cap": [ {...}, ...] }, ... }
            for category, sub_categories in data.items():
                if not isinstance(sub_categories, dict):
                    continue
                for sub_cat, fund_list in sub_categories.items():
                    if not isinstance(fund_list, list):
                        continue
                    for f in fund_list:
                        funds.append({
                            "scheme_name": f.get("fund_name"),
                            "category": category,
                            "sub_category": sub_cat,
                            "nav": _safe_float(f.get("latest_nav")),
                            "aum": _safe_float(f.get("asset_size")),
                            "star_rating": f.get("star_rating"),
                            "returns_1m": _safe_float(f.get("1_month_return")),
                            "returns_3m": _safe_float(f.get("3_month_return")),
                            "returns_6m": _safe_float(f.get("6_month_return")),
                            "returns_1y": _safe_float(f.get("1_year_return")),
                            "returns_3y": _safe_float(f.get("3_year_return")),
                            "returns_5y": _safe_float(f.get("5_year_return")),
                            "source": self.name,
                        })

            return funds

        except Exception as exc:
            logger.error("IndianAPI get_mf_list error: %s", exc)
            return []


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
