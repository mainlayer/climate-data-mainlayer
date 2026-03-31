"""
Climate Data API — FastAPI application.

Provides current weather, forecasts, historical data, monthly climate averages,
weather alerts, and carbon intensity data — all sold to AI agents via Mainlayer.

Auth:   Authorization: Bearer <api_key>
Prices: see individual endpoint docstrings.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.mainlayer import MainlayerAuth
from src.models import (
    AlertsResponse,
    CarbonFootprintResponse,
    CarbonIntensity,
    Coordinates,
    CurrentWeatherResponse,
    ErrorResponse,
    ForecastResponse,
    HistoricalWeatherResponse,
    MonthlyClimateResponse,
)
from src.weather_db import (
    get_alerts,
    get_carbon_intensity,
    get_current_weather,
    get_forecast,
    get_historical,
    get_monthly_climate,
    list_supported_cities,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Climate Data API",
    description=(
        "Climate and weather data API for AI agents. "
        "Powered by Mainlayer — the payment layer for AI agents. "
        "Authenticate with: Authorization: Bearer <api_key>"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "weather", "description": "Real-time and historical weather endpoints"},
        {"name": "climate", "description": "Long-term climate statistics"},
        {"name": "alerts", "description": "Active weather alerts and warnings"},
        {"name": "carbon", "description": "Grid carbon intensity and energy mix"},
        {"name": "meta", "description": "API health and metadata"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Any, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, str):
        detail = {"code": "ERROR", "message": detail}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


@app.get(
    "/",
    tags=["meta"],
    summary="API root — capabilities and pricing",
    include_in_schema=True,
)
async def root() -> dict[str, Any]:
    return {
        "service": "Climate Data API",
        "version": "1.0.0",
        "description": "Climate and weather data for AI agents via Mainlayer",
        "auth": "Authorization: Bearer <api_key>",
        "endpoints": {
            "GET /weather/current": {"price_usd": 0.001, "description": "Current weather for a city"},
            "GET /weather/forecast": {"price_usd": 0.003, "description": "Multi-day forecast"},
            "GET /weather/history": {"price_usd": 0.005, "description": "Historical weather data"},
            "GET /climate/monthly": {"price_usd": 0.002, "description": "Monthly climate averages"},
            "GET /alerts": {"price_usd": 0.001, "description": "Active weather alerts by region"},
            "GET /carbon/footprint": {"price_usd": 0.002, "description": "Grid carbon intensity by coordinates"},
        },
        "supported_cities": list_supported_cities(),
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"], summary="Health check (free)")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Weather endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/weather/current",
    tags=["weather"],
    summary="Current weather — $0.001 per call",
    response_model=CurrentWeatherResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        402: {"model": ErrorResponse, "description": "Insufficient balance"},
        404: {"model": ErrorResponse, "description": "City not found"},
    },
)
async def current_weather(
    city: Annotated[str, Query(description="City name, e.g. London", min_length=1)],
    _auth: Annotated[
        dict[str, Any],
        Depends(MainlayerAuth(price=0.001, endpoint="/weather/current")),
    ],
) -> CurrentWeatherResponse:
    """
    Returns real-time weather conditions for the requested city.

    **Price**: $0.001 per call
    **Auth**: `Authorization: Bearer <api_key>`

    Includes temperature, humidity, wind, pressure, UV index, precipitation
    probability, and sky conditions.
    """
    try:
        data = get_current_weather(city)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CITY_NOT_FOUND", "message": str(exc)},
        )
    return CurrentWeatherResponse(data=data)


@app.get(
    "/weather/forecast",
    tags=["weather"],
    summary="Weather forecast — $0.003 per call",
    response_model=ForecastResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        402: {"model": ErrorResponse, "description": "Insufficient balance"},
        404: {"model": ErrorResponse, "description": "City not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def weather_forecast(
    city: Annotated[str, Query(description="City name", min_length=1)],
    days: Annotated[
        int,
        Query(description="Number of forecast days (1-14)", ge=1, le=14),
    ] = 7,
    _auth: Annotated[
        dict[str, Any],
        Depends(MainlayerAuth(price=0.003, endpoint="/weather/forecast")),
    ],
) -> ForecastResponse:
    """
    Returns a day-by-day weather forecast including hourly breakdowns.

    **Price**: $0.003 per call
    **Auth**: `Authorization: Bearer <api_key>`

    Each day includes min/max temperatures, precipitation, wind, sunrise/sunset
    times, UV index, and 3-hourly slots covering the full day.
    """
    try:
        meta, forecast = get_forecast(city, days)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CITY_NOT_FOUND", "message": str(exc)},
        )
    return ForecastResponse(
        city=meta["name"],
        country=meta["country"],
        coordinates=Coordinates(lat=meta["lat"], lon=meta["lon"]),
        days_requested=days,
        forecast=forecast,
    )


@app.get(
    "/weather/history",
    tags=["weather"],
    summary="Historical weather data — $0.005 per call",
    response_model=HistoricalWeatherResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Date out of range"},
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        402: {"model": ErrorResponse, "description": "Insufficient balance"},
        404: {"model": ErrorResponse, "description": "City not found"},
    },
)
async def weather_history(
    city: Annotated[str, Query(description="City name", min_length=1)],
    date: Annotated[
        str,
        Query(description="Date in YYYY-MM-DD format (up to 40 years back)"),
    ],
    _auth: Annotated[
        dict[str, Any],
        Depends(MainlayerAuth(price=0.005, endpoint="/weather/history")),
    ],
) -> HistoricalWeatherResponse:
    """
    Returns historical weather observations for a given city and date.

    **Price**: $0.005 per call
    **Auth**: `Authorization: Bearer <api_key>`

    Includes daily min/max/average temperature, precipitation, sunshine hours,
    wind, and atmospheric pressure.
    """
    try:
        query_date = _parse_date(date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_DATE", "message": f"Invalid date format '{date}'. Use YYYY-MM-DD."},
        )

    today = _today()
    if query_date >= today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DATE_NOT_HISTORICAL", "message": "Date must be in the past."},
        )

    try:
        data = get_historical(city, query_date)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CITY_NOT_FOUND", "message": str(exc)},
        )
    return HistoricalWeatherResponse(data=data)


# ---------------------------------------------------------------------------
# Climate endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/climate/monthly",
    tags=["climate"],
    summary="Monthly climate averages — $0.002 per call",
    response_model=MonthlyClimateResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        402: {"model": ErrorResponse, "description": "Insufficient balance"},
        404: {"model": ErrorResponse, "description": "City not found"},
    },
)
async def climate_monthly(
    city: Annotated[str, Query(description="City name", min_length=1)],
    _auth: Annotated[
        dict[str, Any],
        Depends(MainlayerAuth(price=0.002, endpoint="/climate/monthly")),
    ],
) -> MonthlyClimateResponse:
    """
    Returns 12-month climate averages (climatological normals) for a city.

    **Price**: $0.002 per call
    **Auth**: `Authorization: Bearer <api_key>`

    Includes mean temperature ranges, precipitation, sunshine hours, rainy days,
    humidity, wind speed, and UV index per month. Also returns the Köppen climate
    classification for the city.
    """
    try:
        data = get_monthly_climate(city)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CITY_NOT_FOUND", "message": str(exc)},
        )
    return MonthlyClimateResponse(
        city=data["name"],
        country=data["country"],
        coordinates=Coordinates(lat=data["lat"], lon=data["lon"]),
        climate_zone=data["climate_zone"],
        koppen_classification=data["koppen"],
        averages=data["averages"],
    )


# ---------------------------------------------------------------------------
# Alerts endpoint
# ---------------------------------------------------------------------------


@app.get(
    "/alerts",
    tags=["alerts"],
    summary="Active weather alerts — $0.001 per call",
    response_model=AlertsResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        402: {"model": ErrorResponse, "description": "Insufficient balance"},
    },
)
async def weather_alerts(
    region: Annotated[
        str,
        Query(description="Region or city name to query alerts for", min_length=1),
    ],
    _auth: Annotated[
        dict[str, Any],
        Depends(MainlayerAuth(price=0.001, endpoint="/alerts")),
    ],
) -> AlertsResponse:
    """
    Returns all currently active weather alerts and warnings for a region.

    **Price**: $0.001 per call
    **Auth**: `Authorization: Bearer <api_key>`

    Each alert includes type (e.g. HEAT_WAVE, FLOOD_WARNING), severity level,
    headline, description, validity window, and the issuing agency.
    """
    alerts = get_alerts(region)
    return AlertsResponse(
        region=region,
        active_alerts=len(alerts),
        alerts=alerts,
    )


# ---------------------------------------------------------------------------
# Carbon / energy endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/carbon/footprint",
    tags=["carbon"],
    summary="Grid carbon intensity — $0.002 per call",
    response_model=CarbonFootprintResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Coordinates out of range"},
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        402: {"model": ErrorResponse, "description": "Insufficient balance"},
    },
)
async def carbon_footprint(
    lat: Annotated[float, Query(description="Latitude (-90 to 90)", ge=-90, le=90)],
    lon: Annotated[float, Query(description="Longitude (-180 to 180)", ge=-180, le=180)],
    _auth: Annotated[
        dict[str, Any],
        Depends(MainlayerAuth(price=0.002, endpoint="/carbon/footprint")),
    ],
) -> CarbonFootprintResponse:
    """
    Returns real-time grid carbon intensity and energy mix for a geographic point.

    **Price**: $0.002 per call
    **Auth**: `Authorization: Bearer <api_key>`

    Returns carbon intensity in gCO2eq/kWh, a categorical index (VERY_LOW to
    VERY_HIGH), the current renewable share, full energy mix breakdown, and
    a one-hour-ahead forecast to help AI agents schedule compute workloads at
    low-carbon times.
    """
    raw = get_carbon_intensity(lat, lon)
    data = CarbonIntensity(**raw)
    return CarbonFootprintResponse(data=data)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_date(s: str) -> date:
    from datetime import date as _date
    return _date.fromisoformat(s)


def _today() -> date:
    return date.today()
