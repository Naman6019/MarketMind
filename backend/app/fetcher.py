import pandas as pd
import time
import logging
import math
import os
from datetime import date
from app.database import supabase
from app.nse_client import fetch_live_quote
from app.stock_universe import load_stock_universe

logger = logging.getLogger(__name__)
STOCK_INFO_ENRICH_LIMIT = int(os.environ.get("STOCK_INFO_ENRICH_LIMIT", "120"))

def get_mf_nav(scheme_code: int):
    """
    Task 1: Replace mfapi.in with Supabase lookup for MF NAV.
    Returns the latest stored NAV from AMFI sync.
    """
    if not supabase:
        return None
    try:
        res = supabase.table('mutual_funds').select('*').eq('scheme_code', scheme_code).single().execute()
        if res.data:
            return {
                "scheme_code": res.data['scheme_code'],
                "scheme_name": res.data['scheme_name'],
                "nav": res.data['nav'],
                "date": res.data['nav_date']
            }
    except Exception as e:
        logger.error(f"Supabase MF lookup failed for {scheme_code}: {e}")
    return None

def compute_rsi(data: pd.DataFrame, window=14):
    if len(data) < window: return None
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])

def fetch_single_ticker(ticker: str, category: str, nifty_hist: pd.DataFrame = None, enrich: bool = True):
    """
    Uses NSE/local sources first. YFinance is only reachable inside
    fetch_live_quote's final fallback path.
    """
    data = {
        "symbol": ticker, "category": category, "rsi": None, "pe_ratio": None, 
        "recommendation": None, "current_price": None,
        "change_pct": None, "market_cap": None, "beta": None, "alpha_vs_nifty": None
    }
    
    try:
        # 1. Primary: Live Quote from NSE/jugaad-data
        quote = fetch_live_quote(ticker)
        if quote:
            data["current_price"] = quote['last_price']
            data["change_pct"] = quote['pchange']
            
        if not enrich:
            return data

        hist = get_local_history(ticker, 90)
        if not hist.empty:
            if not data["current_price"]:
                data["current_price"] = float(round(hist['Close'].iloc[-1], 2))
            
            rsi = compute_rsi(hist)
            if rsi is not None:
                data["rsi"] = float(round(rsi, 2))
                
            if nifty_hist is not None and not nifty_hist.empty and len(hist) >= 2:
                stock_ret = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                nifty_ret = ((nifty_hist['Close'].iloc[-1] - nifty_hist['Close'].iloc[0]) / nifty_hist['Close'].iloc[0]) * 100
                data["alpha_vs_nifty"] = float(round(stock_ret - nifty_ret, 2))
            
    except Exception as e:
        logger.warning(f"Fetch failed for {ticker}: {e}")
        
    # Final cleanup
    for key, value in data.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            data[key] = None
            
    return data


def get_local_history(symbol: str, days: int = 100) -> pd.DataFrame:
    if not supabase:
        return pd.DataFrame()
    try:
        res = supabase.table('stock_history')\
            .select('close, date')\
            .eq('symbol', symbol)\
            .order('date', desc=True)\
            .limit(days)\
            .execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df.rename(columns={'close': 'Close'}, inplace=True)
            return df
    except Exception as e:
        logger.warning("Local stock history failed for %s: %s", symbol, e)
    return pd.DataFrame()

def run_eod_fetch():
    # This is handled by scripts/run_fetch.py in the new architecture
    # but we keep a compatible version here if needed for on-demand
    if not supabase:
        logger.error("Supabase client not initialized")
        return {"error": "Supabase not configured"}
        
    results = []
    stock_universe = load_stock_universe()
    universe_tickers = list(stock_universe.keys())
    
    nifty_baseline = get_local_history("NIFTY", 100)

    for index, ticker in enumerate(universe_tickers):
        category = stock_universe.get(ticker, {}).get("category", "Unknown")
        should_enrich = index < STOCK_INFO_ENRICH_LIMIT
        data = fetch_single_ticker(ticker, category, nifty_baseline if should_enrich else None, enrich=should_enrich)
        try:
            meta = stock_universe.get(ticker, {})
            supabase.table('stocks').upsert({
                "symbol": ticker,
                "exchange": "NSE",
                "company_name": meta.get("company_name") or ticker,
                "isin": meta.get("isin"),
                "series": "EQ",
                "industry": meta.get("industry"),
                "is_active": True,
            }, on_conflict='symbol').execute()
            if data.get("current_price") is not None:
                supabase.table('stock_prices_daily').upsert({
                    "symbol": ticker,
                    "date": date.today().isoformat(),
                    "close": data.get("current_price"),
                    "adj_close": data.get("current_price"),
                    "source": "marketmind_fetcher",
                }, on_conflict='symbol,date,source').execute()
            supabase.table('nifty_stocks').upsert(data).execute()
            results.append(data)
        except Exception as e:
            logger.error(f"Supabase upsert failed for {ticker}: {e}")
        if index < STOCK_INFO_ENRICH_LIMIT:
            time.sleep(1.0)
        
    return {"status": "success", "count": len(results)}
