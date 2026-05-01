from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.database import supabase
from app.providers import get_fundamentals_provider
from app.providers.base import normalize_symbol
from app.providers.yfinance_provider import YFinanceProvider
from app.stock_universe import load_stock_universe, resolve_stock_symbol

logger = logging.getLogger(__name__)


def _rows(table: str, symbol: str, order: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    if not supabase:
        return []
    try:
        query = supabase.table(table).select("*").eq("symbol", normalize_symbol(symbol))
        if order:
            query = query.order(order, desc=True)
        return query.limit(limit).execute().data or []
    except Exception as exc:
        logger.warning("Query failed for %s/%s: %s", table, symbol, exc)
        return []


def _one(table: str, symbol: str, order: str | None = None) -> dict[str, Any] | None:
    rows = _rows(table, symbol, order=order, limit=1)
    return rows[0] if rows else None


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _empty_comparison_item(symbol: str, message: str) -> dict[str, Any]:
    return {
        "symbol": normalize_symbol(symbol),
        "name": normalize_symbol(symbol) or symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "price": None,
        "change_pct": None,
        "pe_ratio": None,
        "market_cap": None,
        "beta": None,
        "alpha_vs_nifty": None,
        "historical_period": None,
        "rsi_14d": None,
        "tv_recommendation": None,
        "fundamentals": _empty_fundamentals(),
        "ratios": {},
        "financials": {"quarterly": [], "annual": []},
        "shareholding": {},
        "price_history": [],
        "data_quality": {"missing_fields": ["symbol"], "message": message},
        "source_summary": {
            "metadata": None,
            "prices": None,
            "ratios": None,
            "shareholding": None,
        },
        "error": message,
    }


def _empty_fundamentals() -> dict[str, Any]:
    return {
        "industry": None,
        "revenue_qtr": None,
        "net_profit_qtr": None,
        "market_cap": None,
        "pe": None,
        "pb": None,
        "ev_ebitda": None,
        "roe": None,
        "roce": None,
        "debt_to_equity": None,
        "dividend_yield": None,
        "sales_growth_3y": None,
        "profit_growth_3y": None,
        "eps_growth_3y": None,
        "eps_ttm": None,
        "promoter_holding": None,
        "fii_holding": None,
        "dii_holding": None,
        "source": None,
    }


def resolve_stock_request(entity: str) -> str | None:
    clean = normalize_symbol(entity)
    resolved = resolve_stock_symbol(entity) or clean
    if not resolved:
        return None
    universe = load_stock_universe()
    if resolved in universe:
        return resolved
    if _one("stocks", resolved) or _one("stock_prices_daily", resolved, "date") or _one("stock_history", resolved, "date"):
        return resolved
    return resolve_stock_symbol(entity)


def get_stock_metadata(symbol: str) -> dict[str, Any] | None:
    clean = normalize_symbol(symbol)
    row = _one("stocks", clean)
    if row:
        return row
    universe_row = load_stock_universe().get(clean)
    if universe_row:
        return {
            "symbol": clean,
            "exchange": "NSE",
            "company_name": universe_row.get("company_name") or clean,
            "isin": universe_row.get("isin"),
            "series": "EQ",
            "sector": None,
            "industry": universe_row.get("industry"),
            "is_active": True,
            "source": "nse_universe",
        }
    legacy = _one("nifty_stocks", clean)
    if legacy:
        return {
            "symbol": clean,
            "exchange": "NSE",
            "company_name": clean,
            "industry": legacy.get("category"),
            "is_active": True,
            "source": "legacy_nifty_stocks",
        }
    return None


def get_stock_price_history(symbol: str, days: int = 365) -> list[dict[str, Any]]:
    clean = normalize_symbol(symbol)
    rows = _rows("stock_prices_daily", clean, order="date", limit=days)
    if rows:
        return list(reversed(rows))

    legacy_rows = _rows("stock_history", clean, order="date", limit=days)
    if legacy_rows:
        return [
            {
                "symbol": clean,
                "date": row.get("date"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "adj_close": row.get("close"),
                "volume": row.get("volume"),
                "source": "legacy_stock_history",
            }
            for row in reversed(legacy_rows)
        ]

    return YFinanceProvider().get_price_history(clean, period="1y")[:days]


def get_stock_financials(symbol: str) -> dict[str, Any]:
    clean = normalize_symbol(symbol)
    rows = _rows("financial_statements", clean, order="period_end_date", limit=12)
    return {
        "quarterly": [row for row in rows if row.get("period_type") == "quarterly"],
        "annual": [row for row in rows if row.get("period_type") == "annual"],
    }


def _latest_shareholding(symbol: str) -> dict[str, Any] | None:
    return _one("shareholding_pattern", symbol, "period_end_date")


def _latest_ratios(symbol: str) -> dict[str, Any] | None:
    ratios = _one("ratios_snapshot", symbol, "snapshot_date")
    if ratios:
        return ratios
    legacy = _one("nifty_stocks", symbol)
    if not legacy:
        return None
    return {
        "symbol": normalize_symbol(symbol),
        "snapshot_date": datetime.now(timezone.utc).date().isoformat(),
        "market_cap": legacy.get("market_cap"),
        "pe": legacy.get("pe_ratio"),
        "source": "legacy_nifty_stocks",
    }


def build_stock_profile(symbol: str) -> dict[str, Any]:
    clean = normalize_symbol(symbol)
    provider = get_fundamentals_provider()
    try:
        provider_profile = provider.get_company_profile(clean)
    except Exception as exc:
        logger.warning("Provider profile failed for %s via %s: %s", clean, provider.name, exc)
        provider_profile = None

    metadata = get_stock_metadata(clean) or provider_profile or {"symbol": clean}
    prices = get_stock_price_history(clean, days=2)
    try:
        provider_ratios = provider.get_ratios_snapshot(clean)
    except Exception as exc:
        logger.warning("Provider ratios failed for %s via %s: %s", clean, provider.name, exc)
        provider_ratios = None
    ratios = provider_ratios or _latest_ratios(clean) or {}

    try:
        shareholding_rows = provider.get_shareholding(clean)
    except Exception as exc:
        logger.warning("Provider shareholding failed for %s via %s: %s", clean, provider.name, exc)
        shareholding_rows = []
    shareholding = shareholding_rows[0] if shareholding_rows else _latest_shareholding(clean)
    shareholding_source = shareholding.get("source") if isinstance(shareholding, dict) else None
    return {
        "symbol": clean,
        "metadata": metadata,
        "latest_price": prices[-1] if prices else None,
        "ratios": ratios,
        "shareholding": shareholding or {},
        "source_summary": {
            "metadata": metadata.get("source") or provider.name,
            "prices": (prices[-1] or {}).get("source") if prices else None,
            "ratios": ratios.get("source") if isinstance(ratios, dict) else None,
            "shareholding": shareholding_source,
        },
    }


def _comparison_item(symbol: str) -> dict[str, Any]:
    clean = normalize_symbol(symbol)
    profile = build_stock_profile(clean)
    prices = get_stock_price_history(clean, days=365)
    financials = get_stock_financials(clean)
    quarterly = financials["quarterly"]
    latest_quarter = quarterly[0] if quarterly else {}
    ratios = profile.get("ratios") or {}
    shareholding = profile.get("shareholding") or {}
    latest = prices[-1] if prices else profile.get("latest_price") or {}
    previous = prices[-2] if len(prices) > 1 else {}
    close = _num(latest.get("close"))
    prev_close = _num(previous.get("close"))
    change_pct = ((close - prev_close) / prev_close * 100) if close is not None and prev_close not in (None, 0) else None

    fundamentals = {
        **_empty_fundamentals(),
        "industry": (profile.get("metadata") or {}).get("industry"),
        "revenue_qtr": latest_quarter.get("revenue"),
        "net_profit_qtr": latest_quarter.get("net_profit"),
        "market_cap": ratios.get("market_cap"),
        "pe": ratios.get("pe"),
        "pb": ratios.get("pb"),
        "ev_ebitda": ratios.get("ev_ebitda"),
        "roe": ratios.get("roe"),
        "roce": ratios.get("roce"),
        "debt_to_equity": ratios.get("debt_to_equity"),
        "dividend_yield": ratios.get("dividend_yield"),
        "sales_growth_3y": ratios.get("sales_growth_3y"),
        "profit_growth_3y": ratios.get("profit_growth_3y"),
        "eps_growth_3y": ratios.get("eps_growth_3y"),
        "eps_ttm": ratios.get("eps_ttm"),
        "promoter_holding": shareholding.get("promoter_holding"),
        "fii_holding": shareholding.get("fii_holding"),
        "dii_holding": shareholding.get("dii_holding"),
        "source": ratios.get("source") or shareholding.get("source"),
    }
    missing = [key for key, value in fundamentals.items() if value is None and key != "source"]
    data_quality = {
        "missing_fields": missing,
        "message": "Some fundamentals are unavailable because no fundamentals provider is configured yet." if missing else "Complete for requested fields.",
    }
    return {
        "symbol": clean,
        "name": (profile.get("metadata") or {}).get("company_name") or clean,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "price": close,
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "pe_ratio": ratios.get("pe"),
        "market_cap": ratios.get("market_cap"),
        "beta": None,
        "alpha_vs_nifty": None,
        "historical_period": "1y",
        "rsi_14d": None,
        "tv_recommendation": None,
        "fundamentals": fundamentals,
        "ratios": ratios,
        "financials": financials,
        "shareholding": shareholding,
        "price_history": prices,
        "data_quality": data_quality,
        "source_summary": profile.get("source_summary", {}),
    }


def build_stock_compare(symbols: list[str] | str) -> dict[str, Any]:
    requested = symbols.split(",") if isinstance(symbols, str) else symbols
    requested = [item.strip() for item in requested if item and item.strip()]
    comparison: dict[str, Any] = {}
    available: list[str] = []
    unavailable: list[str] = []
    metrics: dict[str, Any] = {}
    price_history: dict[str, Any] = {}
    fundamentals: dict[str, Any] = {}
    ratios: dict[str, Any] = {}
    data_quality: dict[str, Any] = {}
    source_summary: dict[str, Any] = {}

    for entity in requested:
        resolved = resolve_stock_request(entity)
        if not resolved:
            unavailable.append(entity)
            item = _empty_comparison_item(entity, "Symbol could not be resolved.")
            comparison[entity] = item
            metrics[entity] = _comparison_metrics(item)
            price_history[entity] = item["price_history"]
            fundamentals[entity] = item["financials"]
            ratios[entity] = item["ratios"]
            data_quality[entity] = item["data_quality"]
            source_summary[entity] = item["source_summary"]
            continue

        try:
            item = _comparison_item(resolved)
        except Exception as exc:
            logger.warning("Stock comparison failed for %s: %s", resolved, exc)
            unavailable.append(entity)
            item = _empty_comparison_item(resolved, "Data lookup failed for this symbol.")
            comparison[entity] = item
            metrics[entity] = _comparison_metrics(item)
            price_history[entity] = item["price_history"]
            fundamentals[entity] = item["financials"]
            ratios[entity] = item["ratios"]
            data_quality[entity] = item["data_quality"]
            source_summary[entity] = item["source_summary"]
            continue

        available.append(resolved)
        comparison[entity] = item
        metrics[resolved] = _comparison_metrics(item)
        price_history[resolved] = item["price_history"]
        fundamentals[resolved] = item["financials"]
        ratios[resolved] = item["ratios"]
        data_quality[resolved] = item["data_quality"]
        source_summary[resolved] = item["source_summary"]

    return {
        "asset_type": "stocks",
        "symbols": requested,
        "available": available,
        "unavailable": unavailable,
        "metrics": metrics,
        "price_history": price_history,
        "fundamentals": fundamentals,
        "ratios": ratios,
        "data_quality": data_quality,
        "source_summary": source_summary,
        "comparison": comparison,
    }


def _comparison_metrics(item: dict[str, Any]) -> dict[str, Any]:
    fundamentals = item.get("fundamentals") or {}
    return {
        "price": item.get("price"),
        "change_pct": item.get("change_pct"),
        "market_cap": item.get("market_cap"),
        "pe": item.get("pe_ratio"),
        "pb": fundamentals.get("pb"),
        "ev_ebitda": fundamentals.get("ev_ebitda"),
        "roe": fundamentals.get("roe"),
        "roce": fundamentals.get("roce"),
        "debt_to_equity": fundamentals.get("debt_to_equity"),
        "dividend_yield": fundamentals.get("dividend_yield"),
    }
