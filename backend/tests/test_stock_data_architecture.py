import pytest

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
    monkeypatch.setenv("FUNDAMENTALS_PROVIDER", "finedge")
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
