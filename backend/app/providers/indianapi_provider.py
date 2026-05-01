from __future__ import annotations

import os

from app.providers.base import FundamentalsProvider


class IndianAPIProvider(FundamentalsProvider):
    name = "indianapi"

    def __init__(self) -> None:
        self.api_key = os.environ.get("INDIANAPI_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    # TODO: Map IndianAPI responses into source-neutral financial tables.
