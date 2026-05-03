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


NSE_ARCHIVE_BASE_URL = "https://nsearchives.nseindia.com/content/cm"
NSE_HEADERS = {
    "User-Agent": "MarketMind/1.0 (Language=python)",
    "Accept-Language": "*",
}


def fetch_nse_bhavcopy(trade_date: date) -> list:
    """
    Downloads NSE CM-UDiFF bhavcopy for trade_date and maps it to stock_prices_daily.
    """
    direct_rows = fetch_nse_udiff_bhavcopy(trade_date)
    if direct_rows:
        return direct_rows

    # Fallback for older dates / transient archive failures.
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
            change_pct = None
            if 'PREVCLOSE' in row and row['PREVCLOSE'] != 0:
                change_pct = ((row['CLOSE'] - row['PREVCLOSE']) / row['PREVCLOSE']) * 100
                
            results.append({
                "symbol": row['SYMBOL'],
                "open": row['OPEN'],
                "high": row['HIGH'],
                "low": row['LOW'],
                "close": row['CLOSE'],
                "adj_close": row['CLOSE'],
                "volume": row['TOTTRDQTY'],
                "value_traded": _safe_number(row.get("TOTTRDVAL")),
                "delivery_qty": None,
                "delivery_percent": None,
                "date": _normalize_date_string(row['TIMESTAMP']),
                "source": "nse_bhavcopy",
                # For compatibility with existing schema:
                "current_price": row['CLOSE'],
                "change_pct": round(float(change_pct), 2) if change_pct is not None else None
            })
            
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return results
    except Exception as e:
        logger.warning(f"NSE Bhavcopy unavailable for {trade_date}: {e}")
        return []


def fetch_nse_udiff_bhavcopy(trade_date: date) -> list[dict]:
    """
    Downloads NSE CM-UDiFF Common Bhavcopy Final zip directly from NSE archives.
    """
    date_key = trade_date.strftime("%Y%m%d")
    filename = f"BhavCopy_NSE_CM_0_0_0_{date_key}_F_0000.csv.zip"
    url = f"{NSE_ARCHIVE_BASE_URL}/{filename}"

    try:
        response = requests.get(url, headers=NSE_HEADERS, timeout=30)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            csv_name = next((name for name in archive.namelist() if name.lower().endswith(".csv")), None)
            if not csv_name:
                logger.warning("NSE UDiFF bhavcopy zip has no CSV for %s", trade_date)
                return []
            with archive.open(csv_name) as csv_file:
                return parse_nse_bhavcopy_csv(csv_file)
    except Exception as exc:
        logger.warning("NSE UDiFF bhavcopy unavailable for %s: %s", trade_date, exc)
        return []


def parse_nse_bhavcopy_csv(csv_file) -> list[dict]:
    df = pd.read_csv(csv_file)
    if {"TckrSymb", "OpnPric", "HghPric", "LwPric", "ClsPric", "TradDt"}.issubset(df.columns):
        return _parse_udiff_bhavcopy_df(df)
    return _parse_legacy_bhavcopy_df(df)


def _parse_udiff_bhavcopy_df(df: pd.DataFrame) -> list[dict]:
    if "Sgmt" in df.columns:
        df = df[df["Sgmt"] == "CM"]
    if "Src" in df.columns:
        df = df[df["Src"] == "NSE"]
    if "FinInstrmTp" in df.columns:
        df = df[df["FinInstrmTp"] == "STK"]
    if "SctySrs" in df.columns:
        df = df[df["SctySrs"].isin(["EQ", "BE"])]

    results = []
    for _, row in df.iterrows():
        symbol = str(row.get("TckrSymb", "")).strip().upper()
        if not symbol:
            continue
        close = _safe_number(row.get("ClsPric"))
        prev_close = _safe_number(row.get("PrvsClsgPric"))
        change_pct = None
        if close is not None and prev_close not in (None, 0):
            change_pct = ((close - prev_close) / prev_close) * 100

        results.append({
            "symbol": symbol,
            "date": str(row.get("TradDt"))[:10],
            "open": _safe_number(row.get("OpnPric")),
            "high": _safe_number(row.get("HghPric")),
            "low": _safe_number(row.get("LwPric")),
            "close": close,
            "adj_close": close,
            "volume": _safe_int(row.get("TtlTradgVol")),
            "value_traded": _safe_number(row.get("TtlTrfVal")),
            "delivery_qty": None,
            "delivery_percent": None,
            "source": "nse_bhavcopy",
            "current_price": close,
            "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
        })
    return results


def _parse_legacy_bhavcopy_df(df: pd.DataFrame) -> list[dict]:
    if "SERIES" in df.columns:
        df = df[df["SERIES"] == "EQ"]

    results = []
    for _, row in df.iterrows():
        close = _safe_number(row.get("CLOSE"))
        prev_close = _safe_number(row.get("PREVCLOSE"))
        change_pct = None
        if close is not None and prev_close not in (None, 0):
            change_pct = ((close - prev_close) / prev_close) * 100

        results.append({
            "symbol": str(row.get("SYMBOL", "")).strip().upper(),
            "open": _safe_number(row.get("OPEN")),
            "high": _safe_number(row.get("HIGH")),
            "low": _safe_number(row.get("LOW")),
            "close": close,
            "adj_close": close,
            "volume": _safe_int(row.get("TOTTRDQTY")),
            "value_traded": _safe_number(row.get("TOTTRDVAL")),
            "delivery_qty": None,
            "delivery_percent": None,
            "date": _normalize_date_string(row.get("TIMESTAMP")),
            "source": "nse_bhavcopy",
            "current_price": close,
            "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
        })
    return [row for row in results if row["symbol"]]


def _safe_number(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_date_string(value):
    if pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return str(value)[:10]


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
            change_pct = None
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
                "change_pct": round(float(change_pct), 2) if change_pct is not None else None,
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
