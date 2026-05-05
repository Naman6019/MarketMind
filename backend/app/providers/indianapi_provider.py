from __future__ import annotations

import logging
import os
import re
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
        self.api_key = os.environ.get("INDIANAPI_KEY") or os.environ.get("INDIAN_API_KEY")
        self._stock_cache: dict[str, dict[str, Any] | None] = {}
        self._statement_cache: dict[tuple[str, str], dict[str, Any] | list[Any] | None] = {}

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def _get_stock_payload(self, symbol: str) -> dict[str, Any] | None:
        clean = symbol.strip().upper()
        if clean in self._stock_cache:
            return self._stock_cache[clean]
        try:
            res = httpx.get(
                f"{self.base_url}/stock",
                params={"name": clean},
                headers=self._get_headers(),
                timeout=15.0,
            )
            if res.status_code != 200:
                logger.warning("IndianAPI /stock failed for %s with %s", clean, res.status_code)
                self._stock_cache[clean] = None
                return None
            data = res.json()
            self._stock_cache[clean] = data if isinstance(data, dict) else None
            return self._stock_cache[clean]
        except Exception as exc:
            logger.error("IndianAPI /stock error for %s: %s", clean, exc)
            self._stock_cache[clean] = None
            return None

    def _get_statement_payload(self, symbol: str, stats: str) -> dict[str, Any] | list[Any] | None:
        clean = symbol.strip().upper()
        key = (clean, stats)
        if key in self._statement_cache:
            return self._statement_cache[key]
        try:
            res = httpx.get(
                f"{self.base_url}/statement",
                params={"stock_name": clean, "stats": stats},
                headers=self._get_headers(),
                timeout=15.0,
            )
            if res.status_code != 200:
                logger.warning("IndianAPI /statement failed for %s/%s with %s", clean, stats, res.status_code)
                self._statement_cache[key] = None
                return None
            data = res.json()
            self._statement_cache[key] = data if isinstance(data, (dict, list)) else None
            return self._statement_cache[key]
        except Exception as exc:
            logger.error("IndianAPI /statement error for %s/%s: %s", clean, stats, exc)
            self._statement_cache[key] = None
            return None

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
    #  Price History                                                       #
    # ------------------------------------------------------------------ #

    def get_eod_prices(self, symbol: str) -> list[dict]:
        try:
            res = httpx.get(
                f"{self.base_url}/historical_data",
                params={"stock_name": symbol, "period": "1yr", "filter": "price"},
                headers=self._get_headers(),
                timeout=15.0,
            )
            if res.status_code != 200:
                logger.warning("IndianAPI get_eod_prices failed for %s with %s", symbol, res.status_code)
                return []

            data = res.json()
            datasets = data.get("datasets", []) if isinstance(data, dict) else []
            price_map: dict[str, float] = {}
            volume_map: dict[str, Any] = {}

            for dataset in datasets:
                metric = str(dataset.get("metric") or "").lower()
                values = dataset.get("values") or []
                if metric == "price":
                    for row in values:
                        if isinstance(row, list) and len(row) >= 2:
                            price_map[str(row[0])] = _safe_float(row[1])
                elif metric == "volume":
                    for row in values:
                        if isinstance(row, list) and len(row) >= 2:
                            meta = row[2] if len(row) > 2 and isinstance(row[2], dict) else {}
                            volume_map[str(row[0])] = {
                                "volume": _safe_int(row[1]),
                                "delivery": _safe_float(meta.get("delivery")),
                            }

            prices = []
            for date_text, close_price in price_map.items():
                if close_price is None:
                    continue
                parsed_date = _parse_period_label(date_text)
                if not parsed_date:
                    continue
                volume_data = volume_map.get(date_text, {})
                prices.append({
                    "symbol": symbol,
                    "date": parsed_date,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": close_price,
                    "adj_close": close_price,
                    "volume": volume_data.get("volume"),
                    "value_traded": None,
                    "delivery_qty": None,
                    "delivery_percent": volume_data.get("delivery"),
                    "source": self.name,
                })
            return sorted(prices, key=lambda row: row["date"])
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
    #  Fundamentals — uses /stock, not historical endpoints                #
    # ------------------------------------------------------------------ #

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        data = self._get_stock_payload(symbol)
        if not data:
            return None
        profile = _first_dict(data.get("companyProfile"), data.get("stockDetailsReusableData"), data)
        return {
            "symbol": (data.get("tickerId") or symbol).strip().upper(),
            "exchange": "NSE",
            "company_name": data.get("companyName") or _pick(profile, "companyName", "company_name", "name"),
            "isin": _pick(profile, "isin", "ISIN"),
            "sector": _pick(profile, "sector", "mgSector"),
            "industry": data.get("industry") or _pick(profile, "industry", "mgIndustry"),
            "is_active": True,
            "source": self.name,
        }

    def get_quarterly_results(self, symbol: str) -> list[dict]:
        data = self._get_statement_payload(symbol, "quarter_results") or self._get_stock_payload(symbol)
        tables = [data] if isinstance(data, dict) and _is_metric_period_table(data) else _find_period_tables(data, ("quarter", "interim"))
        return _statement_rows(symbol, tables, "quarterly", self.name)

    def get_annual_results(self, symbol: str) -> list[dict]:
        data = self._get_statement_payload(symbol, "yoy_results") or self._get_stock_payload(symbol)
        tables = [data] if isinstance(data, dict) and _is_metric_period_table(data) else _find_period_tables(data, ("annual", "yearly", "yoy"))
        return _statement_rows(symbol, tables, "annual", self.name)

    def get_balance_sheet(self, symbol: str) -> list[dict]:
        data = self._get_statement_payload(symbol, "balancesheet")
        tables = [data] if isinstance(data, dict) and _is_metric_period_table(data) else _find_period_tables(data, ("balance",))
        return _statement_rows(symbol, tables, "annual", self.name)

    def get_cash_flow(self, symbol: str) -> list[dict]:
        data = self._get_statement_payload(symbol, "cashflow")
        tables = [data] if isinstance(data, dict) and _is_metric_period_table(data) else _find_period_tables(data, ("cash",))
        return _statement_rows(symbol, tables, "annual", self.name)

    def get_shareholding(self, symbol: str) -> list[dict]:
        data = self._get_statement_payload(symbol, "shareholding_pattern_quarterly") or self._get_stock_payload(symbol)
        if isinstance(data, dict) and _is_metric_period_table(data):
            return _shareholding_rows(symbol, data, self.name)[:4]
        rows = []
        for item in _find_named_sections(data, ("shareholding", "shareholdingpattern")):
            rows.extend(_shareholding_rows(symbol, item, self.name))
        return rows[:4]

    def get_ratios_snapshot(self, symbol: str) -> dict[str, Any] | None:
        statement_data = self._get_statement_payload(symbol, "ratios")
        stock_data = self._get_stock_payload(symbol)
        if not statement_data and not stock_data:
            return None
        ratio_tables = [statement_data] if isinstance(statement_data, dict) and _is_metric_period_table(statement_data) else _find_period_tables(statement_data, ("ratio",))
        sections = _find_named_sections(stock_data, ("keymetrics", "ratio", "valuation", "stockdetailsreusabledata"))
        if stock_data:
            sections.append(stock_data)
        ratios = {
            "symbol": symbol.strip().upper(),
            "snapshot_date": date.today(),
            "market_cap": _latest_metric_number(ratio_tables, "market cap", "marketcap", "mcap") or _find_number(sections, "market cap", "marketcap", "mcap"),
            "enterprise_value": _latest_metric_number(ratio_tables, "enterprise value", "enterprisevalue", "ev") or _find_number(sections, "enterprise value", "enterprisevalue", "ev"),
            "pe": _latest_metric_number(ratio_tables, "p/e", "pe", "pe ratio", "p/e ratio", "price to earnings") or _find_number(sections, "p/e", "pe", "pe ratio", "p/e ratio", "price to earnings"),
            "pb": _latest_metric_number(ratio_tables, "p/b", "pb", "pb ratio", "price to book") or _find_number(sections, "p/b", "pb", "pb ratio", "price to book"),
            "ps": _latest_metric_number(ratio_tables, "p/s", "ps", "price to sales") or _find_number(sections, "p/s", "ps", "price to sales"),
            "ev_ebitda": _latest_metric_number(ratio_tables, "ev/ebitda", "evebitda") or _find_number(sections, "ev/ebitda", "evebitda"),
            "roe": _latest_metric_number(ratio_tables, "roe", "return on equity") or _find_number(sections, "roe", "return on equity"),
            "roce": _latest_metric_number(ratio_tables, "roce", "return on capital employed") or _find_number(sections, "roce", "return on capital employed"),
            "roa": _latest_metric_number(ratio_tables, "roa", "return on assets") or _find_number(sections, "roa", "return on assets"),
            "debt_to_equity": _latest_metric_number(ratio_tables, "debt to equity", "debt/equity", "debttoequity") or _find_number(sections, "debt to equity", "debt/equity", "debttoequity"),
            "current_ratio": _latest_metric_number(ratio_tables, "current ratio", "currentratio") or _find_number(sections, "current ratio", "currentratio"),
            "interest_coverage": _latest_metric_number(ratio_tables, "interest coverage", "interestcoverage") or _find_number(sections, "interest coverage", "interestcoverage"),
            "dividend_yield": _latest_metric_number(ratio_tables, "dividend yield", "dividendyield") or _find_number(sections, "dividend yield", "dividendyield"),
            "sales_growth_1y": _latest_metric_number(ratio_tables, "sales growth 1y", "revenue growth 1y") or _find_number(sections, "sales growth 1y", "revenue growth 1y"),
            "sales_growth_3y": _latest_metric_number(ratio_tables, "sales growth 3y", "revenue growth 3y") or _find_number(sections, "sales growth 3y", "revenue growth 3y"),
            "profit_growth_1y": _latest_metric_number(ratio_tables, "profit growth 1y", "net profit growth 1y") or _find_number(sections, "profit growth 1y", "net profit growth 1y"),
            "profit_growth_3y": _latest_metric_number(ratio_tables, "profit growth 3y", "net profit growth 3y") or _find_number(sections, "profit growth 3y", "net profit growth 3y"),
            "eps_growth_1y": _latest_metric_number(ratio_tables, "eps growth 1y") or _find_number(sections, "eps growth 1y"),
            "eps_growth_3y": _latest_metric_number(ratio_tables, "eps growth 3y") or _find_number(sections, "eps growth 3y"),
            "source": self.name,
        }
        return ratios if any(value is not None for key, value in ratios.items() if key not in {"symbol", "snapshot_date", "source"}) else None

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


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _first_dict(*items: Any) -> dict[str, Any]:
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def _pick(row: dict[str, Any], *keys: str) -> Any:
    normalized = {_norm_key(key): value for key, value in row.items()}
    for key in keys:
        value = normalized.get(_norm_key(key))
        if value not in (None, ""):
            return value
    return None


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _find_named_sections(data: Any, names: tuple[str, ...]) -> list[Any]:
    sections = []
    targets = tuple(_norm_key(name) for name in names)
    for row in _walk(data):
        for key, value in row.items():
            normalized = _norm_key(key)
            if any(target in normalized for target in targets):
                sections.append(value)
    return sections


def _find_period_tables(data: Any, section_names: tuple[str, ...]) -> list[dict[str, Any]]:
    tables = []
    for section in _find_named_sections(data, section_names):
        for row in _walk(section):
            metric_maps = [value for value in row.values() if isinstance(value, dict) and _looks_like_period_map(value)]
            if metric_maps:
                tables.append(row)
    return tables


def _is_metric_period_table(row: dict[str, Any]) -> bool:
    return any(isinstance(value, dict) and _looks_like_period_map(value) for value in row.values())


def _looks_like_period_map(row: dict[str, Any]) -> bool:
    return any(_parse_period_label(key) for key in row.keys())


def _parse_period_label(label: Any) -> date | None:
    text = str(label).strip()
    for fmt in ("%b %Y", "%B %Y", "%Y-%m-%d", "%d %b %Y", "%d-%b-%Y"):
        try:
            parsed = datetime.strptime(text[:11], fmt)
            if fmt in ("%b %Y", "%B %Y"):
                month_end = {3: 31, 6: 30, 9: 30, 12: 31}.get(parsed.month, 28)
                return date(parsed.year, parsed.month, month_end)
            return parsed.date()
        except ValueError:
            continue
    return None


def _statement_rows(symbol: str, tables: list[dict[str, Any]], period_type: str, source: str) -> list[dict]:
    rows_by_date: dict[date, dict[str, Any]] = {}
    for table in tables:
        metrics = {_norm_key(key): value for key, value in table.items() if isinstance(value, dict)}
        field_map = {
            "revenue": ("sales", "revenue", "netsales"),
            "operating_profit": ("operatingprofit", "op"),
            "ebitda": ("ebitda",),
            "ebit": ("ebit",),
            "profit_before_tax": ("profitbeforetax", "pbt"),
            "net_profit": ("netprofit", "pat", "profitaftertax"),
            "eps": ("epsinrs", "eps"),
            "total_assets": ("totalassets", "assets"),
            "total_liabilities": ("totalliabilities", "liabilities"),
            "total_equity": ("totalequity", "equity", "networth"),
            "total_debt": ("totaldebt", "debt", "borrowings", "totalborrowings"),
            "cash_and_equivalents": ("cashandequivalents", "cash", "cashandbank"),
            "cash_from_operations": ("cashfromoperations", "cashfromoperatingactivity", "operatingcashflow"),
            "cash_from_investing": ("cashfrominvesting", "cashfrominvestingactivity", "investingcashflow"),
            "cash_from_financing": ("cashfromfinancing", "cashfromfinancingactivity", "financingcashflow"),
        }
        period_labels = set()
        for metric_values in metrics.values():
            period_labels.update(metric_values.keys())
        for label in period_labels:
            period_end = _parse_period_label(label)
            if not period_end:
                continue
            row = rows_by_date.setdefault(period_end, _empty_statement(symbol, period_type, period_end, source))
            for field, aliases in field_map.items():
                value = _metric_value(metrics, aliases, label)
                if value is not None:
                    row[field] = value
    return sorted(rows_by_date.values(), key=lambda item: item["period_end_date"], reverse=True)


def _empty_statement(symbol: str, period_type: str, period_end: date, source: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "period_type": period_type,
        "period_end_date": period_end,
        "fiscal_year": period_end.year,
        "fiscal_quarter": {6: 1, 9: 2, 12: 3, 3: 4}.get(period_end.month) if period_type == "quarterly" else None,
        "revenue": None,
        "operating_profit": None,
        "ebitda": None,
        "ebit": None,
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
        "source": source,
    }


def _metric_value(metrics: dict[str, dict[str, Any]], aliases: tuple[str, ...], label: Any) -> float | None:
    for alias in aliases:
        values = metrics.get(_norm_key(alias))
        if values and label in values:
            return _safe_float(values[label])
    return None


def _shareholding_rows(symbol: str, data: Any, source: str) -> list[dict]:
    if isinstance(data, list):
        return [_shareholding_row(symbol, item, source) for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and _looks_like_period_map(next((v for v in data.values() if isinstance(v, dict)), {})):
        rows = []
        labels = set()
        for values in data.values():
            if isinstance(values, dict):
                labels.update(values.keys())
        for label in labels:
            period_end = _parse_period_label(label)
            if not period_end:
                continue
            rows.append({
                "symbol": symbol,
                "period_end_date": period_end,
                "promoter_holding": _metric_value({_norm_key(k): v for k, v in data.items() if isinstance(v, dict)}, ("promoters", "promoterholding"), label),
                "promoter_pledge": _metric_value({_norm_key(k): v for k, v in data.items() if isinstance(v, dict)}, ("pledged", "promoterpledge"), label),
                "fii_holding": _metric_value({_norm_key(k): v for k, v in data.items() if isinstance(v, dict)}, ("fii", "foreigninstitutions"), label),
                "dii_holding": _metric_value({_norm_key(k): v for k, v in data.items() if isinstance(v, dict)}, ("dii", "domesticinstitutions"), label),
                "public_holding": _metric_value({_norm_key(k): v for k, v in data.items() if isinstance(v, dict)}, ("public",), label),
                "government_holding": _metric_value({_norm_key(k): v for k, v in data.items() if isinstance(v, dict)}, ("government",), label),
                "source": source,
            })
        return sorted(rows, key=lambda item: item["period_end_date"], reverse=True)
    if isinstance(data, dict):
        return [_shareholding_row(symbol, data, source)]
    return []


def _shareholding_row(symbol: str, row: dict[str, Any], source: str) -> dict:
    period = _pick(row, "period_end_date", "period", "quarter", "date")
    return {
        "symbol": symbol,
        "period_end_date": _parse_period_label(period) or date.today(),
        "promoter_holding": _pick_number(row, "promoter_holding", "promoter holding", "promoters"),
        "promoter_pledge": _pick_number(row, "promoter_pledge", "pledged", "promoter pledge"),
        "fii_holding": _pick_number(row, "fii_holding", "fii", "foreign institutions"),
        "dii_holding": _pick_number(row, "dii_holding", "dii", "domestic institutions"),
        "public_holding": _pick_number(row, "public_holding", "public"),
        "government_holding": _pick_number(row, "government_holding", "government"),
        "source": source,
    }


def _pick_number(row: dict[str, Any], *keys: str) -> float | None:
    return _safe_float(_pick(row, *keys))


def _find_number(sections: list[Any], *keys: str) -> float | None:
    for section in sections:
        for row in _walk(section):
            value = _pick_number(row, *keys)
            if value is not None:
                return value
    return None


def _latest_metric_number(tables: list[dict[str, Any]], *keys: str) -> float | None:
    best: tuple[date, float] | None = None
    aliases = tuple(_norm_key(key) for key in keys)
    for table in tables:
        metrics = {_norm_key(key): value for key, value in table.items() if isinstance(value, dict)}
        for alias in aliases:
            values = metrics.get(alias)
            if not values:
                continue
            for label, raw_value in values.items():
                period_end = _parse_period_label(label)
                value = _safe_float(raw_value)
                if not period_end or value is None:
                    continue
                if best is None or period_end > best[0]:
                    best = (period_end, value)
    return best[1] if best else None
