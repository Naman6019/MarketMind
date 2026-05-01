from __future__ import annotations

import logging
from typing import Any

from app.database import supabase
from app.providers.base import FundamentalsProvider, normalize_symbol

logger = logging.getLogger(__name__)


class ManualFundamentalsProvider(FundamentalsProvider):
    name = "manual"

    def _latest(self, table: str, symbol: str, order_column: str) -> dict[str, Any] | None:
        if not supabase:
            return None
        try:
            res = (
                supabase.table(table)
                .select("*")
                .eq("symbol", normalize_symbol(symbol))
                .order(order_column, desc=True)
                .limit(1)
                .execute()
            )
            return (res.data or [None])[0]
        except Exception as exc:
            logger.warning("Manual provider lookup failed for %s/%s: %s", table, symbol, exc)
            return None

    def _many(self, table: str, symbol: str, order_column: str, limit: int = 8) -> list[dict[str, Any]]:
        if not supabase:
            return []
        try:
            res = (
                supabase.table(table)
                .select("*")
                .eq("symbol", normalize_symbol(symbol))
                .order(order_column, desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.warning("Manual provider list lookup failed for %s/%s: %s", table, symbol, exc)
            return []

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        clean = normalize_symbol(symbol)
        if not supabase:
            return None
        try:
            res = supabase.table("stocks").select("*").eq("symbol", clean).limit(1).execute()
            return (res.data or [None])[0]
        except Exception as exc:
            logger.warning("Manual profile lookup failed for %s: %s", clean, exc)
            return None

    def get_quarterly_results(self, symbol: str) -> list[dict[str, Any]]:
        return [
            row for row in self._many("financial_statements", symbol, "period_end_date")
            if row.get("period_type") == "quarterly"
        ]

    def get_annual_results(self, symbol: str) -> list[dict[str, Any]]:
        return [
            row for row in self._many("financial_statements", symbol, "period_end_date")
            if row.get("period_type") == "annual"
        ]

    def get_balance_sheet(self, symbol: str) -> list[dict[str, Any]]:
        return self._many("financial_statements", symbol, "period_end_date")

    def get_cash_flow(self, symbol: str) -> list[dict[str, Any]]:
        return self._many("financial_statements", symbol, "period_end_date")

    def get_shareholding(self, symbol: str) -> list[dict[str, Any]]:
        return self._many("shareholding_pattern", symbol, "period_end_date", limit=4)

    def get_ratios_snapshot(self, symbol: str) -> dict[str, Any] | None:
        return self._latest("ratios_snapshot", symbol, "snapshot_date")
