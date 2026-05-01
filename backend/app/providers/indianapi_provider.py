from __future__ import annotations

import os
import logging
import httpx
from datetime import date

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

    def get_stock_universe(self) -> list[StockProfile]:
        try:
            res = httpx.get(f"{self.base_url}/static/all_stocks.json", timeout=15.0)
            if res.status_code != 200:
                logger.error("IndianAPI get_stock_universe failed with status %s", res.status_code)
                return []
            
            data = res.json()
            profiles = []
            for item in data:
                # Prefer NSE code, fallback to BSE code, then name
                symbol = item.get("nse-code") or item.get("bse-code") or item.get("name")
                if not symbol or symbol == "null":
                    continue
                
                # We normalize the symbol for MarketMind
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

    def get_eod_prices(self, symbol: str) -> list[dict]:
        try:
            res = httpx.get(f"{self.base_url}/stock", params={"name": symbol}, headers=self._get_headers(), timeout=10.0)
            if res.status_code != 200:
                logger.warning("IndianAPI get_eod_prices failed for %s with %s", symbol, res.status_code)
                return []
            
            data = res.json()
            prices = data.get("currentPrice", {})
            current_price = prices.get("NSE") or prices.get("BSE")
            if current_price is None:
                return []
            
            return [{
                "symbol": symbol,
                "date": date.today(),
                "close": float(current_price),
                "adj_close": float(current_price),
                "source": self.name
            }]
        except Exception as exc:
            logger.error("IndianAPI get_eod_prices error for %s: %s", symbol, exc)
            return []

    def get_quarterly_results(self, symbol: str) -> list[dict]:
        # Detailed JSON mapping to be expanded based on the "financials" key of /stock endpoint
        try:
            res = httpx.get(f"{self.base_url}/stock", params={"name": symbol}, headers=self._get_headers(), timeout=10.0)
            if res.status_code != 200:
                return []
            
            data = res.json()
            financials = data.get("financials", {})
            # Safely returning empty until the full fields map is confirmed with real data
            return []
        except Exception as exc:
            logger.error("IndianAPI get_quarterly_results error for %s: %s", symbol, exc)
            return []

    def get_annual_results(self, symbol: str) -> list[dict]: return []
    def get_balance_sheet(self, symbol: str) -> list[dict]: return []
    def get_cash_flow(self, symbol: str) -> list[dict]: return []
    def get_shareholding(self, symbol: str) -> list[dict]: return []
    def get_corporate_actions(self, symbol: str) -> list[dict]: return []
