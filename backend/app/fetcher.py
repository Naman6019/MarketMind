import pandas as pd
import time
import logging
import math
from app.database import supabase
from app.nse_client import fetch_live_quote
import yfinance as yf

logger = logging.getLogger(__name__)

# Ticker lists maintained for universe consistency
NIFTY_50_TICKERS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "ITC", "SBIN", "BHARTIARTL",
    "BAJFINANCE", "LT", "KOTAKBANK", "HCLTECH", "AXISBANK", "MARUTI", "SUNPHARMA",
    "TITAN", "ULTRACEMCO", "BAJAJFINSV", "ASIANPAINT", "NTPC", "M&M", "TATASTEEL",
    "POWERGRID", "INDUSINDBK", "TATAMOTORS", "HINDUNILVR", "NESTLEIND", "GRASIM",
    "TECHM", "WIPRO", "HINDALCO", "JSWSTEEL", "ADANIENT", "ADANIPORTS", "ONGC",
    "BRITANNIA", "CIPLA", "APOLLOHOSP", "DIVISLAB", "DRREDDY", "BAJAJ-AUTO",
    "TATACONSUM", "EICHERMOT", "COALINDIA", "HEROMOTOCO", "UPL", "BPCL", "LTIM",
    "SBILIFE"
]

MIDCAP_TICKERS = [
    "MAXHEALTH", "YESBANK", "IDFCFIRSTB", "TATACOMM", "RVNL", "AUROPHARMA", "KPITTECH", 
    "PERSISTENT", "CUMMINSIND", "VOLTAS", "CONCOR", "HINDPETRO", "MRF", "ASHOKLEY", 
    "BALKRISIND", "DIXON", "POLYCAB", "LUPIN", "NMDC", "TRENT", "CANBK", "FEDERALBNK",
    "IDBI", "OBEROIRLTY", "PEL", "SRF", "TATAELXSI", "UNIONBANK", "ZEEL", "BATAINDIA"
]

SMALLCAP_TICKERS = [
    "SUZLON", "RITES", "IRFC", "MAZDOCK", "KEC", "MCX", "BSOFT", "CYIENT", "ANGELONE", 
    "CDSL", "ZENSARTECH", "SONATSOFTW", "KEI", "RADICO", "HFCL", "NBCC", "BSE", 
    "HUDCO", "JSL", "CASTROLIND", "CENTRALBK", "FSL", "IEX", "JWL", "PPLPHARMA", 
    "RAILTEL", "SJVN", "SOUTHBANK", "TEJASNET", "WELCORP"
]

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

def fetch_single_ticker(ticker: str, category: str, nifty_hist: pd.DataFrame = None):
    """
    Task 2: Replace live YFinance call with fetch_live_quote().
    Uses YFinance only for history-dependent metrics (RSI, Alpha).
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
            
        # 2. History-dependent metrics (Keep YFinance as fallback/supplement for now as requested)
        # However, Task 2 Step 4 says replace the "live/on-demand YFinance call".
        stock_symbol = f"{ticker}.NS"
        if ticker == "NIFTY": stock_symbol = "^NSEI"
        stock = yf.Ticker(stock_symbol)
        
        # We still need info for PE, Market Cap, Beta
        info = stock.info
        data["pe_ratio"] = info.get("trailingPE", info.get("forwardPE"))
        data["market_cap"] = info.get("marketCap")
        data["beta"] = info.get("beta")
        rec = info.get("recommendationKey")
        if rec and rec != "none":
            data["recommendation"] = str(rec).replace('_', ' ').title()

        # History for RSI and Alpha
        hist = stock.history(period="3mo")
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

def run_eod_fetch():
    # This is handled by scripts/run_fetch.py in the new architecture
    # but we keep a compatible version here if needed for on-demand
    if not supabase:
        logger.error("Supabase client not initialized")
        return {"error": "Supabase not configured"}
        
    results = []
    ticker_groups = [
        (NIFTY_50_TICKERS, "Large Cap"),
        (MIDCAP_TICKERS, "Mid Cap"),
        (SMALLCAP_TICKERS, "Small Cap")
    ]
    
    try:
        nifty_baseline = yf.Ticker("^NSEI").history(period="3mo")
    except:
        nifty_baseline = None

    for tickers, category in ticker_groups:
        for ticker in tickers:
            data = fetch_single_ticker(ticker, category, nifty_baseline)
            try:
                supabase.table('nifty_stocks').upsert(data).execute()
                results.append(data)
            except Exception as e:
                logger.error(f"Supabase upsert failed for {ticker}: {e}")
            time.sleep(1.0)
        
    return {"status": "success", "count": len(results)}
