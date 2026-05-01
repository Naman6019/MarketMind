from __future__ import annotations

import logging
import os

from app.providers.base import FundamentalsProvider
from app.providers.manual_provider import ManualFundamentalsProvider

logger = logging.getLogger(__name__)


def get_fundamentals_provider() -> FundamentalsProvider:
    selected = os.environ.get("STOCK_DATA_PROVIDER", "manual").strip().lower()
    manual = ManualFundamentalsProvider()
    provider: FundamentalsProvider = manual
    if selected == "finedge":
        from app.providers.finedge_provider import FinEdgeProvider
        provider = FinEdgeProvider()
    elif selected == "indianapi":
        from app.providers.indianapi_provider import IndianAPIProvider
        provider = IndianAPIProvider()
    elif selected == "nse":
        from app.providers.nse_provider import NSEProvider
        provider = NSEProvider()
    elif selected == "yfinance":
        from app.providers.yfinance_provider import YFinanceProvider
        provider = YFinanceProvider()

    if not provider.is_available():
        logger.warning(
            "Fundamentals provider %s is not configured; falling back to manual provider.",
            provider.name,
        )
        return manual
    return provider


__all__ = ["FundamentalsProvider", "get_fundamentals_provider"]
