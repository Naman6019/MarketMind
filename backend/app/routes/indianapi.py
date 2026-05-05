from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.indianapi_service import (
    get_mutual_fund_research_profile,
    get_mutual_fund_universe,
    get_stock_analyst_target_optional,
    get_stock_corporate_actions,
    get_stock_forecasts_optional,
    get_stock_fundamentals,
    get_stock_historical_data_optional,
    get_stock_recent_announcements,
    get_stock_research_profile,
    resolve_mutual_fund,
    resolve_stock,
)

router = APIRouter(prefix="/api/provider/indianapi", tags=["indianapi"])


@router.get("/stocks/search")
def search_stocks(query: str = Query(..., min_length=1)):
    return resolve_stock(query)


@router.get("/stocks/{stock_name}/profile")
def stock_profile(stock_name: str):
    return get_stock_research_profile(stock_name)


@router.get("/stocks/{stock_name}/fundamentals")
def stock_fundamentals(stock_name: str, stats: str = Query(..., min_length=1)):
    return get_stock_fundamentals(stock_name, stats)


@router.get("/stocks/{stock_name}/corporate-actions")
def stock_corporate_actions(stock_name: str):
    return get_stock_corporate_actions(stock_name)


@router.get("/stocks/{stock_name}/recent-announcements")
def stock_recent_announcements(stock_name: str):
    return get_stock_recent_announcements(stock_name)


@router.get("/stocks/{stock_name}/historical-data")
def stock_historical_data_optional(
    stock_name: str,
    period: str = Query(..., min_length=1),
    filter: str = Query(..., min_length=1),
):
    return get_stock_historical_data_optional(stock_name, period, filter)


@router.get("/stocks/target-price/{stock_id}")
def stock_target_price_optional(stock_id: str):
    return get_stock_analyst_target_optional(stock_id)


@router.get("/stocks/forecasts/{stock_id}")
def stock_forecasts_optional(
    stock_id: str,
    measure_code: str = Query(..., min_length=1),
    period_type: str = Query(..., min_length=1),
    data_type: str = Query(..., min_length=1),
    age: str = Query(..., min_length=1),
):
    return get_stock_forecasts_optional(stock_id, measure_code, period_type, data_type, age)


@router.get("/mutual-funds/search")
def search_mutual_funds(query: str = Query(..., min_length=1)):
    return resolve_mutual_fund(query)


@router.get("/mutual-funds")
def mutual_fund_universe():
    return get_mutual_fund_universe()


@router.get("/mutual-funds/details")
def mutual_fund_profile(fund_name: str = Query(..., min_length=1)):
    return get_mutual_fund_research_profile(fund_name)
