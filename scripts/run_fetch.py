"""
Standalone EOD Stock Fetcher script for GitHub Actions.
Reads SUPABASE_URL and SUPABASE_KEY from environment variables.
"""
import os
import time
import logging
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

def fetch_single_ticker(ticker: str):
    data = {"symbol": ticker, "rsi": None, "pe_ratio": None, "recommendation": None, "current_price": None}
    try:
        stock = yf.Ticker(f"{ticker}.NS")
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
        logger.warning(f"Failed for {ticker}: {e}")
    return data

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info(f"Starting EOD fetch for {len(NIFTY_50_TICKERS)} tickers...")

    success = 0
    for ticker in NIFTY_50_TICKERS:
        data = fetch_single_ticker(ticker)
        try:
            supabase.table('nifty_stocks').upsert(data).execute()
            success += 1
            logger.info(f"✅  {ticker}: price={data['current_price']} pe={data['pe_ratio']} rsi={data['rsi']}")
        except Exception as e:
            logger.error(f"❌  Supabase upsert failed for {ticker}: {e}")
        time.sleep(1.0)

    logger.info(f"Finished. {success}/{len(NIFTY_50_TICKERS)} stocks updated.")

if __name__ == "__main__":
    main()
