from __future__ import annotations

import logging

import yfinance as yf

from app.providers.base import FundamentalsProvider, normalize_symbol

logger = logging.getLogger(__name__)


class YFinanceProvider(FundamentalsProvider):
    name = "yfinance"

    def get_price_history(self, symbol: str, period: str = "1y") -> list[dict]:
        clean = normalize_symbol(symbol)
        ticker = "^NSEI" if clean == "NIFTY" else f"{clean}.NS"
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if hist.empty:
                return []
            rows = []
            for idx, row in hist.reset_index().iterrows():
                rows.append({
                    "symbol": clean,
                    "date": row["Date"].date().isoformat(),
                    "open": _float_or_none(row.get("Open")),
                    "high": _float_or_none(row.get("High")),
                    "low": _float_or_none(row.get("Low")),
                    "close": _float_or_none(row.get("Close")),
                    "adj_close": _float_or_none(row.get("Close")),
                    "volume": _float_or_none(row.get("Volume")),
                    "source": self.name,
                })
            return rows
        except Exception as exc:
            logger.warning("YFinance price fallback failed for %s: %s", clean, exc)
            return []


def _float_or_none(value):
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
