import os
import logging
import time
import requests
import zipfile
import io
import pandas as pd
from datetime import datetime, date
import pytz
from jugaad_data.nse import bhavcopy_save, NSELive
from nsetools import Nse
import yfinance as yf

logger = logging.getLogger(__name__)

def fetch_nse_bhavcopy(trade_date: date) -> list:
    """
    Downloads NSE bhavcopy CSV for trade_date using jugaad-data.
    Filters to EQ series and maps to Supabase schema.
    """
    temp_dir = "/tmp/nse_bhavcopy"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # jugaad-data: bhavcopy_save returns the path to the saved file
        # Note: trade_date should be a datetime.date object
        file_path = bhavcopy_save(trade_date, temp_dir)
        
        df = pd.read_csv(file_path)
        
        # Filter for EQ series only
        if 'SERIES' in df.columns:
            df = df[df['SERIES'] == 'EQ']
            
        # Mapping columns as per instruction:
        # SYMBOL -> symbol, OPEN -> open, HIGH -> high, LOW -> low, 
        # CLOSE -> close, TOTTRDQTY -> volume, TIMESTAMP -> date
        # Note: We will ALSO include current_price and change_pct to match EXISTING schema
        
        results = []
        for _, row in df.iterrows():
            # Calculate change_pct if PREVCLOSE is available
            change_pct = 0.0
            if 'PREVCLOSE' in row and row['PREVCLOSE'] != 0:
                change_pct = ((row['CLOSE'] - row['PREVCLOSE']) / row['PREVCLOSE']) * 100
                
            results.append({
                "symbol": row['SYMBOL'],
                "open": row['OPEN'],
                "high": row['HIGH'],
                "low": row['LOW'],
                "close": row['CLOSE'],
                "volume": row['TOTTRDQTY'],
                "date": row['TIMESTAMP'],
                # For compatibility with existing schema:
                "current_price": row['CLOSE'],
                "change_pct": round(float(change_pct), 2)
            })
            
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return results
    except Exception as e:
        logger.warning(f"NSE Bhavcopy unavailable for {trade_date}: {e}")
        return []

def fetch_bse_bhavcopy(trade_date: date) -> list:
    """
    Downloads BSE bhavcopy ZIP from official archive.
    Parses CSV in-memory and maps to Supabase schema.
    """
    # BSE URL format: https://www.bseindia.com/download/BhavCopy/Equity/EQ{DDMMYY}_CSV.ZIP
    date_str = trade_date.strftime("%d%m%y")
    url = f"https://www.bseindia.com/download/BhavCopy/Equity/EQ{date_str}_CSV.ZIP"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # BSE filename inside ZIP is usually EQ{DDMMYY}.CSV
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                df = pd.read_csv(f)
                
        # BSE columns: SC_CODE, SC_NAME, OPEN, HIGH, LOW, CLOSE, LAST, PREVCLOSE, NO_TRADES, NO_SHRS, NET_TURNOV, TDCLOINDI
        # Mapping: SC_CODE -> symbol, OPEN -> open, ...
        
        results = []
        for _, row in df.iterrows():
            change_pct = 0.0
            if 'PREVCLOSE' in row and row['PREVCLOSE'] != 0:
                change_pct = ((row['CLOSE'] - row['PREVCLOSE']) / row['PREVCLOSE']) * 100
                
            results.append({
                "symbol": str(row['SC_CODE']),
                "exchange": "BSE",
                "open": row['OPEN'],
                "high": row['HIGH'],
                "low": row['LOW'],
                "close": row['CLOSE'],
                "current_price": row['CLOSE'],
                "change_pct": round(float(change_pct), 2),
                "volume": row['NO_SHRS'],
                "date": trade_date.strftime("%Y-%m-%d")
            })
        return results
    except Exception as e:
        logger.warning(f"BSE Bhavcopy unavailable for {trade_date}: {e}")
        return []

def fetch_live_quote(symbol: str) -> dict:
    """
    Fetches live quote with fallbacks: jugaad-data -> nsetools -> yfinance.
    """
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    
    # Market hours: 09:15 to 15:30 IST
    market_open = now_ist.weekday() < 5 and \
                  (now_ist.hour * 60 + now_ist.minute >= 555) and \
                  (now_ist.hour * 60 + now_ist.minute <= 930)
    
    # 1. PRIMARY: jugaad-data NSELive (only during market hours)
    if market_open:
        try:
            n = NSELive()
            quote = n.stock_quote(symbol)
            if quote and 'priceInfo' in quote:
                return {
                    'symbol': symbol,
                    'last_price': quote['priceInfo']['lastPrice'],
                    'open': quote['priceInfo']['open'],
                    'high': quote['priceInfo']['intraDayHighLow']['max'],
                    'low': quote['priceInfo']['intraDayHighLow']['min'],
                    'prev_close': quote['priceInfo']['previousClose'],
                    'change': quote['priceInfo']['change'],
                    'pchange': quote['priceInfo']['pChange'],
                    'source': 'NSELive'
                }
        except Exception as e:
            logger.debug(f"NSELive failed for {symbol}: {e}")
            time.sleep(1) # Small delay before fallback

    # 2. FALLBACK: nsetools
    try:
        nse = Nse()
        q = nse.get_quote(symbol.lower())
        if q and 'lastPrice' in q:
            return {
                'symbol': symbol,
                'last_price': q['lastPrice'],
                'open': q['open'],
                'high': q['dayHigh'],
                'low': q['dayLow'],
                'prev_close': q['previousClose'],
                'change': q['change'],
                'pchange': q['pChange'],
                'source': 'nsetools'
            }
    except Exception as e:
        logger.debug(f"nsetools failed for {symbol}: {e}")

    # 3. FINAL FALLBACK: YFinance
    try:
        ticker = f"{symbol}.NS"
        stock = yf.Ticker(ticker)
        # info can be slow, but it's our final fallback
        info = stock.info
        if 'currentPrice' in info:
            return {
                'symbol': symbol,
                'last_price': info['currentPrice'],
                'open': info.get('open'),
                'high': info.get('dayHigh'),
                'low': info.get('dayLow'),
                'prev_close': info.get('previousClose'),
                'change': info['currentPrice'] - info.get('previousClose', info['currentPrice']),
                'pchange': ((info['currentPrice'] - info.get('previousClose', info['currentPrice'])) / info.get('previousClose', 1)) * 100,
                'source': 'yfinance'
            }
    except Exception as e:
        logger.error(f"All quote sources failed for {symbol}: {e}")
        
    return None
