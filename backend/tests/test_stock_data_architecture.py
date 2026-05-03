import pytest
from io import StringIO

from app.providers import get_fundamentals_provider
from app.services.ratio_engine import calculate_ratio_snapshot
from app.stock_universe import resolve_stock_symbol
from scripts.run_fetch import build_stock_price_upsert_payload


def test_symbol_resolver_uses_universe(monkeypatch):
    monkeypatch.setattr("app.stock_universe.load_stock_universe", lambda _key=None: {
        "RELIANCE": {"symbol": "RELIANCE", "company_name": "Reliance Industries Limited"},
    })

    assert resolve_stock_symbol("Reliance Industries") == "RELIANCE"


def test_provider_falls_back_when_paid_key_missing(monkeypatch):
    monkeypatch.setenv("STOCK_DATA_PROVIDER", "finedge")
    monkeypatch.delenv("FINEDGE_API_KEY", raising=False)

    assert get_fundamentals_provider().name == "manual"


def test_ratio_engine_full_data():
    annual = [
        {"net_profit": 100, "total_equity": 500, "ebit": 140, "total_assets": 900, "total_liabilities": 300, "total_debt": 100, "cash_and_equivalents": 20, "ebitda": 160, "revenue": 1000, "eps": 10},
        {"revenue": 900, "net_profit": 90, "eps": 9},
        {"revenue": 800, "net_profit": 80, "eps": 8},
        {"revenue": 700, "net_profit": 70, "eps": 7},
    ]
    quarterly = [{"eps": 2, "net_profit": 25, "ebitda": 40} for _ in range(4)]

    result = calculate_ratio_snapshot(annual, quarterly, latest_price=50, shares_outstanding=10, dividend_per_share=1)

    assert result.ratios["roe"] == pytest.approx(0.2)
    assert result.ratios["roce"] == pytest.approx(140 / 600)
    assert result.ratios["debt_to_equity"] == pytest.approx(0.2)
    assert result.ratios["eps_ttm"] == pytest.approx(8)
    assert result.ratios["dividend_yield"] == pytest.approx(0.02)


def test_ratio_engine_missing_data_returns_nulls():
    result = calculate_ratio_snapshot([], [])

    assert result.ratios["roe"] is None
    assert result.ratios["pe"] is None
    assert "roe" in result.data_quality


def test_quant_compare_response_shape(monkeypatch):
    from app.services import quant_service

    monkeypatch.setattr(quant_service, "resolve_stock_request", lambda symbol: "RELIANCE" if symbol == "RELIANCE" else None)
    monkeypatch.setattr(quant_service, "_comparison_item", lambda symbol: {
        "symbol": symbol,
        "price": 100,
        "change_pct": None,
        "pe_ratio": None,
        "market_cap": None,
        "fundamentals": {"roe": None},
        "ratios": {},
        "financials": {"quarterly": [], "annual": []},
        "shareholding": {},
        "price_history": [],
        "data_quality": {"missing_fields": ["roe"], "message": "Missing"},
        "source_summary": {},
    })

    response = quant_service.build_stock_compare("RELIANCE,UNKNOWN")

    assert response["asset_type"] == "stocks"
    assert response["available"] == ["RELIANCE"]
    assert response["unavailable"] == ["UNKNOWN"]
    assert response["comparison"]["UNKNOWN"]["error"]
    assert response["comparison"]["UNKNOWN"]["fundamentals"]["roe"] is None
    assert response["metrics"]["UNKNOWN"]["price"] is None
    assert response["price_history"]["UNKNOWN"] == []


def test_quant_compare_isolates_symbol_failure(monkeypatch):
    from app.services import quant_service

    monkeypatch.setattr(quant_service, "resolve_stock_request", lambda symbol: symbol)

    def fail_one(symbol):
        if symbol == "BROKEN":
            raise RuntimeError("provider exploded")
        return {
            "symbol": symbol,
            "price": None,
            "change_pct": None,
            "pe_ratio": None,
            "market_cap": None,
            "fundamentals": {"roe": None},
            "ratios": {},
            "financials": {"quarterly": [], "annual": []},
            "shareholding": {},
            "price_history": [],
            "data_quality": {"missing_fields": ["roe"], "message": "Missing"},
            "source_summary": {},
        }

    monkeypatch.setattr(quant_service, "_comparison_item", fail_one)

    response = quant_service.build_stock_compare("OK,BROKEN")

    assert response["available"] == ["OK"]
    assert response["unavailable"] == ["BROKEN"]
    assert response["comparison"]["BROKEN"]["error"] == "Data lookup failed for this symbol."


def test_stock_price_upsert_payload_format():
    payload = build_stock_price_upsert_payload("reliance", {
        "date": "2026-05-01",
        "open": 1,
        "high": 2,
        "low": 0.5,
        "close": 1.5,
        "volume": 1000,
    })

    assert payload == {
        "symbol": "RELIANCE",
        "date": "2026-05-01",
        "open": 1,
        "high": 2,
        "low": 0.5,
        "close": 1.5,
        "adj_close": 1.5,
        "volume": 1000,
        "source": "nse_bhavcopy",
    }


def test_indianapi_eod_prices_use_documented_symbol_param(monkeypatch):
    from app.providers import indianapi_provider

    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"datasets": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setenv("INDIANAPI_KEY", "test-key")
    monkeypatch.setattr(indianapi_provider.httpx, "get", fake_get)

    provider = indianapi_provider.IndianAPIProvider()
    provider.get_eod_prices("TATAMOTORS")

    assert captured["url"].endswith("/historical_data")
    assert captured["params"]["symbol"] == "TATAMOTORS"
    assert "stock_name" not in captured["params"]
    assert captured["headers"]["X-API-Key"] == "test-key"


def test_finedge_eod_prices_use_token_query(monkeypatch):
    from app.providers import finedge_provider

    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "symbol": "ITC",
                "price": [{
                    "quote_date": "2026-05-01",
                    "open_price": 1,
                    "high_price": 2,
                    "low_price": 0.5,
                    "close_price": 1.5,
                    "volume": 1000,
                }],
            }

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setenv("FINEDGE_API_KEY", "test-key")
    monkeypatch.setattr(finedge_provider.httpx, "get", fake_get)

    provider = finedge_provider.FinEdgeProvider()
    prices = provider.get_eod_prices("ITC")

    assert captured["url"].endswith("/api/v1/daily-quotes/ITC")
    assert captured["params"]["token"] == "test-key"
    assert prices[0]["close"] == 1.5
    assert prices[0]["source"] == "finedge"


def test_finedge_annual_results_map_basic_financials(monkeypatch):
    from app.providers import finedge_provider

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "symbol": "ITC",
                "basic_financials": [{
                    "year": 2025,
                    "operatingRevenue": 100,
                    "operatingProfit": 20,
                    "ebitda": 25,
                    "ebit": 18,
                }],
            }

    monkeypatch.setenv("FINEDGE_API_KEY", "test-key")
    monkeypatch.setattr(finedge_provider.httpx, "get", lambda *args, **kwargs: FakeResponse())

    result = finedge_provider.FinEdgeProvider().get_annual_results("ITC")

    assert result[0]["period_type"] == "annual"
    assert result[0]["period_end_date"].isoformat() == "2025-03-31"
    assert result[0]["revenue"] == 100
    assert result[0]["source"] == "finedge"


def test_data_quality_issue_allows_legacy_keyword_shape():
    from app.models.stock_models import DataQualityIssue

    issue = DataQualityIssue(
        symbol="ITC",
        table_name="stock_prices_daily",
        issue_type="sync_error",
        issue_message="No price history returned by provider",
        source="finedge",
    )

    assert issue.field_name is None
    assert issue.metadata is None


def test_nse_udiff_bhavcopy_parser_maps_stock_prices():
    from app.nse_client import parse_nse_bhavcopy_csv

    csv_data = StringIO(
        "TradDt,BizDt,Sgmt,Src,FinInstrmTp,ISIN,TckrSymb,SctySrs,FinInstrmNm,"
        "OpnPric,HghPric,LwPric,ClsPric,PrvsClsgPric,TtlTradgVol,TtlTrfVal\n"
        "2024-07-12,2024-07-12,CM,NSE,STK,INE002A01018,RELIANCE,EQ,Reliance,"
        "3000.00,3010.00,2990.00,3005.00,2995.00,1000,3005000.00\n"
        "2024-07-12,2024-07-12,CM,NSE,ETF,INF000000000,ETFTEST,EQ,ETF,"
        "10.00,11.00,9.00,10.50,10.00,100,1050.00\n"
    )

    rows = parse_nse_bhavcopy_csv(csv_data)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "RELIANCE"
    assert rows[0]["date"] == "2024-07-12"
    assert rows[0]["close"] == 3005.0
    assert rows[0]["volume"] == 1000
    assert rows[0]["value_traded"] == 3005000.0
    assert rows[0]["source"] == "nse_bhavcopy"
