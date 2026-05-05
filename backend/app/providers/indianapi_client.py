from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, TypedDict

import httpx

logger = logging.getLogger(__name__)


class ProviderError(TypedDict, total=False):
    status: int
    code: str
    message: str
    bodySnippet: str


class ProviderResult(TypedDict, total=False):
    ok: bool
    source: str
    endpoint: str
    data: Any
    error: ProviderError
    stale: bool


ENDPOINTS: dict[str, dict[str, Any]] = {
    "/industry_search": {"required": ["query"]},
    "/stock": {"required": ["name"]},
    "/historical_stats": {"required": ["stock_name", "stats"]},
    "/mutual_fund_search": {"required": ["query"]},
    "/mutual_funds": {"required": []},
    "/mutual_funds_details": {"required": ["stock_name"]},
    "/corporate_actions": {"required": ["stock_name"]},
    "/recent_announcements": {"required": ["stock_name"]},
    "/historical_data": {"required": ["stock_name", "period", "filter"], "enum_required": ["period", "filter"]},
    "/stock_target_price": {"required": ["stock_id"]},
    "/stock_forecasts": {
        "required": ["stock_id", "measure_code", "period_type", "data_type", "age"],
        "enum_required": ["measure_code", "period_type", "data_type", "age"],
    },
}


class IndianAPIClient:
    source = "indianapi"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 8.0,
        spec_path: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("INDIANAPI_BASE_URL") or "https://stock.indianapi.in").rstrip("/")
        self.api_key = api_key or os.getenv("INDIANAPI_KEY") or os.getenv("INDIAN_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.spec = _load_spec(spec_path)

    def search_stocks(self, query: str) -> ProviderResult:
        return self._get("/industry_search", {"query": query})

    def get_stock_details(self, name: str) -> ProviderResult:
        return self._get("/stock", {"name": name})

    def get_historical_stats(self, stock_name: str, stats: str) -> ProviderResult:
        return self._get("/historical_stats", {"stock_name": stock_name, "stats": stats})

    def search_mutual_funds(self, query: str) -> ProviderResult:
        return self._get("/mutual_fund_search", {"query": query})

    def get_mutual_funds(self) -> ProviderResult:
        return self._get("/mutual_funds", {})

    def get_mutual_fund_details(self, stock_name: str) -> ProviderResult:
        return self._get("/mutual_funds_details", {"stock_name": stock_name})

    def get_corporate_actions(self, stock_name: str) -> ProviderResult:
        return self._get("/corporate_actions", {"stock_name": stock_name})

    def get_recent_announcements(self, stock_name: str) -> ProviderResult:
        return self._get("/recent_announcements", {"stock_name": stock_name})

    def get_historical_data(self, stock_name: str, period: str, filter: str) -> ProviderResult:
        return self._get("/historical_data", {"stock_name": stock_name, "period": period, "filter": filter})

    def get_stock_target_price(self, stock_id: str) -> ProviderResult:
        return self._get("/stock_target_price", {"stock_id": stock_id})

    def get_stock_forecasts(
        self,
        stock_id: str,
        measure_code: str,
        period_type: str,
        data_type: str,
        age: str,
    ) -> ProviderResult:
        return self._get(
            "/stock_forecasts",
            {
                "stock_id": stock_id,
                "measure_code": measure_code,
                "period_type": period_type,
                "data_type": data_type,
                "age": age,
            },
        )

    # Camel-case aliases match the v1 integration names.
    searchStocks = search_stocks
    getStockDetails = get_stock_details
    getHistoricalStats = get_historical_stats
    searchMutualFunds = search_mutual_funds
    getMutualFunds = get_mutual_funds
    getMutualFundDetails = get_mutual_fund_details
    getCorporateActions = get_corporate_actions
    getRecentAnnouncements = get_recent_announcements
    getHistoricalData = get_historical_data
    getStockTargetPrice = get_stock_target_price
    getStockForecasts = get_stock_forecasts

    def _get(self, endpoint: str, params: dict[str, Any]) -> ProviderResult:
        validation_error = self._validate(endpoint, params)
        if validation_error:
            return self._error(endpoint, "validation_error", validation_error)
        if not self.api_key:
            return self._error(endpoint, "missing_api_key", "INDIANAPI_KEY is not configured.")

        started = time.monotonic()
        status = None
        safe_params = {key: value for key, value in params.items() if value not in (None, "")}

        try:
            response = httpx.get(
                f"{self.base_url}{endpoint}",
                params=safe_params,
                headers={"x-api-key": self.api_key},
                timeout=self.timeout_seconds,
            )
            status = response.status_code
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "IndianAPI endpoint=%s params=%s status=%s duration_ms=%s",
                endpoint,
                safe_params,
                status,
                duration_ms,
            )

            if response.status_code >= 400:
                return self._error(
                    endpoint,
                    f"http_{response.status_code}",
                    "Provider request failed.",
                    status=response.status_code,
                    body=response.text,
                )

            try:
                data = response.json()
            except ValueError:
                return self._error(endpoint, "invalid_json", "Provider returned invalid JSON.", status=status, body=response.text)

            return {"ok": True, "source": self.source, "endpoint": endpoint, "data": data}
        except httpx.TimeoutException:
            return self._error(endpoint, "timeout", "Provider request timed out.", status=status)
        except Exception as exc:
            return self._error(endpoint, "request_error", "Provider request failed.", status=status, body=str(exc))

    def _validate(self, endpoint: str, params: dict[str, Any]) -> str | None:
        definition = ENDPOINTS.get(endpoint, {})
        spec_params = _spec_params(self.spec, endpoint)
        required = spec_params.get("required") or definition.get("required", [])

        for name in required:
            if params.get(name) in (None, ""):
                return f"Missing required param: {name}"

        enum_required = definition.get("enum_required", [])
        for name, allowed in spec_params.get("enums", {}).items():
            if params.get(name) not in (None, "") and allowed and params[name] not in allowed:
                return f"Invalid {name}. Allowed values: {', '.join(allowed)}"

        for name in enum_required:
            if name not in spec_params.get("enums", {}):
                return f"Enum values for {endpoint}.{name} are unavailable because docs/api-1.json was not found."

        return None

    def _error(self, endpoint: str, code: str, message: str, status: int | None = None, body: str | None = None) -> ProviderResult:
        error: ProviderError = {"code": code, "message": message}
        if status is not None:
            error["status"] = status
        if body:
            error["bodySnippet"] = body[:500]
        return {"ok": False, "source": self.source, "endpoint": endpoint, "error": error}


def _load_spec(spec_path: str | None = None) -> dict[str, Any]:
    candidates: list[Path] = []
    if spec_path or os.getenv("INDIANAPI_OPENAPI_PATH"):
        candidates.append(Path(spec_path or os.getenv("INDIANAPI_OPENAPI_PATH", "")))
    root = Path(__file__).resolve().parents[3]
    candidates.extend([
        root / "docs" / "api-1.json",
        root / "api.json",
        root / "backend" / "api.json",
        root / "docs" / "api.json",
    ])

    for candidate in candidates:
        try:
            if candidate.exists():
                return json.loads(candidate.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read IndianAPI OpenAPI spec at %s: %s", candidate, exc)
    return {}


def _spec_params(spec: dict[str, Any], endpoint: str) -> dict[str, Any]:
    path_item = (spec.get("paths") or {}).get(endpoint) or {}
    operation = path_item.get("get") or path_item.get("GET") or {}
    required: list[str] = []
    enums: dict[str, list[str]] = {}

    for param in operation.get("parameters") or []:
        name = param.get("name")
        if not name:
            continue
        if param.get("required"):
            required.append(name)
        schema = _resolve_schema(spec, param.get("schema") or {})
        allowed = schema.get("enum")
        if allowed:
            enums[name] = [str(value) for value in allowed]

    return {"required": required, "enums": enums}


def _resolve_schema(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    prefix = "#/components/schemas/"
    if not isinstance(ref, str) or not ref.startswith(prefix):
        return schema
    name = ref[len(prefix):]
    return ((spec.get("components") or {}).get("schemas") or {}).get(name) or schema
