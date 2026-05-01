from __future__ import annotations

from abc import ABC
from typing import Any


class FundamentalsProvider(ABC):
    name = "base"

    def is_available(self) -> bool:
        return True

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        return None

    def get_quarterly_results(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_annual_results(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_balance_sheet(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_cash_flow(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_shareholding(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def get_ratios_snapshot(self, symbol: str) -> dict[str, Any] | None:
        return None


def normalize_symbol(symbol: str | None) -> str:
    if not symbol:
        return ""
    return symbol.replace(".NS", "").replace(".BO", "").strip().upper()
