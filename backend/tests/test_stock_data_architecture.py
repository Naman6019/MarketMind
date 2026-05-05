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


def test_chat_compare_table_handles_empty_risk_period():
    from app import main

    table, notes = main._data_table_markdown("compare", {
        "comparison": {
            "TCS": {
                "symbol": "TCS",
                "price": 100,
                "historical_period": "",
                "fundamentals": {},
            }
        }
    })

    assert notes == []
    assert "Beta (period)" in table
    assert "TCS" in table


def test_chat_stock_compare_item_uses_quant_service_shape(monkeypatch):
    from app import main

    def fake_build_stock_compare(symbols):
        assert symbols == ["TCS"]
        return {
            "comparison": {
                "TCS": {
                    "symbol": "TCS",
                    "price": 100,
                    "historical_period": "1y",
                    "fundamentals": {},
                }
            }
        }

    monkeypatch.setattr(main, "build_stock_compare", fake_build_stock_compare)

    item = main._stock_compare_item("TCS", {"beta": 1.1, "risk_period": "3Y"})

    assert item["price"] == 100
    assert item["beta"] == 1.1
    assert item["risk_period"] == "3Y"


def test_synthesis_prompt_excludes_large_comparison_payload(monkeypatch):
    import asyncio
    from app import main

    captured = {}

    async def fake_chat(messages, format="text", max_retries=2):
        captured["context"] = messages[1]["content"]
        return "TCS and Reliance have structured comparison data, with missing values limiting the conclusion."

    monkeypatch.setattr(main, "function_ollama_chat", fake_chat)

    quant_data = {
        "comparison": {
            "TCS": {
                "symbol": "TCS",
                "price": 100,
                "historical_period": "1y",
                "fundamentals": {},
                "price_history": [{"date": f"2026-01-{day:02d}", "close": day} for day in range(1, 29)],
                "financials": {"annual": [{"revenue": 1}], "quarterly": [{"revenue": 2}]},
            },
            "Reliance": {
                "symbol": "RELIANCE",
                "price": 200,
                "historical_period": "1y",
                "fundamentals": {},
                "price_history": [{"date": f"2026-02-{day:02d}", "close": day} for day in range(1, 29)],
                "financials": {"annual": [{"revenue": 3}], "quarterly": [{"revenue": 4}]},
            },
        }
    }

    answer = asyncio.run(main.synthesis_response(
        "Compare TCS and Reliance",
        {"intent": "compare", "compare_entities": ["TCS", "Reliance"]},
        quant_data,
        [],
    ))

    assert "### Data Table" in answer
    assert "Structured Data Table:" in captured["context"]
    assert "price_history" not in captured["context"]
    assert "financials" not in captured["context"]
    assert len(captured["context"]) < 5000


def test_corporate_events_job_uses_indianapi(monkeypatch):
    from app.jobs import sync_corporate_events

    monkeypatch.setenv("STOCK_DATA_PROVIDER", "indianapi")
    monkeypatch.setenv("INDIANAPI_KEY", "good-key")

    provider = sync_corporate_events.get_corporate_events_provider()

    assert provider.name == "indianapi"


def test_corporate_events_job_requires_indianapi_key(monkeypatch):
    from app.jobs import sync_corporate_events

    monkeypatch.setenv("STOCK_DATA_PROVIDER", "indianapi")
    monkeypatch.delenv("INDIANAPI_KEY", raising=False)
    monkeypatch.delenv("INDIAN_API_KEY", raising=False)

    assert sync_corporate_events.get_corporate_events_provider() is None


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


def test_indianapi_eod_prices_use_documented_stock_name_param(monkeypatch):
    from app.providers import indianapi_provider

    captured = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "datasets": [
                    {"metric": "Price", "values": [["2026-05-01", "100.5"]]},
                    {"metric": "Volume", "values": [["2026-05-01", 1200, {"delivery": 52}]]},
                ]
            }

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.append({"url": url, "params": params, "headers": headers})
        return FakeResponse()

    monkeypatch.setenv("INDIANAPI_KEY", "test-key")
    monkeypatch.setattr(indianapi_provider.httpx, "get", fake_get)

    provider = indianapi_provider.IndianAPIProvider()
    prices = provider.get_eod_prices("TATAMOTORS")

    assert captured[0]["url"].endswith("/historical_data")
    assert captured[0]["params"] == {"stock_name": "TATAMOTORS", "period": "1yr", "filter": "price"}
    assert captured[0]["headers"]["X-API-Key"] == "test-key"
    assert prices[0]["close"] == 100.5
    assert prices[0]["volume"] == 1200
    assert prices[0]["delivery_percent"] == 52


def test_indianapi_stock_endpoint_maps_ratios_and_shareholding(monkeypatch):
    from app.providers import indianapi_provider

    captured = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "tickerId": "TCS",
                "companyName": "Tata Consultancy Services",
                "industry": "IT Services",
                "keyMetrics": {
                    "Market Cap": 1000,
                    "P/E Ratio": 25,
                    "ROE": 0.32,
                    "Debt to Equity": 0.1,
                },
                "shareholding": {
                    "Promoters": {"Mar 2026": 72.3},
                    "FII": {"Mar 2026": 12.4},
                    "DII": {"Mar 2026": 8.1},
                    "Public": {"Mar 2026": 7.2},
                },
                "financials": {
                    "quarter_results": {
                        "Sales": {"Mar 2026": 100},
                        "Net Profit": {"Mar 2026": 20},
                        "EPS in Rs": {"Mar 2026": 5},
                    }
                },
            }

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.append({"url": url, "params": params, "headers": headers})
        return FakeResponse()

    monkeypatch.setenv("INDIANAPI_KEY", "test-key")
    monkeypatch.setattr(indianapi_provider.httpx, "get", fake_get)

    provider = indianapi_provider.IndianAPIProvider()
    ratios = provider.get_ratios_snapshot("TCS")
    shareholding = provider.get_shareholding("TCS")
    quarterly = provider.get_quarterly_results("TCS")

    assert any(call["url"].endswith("/stock") and call["params"] == {"name": "TCS"} for call in captured)
    assert captured[0]["headers"]["X-API-Key"] == "test-key"
    assert ratios["pe"] == 25
    assert ratios["roe"] == 0.32
    assert ratios["debt_to_equity"] == 0.1
    assert shareholding[0]["promoter_holding"] == 72.3
    assert quarterly[0]["period_type"] == "quarterly"
    assert quarterly[0]["revenue"] == 100
    assert quarterly[0]["net_profit"] == 20


def test_indianapi_statement_endpoint_maps_fundamentals(monkeypatch):
    from app.providers import indianapi_provider

    calls = []

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        if url.endswith("/statement") and params["stats"] == "quarter_results":
            return FakeResponse({
                "Sales": {"Mar 2026": 100},
                "Net Profit": {"Mar 2026": 20},
                "EPS in Rs": {"Mar 2026": 5},
            })
        if url.endswith("/statement") and params["stats"] == "ratios":
            return FakeResponse({
                "ROCE": {"Mar 2025": 0.2, "Mar 2026": 0.25},
                "P/E": {"Mar 2026": 22},
            })
        if url.endswith("/stock"):
            return FakeResponse({})
        return FakeResponse({})

    monkeypatch.setenv("INDIANAPI_KEY", "test-key")
    monkeypatch.setattr(indianapi_provider.httpx, "get", fake_get)

    provider = indianapi_provider.IndianAPIProvider()
    quarterly = provider.get_quarterly_results("TCS")
    ratios = provider.get_ratios_snapshot("TCS")

    assert calls[0][0].endswith("/statement")
    assert calls[0][1] == {"stock_name": "TCS", "stats": "quarter_results"}
    assert quarterly[0]["revenue"] == 100
    assert quarterly[0]["net_profit"] == 20
    assert ratios["roce"] == 0.25
    assert ratios["pe"] == 22


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
