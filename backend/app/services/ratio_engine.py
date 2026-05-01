from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.models.stock_models import FinancialStatement, RatioSnapshot


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


def _dec(val: Any) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (TypeError, ValueError):
        return None


def _safe_div_dec(n: Any, d: Any) -> Decimal | None:
    n_dec = _dec(n)
    d_dec = _dec(d)
    if n_dec is None or d_dec is None or d_dec == Decimal('0'):
        return None
    return n_dec / d_dec


def calculate_ratios(
    symbol: str, 
    statements: list[FinancialStatement], 
    latest_price: Decimal | None, 
    market_cap: Decimal | None
) -> RatioSnapshot:
    annuals = sorted([s for s in statements if s.period_type == 'annual'], key=lambda x: x.period_end_date, reverse=True)
    quarters = sorted([s for s in statements if s.period_type == 'quarterly'], key=lambda x: x.period_end_date, reverse=True)

    latest_annual = annuals[0] if annuals else None
    data_quality = []

    # ROE = net_profit / total_equity (use latest annual statement)
    roe = None
    if latest_annual:
        roe = _safe_div_dec(latest_annual.net_profit, latest_annual.total_equity)
        if roe is None: data_quality.append("ROE: Missing net_profit or total_equity in latest annual.")
    else:
        data_quality.append("ROE: No annual statements available.")

    # ROCE = ebit / (total_equity + total_debt) (capital employed)
    roce = None
    if latest_annual:
        te = _dec(latest_annual.total_equity)
        td = _dec(latest_annual.total_debt)
        if te is not None and td is not None:
            roce = _safe_div_dec(latest_annual.ebit, te + td)
        if roce is None: data_quality.append("ROCE: Missing ebit, total_equity, or total_debt in latest annual.")
    else:
        data_quality.append("ROCE: No annual statements available.")

    # ROA = net_profit / total_assets
    roa = None
    if latest_annual:
        roa = _safe_div_dec(latest_annual.net_profit, latest_annual.total_assets)
        if roa is None: data_quality.append("ROA: Missing net_profit or total_assets in latest annual.")
    else:
        data_quality.append("ROA: No annual statements available.")

    # Debt to Equity = total_debt / total_equity
    debt_to_equity = None
    if latest_annual:
        debt_to_equity = _safe_div_dec(latest_annual.total_debt, latest_annual.total_equity)
        if debt_to_equity is None: data_quality.append("Debt to Equity: Missing total_debt or total_equity in latest annual.")
    else:
        data_quality.append("Debt to Equity: No annual statements available.")

    # EPS TTM = sum of last 4 quarterly eps values (return None if fewer than 4 exist)
    last_4q = quarters[:4]
    eps_ttm = None
    if len(last_4q) == 4 and all(q.eps is not None for q in last_4q):
        eps_ttm = sum((_dec(q.eps) for q in last_4q), Decimal('0'))

    # Revenue TTM = sum of last 4 quarterly revenue values
    revenue_ttm = None
    if len(last_4q) == 4 and all(q.revenue is not None for q in last_4q):
        revenue_ttm = sum((_dec(q.revenue) for q in last_4q), Decimal('0'))

    # Net Profit TTM = sum of last 4 quarterly net_profit values
    net_profit_ttm = None
    if len(last_4q) == 4 and all(q.net_profit is not None for q in last_4q):
        net_profit_ttm = sum((_dec(q.net_profit) for q in last_4q), Decimal('0'))

    # EBITDA TTM = sum of last 4 quarterly ebitda values
    ebitda_ttm = None
    if len(last_4q) == 4 and all(q.ebitda is not None for q in last_4q):
        ebitda_ttm = sum((_dec(q.ebitda) for q in last_4q), Decimal('0'))

    # PE = market_cap / net_profit_ttm (if both available); fallback: latest_price / eps_ttm
    pe = None
    if market_cap is not None and net_profit_ttm is not None:
        pe = _safe_div_dec(market_cap, net_profit_ttm)
    elif latest_price is not None and eps_ttm is not None:
        pe = _safe_div_dec(latest_price, eps_ttm)
    if pe is None: data_quality.append("PE: Missing market_cap/net_profit_ttm and latest_price/eps_ttm.")

    # PB = market_cap / total_equity (latest annual)
    pb = None
    if market_cap is not None and latest_annual:
        pb = _safe_div_dec(market_cap, latest_annual.total_equity)
    if pb is None: data_quality.append("PB: Missing market_cap or latest annual total_equity.")

    # PS = market_cap / revenue_ttm
    ps = None
    if market_cap is not None and revenue_ttm is not None:
        ps = _safe_div_dec(market_cap, revenue_ttm)
    if ps is None: data_quality.append("PS: Missing market_cap or revenue_ttm.")

    # EV/EBITDA = enterprise_value / ebitda_ttm (return None if enterprise_value not available)
    enterprise_value = None
    if market_cap is not None and latest_annual:
        td = _dec(latest_annual.total_debt)
        cash = _dec(latest_annual.cash_and_equivalents)
        if td is not None and cash is not None:
            enterprise_value = market_cap + td - cash

    ev_ebitda = None
    if enterprise_value is not None and ebitda_ttm is not None:
        ev_ebitda = _safe_div_dec(enterprise_value, ebitda_ttm)
    if ev_ebitda is None: data_quality.append("EV/EBITDA: Missing enterprise_value or ebitda_ttm.")

    def _growth(field: str, periods: int) -> Decimal | None:
        if len(annuals) <= periods:
            return None
        current = _dec(getattr(annuals[0], field, None))
        past = _dec(getattr(annuals[periods], field, None))
        if current is None or past is None or past == Decimal('0'):
            return None
        if periods == 1:
            return (current - past) / past
        else:
            try:
                # Sales growth 3Y = CAGR over 3 annual periods if 4 annual rows exist
                if float(current) < 0 or float(past) < 0:
                    # CAGR with negative numbers is complex, safe to skip or fallback
                    return None
                return Decimal(str((float(current) / float(past)) ** (1.0 / periods) - 1))
            except (ValueError, ArithmeticError):
                return None

    # Sales growth 1Y = (latest_annual_revenue - prev_annual_revenue) / prev_annual_revenue
    sales_growth_1y = _growth('revenue', 1)
    if sales_growth_1y is None: data_quality.append("Sales growth 1Y: Missing or zero revenue points.")
    sales_growth_3y = _growth('revenue', 3)
    if sales_growth_3y is None: data_quality.append("Sales growth 3Y: Missing or zero revenue points for CAGR.")

    profit_growth_1y = _growth('net_profit', 1)
    if profit_growth_1y is None: data_quality.append("Profit growth 1Y: Missing or zero net_profit points.")
    profit_growth_3y = _growth('net_profit', 3)
    if profit_growth_3y is None: data_quality.append("Profit growth 3Y: Missing or zero net_profit points for CAGR.")

    eps_growth_1y = _growth('eps', 1)
    if eps_growth_1y is None: data_quality.append("EPS growth 1Y: Missing or zero eps points.")
    eps_growth_3y = _growth('eps', 3)
    if eps_growth_3y is None: data_quality.append("EPS growth 3Y: Missing or zero eps points for CAGR.")

    snapshot = RatioSnapshot(
        symbol=symbol,
        snapshot_date=date.today(),
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        pe=pe,
        pb=pb,
        ps=ps,
        ev_ebitda=ev_ebitda,
        roe=roe,
        roce=roce,
        roa=roa,
        debt_to_equity=debt_to_equity,
        current_ratio=None,
        interest_coverage=None,
        dividend_yield=None,
        sales_growth_1y=sales_growth_1y,
        sales_growth_3y=sales_growth_3y,
        profit_growth_1y=profit_growth_1y,
        profit_growth_3y=profit_growth_3y,
        eps_growth_1y=eps_growth_1y,
        eps_growth_3y=eps_growth_3y,
        source='calculated'
    )
    # Include a data_quality list in metadata explaining each None value.
    snapshot.metadata = {"data_quality": data_quality}
    return snapshot
