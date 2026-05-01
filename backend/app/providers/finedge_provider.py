from __future__ import annotations

import os

from app.providers.base import FundamentalsProvider


class FinEdgeProvider(FundamentalsProvider):
    name = "finedge"

    def __init__(self) -> None:
        self.api_key = os.environ.get("FINEDGE_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    # TODO: Map FinEdge responses into source-neutral financial_statements,
    # ratios_snapshot, shareholding_pattern, and corporate_events payloads.
