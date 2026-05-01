"""
DEPRECATED: one-off legacy import for old CSV exports.

This is not part of production jobs. MarketMind now uses source-neutral stock
tables plus provider adapters for fundamentals.

Usage:
  python backend/scripts/deprecated/legacy_screener_csv_import.py path/to/export.csv
"""
import csv
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
from app.stock_universe import resolve_stock_symbol

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BATCH_SIZE = int(os.environ.get("SCREENER_IMPORT_BATCH_SIZE", "500"))

ALIASES = {
    "symbol": ["nse code", "nsecode", "nse symbol", "symbol", "ticker"],
    "company_name": ["name", "company", "company name"],
    "industry": ["industry", "sector"],
    "cmp": ["cmp", "cmp rs.", "cmp rs", "current market price"],
    "dividend_yield": ["div yld", "div yld %", "dividend yield", "dividend yield %"],
    "net_profit_qtr": ["np qtr", "np qtr rs.cr.", "np qtr rs.cr", "net profit qtr", "net profit quarter"],
    "qtr_profit_var": ["qtr profit var", "qtr profit var %", "quarter profit var", "quarter profit variation"],
    "sales_qtr": ["sales qtr", "sales qtr rs.cr.", "sales qtr rs.cr", "quarter sales", "sales quarter"],
    "qtr_sales_var": ["qtr sales var", "qtr sales var %", "quarter sales var", "quarter sales variation"],
    "pe_ratio": ["stock p/e", "p/e", "pe", "pe ratio"],
    "market_cap": ["market capitalization", "market cap", "mcap", "market cap."],
    "roce": ["roce", "roce %", "return on capital employed"],
    "roe": ["roe", "roe %", "return on equity"],
    "eps_12m": ["eps 12m", "eps 12m rs.", "eps 12m rs", "eps ttm"],
    "ev_ebitda": ["ev / ebitda", "ev/ebitda", "ev ebitda"],
    "sales_growth_3y": ["sales var 3yrs", "sales var 3yrs %", "sales growth 3years", "sales growth 3 years", "sales growth 3y", "sales growth"],
    "profit_growth_3y": ["profit var 3yrs", "profit var 3yrs %", "profit growth 3years", "profit growth 3 years", "profit growth 3y", "profit growth"],
    "debt_to_equity": ["debt to equity", "debt/equity", "debt equity"],
    "promoter_holding": ["promoter holding", "promoters holding", "promoter %"],
    "fii_holding": ["fii holding", "fii %"],
    "dii_holding": ["dii holding", "dii %"],
}


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("\ufeff", ""))


def find_column(headers: list[str], aliases: list[str]) -> str | None:
    normalized = {normalize_header(header): header for header in headers}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    for alias in aliases:
        for key, original in normalized.items():
            if alias in key:
                return original
    return None


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "none", "null", "-"}:
        return None
    multiplier = 1.0
    lowered = text.lower()
    if "cr" in lowered or "crore" in lowered:
        multiplier = 1_00_00_000
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", ".", "-"}:
        return None
    try:
        return round(float(cleaned) * multiplier, 4)
    except ValueError:
        return None


def clean_symbol(value: Any) -> str | None:
    if value is None:
        return None
    symbol = str(value).strip().upper()
    symbol = symbol.replace(".NS", "").replace(".BO", "")
    symbol = re.sub(r"[^A-Z0-9&-]", "", symbol)
    return symbol or None


def build_record(row: dict[str, str], columns: dict[str, str | None]) -> dict[str, Any] | None:
    symbol_col = columns.get("symbol")
    symbol = clean_symbol(row.get(symbol_col or ""))
    company_col = columns.get("company_name")
    company_name = row.get(company_col or "")
    if not symbol and company_name:
        symbol = resolve_stock_symbol(company_name) or clean_symbol(company_name)
    if not symbol:
        logger.warning("Skipping legacy CSV row without symbol match: %s", company_name or row)
        return None

    record: dict[str, Any] = {
        "symbol": symbol,
        "source": "Screener CSV",
        "source_updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "raw_data": row,
    }

    for field in ["company_name", "industry"]:
        col = columns.get(field)
        if col and row.get(col):
            record[field] = row[col].strip()

    for field in [
        "cmp",
        "dividend_yield",
        "net_profit_qtr",
        "qtr_profit_var",
        "sales_qtr",
        "qtr_sales_var",
        "pe_ratio",
        "market_cap",
        "roce",
        "roe",
        "eps_12m",
        "ev_ebitda",
        "sales_growth_3y",
        "profit_growth_3y",
        "debt_to_equity",
        "promoter_holding",
        "fii_holding",
        "dii_holding",
    ]:
        col = columns.get(field)
        if col:
            record[field] = parse_number(row.get(col))

    return record


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python backend/scripts/deprecated/legacy_screener_csv_import.py path/to/export.csv")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    csv_path = Path(sys.argv[1]).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        columns = {field: find_column(headers, aliases) for field, aliases in ALIASES.items()}
        if not columns.get("symbol") and not columns.get("company_name"):
            raise RuntimeError("Could not find a symbol or Name column in the legacy CSV.")

        records = [record for row in reader if (record := build_record(row, columns))]

    written = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        supabase.table("stock_fundamentals").upsert(batch, on_conflict="symbol").execute()
        written += len(batch)

    logger.info("Imported %s legacy CSV rows into stock_fundamentals.", written)


if __name__ == "__main__":
    main()
