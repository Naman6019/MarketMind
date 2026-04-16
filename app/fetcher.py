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

def fetch_single_ticker(ticker: str):
    data = {"symbol": ticker, "rsi": None, "pe_ratio": None, "recommendation": None, "current_price": None}
    
    try:
        stock_symbol = f"{ticker}.NS"
        if ticker == "NIFTY": stock_symbol = "^NSEI"
        stock = yf.Ticker(stock_symbol)
        
        info = stock.info
        hist = stock.history(period="3mo")
        
        if not hist.empty:
            data["current_price"] = float(round(hist['Close'].iloc[-1], 2))
            rsi = compute_rsi(hist)
            if rsi is not None:
                data["rsi"] = float(round(rsi, 2))
        
        pe = info.get("trailingPE", info.get("forwardPE"))
        if pe is not None:
            data["pe_ratio"] = float(round(pe, 2))
            
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
    for ticker in NIFTY_50_TICKERS:
        data = fetch_single_ticker(ticker)
        
        # Upsert
        try:
            res = supabase.table('nifty_stocks').upsert(data).execute()
            results.append(data)
        except Exception as e:
            logger.error(f"Supabase upsert failed for {ticker}: {e}")
        
        time.sleep(1.0) # YFinance requires less resting time
        
    logger.info("Finished background EOD fetch.")
    return {"status": "success", "count": len(results)}
