import os
import json
import logging
import asyncio
import sys
import time
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Literal
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
import pytz
import numpy as np
import pandas as pd

# Redirect yfinance cache to the writable /tmp directory
os.environ["YFINANCE_CACHE_DIR"] = "/tmp/yfinance_cache"
yf.set_tz_cache_location("/tmp/yfinance_tz_cache")

# Must run before any os.environ.get()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.database import supabase
from app.fetcher import run_eod_fetch
from app.nse_client import fetch_live_quote
from app.stock_universe import resolve_stock_symbol
from app.services.quant_service import (
    build_stock_compare,
    build_stock_profile,
    get_stock_financials,
    get_stock_price_history,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://marketmind.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "MarketMind API is running. Use /health for health checks."}

@app.get("/health")
def health():
    return {"status": "ok"}

class ChatRequest(BaseModel):
    query: str
    asset_type: Literal["auto", "stock", "mutual_fund"] = "auto"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
IST = pytz.timezone('Asia/Kolkata')
QUANT_CACHE: Dict[str, Any] = {}
QUANT_CACHE_TTL_SECONDS = 120

async def function_ollama_chat(messages, format="json", max_retries=2):
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        logger.error("Missing GROQ_API_KEY in environment!")
        return None
        
    req_messages = [dict(m) for m in messages]
    payload = {
        "model": GROQ_MODEL,
    }
    
    if format == "json":
        payload["response_format"] = {"type": "json_object"}
        if "json" not in req_messages[0]["content"].lower():
            req_messages[0]["content"] += "\nReturn output strictly in JSON format."
            
    payload["messages"] = req_messages
            
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(GROQ_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Groq API Error: {e}")
            return None

async def route_query(query: str, asset_type: str = "auto") -> dict:
    """Agent 1: Router"""
    asset_instruction = ""
    if asset_type == "mutual_fund":
        asset_instruction = """
The user explicitly selected Mutual Funds mode. Treat ambiguous names as mutual fund scheme names, not stocks.
Preserve category words from the user query like Small Cap, Flexi Cap, Mid Cap, Large Cap, Index, Direct, Growth in compare_entities.
Do not classify mutual fund requests as stock screening requests.
"""
    elif asset_type == "stock":
        asset_instruction = """
The user explicitly selected Stocks mode. Treat ambiguous names as stocks or indices, not mutual fund schemes.
Do not classify stock requests as mutual fund requests.
"""

    system_prompt = """You are the Router Agent for MarketMind. Classify the user query intent.
If the query asks to filter, list, or screen stocks (e.g., "Find stocks with PE < 20", "Show me oversold stocks", "Mid cap stocks with RSI < 30"), set intent to 'screen' and populate 'screen_filters'.
If the query asks to compare two or more mutual funds or stocks, set intent to 'compare' and populate 'compare_entities' with a list of their names (e.g. ["HDFC Flexi Cap", "Parag Parikh Flexi Cap"]).
Otherwise, use 'quant', 'news', 'both', or 'general'.
Extract primary NSE/BSE ticker explicitly (e.g. RELIANCE.NS, ^NSEI for Nifty). 

Check for historical period mentions (e.g., '1m', '1y') and sentiment mentions.

Output strict JSON only format:
{
  "intent": "quant|news|both|general|screen|compare",
  "ticker": "TICKER.NS",
  "historical_period": "1mo|1y|5y|max", 
  "sentiment_flag": true/false,
  "screen_filters": {
    "min_pe": 0,
    "max_pe": 100,
    "rsi_range": {"min": 0, "max": 100},
    "category": "Large Cap|Mid Cap|Small Cap"
  },
  "compare_entities": ["Asset 1 Name", "Asset 2 Name"]
}
If a filter is not mentioned, exclude it from screen_filters. Default historical_period to "1mo" if not mentioned. Default sentiment_flag to false unless news sentiment is requested.
    """ + asset_instruction
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
    
    result = await function_ollama_chat(messages, format="json")
    if result:
        try:
            return json.loads(result)
        except Exception as e:
            logger.error(f"Router parsing error: {e}")
    return {"intent": "general", "ticker": None}

def calculate_beta(stock_returns, nifty_returns):
    if len(stock_returns) < 10 or len(stock_returns) != len(nifty_returns):
        return 1.0
    try:
        # Use simple linear regression for beta (Slope of Stock Returns vs Market Returns)
        # Handle cases with constant returns or zero variance
        if np.var(nifty_returns) < 1e-9:
            return 1.0
        
        cov_matrix = np.cov(stock_returns, nifty_returns)
        if cov_matrix.shape == (2, 2):
            cov = cov_matrix[0][1]
            var = np.var(nifty_returns)
            beta = cov / var
            # Sanity check: Beta for a Flexi Cap equity fund should not be near zero
            # If it is, it might indicate bad data alignment
            if abs(beta) < 0.05:
                return 1.0
            return round(float(beta), 2)
        return 1.0
    except:
        return 1.0

def calculate_alpha_beta_v2(stock_hist, nifty_hist):
    if stock_hist.empty or nifty_hist.empty or len(stock_hist) < 20 or len(nifty_hist) < 20:
        return {"alpha": "N/A", "beta": "N/A"}

    stock_hist = _normalize_price_df_index(stock_hist)
    nifty_hist = _normalize_price_df_index(nifty_hist)
    
    # Pre-process: ensure we have numeric data and no NaNs in Close
    s_close = stock_hist['Close'].ffill().dropna()
    n_close = nifty_hist['Close'].ffill().dropna()
    
    stock_returns = s_close.pct_change().dropna()
    nifty_returns = n_close.pct_change().dropna()
    
    # Align returns on the same dates
    aligned = stock_returns.to_frame('stock').join(nifty_returns.to_frame('nifty'), how='inner')
    
    if len(aligned) < 10: return {"alpha": "N/A", "beta": "N/A"}
    
    beta = calculate_beta(aligned['stock'].tolist(), aligned['nifty'].tolist())
    
    # Annualized Returns for Alpha
    # Using the first and last valid prices to get total return
    stock_ret_total = (s_close.iloc[-1] - s_close.iloc[0]) / s_close.iloc[0]
    nifty_ret_total = (n_close.iloc[-1] - n_close.iloc[0]) / n_close.iloc[0]
    
    days = (s_close.index[-1] - s_close.index[0]).days
    if days <= 0: return {"alpha": "N/A", "beta": beta}
    
    # Annualize the returns
    years = days / 365.25
    stock_ann_ret = (1 + stock_ret_total) ** (1 / years) - 1
    nifty_ann_ret = (1 + nifty_ret_total) ** (1 / years) - 1
    
    # Risk-free rate (approx 6.5% for India)
    rf = 0.065
    
    # Alpha = R_p - [R_f + Beta * (R_m - R_f)]
    alpha = (stock_ann_ret - (rf + beta * (nifty_ann_ret - rf))) * 100
    
    return {"alpha": round(alpha, 2), "beta": beta, "period_years": round(years, 1)}

def _normalize_price_df_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    normalized = df.copy()
    normalized.index = pd.to_datetime(normalized.index, errors="coerce")
    normalized = normalized[normalized.index.notna()]
    if getattr(normalized.index, "tz", None) is not None:
        normalized.index = normalized.index.tz_convert(None)
    normalized.index = normalized.index.normalize()
    return normalized.sort_index()

def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close

def fetch_source_neutral_fundamentals(symbol: str) -> dict | None:
    if not symbol:
        return None
    clean_symbol = symbol.replace(".NS", "").replace(".BO", "").upper()
    try:
        comparison = build_stock_compare([clean_symbol])
        item = next(iter((comparison.get("comparison") or {}).values()), None)
        if not item or item.get("error"):
            return None
        return item.get("fundamentals") or None
    except Exception as e:
        logger.warning("Stock fundamentals lookup failed for %s: %s", clean_symbol, e)
        return None

def enrich_with_source_neutral_fundamentals(data: dict, symbol: str) -> dict:
    fundamentals = fetch_source_neutral_fundamentals(symbol)
    if not fundamentals:
        return data
    enriched = dict(data)
    enriched["fundamentals"] = fundamentals
    if enriched.get("pe_ratio") in [None, "N/A"]:
        enriched["pe_ratio"] = fundamentals.get("pe", "N/A")
    if enriched.get("market_cap") in [None, "N/A"]:
        enriched["market_cap"] = fundamentals.get("market_cap", "N/A")
    return enriched

async def resolve_mf_ticker(entity_name: str) -> str:
    """Helper to map a name to a yfinance-compatible ticker or ISIN."""
    fallback_map = {
        "hdfc flexi cap": "0P0000XW94.BO",
        "parag parikh flexi cap": "0P0000YWL2.BO",
        "quant small cap": "0P0000XW86.BO",
        "nippon india small cap": "0P0000XVUA.BO"
    }
    ent_lower = entity_name.lower()
    for key, ticker in fallback_map.items():
        if key in ent_lower:
            return ticker
    return None

def fetch_quant_data(ticker: str, period: str = "1mo") -> dict:
    """Agent 2: Quant Data"""
    if not ticker: return {"error": "No ticker identified"}
    
    clean_ticker = ticker.replace('.NS', '').replace('.BO', '').replace('^NSEI', 'NIFTY')

    cache_key = f"{clean_ticker}:{period}"
    cached_entry = QUANT_CACHE.get(cache_key)
    now_ts = time.time()
    if cached_entry and (now_ts - cached_entry["ts"]) < QUANT_CACHE_TTL_SECONDS:
        return cached_entry["data"]

    def cache_and_return(data: dict) -> dict:
        QUANT_CACHE[cache_key] = {"ts": time.time(), "data": data}
        return data

    def get_local_quant_snapshot(symbol: str) -> dict | None:
        if not supabase:
            return None
        try:
            snapshot_row = None
            snapshot_res = supabase.table('nifty_stocks').select('*').eq('symbol', symbol).limit(1).execute()
            if snapshot_res.data:
                snapshot_row = snapshot_res.data[0]

            history_res = supabase.table('stock_history').select('close, date').eq('symbol', symbol).order('date', desc=True).limit(2).execute()
            history_rows = history_res.data or []

            if not snapshot_row and not history_rows:
                return None

            latest_close = history_rows[0]["close"] if history_rows else None
            prev_close = history_rows[1]["close"] if len(history_rows) > 1 else None
            price = snapshot_row.get("current_price") if snapshot_row else latest_close
            if price in [None, "N/A"]:
                price = latest_close

            change_pct = snapshot_row.get("change_pct") if snapshot_row else None
            if (change_pct in [None, "N/A"]) and latest_close is not None and prev_close not in [None, 0]:
                change_pct = round(((latest_close - prev_close) / prev_close) * 100, 2)

            data = {
                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST") + " (Supabase Local Snapshot)",
                "price": round(float(price), 2) if price not in [None, "N/A"] else "N/A",
                "change_pct": change_pct if change_pct not in [None, "N/A"] else "N/A",
                "pe_ratio": snapshot_row.get("pe_ratio", "N/A") if snapshot_row else "N/A",
                "market_cap": snapshot_row.get("market_cap", "N/A") if snapshot_row else "N/A",
                "beta": snapshot_row.get("beta", "N/A") if snapshot_row else "N/A",
                "alpha_vs_nifty": snapshot_row.get("alpha_vs_nifty", "N/A") if snapshot_row else "N/A",
                "historical_period": "1d (EOD local)",
                "rsi_14d": snapshot_row.get("rsi", "N/A") if snapshot_row else "N/A",
                "tv_recommendation": snapshot_row.get("recommendation", "N/A") if snapshot_row else "N/A"
            }

            if symbol == "NIFTY":
                data["beta"] = 1.0
                data["alpha_vs_nifty"] = 0.0

            return enrich_with_source_neutral_fundamentals(data, symbol)
        except Exception as e:
            logger.warning(f"Supabase local snapshot error for {symbol}: {e}")
            return None

    def get_live_nifty_snapshot() -> dict | None:
        try:
            nifty = yf.Ticker("^NSEI")
            intraday = nifty.history(period="1d", interval="1m")
            if intraday.empty:
                return None

            last_price = float(intraday["Close"].dropna().iloc[-1])
            local_data = get_local_quant_snapshot("NIFTY") or {}
            prev_close = local_data.get("price")
            change_pct = local_data.get("change_pct", "N/A")

            if prev_close not in [None, "N/A", 0]:
                change_pct = round(((last_price - float(prev_close)) / float(prev_close)) * 100, 2)

            return {
                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST") + " (Live NIFTY)",
                "price": round(last_price, 2),
                "change_pct": change_pct,
                "pe_ratio": "N/A",
                "market_cap": "N/A",
                "beta": 1.0,
                "alpha_vs_nifty": 0.0,
                "historical_period": "1d (live)",
                "rsi_14d": "N/A",
                "tv_recommendation": "N/A"
            }
        except Exception as e:
            logger.warning(f"Live NIFTY snapshot failed: {e}")
            return None

    if is_market_open():
        if clean_ticker == "NIFTY":
            local_nifty = get_local_quant_snapshot("NIFTY")
            if local_nifty:
                return cache_and_return(local_nifty)
            live_nifty = get_live_nifty_snapshot()
            if live_nifty:
                return cache_and_return(live_nifty)
        else:
            live_quote = fetch_live_quote(clean_ticker)
            if live_quote:
                local_data = get_local_quant_snapshot(clean_ticker) or {}
                live_data = {
                    "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST") + f" ({live_quote.get('source', 'Live Quote')})",
                    "price": round(float(live_quote["last_price"]), 2),
                    "change_pct": round(float(live_quote["pchange"]), 2) if live_quote.get("pchange") is not None else "N/A",
                    "pe_ratio": local_data.get("pe_ratio", "N/A"),
                    "market_cap": local_data.get("market_cap", "N/A"),
                    "beta": local_data.get("beta", "N/A"),
                    "alpha_vs_nifty": local_data.get("alpha_vs_nifty", "N/A"),
                    "historical_period": "1d (live)",
                    "rsi_14d": local_data.get("rsi_14d", "N/A"),
                    "tv_recommendation": local_data.get("tv_recommendation", "N/A")
                }
                return cache_and_return(enrich_with_source_neutral_fundamentals(live_data, clean_ticker))

    # Prefer local data for NIFTY off-market, and for off-market short-window queries.
    if clean_ticker == "NIFTY" or (period in ["1d", "1mo"] and not is_market_open()):
        local_data = get_local_quant_snapshot(clean_ticker)
        if local_data:
            return cache_and_return(local_data)

    try:
        if period not in ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]:
            period = "1y"
            
        stock = yf.Ticker(ticker)
        nifty = yf.Ticker("^NSEI")
        try:
            info = stock.info
        except Exception as e:
            logger.warning(f"YFinance info lookup failed for {ticker}: {e}")
            info = {}
        
        hist = stock.history(period=period)
        # Use 3y for stable risk metrics calculation
        calc_period = "3y"
        hist_calc = stock.history(period=calc_period)
        nifty_hist = nifty.history(period=calc_period)
        
        if hist.empty:
            local_data = get_local_quant_snapshot(clean_ticker)
            if local_data:
                return cache_and_return(local_data)
            return {"error": "No recent data found"}
            
        current_price = info.get('currentPrice', hist['Close'].iloc[-1])
        prev_close = info.get('previousClose', hist['Close'].iloc[-2] if len(hist) > 1 else current_price)
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        risk_metrics = calculate_alpha_beta_v2(hist_calc, nifty_hist)
        
        data = {
            "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            "price": round(current_price, 2),
            "change_pct": round(change_pct, 2),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
            "beta": risk_metrics["beta"],
            "alpha_vs_nifty": risk_metrics["alpha"],
            "risk_period": f"{risk_metrics.get('period_years', 3)}Y",
            "historical_period": period,
            "rsi_14d": "N/A",
            "tv_recommendation": "N/A",
            "aum": info.get("totalAssets", "N/A")
        }
        return cache_and_return(enrich_with_source_neutral_fundamentals(data, clean_ticker))
    except Exception as e:
        logger.error(f"Quant Error: {e}")
        local_data = get_local_quant_snapshot(clean_ticker)
        if local_data:
            return cache_and_return(local_data)
        return {"error": str(e)}

async def analyze_news_sentiment(news_items: list) -> list:
    """Agent: Sentiment Analyzer"""
    if not news_items: return []
    
    system_prompt = """You are a financial sentiment analyzer. Given a list of news headlines, assign a sentiment of POSITIVE, NEGATIVE, or NEUTRAL to each. 
Return exactly in this JSON format:
{"evaluations": [{"title": "Headline", "sentiment": "POSITIVE"}]}"""
    
    titles = "\\n".join([n['title'] for n in news_items])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": titles}
    ]
    
    result = await function_ollama_chat(messages, format="json")
    if result:
        try:
            evals = json.loads(result).get("evaluations", [])
            sentiment_map = {e["title"]: e["sentiment"] for e in evals}
            for n in news_items:
                n["sentiment"] = sentiment_map.get(n["title"], "NEUTRAL")
            return news_items
        except Exception as e:
            logger.error(f"Sentiment parsing error: {e}")
    
    for n in news_items: n["sentiment"] = "NEUTRAL"
    return news_items

def fetch_news(query: str, ticker: str, sentiment_flag: bool = False) -> list:
    """Agent 3: News Parser"""
    search_term = ticker.replace('.NS', '').replace('.BO', '') if ticker else query
    encoded_term = search_term.replace(' ', '+')
    rss_url = f"https://news.google.com/rss/search?q={encoded_term}+India+Stock+Market&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:6]: 
            news_items.append({
                "title": entry.title,
                "source": entry.source.title if hasattr(entry, 'source') else "News Source",
                "published": entry.published
            })
        return news_items
    except Exception as e:
        logger.error(f"News Error: {e}")
        return []

DISCLAIMER = "> ⚠️ **Disclaimer:** *MarketMind is an informational research tool only. Nothing presented here constitutes investment advice, a solicitation, or a recommendation to buy or sell any security. Always conduct your own research and consult a SEBI-registered Investment Advisor before making any financial decision.*"
DATA_UNAVAILABLE = "Data Unavailable"

ADVICE_REPLACEMENTS = {
    "attractive option for long-term investment": "candidate for further independent research",
    "attractive option": "candidate for further independent research",
    "investors should": "readers can",
    "investor should": "readers can",
    "buy or sell": "act on",
    "buy": "positive technical rating",
    "sell": "negative technical rating",
    "long-term investment": "longer-horizon research",
    "investment decision": "research decision",
    "invest": "research further",
}

def _is_missing(value: Any) -> bool:
    return value is None or value == "" or str(value).strip().upper() in {"N/A", "NA", "NONE", "NULL", "NAN"}

def _safe_value(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)

def _format_percent(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    if isinstance(value, str) and value.strip().endswith("%"):
        return value
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return _safe_value(value)

def _format_ratio_percent(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    if isinstance(value, str) and value.strip().endswith("%"):
        return value
    try:
        amount = float(value)
        percent = amount * 100 if abs(amount) <= 1 else amount
        return f"{percent:.2f}%"
    except (TypeError, ValueError):
        return _safe_value(value)

def _format_price(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return _safe_value(value)

def _format_inr_market_cap(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return _safe_value(value)

    if amount >= 1_00_00_00_00_000:
        return f"₹{amount / 1_00_00_00_00_000:.2f} lakh crore"
    if amount >= 1_00_00_000:
        return f"₹{amount / 1_00_00_000:.2f} crore"
    return f"₹{amount:,.0f}"

def _risk_period(data: dict) -> str:
    period = data.get("risk_period") or data.get("historical_period") or ""
    text = str(period).split()[0].upper()
    return text if text else "period"

def _safe_recommendation(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    text = str(value).strip().lower()
    mapping = {
        "strong buy": "Strong positive technical rating",
        "buy": "Positive technical rating",
        "sell": "Negative technical rating",
        "strong sell": "Strong negative technical rating",
    }
    return mapping.get(text, str(value))

def _is_unavailable_entity(data: Any) -> bool:
    return not isinstance(data, dict) or bool(data.get("error"))

def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, divider, *body])

def _stock_metric_rows(data: dict) -> list[tuple[str, str]]:
    period = _risk_period(data)
    rows = [
        ("Timestamp", _safe_value(data.get("timestamp"))),
        ("Price", _format_price(data.get("price"))),
        ("Change", _format_percent(data.get("change_pct"))),
        ("P/E Ratio", _safe_value(data.get("pe_ratio"))),
        ("Market Cap", _format_inr_market_cap(data.get("market_cap"))),
        (f"Beta ({period})", _safe_value(data.get("beta"))),
        (f"Alpha vs Nifty ({period})", _format_percent(data.get("alpha_vs_nifty"))),
        ("RSI (14D)", _safe_value(data.get("rsi_14d"))),
        ("Technical Rating", _safe_recommendation(data.get("tv_recommendation"))),
    ]
    fundamentals = data.get("fundamentals") or {}
    if fundamentals:
        rows.extend([
            ("Industry", _safe_value(fundamentals.get("industry"))),
            ("PB Ratio", _safe_value(fundamentals.get("pb"))),
            ("Dividend Yield", _format_ratio_percent(fundamentals.get("dividend_yield"))),
            ("Latest Quarterly Net Profit", _format_inr_market_cap(fundamentals.get("net_profit_qtr"))),
            ("Latest Quarterly Revenue", _format_inr_market_cap(fundamentals.get("revenue_qtr"))),
            ("ROCE", _format_ratio_percent(fundamentals.get("roce"))),
            ("ROE", _format_ratio_percent(fundamentals.get("roe"))),
            ("EPS TTM", _format_price(fundamentals.get("eps_ttm"))),
            ("EV / EBITDA", _safe_value(fundamentals.get("ev_ebitda"))),
            ("Sales Growth (3Y)", _format_ratio_percent(fundamentals.get("sales_growth_3y"))),
            ("Profit Growth (3Y)", _format_ratio_percent(fundamentals.get("profit_growth_3y"))),
            ("EPS Growth (3Y)", _format_ratio_percent(fundamentals.get("eps_growth_3y"))),
            ("Debt to Equity", _safe_value(fundamentals.get("debt_to_equity"))),
            ("Promoter Holding", _format_ratio_percent(fundamentals.get("promoter_holding"))),
            ("FII Holding", _format_ratio_percent(fundamentals.get("fii_holding"))),
            ("DII Holding", _format_ratio_percent(fundamentals.get("dii_holding"))),
            ("Data Source", _safe_value(fundamentals.get("source") or "source unavailable")),
        ])
    return rows

def _fund_metric_rows(data: dict) -> list[tuple[str, str]]:
    period = _risk_period(data)
    nav = data.get("nav", data.get("price"))
    nav_date = data.get("nav_date", data.get("date"))
    return [
        ("Matched Name", _safe_value(data.get("name"))),
        ("NAV", _format_price(nav)),
        ("NAV Date", _safe_value(nav_date)),
        ("Fund House", _safe_value(data.get("fund_house"))),
        ("Category", _safe_value(data.get("category"))),
        ("Expense Ratio", _safe_value(data.get("expense_ratio"))),
        ("AUM", _format_inr_market_cap(data.get("aum"))),
        (f"Beta ({period})", _safe_value(data.get("beta"))),
        (f"Alpha vs Nifty ({period})", _format_percent(data.get("alpha_vs_nifty"))),
    ]

def _looks_like_fund(data: dict) -> bool:
    return any(key in data for key in ["nav", "nav_date", "fund_house", "expense_ratio"]) and "timestamp" not in data

def _comparison_rows(comparison: dict) -> tuple[list[str], list[list[str]], list[str]]:
    entities = list(comparison.keys())
    valid_entities = {name: data for name, data in comparison.items() if not _is_unavailable_entity(data)}
    notes = [
        f"{name} could not be matched in MarketMind data."
        for name, data in comparison.items()
        if _is_unavailable_entity(data)
    ]
    for name, data in valid_entities.items():
        quality = data.get("data_quality") or {}
        message = quality.get("message")
        if message and message not in notes and quality.get("missing_fields"):
            notes.append(f"{name}: {message}")

    uses_fund_metrics = any(_looks_like_fund(data) for data in valid_entities.values())
    metric_rows = _fund_metric_rows if uses_fund_metrics else _stock_metric_rows
    metric_names: list[str] = []
    values_by_entity: dict[str, dict[str, str]] = {}

    for entity in entities:
        data = comparison.get(entity, {})
        values_by_entity[entity] = {}
        if _is_unavailable_entity(data):
            continue
        for metric, value in metric_rows(data):
            if metric not in metric_names:
                metric_names.append(metric)
            values_by_entity[entity][metric] = value

    if not metric_names:
        metric_names = ["Status"]

    rows = []
    for metric in metric_names:
        row = [metric]
        for entity in entities:
            row.append(values_by_entity.get(entity, {}).get(metric, DATA_UNAVAILABLE))
        rows.append(row)

    rows.append(["Data Status", *[
        DATA_UNAVAILABLE if _is_unavailable_entity(comparison.get(entity)) else "Available"
        for entity in entities
    ]])

    return ["Metric", *entities], rows, notes

def _data_table_markdown(intent: str, quant_data: Any, screening_results: list | None = None) -> tuple[str, list[str]]:
    notes: list[str] = []
    if intent == "screen":
        rows = []
        for item in screening_results or []:
            rows.append([
                _safe_value(item.get("symbol")),
                _safe_value(item.get("name")),
                _format_price(item.get("price")),
                _safe_value(item.get("pe_ratio")),
                _safe_value(item.get("rsi")),
            ])
        return _markdown_table(["Symbol", "Name", "Price", "P/E", "RSI"], rows or [["N/A", "N/A", "N/A", "N/A", "N/A"]]), notes

    if isinstance(quant_data, dict) and "comparison" in quant_data:
        headers, rows, notes = _comparison_rows(quant_data.get("comparison") or {})
        return _markdown_table(headers, rows), notes

    if isinstance(quant_data, dict) and quant_data.get("error"):
        return _markdown_table(["Metric", "Value"], [["Status", DATA_UNAVAILABLE], ["Reason", _safe_value(quant_data.get("error"))]]), notes

    if isinstance(quant_data, dict) and quant_data:
        rows = _fund_metric_rows(quant_data) if _looks_like_fund(quant_data) else _stock_metric_rows(quant_data)
        return _markdown_table(["Metric", "Value"], [[metric, value] for metric, value in rows]), notes

    return _markdown_table(["Metric", "Value"], [["Status", DATA_UNAVAILABLE]]), notes

def _news_markdown(news_data: list) -> str:
    if not news_data:
        return "- No recent news found from configured sources."

    rows = []
    for item in news_data[:6]:
        sentiment = f"**[{item.get('sentiment')}]** " if item.get("sentiment") else ""
        published = _safe_value(item.get("published"))
        source = _safe_value(item.get("source"))
        title = _safe_value(item.get("title"))
        rows.append(f"- {sentiment}{published} {source}: {title}")
    return "\n".join(rows) if rows else "- No recent news found from configured sources."

def _sanitize_research_text(text: str) -> str:
    sanitized = text or ""
    for bad, replacement in ADVICE_REPLACEMENTS.items():
        pattern = rf"\b{re.escape(bad)}\b"
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized

def _summary_subject(query: str, intent_info: dict, quant_data: Any) -> str:
    if isinstance(quant_data, dict) and "comparison" in quant_data:
        return " vs ".join(quant_data["comparison"].keys())
    ticker = intent_info.get("ticker")
    return ticker or query

def _snapshot_line(intent: str, quant_data: Any) -> str:
    if isinstance(quant_data, dict) and "comparison" in quant_data:
        available = sum(1 for item in quant_data["comparison"].values() if not _is_unavailable_entity(item))
        total = len(quant_data["comparison"])
        return f"{available} of {total} requested entities have structured MarketMind data."
    if isinstance(quant_data, dict) and quant_data.get("price"):
        return f"Latest structured price is {_format_price(quant_data.get('price'))} with {_format_percent(quant_data.get('change_pct'))} change."
    if isinstance(quant_data, dict) and quant_data.get("nav"):
        return f"Latest structured NAV is {_format_price(quant_data.get('nav'))}."
    return "Structured data is limited for this query."

async def run_stock_screen(filters: dict) -> list:
    """Stock screening against the local stock universe."""
    if not supabase:
        logger.error("Supabase client not initialized")
        return []

    try:
        query = supabase.table('nifty_stocks').select('*')
        
        min_pe = filters.get("min_pe")
        max_pe = filters.get("max_pe")
        if min_pe is not None: query = query.gte('pe_ratio', min_pe)
        if max_pe is not None: query = query.lte('pe_ratio', max_pe)
            
        rsi_range = filters.get("rsi_range", {})
        rsi_min = rsi_range.get("min")
        rsi_max = rsi_range.get("max")
        if rsi_min is not None: query = query.gte('rsi', rsi_min)
        if rsi_max is not None: query = query.lte('rsi', rsi_max)
            
        category = filters.get("category")
        if category: query = query.eq('category', category)
            
        res = query.execute()
        raw_results = res.data
        
        formatted_results = []
        for r in raw_results:
            formatted_results.append({
                "Symbol": r["symbol"],
                "Category": r.get("category", "N/A"),
                "RSI": round(r["rsi"], 2) if r.get("rsi") is not None else "N/A",
                "P/E": round(r["pe_ratio"], 2) if r.get("pe_ratio") is not None else "N/A",
                "Recommendation": r.get("recommendation", "N/A")
            })
        return formatted_results
    except Exception as e:
        logger.error(f"Stock screening DB error: {e}")
        return []

async def synthesis_response(query: str, intent_info: dict, quant_data: Any, news_data: list, screening_results: list = None) -> str:
    """Synthesis Core"""
    
    intent = intent_info.get("intent")
    
    if intent == "general":
        system_prompt_gen = """You are MarketMind, an expert AI stock market research assistant and financial educator.
If the user asks basic educational questions (e.g., 'What is PE ratio?', 'Explain the metrics used here'), provide a clear, comprehensive, and beginner-friendly explanation. 
Break down metrics like P/E Ratio (valuation), RSI (momentum/overbought/oversold), and moving averages carefully. Use bullet points and analogies if helpful. 
Do NOT be overly brief when explaining concepts. Provide deep value to the user.
NEVER give direct financial advice to buy or sell a specific stock."""
        messages = [
            {"role": "system", "content": system_prompt_gen},
            {"role": "user", "content": query}
        ]
        return await function_ollama_chat(messages, format="text")

    table_markdown, data_notes = _data_table_markdown(intent, quant_data, screening_results)
    news_markdown = _news_markdown(news_data)
    subject = _summary_subject(query, intent_info, quant_data)
    snapshot = _snapshot_line(intent, quant_data)

    system_prompt = """You are MarketMind, a research-only Indian market analyst.
Write only the Trend Observation paragraph.
Use the provided structured facts only. Do not add new numbers.
Use neutral research language. Do not use advice words or phrases like buy, sell, invest, avoid, investors should, attractive option, or long-term investment.
If data is unavailable for an entity, mention that the comparison is limited by missing data.
Keep it to 3-5 concise sentences."""
    
    context = f"""
User Query: {query}
Identified Intent: {intent}
Identified Ticker: {intent_info.get('ticker')}

Structured Data:
{json.dumps(quant_data, indent=2)}

News Data:
{json.dumps(news_data, indent=2)}

Screening Results:
{json.dumps(screening_results, indent=2)}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context}
    ]
    
    trend = await function_ollama_chat(messages, format="text")
    if not trend:
        trend = "The structured data above should be read as market context, not as a recommendation. Metrics can be useful for comparison, but missing values and source freshness limit the strength of any conclusion. Use the available figures as a starting point for independent research."
    trend = _sanitize_research_text(trend.strip())

    notes_markdown = ""
    if data_notes:
        notes_markdown = "\n\n### Data Notes\n" + "\n".join([f"- {note}" for note in data_notes])

    return f"""### {subject} — Snapshot
> {snapshot}

### Data Table
{table_markdown}{notes_markdown}

### News & Announcements *(last 48-72 hrs)*
{news_markdown}

### Trend Observation

{trend}

{DISCLAIMER}"""

@app.get("/api/trigger-fetch")
async def trigger_eod_fetch(background_tasks: BackgroundTasks):
    """Trigger background EOD fetching process via cron tool"""
    background_tasks.add_task(run_eod_fetch)
    return {"message": "Background fetch process triggered successfully."}

async def get_mf_history_df(scheme_code: int, days: int = 1100):
    """Fetch MF history from Supabase and return as a DataFrame compatible with risk functions."""
    async def fetch_remote_history() -> pd.DataFrame:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(f"https://api.mfapi.in/mf/{scheme_code}")
                res.raise_for_status()
                payload = res.json()
            rows = payload.get("data") or []
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
            df["Close"] = pd.to_numeric(df["nav"], errors="coerce")
            df = df.dropna(subset=["date", "Close"]).sort_values("date")
            df.set_index("date", inplace=True)
            return _normalize_price_df_index(df[["Close"]])
        except Exception as e:
            logger.warning(f"MFAPI history fallback failed for {scheme_code}: {e}")
            return pd.DataFrame()

    if not supabase: return pd.DataFrame()
    try:
        # Default is ~3 years; callers can request more for 5Y UI metrics.
        res = supabase.table('mutual_fund_history').select('nav, nav_date').eq('scheme_code', scheme_code).order('nav_date', desc=True).limit(days).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['date'] = pd.to_datetime(df['nav_date'])
            df = df.sort_values('date')
            df.rename(columns={'nav': 'Close'}, inplace=True)
            df.set_index('date', inplace=True)
            if len(df) < min(days, 500):
                remote_df = await fetch_remote_history()
                if not remote_df.empty:
                    return remote_df.tail(days)
            return _normalize_price_df_index(df)
    except Exception as e:
        logger.error(f"Failed to fetch local MF history for {scheme_code}: {e}")
    return await fetch_remote_history()

async def get_nifty_history_df(days: int = 1100):
    """Fetch NIFTY history from Supabase stock_history table."""
    def fetch_yfinance_nifty() -> pd.DataFrame:
        try:
            hist = yf.Ticker("^NSEI").history(period="5y")
            if hist.empty:
                return pd.DataFrame()
            return _normalize_price_df_index(hist[["Close"]]).tail(days)
        except Exception as e:
            logger.warning(f"YFinance NIFTY fallback failed: {e}")
            return pd.DataFrame()

    if not supabase: return fetch_yfinance_nifty()
    try:
        res = supabase.table('stock_history').select('close, date').eq('symbol', 'NIFTY').order('date', desc=True).limit(days).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df.rename(columns={'close': 'Close'}, inplace=True)
            df.set_index('date', inplace=True)
            if len(df) < min(days, 500):
                yf_df = fetch_yfinance_nifty()
                if not yf_df.empty:
                    return yf_df
            return _normalize_price_df_index(df)
    except Exception as e:
        logger.error(f"Failed to fetch local NIFTY history: {e}")
    return fetch_yfinance_nifty()

def _normalize_fund_text(text: str) -> str:
    return " ".join(
        text.lower()
        .replace("smallcap", "small cap")
        .replace("midcap", "mid cap")
        .replace("largecap", "large cap")
        .replace("-", " ")
        .split()
    )

def _pick_best_fund_match(entity: str, rows: list[dict]) -> dict | None:
    if not rows:
        return None

    entity_norm = _normalize_fund_text(entity.replace(" fund", "").replace(" growth", ""))
    entity_words = [w for w in entity_norm.split() if len(w) > 2]

    def score(row: dict) -> int:
        name_norm = _normalize_fund_text(row.get("scheme_name", ""))
        value = 0
        if entity_norm and entity_norm in name_norm:
            value += 100
        value += sum(10 for word in entity_words if word in name_norm)
        if "direct" in name_norm and "growth" in name_norm:
            value += 20
        if "regular" in name_norm:
            value -= 15
        if "idcw" in name_norm or "dividend" in name_norm:
            value -= 20
        if "index" in name_norm and "index" not in entity_norm:
            value -= 35
        if "etf" in name_norm and "etf" not in entity_norm:
            value -= 35
        return value

    return max(rows, key=score)

def _compute_cagr_from_close(close_series: pd.Series, years: int) -> float | None:
    if close_series.empty:
        return None
    current_date = close_series.index[-1]
    target_date = current_date - pd.DateOffset(years=years)
    historical = close_series[close_series.index <= target_date]
    if historical.empty:
        return None
    current_val = float(close_series.iloc[-1])
    past_val = float(historical.iloc[-1])
    if past_val <= 0:
        return None
    cagr = (current_val / past_val) ** (1 / years) - 1
    return round(cagr * 100, 2)

def _compute_nav_risk_metrics(close_series: pd.Series, risk_free_rate: float = 0.06):
    close_series = close_series.astype(float).dropna()
    if len(close_series) < 2:
        return None

    returns = close_series.pct_change().dropna()
    if returns.empty:
        return None

    mean_daily = float(returns.mean())
    std_daily = float(returns.std(ddof=0))
    ann_std = std_daily * np.sqrt(252)
    ann_return = mean_daily * 252

    sharpe = None if ann_std == 0 else (ann_return - risk_free_rate) / ann_std
    downside = returns[returns < 0]
    downside_std = float(np.sqrt(np.mean(np.square(downside)))) * np.sqrt(252) if len(downside) > 0 else 0.0
    sortino = None if downside_std == 0 else (ann_return - risk_free_rate) / downside_std

    running_max = close_series.cummax()
    drawdown = (running_max - close_series) / running_max.replace(0, np.nan)
    max_drawdown = float(drawdown.max()) if not drawdown.empty else 0.0

    return {
        "stdDev": round(ann_std, 4),
        "sharpeRatio": round(sharpe, 2) if sharpe is not None else None,
        "sortinoRatio": round(sortino, 2) if sortino is not None else None,
        "maxDrawdown": round(max_drawdown, 4)
    }

@app.get("/api/quant/stocks/compare")
async def compare_stocks_quant(symbols: str = Query(..., min_length=1)):
    try:
        return build_stock_compare(symbols)
    except Exception as e:
        logger.error("Stock quant compare failed: %s", e)
        raise HTTPException(status_code=500, detail="Stock quant comparison failed")


@app.get("/api/quant/stocks/{symbol}/profile")
async def stock_quant_profile(symbol: str):
    try:
        return build_stock_profile(symbol)
    except Exception as e:
        logger.error("Stock profile failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Stock profile failed")


@app.get("/api/quant/stocks/{symbol}/financials")
async def stock_quant_financials(symbol: str):
    try:
        return get_stock_financials(symbol)
    except Exception as e:
        logger.error("Stock financials failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Stock financials failed")


@app.get("/api/quant/stocks/{symbol}/price-history")
async def stock_quant_price_history(symbol: str, days: int = Query(365, ge=1, le=5000)):
    try:
        return {"symbol": symbol.upper(), "price_history": get_stock_price_history(symbol, days=days)}
    except Exception as e:
        logger.error("Stock price history failed for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail="Stock price history failed")


@app.get("/api/mf/{scheme_code}")
async def get_mutual_fund_details(scheme_code: int):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")

    try:
        fund_res = supabase.table('mutual_funds').select('*').eq('scheme_code', scheme_code).limit(1).execute()
        if not fund_res.data:
            raise HTTPException(status_code=404, detail="Mutual fund not found")

        details = fund_res.data[0]
        hist_df = await get_mf_history_df(scheme_code, days=2200)
        close_series = hist_df["Close"] if not hist_df.empty else pd.Series(dtype=float)

        returns = {
            "1Y": _compute_cagr_from_close(close_series, 1),
            "3Y": _compute_cagr_from_close(close_series, 3),
            "5Y": _compute_cagr_from_close(close_series, 5)
        }
        risk_metrics = _compute_nav_risk_metrics(close_series)
        nifty_hist = await get_nifty_history_df(days=2200)
        if risk_metrics is None:
            risk_metrics = {}
        if not hist_df.empty and not nifty_hist.empty:
            alpha_beta = calculate_alpha_beta_v2(hist_df, nifty_hist)
            risk_metrics.update({
                "beta": alpha_beta.get("beta"),
                "alpha_vs_nifty": alpha_beta.get("alpha"),
                "risk_period": f"{alpha_beta.get('period_years', 3)}Y"
            })

        chart_df = hist_df.sort_index().tail(250) if not hist_df.empty else pd.DataFrame()
        chart_data = []
        if not chart_df.empty:
            chart_data = [
                {
                    "date": idx.strftime("%d-%m-%Y"),
                    "value": round(float(val), 4)
                }
                for idx, val in chart_df["Close"].items()
            ]
        full_data = []
        if not hist_df.empty:
            full_data = [
                {
                    "date": idx.strftime("%d-%m-%Y"),
                    "value": round(float(val), 4)
                }
                for idx, val in hist_df.sort_index(ascending=False)["Close"].items()
            ]

        return {
            "details": details,
            "returns": returns,
            "riskMetrics": risk_metrics,
            "chartData": chart_data,
            "fullData": full_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MF details endpoint error for {scheme_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    asset_type = req.asset_type
    intent_info = await route_query(req.query, asset_type)
    intent = intent_info.get("intent", "general")
    ticker = intent_info.get("ticker")
    period = intent_info.get("historical_period", "1mo")
    sentiment = intent_info.get("sentiment_flag", False)
    
    quant_data = {}
    news_data = []
    screening_results = None

    def _entity_search_term(entity: str) -> str:
        query_lower = req.query.lower()
        entity_lower = entity.lower()
        additions = []
        for phrase in ["small cap", "mid cap", "large cap", "flexi cap", "multi cap", "index"]:
            if phrase in query_lower and phrase not in entity_lower:
                additions.append(phrase)
        return " ".join([entity, *additions]).strip()

    def _fund_search_pattern(search_term: str) -> str:
        cleaned = (
            search_term.lower()
            .replace(' fund', '')
            .replace(' growth', '')
            .replace('.', ' ')
            .replace(',', ' ')
            .strip()
        )
        words = [word for word in cleaned.split() if word]
        return f"%{'%'.join(words)}%" if words else "%"
    
    if intent == "screen":
        filters = intent_info.get("screen_filters", {})
        screening_results = await run_stock_screen(filters)
        
    elif intent == "compare":
        entities = intent_info.get("compare_entities", [])
        
        # If user only provided one entity, treat as a single quant lookup
        if len(entities) == 1:
            intent = "quant"
            ticker = entities[0]
        else:
            comparison_results = {}
            # Pre-fetch Nifty history once for all comparisons
            n_hist_local = await get_nifty_history_df()
            
            for entity in entities:
                db_data = None
                scheme_code = None
                if supabase and asset_type != "stock":
                    try:
                        search_term = _entity_search_term(entity)
                        search_pattern = _fund_search_pattern(search_term)
                        res = supabase.table('mutual_funds').select('*').ilike('scheme_name', search_pattern).limit(25).execute()
                        if res.data:
                            best_match = _pick_best_fund_match(search_term, res.data)
                            scheme_code = best_match['scheme_code']
                            db_data = {
                                "name": best_match['scheme_name'],
                                "nav": best_match['nav'],
                                "nav_date": best_match['nav_date'],
                                "category": best_match['category'],
                                "fund_house": best_match['fund_house'],
                                "expense_ratio": best_match.get('expense_ratio', "N/A"),
                                "aum": best_match.get('aum', "N/A"),
                                "source": "MarketMind DB"
                            }
                    except Exception as e:
                        logger.error(f"Supabase compare error: {e}")

                risk_metrics = {}
                yf_ticker = None if asset_type == "mutual_fund" else await resolve_mf_ticker(entity)
                stock_symbol = None if asset_type == "mutual_fund" else resolve_stock_symbol(entity)
                
                try:
                    hist = pd.DataFrame()
                    nifty_hist = pd.DataFrame()

                    # Prefer local MF history for compare mode. It is faster, more stable,
                    # and avoids third-party ticker mismatches for Indian mutual funds.
                    if scheme_code:
                        hist = await get_mf_history_df(scheme_code)
                        nifty_hist = n_hist_local

                    # Only fall back to YFinance when local history is unavailable.
                    if hist.empty and yf_ticker:
                        stock = yf.Ticker(yf_ticker)
                        hist = stock.history(period="3y")
                        nifty = yf.Ticker("^NSEI")
                        nifty_hist = nifty.history(period="3y")
                        # Add AUM if missing
                        if db_data and (not db_data.get("aum") or db_data["aum"] == "N/A"):
                            db_data["aum"] = stock.info.get("totalAssets", "N/A")
                        
                    if not hist.empty and not nifty_hist.empty:
                        metrics = calculate_alpha_beta_v2(hist, nifty_hist)
                        risk_metrics = {
                            "beta": metrics["beta"],
                            "alpha_vs_nifty": metrics["alpha"],
                            "risk_period": f"{metrics.get('period_years', 3)}Y"
                        }
                except:
                    pass

                if db_data:
                    db_data.update(risk_metrics)
                    comparison_results[entity] = db_data
                elif asset_type != "mutual_fund" and (stock_symbol or yf_ticker):
                    stock_compare = build_stock_compare([stock_symbol or yf_ticker])
                    comparison_results[entity] = next(
                        iter((stock_compare.get("comparison") or {}).values()),
                        {"error": "Data not found for this entity"},
                    )
                elif asset_type != "mutual_fund":
                    stock_compare = build_stock_compare([entity])
                    comparison_results[entity] = next(
                        iter((stock_compare.get("comparison") or {}).values()),
                        {"error": "Data not found for this entity"},
                    )
                else:
                    comparison_results[entity] = {"error": "Data not found for this entity"}
                    
            quant_data = {"comparison": comparison_results}
    
    # Handle single quant lookup (or forced single comparison)
    if intent in ["quant", "both"]:
        quant_data = {}

        if asset_type != "mutual_fund":
            stock_symbol = resolve_stock_symbol(ticker or req.query)
            yf_ticker = await resolve_mf_ticker(ticker or req.query)
            final_ticker = stock_symbol or yf_ticker or ticker
            quant_data = fetch_quant_data(final_ticker, period)
        
        # Fallback to Supabase
        if (not quant_data or "error" in quant_data) and supabase and asset_type != "stock":
            try:
                search_term = ticker or req.query
                search_pattern = _fund_search_pattern(search_term)
                res = supabase.table('mutual_funds').select('*').ilike('scheme_name', search_pattern).limit(25).execute()
                if res.data:
                    fund = _pick_best_fund_match(search_term, res.data)
                    scheme_code = fund['scheme_code']
                    quant_data = {
                        "name": fund['scheme_name'],
                        "price": fund['nav'],
                        "date": fund['nav_date'],
                        "fund_house": fund['fund_house'],
                        "aum": fund.get('aum', "N/A"),
                        "expense_ratio": fund.get('expense_ratio', "N/A"),
                        "source": "MarketMind DB"
                    }
                    
                    # Compute risk metrics locally for single entity too!
                    hist = await get_mf_history_df(scheme_code)
                    nifty_hist = await get_nifty_history_df()
                    if not hist.empty and not nifty_hist.empty:
                        metrics = calculate_alpha_beta_v2(hist, nifty_hist)
                        quant_data.update({
                            "beta": metrics["beta"],
                            "alpha_vs_nifty": metrics["alpha"],
                            "risk_period": f"{metrics.get('period_years', 3)}Y"
                        })
            except: pass
            
        if intent in ["news", "both"]:
            news_items = fetch_news(req.query, ticker)
            if sentiment:
                news_items = await analyze_news_sentiment(news_items)
            news_data = news_items

    if intent in ["news", "compare"] and not news_data:
        news_items = fetch_news(req.query, ticker)
        if sentiment:
            news_items = await analyze_news_sentiment(news_items)
        news_data = news_items
            
    final_answer = await synthesis_response(req.query, intent_info, quant_data, news_data, screening_results)
    response_json = {
        "answer": final_answer,
        "debug_intent": intent_info,
        "quant_data": quant_data
    }
    
    if intent == "compare":
        entities = intent_info.get("compare_entities", [])
        if len(entities) >= 2:
            resolved_ids = []
            comparison_payload = quant_data.get("comparison", {}) if isinstance(quant_data, dict) else {}
            fallback_map = {
                "hdfc flexi cap": "118955",
                "parag parikh flexi cap": "122639",
                "quant small cap": "120847",
                "nippon india small cap": "119332"
            }
            
            for entity in entities:
                if comparison_payload and _is_unavailable_entity(comparison_payload.get(entity)):
                    continue
                ent_lower = entity.lower()
                resolved = False
                if asset_type != "stock":
                    for key, code in fallback_map.items():
                        if key in ent_lower:
                            resolved_ids.append(code); resolved = True; break
                if resolved: continue
                if supabase and asset_type != "stock":
                    try:
                        search_term = _entity_search_term(entity)
                        search_pattern = _fund_search_pattern(search_term)
                        res = supabase.table('mutual_funds').select('scheme_code', 'scheme_name').ilike('scheme_name', search_pattern).limit(25).execute()
                        if res.data and len(res.data) > 0:
                            best_match = _pick_best_fund_match(search_term, res.data)
                            resolved_ids.append(str(best_match['scheme_code']))
                            resolved = True
                    except: pass
                if resolved: continue
                if asset_type != "mutual_fund":
                    stock_symbol = resolve_stock_symbol(entity)
                    ticker_clean = stock_symbol or entity.split()[0].upper()
                    resolved_ids.append(ticker_clean); resolved = True
            
            if len(resolved_ids) >= 2:
                response_json["system_action"] = {"type": "COMPARE", "ids": resolved_ids[:2]}
                
    return response_json

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
