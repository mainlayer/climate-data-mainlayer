"""
Pydantic models for the Climate Data API.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


class Coordinates(BaseModel):
    lat: float = Field(..., description="Latitude in decimal degrees")
    lon: float = Field(..., description="Longitude in decimal degrees")


class Wind(BaseModel):
    speed_kmh: float = Field(..., description="Wind speed in km/h")
    direction_deg: int = Field(..., description="Wind direction in degrees (0-359)")
    direction_label: str = Field(..., description="Cardinal direction label, e.g. NW")


class Precipitation(BaseModel):
    mm: float = Field(..., description="Precipitation in millimetres")
    probability_pct: float = Field(..., description="Probability of precipitation (0-100)")


# ---------------------------------------------------------------------------
# Current weather
# ---------------------------------------------------------------------------


class CurrentWeather(BaseModel):
    city: str
    country: str
    coordinates: Coordinates
    timestamp: datetime
    temperature_c: float = Field(..., description="Temperature in Celsius")
    feels_like_c: float = Field(..., description="Feels-like temperature in Celsius")
    humidity_pct: float = Field(..., description="Relative humidity (0-100)")
    dew_point_c: float
    pressure_hpa: float = Field(..., description="Atmospheric pressure in hPa")
    visibility_km: float
    uv_index: float
    wind: Wind
    precipitation: Precipitation
    condition: str = Field(..., description="Human-readable weather condition")
    condition_code: str = Field(..., description="Machine-readable condition code")
    cloud_cover_pct: float
    is_day: bool


class CurrentWeatherResponse(BaseModel):
    data: CurrentWeather
    cached: bool = False
    source: str = "climate-data-mainlayer"
    price_usd: float = 0.001


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------


class HourlySlot(BaseModel):
    hour: int
    temperature_c: float
    feels_like_c: float
    humidity_pct: float
    wind: Wind
    precipitation: Precipitation
    condition: str
    condition_code: str
    cloud_cover_pct: float


class DailyForecast(BaseModel):
    date: date
    temp_min_c: float
    temp_max_c: float
    temp_avg_c: float
    humidity_avg_pct: float
    wind: Wind
    precipitation: Precipitation
    sunrise: str = Field(..., description="Local sunrise time HH:MM")
    sunset: str = Field(..., description="Local sunset time HH:MM")
    condition: str
    condition_code: str
    uv_index_max: float
    hourly: list[HourlySlot]


class ForecastResponse(BaseModel):
    city: str
    country: str
    coordinates: Coordinates
    days_requested: int
    forecast: list[DailyForecast]
    source: str = "climate-data-mainlayer"
    price_usd: float = 0.003


# ---------------------------------------------------------------------------
# Historical
# ---------------------------------------------------------------------------


class HistoricalWeather(BaseModel):
    city: str
    country: str
    coordinates: Coordinates
    date: date
    temp_min_c: float
    temp_max_c: float
    temp_avg_c: float
    humidity_avg_pct: float
    wind: Wind
    precipitation_total_mm: float
    sunshine_hours: float
    pressure_avg_hpa: float
    condition: str
    condition_code: str


class HistoricalWeatherResponse(BaseModel):
    data: HistoricalWeather
    source: str = "climate-data-mainlayer"
    price_usd: float = 0.005


# ---------------------------------------------------------------------------
# Monthly climate averages
# ---------------------------------------------------------------------------


class MonthlyAverage(BaseModel):
    month: int = Field(..., ge=1, le=12)
    month_name: str
    temp_min_avg_c: float
    temp_max_avg_c: float
    temp_mean_c: float
    precipitation_avg_mm: float
    humidity_avg_pct: float
    sunshine_hours_avg: float
    wind_speed_avg_kmh: float
    rainy_days_avg: float
    uv_index_avg: float


class MonthlyClimateResponse(BaseModel):
    city: str
    country: str
    coordinates: Coordinates
    climate_zone: str
    koppen_classification: str
    averages: list[MonthlyAverage]
    source: str = "climate-data-mainlayer"
    price_usd: float = 0.002


# ---------------------------------------------------------------------------
# Weather alerts
# ---------------------------------------------------------------------------


class WeatherAlert(BaseModel):
    alert_id: str
    region: str
    type: str = Field(..., description="Alert type, e.g. HEAT_WAVE, FLOOD, STORM")
    severity: str = Field(..., description="LOW | MODERATE | HIGH | EXTREME")
    headline: str
    description: str
    issued_at: datetime
    expires_at: datetime
    affected_area: str
    source_agency: str


class AlertsResponse(BaseModel):
    region: str
    active_alerts: int
    alerts: list[WeatherAlert]
    source: str = "climate-data-mainlayer"
    price_usd: float = 0.001


# ---------------------------------------------------------------------------
# Carbon / grid intensity
# ---------------------------------------------------------------------------


class EnergyMix(BaseModel):
    renewable_pct: float
    fossil_pct: float
    nuclear_pct: float
    solar_pct: float
    wind_pct: float
    hydro_pct: float


class CarbonIntensity(BaseModel):
    lat: float
    lon: float
    region_name: str
    country: str
    timestamp: datetime
    carbon_intensity_gco2_kwh: float = Field(
        ..., description="Grid carbon intensity in gCO2eq/kWh"
    )
    carbon_index: str = Field(
        ..., description="VERY_LOW | LOW | MODERATE | HIGH | VERY_HIGH"
    )
    renewable_share_pct: float
    energy_mix: EnergyMix
    forecast_next_hour_gco2_kwh: float
    best_time_today: str = Field(..., description="Suggested best time for low-carbon usage")


class CarbonFootprintResponse(BaseModel):
    data: CarbonIntensity
    source: str = "climate-data-mainlayer"
    price_usd: float = 0.002


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
