"""
Sync mutual fund metadata from public AMFI/AMC disclosures.

Supported data:
- TER / expense ratio
- AUM
- holdings / sector rows when the source table exposes them

Sources are configured in backend/config/mf_metadata_sources.json and may be
extended with MF_METADATA_EXTRA_URLS for direct CSV/XLS/XLSX/PDF disclosure URLs.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from supabase import create_client

from mf_ingest_utils import (
    build_scheme_index,
    clean_scheme_name,
    create_session,
    find_column,
    load_source_registry,
    match_fund,
    normalize_dataframe,
    parse_number,
    read_tables_from_url,
    utc_now,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BATCH_SIZE = int(os.environ.get("MF_METADATA_BATCH_SIZE", "500"))
AMFI_BASE_URL = os.environ.get("AMFI_BASE_URL", "https://www.amfiindia.com").rstrip("/")
AMFI_PAGE_SIZE = int(os.environ.get("AMFI_METADATA_PAGE_SIZE", "10000"))
AMFI_TER_MAX_PAGES = int(os.environ.get("AMFI_TER_MAX_PAGES", "20"))
AMFI_HOLDINGS_FUND_LIMIT = int(os.environ.get("AMFI_HOLDINGS_FUND_LIMIT", "60"))

SCHEME_ALIASES = [
    "scheme name",
    "scheme",
    "fund name",
    "name of scheme",
    "name of the scheme",
    "mutual fund scheme",
]
TER_ALIASES = [
    "ter",
    "total expense ratio",
    "expense ratio",
    "direct plan",
    "direct",
    "total ter",
    "base ter",
]
AUM_ALIASES = [
    "aum",
    "aaum",
    "average aum",
    "month end aum",
    "aum as on",
    "net assets",
    "assets under management",
]
SECURITY_ALIASES = ["security", "security name", "company", "issuer", "instrument", "name of instrument"]
ISIN_ALIASES = ["isin", "isin code"]
SECTOR_ALIASES = ["sector", "industry"]
WEIGHT_ALIASES = ["% to nav", "percentage to nav", "weight", "holding", "allocation", "% assets"]


def amfi_get_json(session, path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{AMFI_BASE_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    res = session.get(url, timeout=60, headers={"Accept": "application/json,*/*"})
    res.raise_for_status()
    return res.json()


def amfi_ter_year_candidates() -> list[str]:
    now = datetime.now(timezone.utc)
    candidates = [f"{now.year - 1}-{now.year}", f"{now.year}-{now.year + 1}"]
    return list(dict.fromkeys(candidates))


def latest_amfi_ter_month(session) -> str | None:
    explicit_month = os.environ.get("MF_TER_MONTH")
    if explicit_month:
        return explicit_month

    years = [os.environ["MF_TER_YEAR"]] if os.environ.get("MF_TER_YEAR") else amfi_ter_year_candidates()
    for year in years:
        try:
            months = amfi_get_json(session, "/api/populate-ter-month", {"year": year})
        except Exception as e:
            logger.warning("AMFI TER month lookup failed for %s: %s", year, e)
            continue
        if isinstance(months, list) and months:
            return months[0].get("MonthNumber")
    return None


def parse_amfi_payload_options(session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        res = session.get(f"{AMFI_BASE_URL}/otherdata/scheme-wise-disclosure", timeout=60)
        res.raise_for_status()
        html = res.text
    except Exception as e:
        logger.warning("Unable to load AMFI scheme-wise disclosure page: %s", e)
        return [], []

    import re

    funds = [
        {"mf_id": mf_id, "mf_name": name}
        for mf_id, name in re.findall(r'\\"mf_id\\":\\"(\d+)\\",\\"mf_name\\":\\"([^\\"]+)', html)
    ]
    quarters = [
        {"QuarterDate": date, "QuarterName": name}
        for date, name in re.findall(r'\\"QuarterDate\\":\\"([^\\"]+)\\",\\"QuarterName\\":\\"([^\\"]+)', html)
    ]
    return funds, quarters


def quarter_endpoint_date(raw_date: str) -> tuple[str, str | None]:
    dt = datetime.fromisoformat(raw_date)
    return dt.strftime("%d-%b-%Y"), dt.date().isoformat()


def update_funds(supabase, updates: list[dict[str, Any]], source_name: str) -> int:
    if not updates:
        return 0

    written = 0
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i + BATCH_SIZE]
        try:
            supabase.table("mutual_funds").upsert(batch, on_conflict="scheme_code").execute()
            written += len(batch)
        except Exception as e:
            logger.error("%s metadata upsert failed: %s", source_name, e)
    return written


def build_fund_update(fund: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    return {
        "scheme_code": int(fund["scheme_code"]),
        "scheme_name": fund["scheme_name"],
        "fund_house": fund.get("fund_house") or "Unknown",
        "category": fund.get("category") or "Unknown",
        "sub_category": fund.get("sub_category") or "Unknown",
        "nav": fund.get("nav") or 0,
        "nav_date": fund.get("nav_date"),
        "updated_at": utc_now(),
        **values,
    }


def sync_amfi_ter_api(supabase, funds: list[dict[str, Any]], session) -> int:
    month = latest_amfi_ter_month(session)
    if not month:
        logger.warning("AMFI TER sync skipped: no month available.")
        return 0

    updates_by_code: dict[int, dict[str, Any]] = {}
    for page in range(1, AMFI_TER_MAX_PAGES + 1):
        payload = amfi_get_json(
            session,
            "/api/populate-te-rdata-revised",
            {
                "MF_ID": "All",
                "Month": month,
                "strCat": "-1",
                "strType": "-1",
                "page": page,
                "pageSize": AMFI_PAGE_SIZE,
            },
        )
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not rows:
            break

        for row in rows:
            scheme_name = clean_scheme_name(row.get("Scheme_Name"))
            expense_ratio = parse_number(row.get("D_TER")) or parse_number(row.get("R_TER"))
            if not scheme_name or expense_ratio is None:
                continue
            fund = match_fund(scheme_name, funds)
            if not fund:
                continue
            updates_by_code[int(fund["scheme_code"])] = build_fund_update(
                fund,
                {"expense_ratio": expense_ratio},
            )

        if len(rows) < AMFI_PAGE_SIZE:
            break

    written = update_funds(supabase, list(updates_by_code.values()), "AMFI TER API")
    logger.info("AMFI TER API updated %s schemes from month %s.", written, month)
    return written


def sync_ter_sources(supabase, funds: list[dict[str, Any]], registry: dict, session) -> int:
    updates_by_code: dict[int, dict[str, Any]] = {}

    for source in registry["ter"]:
        for raw_df in read_tables_from_url(source, session):
            df = normalize_dataframe(raw_df)
            if df.empty:
                continue

            scheme_col = find_column(list(df.columns), SCHEME_ALIASES)
            ter_col = find_column(list(df.columns), TER_ALIASES)
            if not scheme_col or not ter_col:
                continue

            for _, row in df.iterrows():
                scheme_name = clean_scheme_name(row.get(scheme_col))
                expense_ratio = parse_number(row.get(ter_col))
                if not scheme_name or expense_ratio is None:
                    continue
                fund = match_fund(scheme_name, funds)
                if not fund:
                    continue
                updates_by_code[int(fund["scheme_code"])] = build_fund_update(
                    fund,
                    {"expense_ratio": expense_ratio},
                )

    written = update_funds(supabase, list(updates_by_code.values()), "TER")
    logger.info("TER sync updated %s schemes.", written)
    return written


def latest_amfi_aum_period(session) -> tuple[int | None, int | None]:
    years = amfi_get_json(
        session,
        "/api/average-aum-schemewise",
        {"strType": "Categorywise", "MF_ID": 0},
    )
    year_rows = years.get("data", []) if isinstance(years, dict) else []
    if not year_rows:
        return None, None

    fy_id = int(year_rows[0]["id"])
    periods = amfi_get_json(
        session,
        "/api/average-aum-schemewise",
        {"strType": "Categorywise", "fyId": fy_id, "MF_ID": 0},
    )
    period_rows = periods.get("data", {}).get("periods", []) if isinstance(periods, dict) else []
    if not period_rows:
        return fy_id, None
    return fy_id, int(period_rows[0]["id"])


def sync_amfi_aum_api(supabase, funds: list[dict[str, Any]], session) -> int:
    fy_id = int(os.environ["MF_AUM_FY_ID"]) if os.environ.get("MF_AUM_FY_ID") else None
    period_id = int(os.environ["MF_AUM_PERIOD_ID"]) if os.environ.get("MF_AUM_PERIOD_ID") else None
    if fy_id is None or period_id is None:
        fy_id, period_id = latest_amfi_aum_period(session)
    if fy_id is None or period_id is None:
        logger.warning("AMFI AUM sync skipped: no period available.")
        return 0

    payload = amfi_get_json(
        session,
        "/api/average-aum-schemewise",
        {"strType": "Categorywise", "fyId": fy_id, "periodId": period_id, "MF_ID": 0},
    )
    groups = payload.get("data", []) if isinstance(payload, dict) else []
    funds_by_code = {int(f["scheme_code"]): f for f in funds if f.get("scheme_code") is not None}
    updates = []

    for group in groups:
        for scheme in group.get("schemes", []) or []:
            scheme_code = parse_number(scheme.get("AMFI_Code"))
            aum_values = scheme.get("AverageAumForTheMonth") or {}
            raw_aum = parse_number(aum_values.get("ExcludingFundOfFundsDomesticButIncludingFundOfFundsOverseas"))
            if scheme_code is None or raw_aum is None:
                continue
            fund = funds_by_code.get(int(scheme_code))
            if not fund:
                continue
            updates.append(build_fund_update(fund, {"aum": round(raw_aum / 100, 2)}))

    written = update_funds(supabase, updates, "AMFI AUM API")
    logger.info("AMFI AUM API updated %s schemes for fyId=%s periodId=%s.", written, fy_id, period_id)
    return written


def sync_aum_sources(supabase, funds: list[dict[str, Any]], registry: dict, session) -> int:
    updates_by_code: dict[int, dict[str, Any]] = {}

    for source in registry["aum"]:
        for raw_df in read_tables_from_url(source, session):
            df = normalize_dataframe(raw_df)
            if df.empty:
                continue

            scheme_col = find_column(list(df.columns), SCHEME_ALIASES)
            aum_col = find_column(list(df.columns), AUM_ALIASES)
            if not scheme_col or not aum_col:
                continue

            aum_in_lakhs = "lakh" in aum_col.lower()
            for _, row in df.iterrows():
                scheme_name = clean_scheme_name(row.get(scheme_col))
                aum = parse_number(row.get(aum_col))
                if not scheme_name or aum is None:
                    continue
                if aum_in_lakhs:
                    aum = aum / 100
                fund = match_fund(scheme_name, funds)
                if not fund:
                    continue
                updates_by_code[int(fund["scheme_code"])] = build_fund_update(
                    fund,
                    {"aum": round(aum, 2)},
                )

    written = update_funds(supabase, list(updates_by_code.values()), "AUM")
    logger.info("AUM sync updated %s schemes.", written)
    return written


def sync_amfi_holdings_api(supabase, funds: list[dict[str, Any]], session) -> int:
    amfi_funds, quarters = parse_amfi_payload_options(session)
    if not amfi_funds or not quarters:
        logger.warning("AMFI holdings sync skipped: fund or quarter options unavailable.")
        return 0

    explicit_quarter = os.environ.get("MF_HOLDINGS_QUARTER_DATE")
    if explicit_quarter:
        str_month, as_of_date = quarter_endpoint_date(explicit_quarter)
    else:
        str_month, as_of_date = quarter_endpoint_date(quarters[0]["QuarterDate"])

    holdings = []
    for amfi_fund in amfi_funds[:AMFI_HOLDINGS_FUND_LIMIT]:
        try:
            rows = amfi_get_json(
                session,
                "/api/schemewisedisclosure-investment",
                {"MF_ID": amfi_fund["mf_id"], "strMonth": str_month},
            )
        except Exception as e:
            logger.info("No AMFI holdings rows for %s: %s", amfi_fund["mf_name"], e)
            continue

        if not isinstance(rows, list):
            continue

        for row in rows:
            scheme_name = clean_scheme_name(row.get("Scheme_Name"))
            security_name = clean_scheme_name(row.get("Company_Name"))
            weight_pct = parse_number(row.get("MarketValuePercentage"))
            if not scheme_name or not security_name or weight_pct is None:
                continue
            fund = match_fund(scheme_name, funds)
            if not fund:
                continue
            holdings.append({
                "scheme_code": int(fund["scheme_code"]),
                "as_of_date": as_of_date,
                "security_name": security_name,
                "isin": clean_scheme_name(row.get("ISIN")) or None,
                "sector": clean_scheme_name(row.get("Security_Type")) or None,
                "weight_pct": weight_pct,
                "source": f"AMFI scheme-wise disclosure: {amfi_fund['mf_name']}",
                "updated_at": utc_now(),
            })

    written = upsert_holdings(supabase, holdings)
    logger.info("AMFI holdings API upserted %s rows for %s.", written, as_of_date)
    return written


def upsert_holdings(supabase, holdings: list[dict[str, Any]]) -> int:
    if not holdings:
        return 0

    written = 0
    for i in range(0, len(holdings), BATCH_SIZE):
        batch = holdings[i:i + BATCH_SIZE]
        try:
            supabase.table("mutual_fund_holdings").upsert(
                batch,
                on_conflict="scheme_code,as_of_date,security_name,isin",
            ).execute()
            written += len(batch)
        except Exception as e:
            logger.error("Holdings upsert failed: %s", e)
    return written


def sync_holding_sources(supabase, funds: list[dict[str, Any]], registry: dict, session) -> int:
    holdings = []

    for source in registry["holdings"]:
        as_of_date = source.get("as_of_date")
        source_name = source.get("name", "unknown")
        for raw_df in read_tables_from_url(source, session):
            df = normalize_dataframe(raw_df)
            if df.empty:
                continue

            scheme_col = find_column(list(df.columns), SCHEME_ALIASES)
            security_col = find_column(list(df.columns), SECURITY_ALIASES)
            weight_col = find_column(list(df.columns), WEIGHT_ALIASES)
            if not scheme_col or not security_col or not weight_col:
                continue

            isin_col = find_column(list(df.columns), ISIN_ALIASES)
            sector_col = find_column(list(df.columns), SECTOR_ALIASES)
            for _, row in df.iterrows():
                scheme_name = clean_scheme_name(row.get(scheme_col))
                security_name = clean_scheme_name(row.get(security_col))
                weight_pct = parse_number(row.get(weight_col))
                if not scheme_name or not security_name or weight_pct is None:
                    continue
                fund = match_fund(scheme_name, funds)
                if not fund:
                    continue
                holdings.append({
                    "scheme_code": int(fund["scheme_code"]),
                    "as_of_date": as_of_date,
                    "security_name": security_name,
                    "isin": clean_scheme_name(row.get(isin_col)) if isin_col else None,
                    "sector": clean_scheme_name(row.get(sector_col)) if sector_col else None,
                    "weight_pct": weight_pct,
                    "source": source_name,
                    "updated_at": utc_now(),
                })

    if not holdings:
        logger.info("Holdings sync found no parseable rows.")
        return 0

    written = upsert_holdings(supabase, holdings)
    logger.info("Holdings sync upserted %s rows.", written)
    return written


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    session = create_session()
    registry = load_source_registry()

    funds_res = supabase.table("mutual_funds").select("*").execute()
    funds = build_scheme_index(funds_res.data or [])
    if not funds:
        logger.warning("No mutual_funds rows found. Run sync_mf.py first.")
        return

    try:
        sync_amfi_ter_api(supabase, funds, session)
    except Exception as e:
        logger.error("AMFI TER API sync failed: %s", e)

    try:
        sync_amfi_aum_api(supabase, funds, session)
    except Exception as e:
        logger.error("AMFI AUM API sync failed: %s", e)

    try:
        sync_amfi_holdings_api(supabase, funds, session)
    except Exception as e:
        logger.error("AMFI holdings API sync failed: %s", e)

    sync_ter_sources(supabase, funds, registry, session)
    sync_aum_sources(supabase, funds, registry, session)
    sync_holding_sources(supabase, funds, registry, session)


if __name__ == "__main__":
    main()
