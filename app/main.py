import os
import json
import logging
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import httpx
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
import pytz
from tradingview_ta import TA_Handler, Interval

# Must run before any os.environ.get()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.database import supabase
from app.fetcher import run_eod_fetch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Directory setups
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
IST = pytz.timezone('Asia/Kolkata')

NIFTY_50_TICKERS_TV = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "ITC", "SBIN", "BHARTIARTL",
    "BAJFINANCE", "LARSEN", "KOTAKBANK", "HCLTECH", "AXISBANK", "MARUTI", "SUNPHARMA",
    "TITAN", "ULTRACEMCO", "BAJAJFINSV", "ASIANPAINT", "NTPC", "M&M", "TATASTEEL",
    "POWERGRID", "INDUSINDBK", "TATAMOTORS", "HINDUNILVR", "NESTLEIND", "GRASIM",
    "TECHM", "WIPRO", "HINDALCO", "JSWSTEEL", "ADANIENT", "ADANIPORTS", "ONGC",
    "BRITANNIA", "CIPLA", "APOLLOHOSP", "DIVISLAB", "DRREDDY", "BAJAJ-AUTO",
    "TATACONSUM", "EICHERMOT", "COALINDIA", "HEROMOTOCO", "UPL", "BPCL", "LTIM",
    "SBILIFE"
]

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

async def route_query(query: str) -> dict:
    """Agent 1: Router"""
    system_prompt = """You are the Router Agent for MarketMind. Classify the user query intent.
If the query asks to filter, list, or screen stocks (e.g., "Find stocks with PE < 20", "Show me oversold stocks"), set intent to 'screener' and populate 'screener_filters'.
Otherwise, use 'quant', 'news', 'both', or 'general'.
Extract primary NSE/BSE ticker explicitly (e.g. RELIANCE.NS, ^NSEI for Nifty). 

Check for historical period mentions (e.g., '1m', '1y') and sentiment mentions.

Output strict JSON only format:
{
  "intent": "quant|news|both|general|screener",
  "ticker": "TICKER.NS",
  "historical_period": "1mo|1y|5y|max", 
  "sentiment_flag": true/false,
  "screener_filters": {
    "min_pe": 0,
    "max_pe": 100,
    "rsi_range": {"min": 0, "max": 100}
  }
}
If a filter is not mentioned, exclude it from screener_filters. Default historical_period to "1mo" if not mentioned. Default sentiment_flag to false unless news sentiment is requested.
    """
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

def calculate_alpha_beta(stock_hist, nifty_hist):
    if stock_hist.empty or nifty_hist.empty or len(stock_hist) < 2 or len(nifty_hist) < 2:
        return "N/A"
    
    stock_return = (stock_hist['Close'].iloc[-1] - stock_hist['Close'].iloc[0]) / stock_hist['Close'].iloc[0] * 100
    nifty_return = (nifty_hist['Close'].iloc[-1] - nifty_hist['Close'].iloc[0]) / nifty_hist['Close'].iloc[0] * 100
    
    alpha = stock_return - nifty_return
    return round(alpha, 2)

def fetch_quant_data(ticker: str, period: str = "1mo") -> dict:
    """Agent 2: Quant Data"""
    if not ticker: return {"error": "No ticker identified"}
    
    try:
        if period not in ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]:
            period = "1y" # default fallback
            
        stock = yf.Ticker(ticker)
        nifty = yf.Ticker("^NSEI")
        info = stock.info
        
        hist = stock.history(period=period)
        nifty_hist = nifty.history(period=period)
        
        if hist.empty:
            return {"error": "No recent data found"}
            
        current_price = info.get('currentPrice', hist['Close'].iloc[-1])
        prev_close = info.get('previousClose', hist['Close'].iloc[-2] if len(hist) > 1 else current_price)
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        data = {
            "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            "price": current_price,
            "change_pct": round(change_pct, 2),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
            "beta": info.get("beta", "N/A"),
            "alpha_vs_nifty": calculate_alpha_beta(hist, nifty_hist),
            "historical_period": period,
            "rsi_14d": "N/A",
            "tv_recommendation": "N/A"
        }
        
        try:
            tv_ticker = ticker.replace('.NS', '').replace('.BO', '')
            if tv_ticker == '^NSEI': tv_ticker = 'NIFTY'
            handler = TA_Handler(symbol=tv_ticker, screener="india", exchange="NSE", interval=Interval.INTERVAL_1_DAY)
            analysis = handler.get_analysis()
            data["tv_recommendation"] = analysis.summary.get('RECOMMENDATION', 'N/A')
            if 'RSI' in analysis.indicators:
                data["rsi_14d"] = round(analysis.indicators['RSI'], 2)
        except Exception as tv_e:
            pass
            
        return data
    except Exception as e:
        logger.error(f"Quant Error: {e}")
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

async def run_screener(filters: dict) -> list:
    """Screener Engine against NIFTY 50 universe using Supabase"""
    if not supabase:
        logger.error("Supabase client not initialized")
        return []

    try:
        # Start DB Query
        query = supabase.table('nifty_stocks').select('*')
        
        # Filter Logic
        min_pe = filters.get("min_pe")
        max_pe = filters.get("max_pe")
        if min_pe is not None:
            query = query.gte('pe_ratio', min_pe)
        if max_pe is not None:
            query = query.lte('pe_ratio', max_pe)
            
        rsi_range = filters.get("rsi_range", {})
        rsi_min = rsi_range.get("min")
        rsi_max = rsi_range.get("max")
        if rsi_min is not None:
            query = query.gte('rsi', rsi_min)
        if rsi_max is not None:
            query = query.lte('rsi', rsi_max)
            
        res = query.execute()
        raw_results = res.data
        
        # Format for output
        formatted_results = []
        for r in raw_results:
            formatted_results.append({
                "Symbol": r["symbol"],
                "RSI": round(r["rsi"], 2) if r.get("rsi") is not None else "N/A",
                "P/E": round(r["pe_ratio"], 2) if r.get("pe_ratio") is not None else "N/A",
                "Recommendation": r.get("recommendation", "N/A")
            })
        return formatted_results
    except Exception as e:
        logger.error(f"Screener DB error: {e}")
        return []

async def synthesis_response(query: str, intent_info: dict, quant_data: dict, news_data: list, screener_results: list = None) -> str:
    """Synthesis Core"""
    
    if intent_info.get("intent") == "general":
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

    system_prompt = """You are MarketMind, a 3-agent stock market research assistant for Indian retail investors. 
You are synthesizing data into a final response. 

## SYNTHESIS RULES
1. Open with a one-line market context statement.
2. Present quantitative data or screener results in a clean, scannable markdown table.
3. Follow with relevant news (if any), newest first. Including the [Sentiment] tag if provided.
4. Close with a Trend Observation — Provide DEEP, ANALYTICAL reasoning here. Do not just regurgitate the numbers; explain exactly *why* the numbers matter together. For example, if P/E is uniquely low but RSI indicates it is oversold, hypothesize the market conditions causing this and provide strong supporting arguments. Make your analysis highly educational, uncovering the 'why' behind the metrics. Provide well-reasoned hypotheses, not shallow summaries.
5. Append the complete mandatory disclaimer at the very end. Format it precisely as a blockquote using `> ⚠️ **Disclaimer:**`.
6. Ensure neat spacing. ALWAYS use double blank lines (`\n\n`) between the Snapshot, Table, News List, Trend Observation, and the final Disclaimer.

## RESPONSE FORMAT MUST BE EXACTLY LIKE THIS:

### [Topic] — Snapshot
> [One-line current status]

### Data Table
| Metric | Value | 
|---|---|
| ... | ... |

### News & Announcements *(last 48–72 hrs)*
- **[SENTIMENT]** [DD MMM] [Source]: [One-line summary]
...

### Trend Observation

[4–6 sentences. Neutral tone, highly detailed...]

> ⚠️ **Disclaimer:** *MarketMind is an informational research tool only. Nothing presented here constitutes investment advice, a solicitation, or a recommendation to buy or sell any security. Always conduct your own research and consult a SEBI-registered Investment Advisor before making any financial decision.*

## ABSOLUTE RULES
- Never say "buy", "sell", "invest", "avoid". No advice.
- Timestamp everything. 
- Use the data provided. DO NOT HALLUCINATE NUMBERS.
"""
    
    context = f"""
User Query: {query}
Identified Ticker: {intent_info.get('ticker')}

Quant Data:
{json.dumps(quant_data, indent=2)}

News Data:
{json.dumps(news_data, indent=2)}

Screener Results:
{json.dumps(screener_results, indent=2)}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context}
    ]
    
    response = await function_ollama_chat(messages, format="text")
    if not response:
        return "Sorry, I am facing connectivity issues with the intelligence core."
        
    return response

@app.get("/")
def serve_index(): return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))
@app.get("/style.css")
def serve_css(): return FileResponse(os.path.join(PUBLIC_DIR, "style.css"))
@app.get("/script.js")
def serve_js(): return FileResponse(os.path.join(PUBLIC_DIR, "script.js"))

@app.get("/api/trigger-fetch")
async def trigger_eod_fetch(background_tasks: BackgroundTasks):
    """Trigger background EOD fetching process via cron tool"""
    background_tasks.add_task(run_eod_fetch)
    return {"message": "Background fetch process triggered successfully."}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    intent_info = await route_query(req.query)
    intent = intent_info.get("intent", "general")
    ticker = intent_info.get("ticker")
    period = intent_info.get("historical_period", "1mo")
    sentiment = intent_info.get("sentiment_flag", False)
    
    quant_data = {}
    news_data = []
    screener_results = None
    
    if intent == "screener":
        filters = intent_info.get("screener_filters", {})
        screener_results = await run_screener(filters)
        
    else:
        if intent in ["quant", "both"]:
            quant_data = fetch_quant_data(ticker, period)
            
        if intent in ["news", "both"]:
            news_items = fetch_news(req.query, ticker)
            if sentiment:
                news_items = await analyze_news_sentiment(news_items)
            news_data = news_items
            
    final_answer = await synthesis_response(req.query, intent_info, quant_data, news_data, screener_results)
    return {"answer": final_answer, "debug_intent": intent_info}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
