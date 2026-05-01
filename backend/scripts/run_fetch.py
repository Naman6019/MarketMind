"""
Standalone EOD Stock Fetcher script for GitHub Actions.
Reads SUPABASE_URL and SUPABASE_KEY from environment variables.
"""
import os
# DEPRECATED: Replaced by provider adapter layer. Do not use in new code.
import sys
import time
import logging
import math
import pandas as pd
import yfinance as yf
from datetime import date, datetime, timezone
from supabase import create_client

# Add parent directory to path to allow importing from app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.stock_universe import load_stock_universe

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
STOCK_INFO_ENRICH_LIMIT = int(os.environ.get("STOCK_INFO_ENRICH_LIMIT", "120"))
STOCK_YFINANCE_FALLBACK_LIMIT = int(os.environ.get("STOCK_YFINANCE_FALLBACK_LIMIT", "150"))
supabase = None


def build_stock_price_upsert_payload(ticker: str, row: dict, source: str = "nse_bhavcopy") -> dict:
    return {
        "symbol": ticker.upper(),
        "date": row.get("date"),
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row.get("close") or row.get("current_price"),
        "adj_close": row.get("close") or row.get("current_price"),
        "volume": row.get("volume"),
        "source": source,
    }


def build_stock_metadata_payload(ticker: str, meta: dict) -> dict:
    return {
        "symbol": ticker.upper(),
        "exchange": "NSE",
        "company_name": meta.get("company_name") or ticker.upper(),
        "isin": meta.get("isin"),
        "series": "EQ",
        "industry": meta.get("industry"),
        "is_active": True,
    }


def create_provider_run(job_name: str, provider: str, attempted: int) -> str | None:
    try:
        res = supabase.table("data_provider_runs").insert({
            "provider": provider,
            "job_name": job_name,
            "status": "running",
            "symbols_attempted": attempted,
        }).execute()
        return (res.data or [{}])[0].get("id")
    except Exception as e:
        logger.warning("Could not create provider run row: %s", e)
        return None


def finish_provider_run(run_id: str | None, status: str, succeeded: int, failed: int, error_summary: str | None = None):
    if not run_id:
        return
    try:
        supabase.table("data_provider_runs").update({
            "status": status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "symbols_succeeded": succeeded,
            "symbols_failed": failed,
            "error_summary": error_summary,
        }).eq("id", run_id).execute()
    except Exception as e:
        logger.warning("Could not finish provider run row: %s", e)

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

def fetch_single_ticker_yfinance(ticker: str, category: str, nifty_hist: pd.DataFrame = None):
    """Old YFinance fetch logic as fallback"""
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
            data["change_pct"] = float(round(((current - prev) / prev) * 100, 2)) if prev else None
            
            rsi = compute_rsi(hist)
            if rsi is not None:
                data["rsi"] = float(round(rsi, 2))
                
            if nifty_hist is not None and not nifty_hist.empty and len(hist) >= 2:
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
        logger.warning(f"Fallback YFinance failed for {ticker}: {e}")
        
    for key, value in data.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            data[key] = None
    return data

def get_local_history(symbol: str, days: int = 100):
    """Fetch EOD history from Supabase for local calculations."""
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
        logger.error(f"Failed to fetch local history for {symbol}: {e}")
    return pd.DataFrame()

def main():
    global supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    stock_universe = load_stock_universe()
    universe_tickers = list(stock_universe.keys())
    run_id = create_provider_run("sync_nse_eod_prices", "nse", len(universe_tickers))
    
    logger.info(f"Starting EOD fetch for {len(universe_tickers)} tickers...")
    
    # 1. Primary: NSE Bhavcopy
    from app.nse_client import fetch_nse_bhavcopy
    today = date.today()
    bhavcopy_data = fetch_nse_bhavcopy(today)
    
    if bhavcopy_data:
        logger.info(f"Successfully fetched NSE Bhavcopy with {len(bhavcopy_data)} rows.")
        bhav_map = {row['symbol']: row for row in bhavcopy_data}
        
        # Pre-fetch NIFTY history from DB for Alpha calculation
        nifty_hist = get_local_history("NIFTY", 100)
        
        success = 0
        failed = 0
        for index, ticker in enumerate(universe_tickers):
            if ticker in bhav_map:
                b_row = bhav_map[ticker]
                meta = stock_universe.get(ticker, {})
                category = meta.get("category", "Unknown")
                
                # 1. Start with Bhavcopy data
                data = {
                    "symbol": ticker,
                    "category": category,
                    "current_price": b_row['current_price'],
                    "change_pct": b_row['change_pct'],
                    "rsi": None,
                    "pe_ratio": None,
                    "recommendation": None,
                    "market_cap": None,
                    "beta": None,
                    "alpha_vs_nifty": None
                }

                # 2. Calculate local metrics from DB history.
                hist = get_local_history(ticker, 30) # Need ~15-20 days for RSI
                if not hist.empty:
                    # RSI
                    rsi = compute_rsi(hist)
                    data["rsi"] = round(float(rsi), 2) if rsi is not None else None
                    
                    # Alpha (vs NIFTY baseline from DB)
                    if not nifty_hist.empty and len(hist) >= 20:
                        # Simple Alpha: Stock Return - Nifty Return over the same window
                        stock_ret = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                        n_start = nifty_hist[nifty_hist['date'] >= hist['date'].iloc[0]]
                        if not n_start.empty:
                            nifty_ret = ((nifty_hist['Close'].iloc[-1] - n_start['Close'].iloc[0]) / n_start['Close'].iloc[0]) * 100
                            data["alpha_vs_nifty"] = round(float(stock_ret - nifty_ret), 2)

                try:
                    supabase.table('stocks').upsert(
                        build_stock_metadata_payload(ticker, meta),
                        on_conflict='symbol'
                    ).execute()
                    supabase.table('stock_prices_daily').upsert(
                        build_stock_price_upsert_payload(ticker, b_row),
                        on_conflict='symbol,date,source'
                    ).execute()
                    supabase.table('nifty_stocks').upsert(data).execute()
                    
                    # Save to history table
                    history_row = {
                        "symbol": ticker,
                        "date": b_row['date'],
                        "close": b_row['current_price'],
                        "volume": b_row['volume']
                    }
                    supabase.table('stock_history').upsert(history_row, on_conflict='symbol,date').execute()
                    success += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Supabase upsert failed for {ticker}: {e}")
                
        logger.info(f"Finished NSE Bhavcopy fetch. {success} stocks updated.")
        finish_provider_run(run_id, "success" if failed == 0 else "partial", success, failed)
        
        # Note: We are NOT falling back if bhavcopy succeeded for some stocks 
        # but missing some tickers. The prompt says "If NSE bhavcopy returns empty... fall back".
    else:
        logger.warning("NSE Bhavcopy returned empty. Falling back to YFinance...")
        
        logger.info("Pre-fetching NIFTY 50 baseline...")
        try:
            nifty_baseline = yf.Ticker("^NSEI").history(period="3mo")
        except:
            nifty_baseline = None

        success = 0
        failed = 0
        for ticker in universe_tickers[:STOCK_YFINANCE_FALLBACK_LIMIT]:
            category = stock_universe.get(ticker, {}).get("category", "Unknown")
            data = fetch_single_ticker_yfinance(ticker, category, nifty_baseline)
            try:
                meta = stock_universe.get(ticker, {})
                supabase.table('stocks').upsert(
                    build_stock_metadata_payload(ticker, meta),
                    on_conflict='symbol'
                ).execute()
                supabase.table('stock_prices_daily').upsert(
                    build_stock_price_upsert_payload(
                        ticker,
                        {
                            "date": date.today().strftime("%Y-%m-%d"),
                            "close": data['current_price'],
                            "volume": None,
                        },
                        source="yfinance",
                    ),
                    on_conflict='symbol,date,source'
                ).execute()
                supabase.table('nifty_stocks').upsert(data).execute()
                
                # Save to history table
                history_row = {
                    "symbol": ticker,
                    "date": date.today().strftime("%Y-%m-%d"),
                    "close": data['current_price'],
                    "volume": None
                }
                supabase.table('stock_history').upsert(history_row, on_conflict='symbol,date').execute()
                
                success += 1
            except Exception as e:
                failed += 1
                logger.error(f"Supabase upsert failed for {ticker}: {e}")
            time.sleep(1.0)
        
        logger.info(f"Finished YFinance fallback fetch. {success} stocks updated.")
        finish_provider_run(run_id, "success" if failed == 0 else "partial", success, failed)

if __name__ == "__main__":
    main()
