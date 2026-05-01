from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    n = _num(numerator)
    d = _num(denominator)
    if n is None or d in (None, 0):
        return None
    return n / d


@dataclass
class RatioResult:
    ratios: dict[str, float | None] = field(default_factory=dict)
    data_quality: dict[str, list[str]] = field(default_factory=dict)

    def missing(self, metric: str, reason: str) -> None:
        self.data_quality.setdefault(metric, []).append(reason)


def calculate_ratio_snapshot(
    annual_statements: list[dict[str, Any]],
    quarterly_statements: list[dict[str, Any]],
    latest_price: float | None = None,
    shares_outstanding: float | None = None,
    dividend_per_share: float | None = None,
) -> RatioResult:
    result = RatioResult()
    latest_annual = annual_statements[0] if annual_statements else {}

    net_profit = _num(latest_annual.get("net_profit"))
    total_equity = _num(latest_annual.get("total_equity"))
    ebit = _num(latest_annual.get("ebit"))
    total_debt = _num(latest_annual.get("total_debt"))
    cash = _num(latest_annual.get("cash_and_equivalents"))
    ebitda = _num(latest_annual.get("ebitda"))
    total_assets = _num(latest_annual.get("total_assets"))
    total_liabilities = _num(latest_annual.get("total_liabilities"))
    capital_employed = total_assets - total_liabilities if total_assets is not None and total_liabilities is not None else None

    result.ratios["roe"] = _safe_div(net_profit, total_equity)
    result.ratios["roce"] = _safe_div(ebit, capital_employed)
    result.ratios["debt_to_equity"] = _safe_div(total_debt, total_equity)

    last_four_quarters = quarterly_statements[:4]
    eps_values = [_num(row.get("eps")) for row in last_four_quarters]
    net_profit_values = [_num(row.get("net_profit")) for row in last_four_quarters]
    ebitda_values = [_num(row.get("ebitda")) for row in last_four_quarters]
    eps_ttm = sum(v for v in eps_values if v is not None) if len([v for v in eps_values if v is not None]) == 4 else None
    net_profit_ttm = sum(v for v in net_profit_values if v is not None) if len([v for v in net_profit_values if v is not None]) == 4 else None
    ebitda_ttm = sum(v for v in ebitda_values if v is not None) if len([v for v in ebitda_values if v is not None]) == 4 else None

    result.ratios["eps_ttm"] = eps_ttm

    market_cap = latest_price * shares_outstanding if latest_price is not None and shares_outstanding else None
    result.ratios["pe"] = _safe_div(market_cap, net_profit_ttm) if market_cap is not None else _safe_div(latest_price, eps_ttm)
    result.ratios["pb"] = _safe_div(market_cap, total_equity) if market_cap is not None else None

    enterprise_value = market_cap + total_debt - cash if market_cap is not None and total_debt is not None and cash is not None else None
    result.ratios["ev_ebitda"] = _safe_div(enterprise_value, ebitda_ttm or ebitda)
    result.ratios["dividend_yield"] = _safe_div(dividend_per_share, latest_price)

    result.ratios["sales_growth_3y"] = _growth(annual_statements, "revenue", years=3)
    result.ratios["profit_growth_3y"] = _growth(annual_statements, "net_profit", years=3)
    result.ratios["eps_growth_3y"] = _growth(annual_statements, "eps", years=3)

    required = {
        "roe": ["net_profit", "total_equity"],
        "roce": ["ebit", "total_assets", "total_liabilities"],
        "debt_to_equity": ["total_debt", "total_equity"],
        "pe": ["market_cap or price", "net_profit_ttm or eps_ttm"],
        "pb": ["market_cap", "total_equity"],
        "ev_ebitda": ["enterprise_value", "ebitda_ttm"],
        "dividend_yield": ["dividend_per_share", "price"],
        "sales_growth_3y": ["four annual revenue points"],
        "profit_growth_3y": ["four annual net_profit points"],
        "eps_growth_3y": ["four annual eps points"],
    }
    for metric, fields in required.items():
        if result.ratios.get(metric) is None:
            result.missing(metric, "Missing " + ", ".join(fields))

    return result


def _growth(rows: list[dict[str, Any]], field: str, years: int) -> float | None:
    if len(rows) <= years:
        return None
    current = _num(rows[0].get(field))
    past = _num(rows[years].get(field))
    if current is None or past in (None, 0):
        return None
    return (current / past) - 1
