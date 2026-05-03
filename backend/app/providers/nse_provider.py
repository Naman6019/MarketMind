from __future__ import annotations

from datetime import date

from app.nse_client import fetch_nse_bhavcopy
from app.providers.base import FundamentalsProvider
from app.stock_universe import load_stock_universe


class NSEProvider(FundamentalsProvider):
    name = "nse"

    def get_company_profile(self, symbol: str):
        return load_stock_universe().get(symbol.upper())

    def get_daily_prices(self, trade_date: date):
        return fetch_nse_bhavcopy(trade_date)

    def get_eod_prices_for_date(self, trade_date: date):
        return fetch_nse_bhavcopy(trade_date)
