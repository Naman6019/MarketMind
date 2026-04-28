import io
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "MarketMind research data sync/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml,text/csv,application/pdf,*/*",
}


def create_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session


def load_source_registry() -> dict[str, list[dict[str, Any]]]:
    registry_path = Path(os.environ.get("MF_METADATA_SOURCES", "backend/config/mf_metadata_sources.json"))
    if not registry_path.exists():
        return {"ter": [], "aum": [], "holdings": []}

    with registry_path.open("r", encoding="utf-8") as f:
        registry = json.load(f)

    for key in ["ter", "aum", "holdings"]:
        registry.setdefault(key, [])

    env_urls = os.environ.get("MF_METADATA_EXTRA_URLS", "")
    for raw_url in [u.strip() for u in env_urls.split(",") if u.strip()]:
        registry["ter"].append({"name": "env-extra", "url": raw_url, "type": "auto"})
        registry["aum"].append({"name": "env-extra", "url": raw_url, "type": "auto"})

    return registry


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.lower()
    text = text.replace("&", " and ")
    text = text.replace("smallcap", "small cap").replace("midcap", "mid cap").replace("largecap", "large cap")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a", "na", "-", "--"}:
        return None
    text = text.replace(",", "").replace("%", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", ".", "-", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clean_scheme_name(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_column(columns: list[str], aliases: list[str]) -> str | None:
    normalized = {col: normalize_text(col) for col in columns}
    alias_norm = [normalize_text(alias) for alias in aliases]

    for col, norm in normalized.items():
        if norm in alias_norm:
            return col
    for col, norm in normalized.items():
        if any(alias in norm for alias in alias_norm):
            return col
    return None


def read_tables_from_url(source: dict[str, Any], session: requests.Session) -> list[pd.DataFrame]:
    url = source["url"]
    source_type = (source.get("type") or "auto").lower()
    logger.info("Fetching %s from %s", source.get("name", "source"), url)

    tables: list[pd.DataFrame] = []
    content = b""
    try:
        response = session.get(url, timeout=45)
        response.raise_for_status()

        content = response.content
        content_type = response.headers.get("content-type", "").lower()
        suffix = Path(url.split("?", 1)[0]).suffix.lower()

        if source_type == "csv" or suffix == ".csv" or "text/csv" in content_type:
            return [pd.read_csv(io.BytesIO(content))]

        if source_type in {"xlsx", "xls"} or suffix in {".xlsx", ".xls"}:
            return list(pd.read_excel(io.BytesIO(content), sheet_name=None).values())

        if source_type == "pdf" or suffix == ".pdf" or "application/pdf" in content_type:
            return read_pdf_tables(content)

        tables = pd.read_html(io.BytesIO(content), flavor="lxml")
    except Exception as e:
        logger.warning("No tabular data parsed from %s: %s", url, e)

    if source.get("crawl_links"):
        tables.extend(read_tables_from_discovered_links(url, content, session, source.get("link_limit", 8)))

    return tables


def read_tables_from_discovered_links(base_url: str, content: bytes, session: requests.Session, link_limit: int) -> list[pd.DataFrame]:
    try:
        from bs4 import BeautifulSoup
    except Exception as e:
        logger.warning("BeautifulSoup unavailable for link discovery: %s", e)
        return []

    soup = BeautifulSoup(content, "html.parser")
    urls = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if re.search(r"\.(csv|xls|xlsx|pdf)(\?|$)", href, re.I):
            urls.append(urljoin(base_url, href))

    tables: list[pd.DataFrame] = []
    for url in list(dict.fromkeys(urls))[:link_limit]:
        child_source = {"name": f"linked:{url}", "url": url, "type": "auto"}
        tables.extend(read_tables_from_url(child_source, session))
    return tables


def read_pdf_tables(content: bytes) -> list[pd.DataFrame]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        logger.warning("pypdf unavailable for PDF parsing: %s", e)
        return []

    try:
        reader = PdfReader(io.BytesIO(content))
        rows = []
        for page in reader.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) >= 2:
                    rows.append(parts)
        if not rows:
            return []
        max_len = max(len(row) for row in rows)
        padded = [row + [None] * (max_len - len(row)) for row in rows]
        return [pd.DataFrame(padded)]
    except Exception as e:
        logger.warning("PDF parsing failed: %s", e)
        return []


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.empty:
        return df

    if not all(isinstance(c, str) and c.strip() for c in df.columns):
        first_row = df.iloc[0].astype(str).tolist()
        if any(re.search(r"scheme|fund|aum|ter|expense|security|isin", c, re.I) for c in first_row):
            df = df.iloc[1:].copy()
            df.columns = first_row

    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


def build_scheme_index(funds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = []
    for fund in funds:
        name = fund.get("scheme_name", "")
        indexed.append({**fund, "_norm": normalize_text(name)})
    return indexed


def match_fund(name: str, funds: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = normalize_text(name)
    if not target:
        return None
    target_words = [w for w in target.split() if len(w) > 2]

    def score(fund: dict[str, Any]) -> int:
        norm = fund["_norm"]
        value = 0
        if target == norm:
            value += 200
        if target in norm or norm in target:
            value += 100
        value += sum(10 for word in target_words if word in norm)
        if "direct" in target and "direct" in norm:
            value += 20
        if "growth" in target and "growth" in norm:
            value += 20
        if "regular" in norm and "regular" not in target:
            value -= 15
        if "idcw" in norm and "idcw" not in target:
            value -= 20
        return value

    best = max(funds, key=score, default=None)
    if not best or score(best) < 30:
        return None
    return best


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
