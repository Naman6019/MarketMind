"""
Standalone EOD Stock Fetcher script for GitHub Actions.
Reads SUPABASE_URL and SUPABASE_KEY from environment variables.
"""
import os
import time
import logging
import math
import pandas as pd
import yfinance as yf
from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

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

def compute_rsi(data: pd.DataFrame, window=14):
    if len(data) < window:
        return None
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])

def fetch_single_ticker(ticker: str, category: str, nifty_hist: pd.DataFrame = None):
    data = {
        "symbol": ticker, "category": category, "rsi": None, "pe_ratio": None, 
        "recommendation": None, "current_price": None,
        "change_pct": None, "market_cap": None, "beta": None, "alpha_vs_nifty": None
    }
    try:
        stock = yf.Ticker(f"{ticker}.NS")
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
        logger.warning(f"Failed for {ticker}: {e}")
        
    # --- NEW CLEANUP BLOCK ---
    # Convert any NaN or Infinity floats to None (JSON null)
    for key, value in data.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            data[key] = None
            
    return data

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    ticker_groups = [
        (NIFTY_50_TICKERS, "Large Cap"),
        (MIDCAP_TICKERS, "Mid Cap"),
        (SMALLCAP_TICKERS, "Small Cap")
    ]
    
    total_tickers = sum(len(g[0]) for g in ticker_groups)
    logger.info(f"Starting EOD fetch for {total_tickers} tickers...")
    
    logger.info("Pre-fetching NIFTY 50 baseline...")
    try:
        nifty_baseline = yf.Ticker("^NSEI").history(period="3mo")
    except:
        nifty_baseline = None

    success = 0
    for tickers, category in ticker_groups:
        logger.info(f"Processing {category} group ({len(tickers)} tickers)...")
        for ticker in tickers:
            data = fetch_single_ticker(ticker, category, nifty_baseline)
            try:
                supabase.table('nifty_stocks').upsert(data).execute()
                success += 1
                logger.info(f"✅  {ticker} ({category}): price={data['current_price']} pe={data['pe_ratio']} rsi={data['rsi']}")
            except Exception as e:
                logger.error(f"❌  Supabase upsert failed for {ticker}: {e}")
            time.sleep(1.0)

    logger.info(f"Finished. {success}/{total_tickers} stocks updated.")


if __name__ == "__main__":
    main()
