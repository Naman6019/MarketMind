from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Any
from datetime import datetime, timezone
from dataclasses import asdict

from app.repositories.stock_repository import StockRepository
from app.models.stock_models import StockProfile, FinancialStatement, StockPriceDaily, RatioSnapshot
from app.providers.manual_provider import ManualFundamentalsProvider
from app.providers.finedge_provider import FinEdgeProvider
from app.providers.indianapi_provider import IndianAPIProvider
from app.providers.nse_provider import NSEProvider
from app.providers.yfinance_provider import YFinanceProvider
from app.stock_universe import load_stock_universe

router = APIRouter(prefix="/api/quant", tags=["quant"])
repository = StockRepository()

class ProviderRegistry:
    @staticmethod
    def get_status() -> dict[str, list[str]]:
        providers = [
            ManualFundamentalsProvider(),
            FinEdgeProvider(),
            IndianAPIProvider(),
            NSEProvider(),
            YFinanceProvider()
        ]
        
        status = {
            "configured": [],
            "available": [],
            "unavailable": []
        }
        
        for p in providers:
            status["configured"].append(p.name)
            if p.is_available():
                status["available"].append(p.name)
            else:
                status["unavailable"].append(p.name)
                
        return status

registry = ProviderRegistry()

def _safe_asdict(obj: Any) -> Any:
    if obj is None:
        return None
    d = asdict(obj)
    if hasattr(obj, 'metadata'):
        d['metadata'] = getattr(obj, 'metadata')
    return d

def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

@router.get("/stocks/compare")
def compare_stocks(symbols: str = Query(..., description="Comma separated symbols")):
    if not symbols or not symbols.strip():
        raise HTTPException(status_code=400, detail="Missing required param: symbols")
        
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="Missing required param: symbols")

    response = {
        "asset_type": "stocks",
        "symbols": symbol_list,
        "available": [],
        "unavailable": [],
        "profiles": {},
        "price_history": {},
        "financials": {},
        "ratios": {},
        "shareholding": {},
        "corporate_events": {},
        "data_quality": {},
        "source_summary": {},
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        comparison = repository.compare_stocks(symbol_list)
        for sym in symbol_list:
            data = comparison.get(sym)
            if not data or not data.get("profile"):
                response["unavailable"].append({"input": sym, "reason": "not_found"})
                continue
                
            response["available"].append(sym)
            response["profiles"][sym] = _safe_asdict(data["profile"])
            response["ratios"][sym] = _safe_asdict(data.get("ratios"))
            
            financials = data.get("financials")
            response["financials"][sym] = [_safe_asdict(f) for f in financials] if financials else []
            
            shareholding = data.get("shareholding")
            response["shareholding"][sym] = [_safe_asdict(s) for s in shareholding] if shareholding else []
            
            # Fetch missing items manually
            price_hist = repository.get_price_history(sym)
            response["price_history"][sym] = [_safe_asdict(p) for p in price_hist] if price_hist else []
            
            response["corporate_events"][sym] = []
            response["data_quality"][sym] = {}
            response["source_summary"][sym] = {}
            
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unexpected error during comparison")

    return response

@router.get("/stocks/nifty50/ticker")
def get_nifty50_ticker():
    try:
        universe = load_stock_universe("NIFTY50")
        symbols = list(universe.keys())[:50]
        items = []

        for symbol in symbols:
            prices = repository.get_recent_price_history(symbol, limit=2)
            latest = prices[-1] if prices else None
            previous = prices[-2] if len(prices) > 1 else None
            close = _safe_float(getattr(latest, "close", None))
            prev_close = _safe_float(getattr(previous, "close", None))
            change_pct = ((close - prev_close) / prev_close * 100) if close is not None and prev_close not in (None, 0) else None

            items.append({
                "symbol": symbol,
                "name": universe.get(symbol, {}).get("company_name") or symbol,
                "price": close,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "date": getattr(latest, "date", None).isoformat() if latest else None,
            })

        return {
            "index": "NIFTY50",
            "items": items,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error")

@router.get("/stocks/{symbol}/profile")
def get_stock_profile(symbol: str):
    try:
        profile = repository.get_stock_profile(symbol)
        if not profile:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return _safe_asdict(profile)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error")

@router.get("/stocks/{symbol}/financials")
def get_stock_financials(symbol: str, period_type: Optional[str] = None):
    try:
        financials = repository.get_financial_statements(symbol, period_type=period_type)
        return [_safe_asdict(f) for f in financials]
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error")

@router.get("/stocks/{symbol}/price-history")
def get_stock_price_history(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    try:
        history = repository.get_price_history(symbol, start_date=start_date, end_date=end_date)
        return [_safe_asdict(h) for h in history]
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error")

@router.get("/providers/status")
def get_provider_status():
    try:
        status = registry.get_status()
        if not status.get("configured"):
            raise HTTPException(status_code=503, detail={"error": "provider_unavailable"})
        return status
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error")
