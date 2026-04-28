import csv
import io
import logging
import os
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import requests

logger = logging.getLogger(__name__)

NSE_INDEX_BASE = "https://archives.nseindia.com/content/indices"

INDEX_URLS = {
    "NIFTY50": f"{NSE_INDEX_BASE}/ind_nifty50list.csv",
    "NIFTY100": f"{NSE_INDEX_BASE}/ind_nifty100list.csv",
    "NIFTYMIDCAP150": f"{NSE_INDEX_BASE}/ind_niftymidcap150list.csv",
    "NIFTYSMALLCAP250": f"{NSE_INDEX_BASE}/ind_niftysmallcap250list.csv",
    "NIFTY500": f"{NSE_INDEX_BASE}/ind_nifty500list.csv",
    "NIFTYTOTALMARKET": f"{NSE_INDEX_BASE}/ind_niftytotalmarket_list.csv",
    "NIFTYMICROCAP250": f"{NSE_INDEX_BASE}/ind_niftymicrocap250_list.csv",
}

FALLBACK_SYMBOLS = {
    "RELIANCE": "Large Cap",
    "TCS": "Large Cap",
    "HDFCBANK": "Large Cap",
    "ICICIBANK": "Large Cap",
    "INFY": "Large Cap",
    "ITC": "Large Cap",
    "SBIN": "Large Cap",
    "BHARTIARTL": "Large Cap",
    "TATAMOTORS": "Large Cap",
    "WAAREEENER": "Nifty 500",
}


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "MarketMind stock universe sync/1.0",
        "Accept": "text/csv,*/*",
    }


def _fetch_index_rows(index_key: str) -> list[dict[str, str]]:
    url = INDEX_URLS[index_key]
    res = requests.get(url, headers=_headers(), timeout=30)
    res.raise_for_status()
    reader = csv.DictReader(io.StringIO(res.text))
    rows = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip().upper()
        series = (row.get("Series") or "").strip().upper()
        if symbol and (not series or series == "EQ"):
            rows.append({
                "symbol": symbol,
                "company_name": (row.get("Company Name") or "").strip(),
                "industry": (row.get("Industry") or "").strip(),
                "isin": (row.get("ISIN Code") or "").strip(),
            })
    return rows


def _fallback_universe() -> dict[str, dict[str, Any]]:
    return {
        symbol: {
            "symbol": symbol,
            "company_name": symbol,
            "industry": None,
            "isin": None,
            "category": category,
            "universe": "Fallback",
        }
        for symbol, category in FALLBACK_SYMBOLS.items()
    }


@lru_cache(maxsize=8)
def load_stock_universe(universe_key: str | None = None) -> dict[str, dict[str, Any]]:
    key = (universe_key or os.environ.get("STOCK_UNIVERSE_INDEX") or "NIFTY500").upper()
    if key not in INDEX_URLS:
        key = "NIFTY500"

    try:
        universe = {
            row["symbol"]: {
                **row,
                "category": key.replace("NIFTY", "Nifty "),
                "universe": key,
            }
            for row in _fetch_index_rows(key)
        }

        category_sources = [
            ("NIFTY100", "Large Cap"),
            ("NIFTYMIDCAP150", "Mid Cap"),
            ("NIFTYSMALLCAP250", "Small Cap"),
            ("NIFTYMICROCAP250", "Micro Cap"),
        ]
        for source_key, category in category_sources:
            if source_key == "NIFTYMICROCAP250" and key != "NIFTYTOTALMARKET":
                continue
            for row in _fetch_index_rows(source_key):
                if row["symbol"] in universe:
                    universe[row["symbol"]]["category"] = category

        if universe:
            logger.info("Loaded %s stocks for %s universe.", len(universe), key)
            return universe
    except Exception as e:
        logger.warning("Falling back to small local stock universe: %s", e)

    return _fallback_universe()


def resolve_stock_symbol(name: str, universe_key: str | None = None) -> str | None:
    query = " ".join(name.upper().replace(".", " ").replace(",", " ").split())
    if not query:
        return None

    universe = load_stock_universe(universe_key)
    if query in universe:
        return query

    query_words = [word for word in query.split() if len(word) > 2]

    def score(item: dict[str, Any]) -> int:
        symbol = item["symbol"]
        company = (item.get("company_name") or "").upper()
        value = 0
        if query == symbol:
            value += 200
        if query in company:
            value += 120
        value += sum(20 for word in query_words if word in company)
        value += sum(10 for word in query_words if word in symbol)
        value += int(SequenceMatcher(None, query, company).ratio() * 80)
        value += int(SequenceMatcher(None, query, symbol).ratio() * 40)
        return value

    best = max(universe.values(), key=score, default=None)
    if not best or score(best) < 40:
        return None
    return best["symbol"]
