import yfinance as yf
import pandas as pd
import time
import logging
from app.database import supabase

logger = logging.getLogger(__name__)

# To prevent cyclical import, we define the NIFTY list here.
# Changed LARSEN to LT for Yahoo Finance compatibility
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

def fetch_single_ticker(ticker: str, nifty_hist: pd.DataFrame = None):
    data = {
        "symbol": ticker, "rsi": None, "pe_ratio": None, 
        "recommendation": None, "current_price": None,
        "change_pct": None, "market_cap": None, "beta": None, "alpha_vs_nifty": None
    }
    
    try:
        stock_symbol = f"{ticker}.NS"
        if ticker == "NIFTY": stock_symbol = "^NSEI"
        stock = yf.Ticker(stock_symbol)
        
        info = stock.info
        hist = stock.history(period="3mo")
        
        if not hist.empty:
            current = float(round(hist['Close'].iloc[-1], 2))
            prev = float(round(hist['Close'].iloc[-2], 2)) if len(hist) > 1 else current
            data["current_price"] = current
            data["change_pct"] = float(round(((current - prev) / prev) * 100, 2)) if prev else 0.0
            
            rsi = compute_rsi(hist)
            if rsi is not None:
                data["rsi"] = float(round(rsi, 2))
                
            if nifty_hist is not None and not nifty_hist.empty and len(hist) >= 2:
                # 3 month return
                stock_ret = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                nifty_ret = ((nifty_hist['Close'].iloc[-1] - nifty_hist['Close'].iloc[0]) / nifty_hist['Close'].iloc[0]) * 100
                data["alpha_vs_nifty"] = float(round(stock_ret - nifty_ret, 2))
        
        pe = info.get("trailingPE", info.get("forwardPE"))
        if pe is not None:
            data["pe_ratio"] = float(round(pe, 2))
            
        data["market_cap"] = info.get("marketCap")
        data["beta"] = info.get("beta")
            
        rec = info.get("recommendationKey")
        if rec and rec != "none":
            data["recommendation"] = str(rec).replace('_', ' ').title()
            
    except Exception as e:
        logger.warning(f"YFinance failed for {ticker}: {e}")
        
    return data

def run_eod_fetch():
    if not supabase:
        logger.error("Supabase client not initialized")
        return {"error": "Supabase not configured"}
        
    results = []
    logger.info("Starting background EOD fetch for NIFTY 50 strictly using YFinance...")
    
    # Pre-fetch Nifty history for relative alpha calculation
    logger.info("Pre-fetching NIFTY 50 baseline...")
    try:
        nifty_baseline = yf.Ticker("^NSEI").history(period="3mo")
    except:
        nifty_baseline = None

    for ticker in NIFTY_50_TICKERS:
        data = fetch_single_ticker(ticker, nifty_baseline)
        
        # Upsert
        try:
            res = supabase.table('nifty_stocks').upsert(data).execute()
            results.append(data)
        except Exception as e:
            logger.error(f"Supabase upsert failed for {ticker}: {e}")
        
        time.sleep(1.0) # YFinance requires less resting time
        
    logger.info("Finished background EOD fetch.")
    return {"status": "success", "count": len(results)}
