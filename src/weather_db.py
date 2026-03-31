"""
Realistic weather data generator / in-memory database.

Produces deterministic but plausible weather values for a large set of cities
using statistical climate profiles (Köppen zones) plus seeded pseudo-randomness
so repeated calls for the same city+date return consistent results.
"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.models import (
    Coordinates,
    CurrentWeather,
    DailyForecast,
    EnergyMix,
    HistoricalWeather,
    HourlySlot,
    MonthlyAverage,
    Precipitation,
    WeatherAlert,
    Wind,
)

# ---------------------------------------------------------------------------
# City registry
# ---------------------------------------------------------------------------

CITIES: dict[str, dict[str, Any]] = {
    "london": {
        "name": "London",
        "country": "GB",
        "lat": 51.5074,
        "lon": -0.1278,
        "koppen": "Cfb",
        "climate_zone": "Temperate Oceanic",
        "tz_offset": 0,
        "monthly_temp": [-1, 0, 3, 6, 10, 13, 15, 15, 12, 8, 4, 1],
        "monthly_precip": [55, 40, 40, 45, 45, 45, 45, 50, 50, 65, 60, 55],
        "monthly_sun": [60, 80, 120, 165, 195, 205, 205, 185, 140, 100, 65, 50],
    },
    "new york": {
        "name": "New York",
        "country": "US",
        "lat": 40.7128,
        "lon": -74.0060,
        "koppen": "Cfa",
        "climate_zone": "Humid Subtropical",
        "tz_offset": -5,
        "monthly_temp": [-3, -2, 3, 9, 15, 20, 23, 22, 18, 12, 6, 1],
        "monthly_precip": [90, 80, 100, 100, 100, 100, 110, 110, 90, 90, 95, 95],
        "monthly_sun": [140, 150, 175, 195, 215, 250, 265, 255, 210, 185, 130, 120],
    },
    "tokyo": {
        "name": "Tokyo",
        "country": "JP",
        "lat": 35.6762,
        "lon": 139.6503,
        "koppen": "Cfa",
        "climate_zone": "Humid Subtropical",
        "tz_offset": 9,
        "monthly_temp": [3, 4, 7, 13, 18, 21, 25, 26, 22, 16, 11, 5],
        "monthly_precip": [60, 55, 120, 130, 140, 165, 155, 155, 210, 195, 95, 55],
        "monthly_sun": [195, 175, 170, 175, 180, 130, 155, 175, 120, 135, 150, 175],
    },
    "dubai": {
        "name": "Dubai",
        "country": "AE",
        "lat": 25.2048,
        "lon": 55.2708,
        "koppen": "BWh",
        "climate_zone": "Hot Desert",
        "tz_offset": 4,
        "monthly_temp": [18, 19, 22, 26, 30, 33, 35, 35, 32, 29, 24, 19],
        "monthly_precip": [10, 20, 15, 5, 0, 0, 0, 0, 0, 0, 5, 15],
        "monthly_sun": [240, 235, 265, 290, 310, 345, 340, 330, 310, 295, 265, 240],
    },
    "sydney": {
        "name": "Sydney",
        "country": "AU",
        "lat": -33.8688,
        "lon": 151.2093,
        "koppen": "Cfa",
        "climate_zone": "Humid Subtropical",
        "tz_offset": 10,
        "monthly_temp": [22, 22, 20, 17, 14, 11, 10, 11, 14, 16, 19, 21],
        "monthly_precip": [100, 115, 130, 125, 120, 130, 100, 80, 70, 75, 85, 75],
        "monthly_sun": [240, 205, 200, 180, 170, 145, 160, 185, 200, 225, 235, 245],
    },
    "paris": {
        "name": "Paris",
        "country": "FR",
        "lat": 48.8566,
        "lon": 2.3522,
        "koppen": "Cfb",
        "climate_zone": "Temperate Oceanic",
        "tz_offset": 1,
        "monthly_temp": [3, 4, 7, 10, 14, 17, 19, 19, 16, 12, 7, 4],
        "monthly_precip": [50, 45, 50, 50, 65, 55, 55, 60, 55, 55, 55, 55],
        "monthly_sun": [60, 80, 130, 170, 205, 220, 230, 210, 165, 115, 65, 50],
    },
    "singapore": {
        "name": "Singapore",
        "country": "SG",
        "lat": 1.3521,
        "lon": 103.8198,
        "koppen": "Af",
        "climate_zone": "Tropical Rainforest",
        "tz_offset": 8,
        "monthly_temp": [26, 27, 27, 28, 28, 28, 27, 27, 27, 27, 27, 26],
        "monthly_precip": [250, 170, 180, 165, 170, 165, 155, 155, 165, 170, 265, 320],
        "monthly_sun": [170, 175, 185, 185, 185, 180, 185, 185, 165, 155, 130, 145],
    },
    "cairo": {
        "name": "Cairo",
        "country": "EG",
        "lat": 30.0444,
        "lon": 31.2357,
        "koppen": "BWh",
        "climate_zone": "Hot Desert",
        "tz_offset": 2,
        "monthly_temp": [13, 15, 18, 22, 27, 30, 31, 31, 28, 24, 19, 14],
        "monthly_precip": [5, 4, 3, 1, 0, 0, 0, 0, 0, 1, 4, 7],
        "monthly_sun": [270, 255, 285, 305, 340, 360, 365, 355, 325, 305, 270, 255],
    },
    "moscow": {
        "name": "Moscow",
        "country": "RU",
        "lat": 55.7558,
        "lon": 37.6173,
        "koppen": "Dfb",
        "climate_zone": "Humid Continental",
        "tz_offset": 3,
        "monthly_temp": [-8, -7, -2, 6, 13, 17, 19, 17, 11, 4, -2, -6],
        "monthly_precip": [45, 35, 35, 40, 55, 70, 90, 80, 65, 60, 55, 55],
        "monthly_sun": [25, 50, 105, 165, 230, 255, 265, 230, 155, 80, 30, 20],
    },
    "sao paulo": {
        "name": "São Paulo",
        "country": "BR",
        "lat": -23.5505,
        "lon": -46.6333,
        "koppen": "Cfa",
        "climate_zone": "Humid Subtropical",
        "tz_offset": -3,
        "monthly_temp": [22, 22, 21, 19, 17, 16, 15, 17, 18, 19, 20, 21],
        "monthly_precip": [240, 215, 160, 80, 75, 55, 45, 40, 75, 120, 145, 200],
        "monthly_sun": [185, 165, 175, 175, 175, 165, 185, 200, 180, 175, 175, 185],
    },
    "berlin": {
        "name": "Berlin",
        "country": "DE",
        "lat": 52.5200,
        "lon": 13.4050,
        "koppen": "Cfb",
        "climate_zone": "Temperate Oceanic",
        "tz_offset": 1,
        "monthly_temp": [-1, 0, 4, 9, 14, 17, 19, 18, 14, 9, 4, 1],
        "monthly_precip": [42, 33, 40, 37, 54, 69, 56, 58, 45, 37, 44, 55],
        "monthly_sun": [45, 75, 130, 170, 220, 230, 230, 205, 155, 100, 50, 35],
    },
    "mumbai": {
        "name": "Mumbai",
        "country": "IN",
        "lat": 19.0760,
        "lon": 72.8777,
        "koppen": "Aw",
        "climate_zone": "Tropical Savanna",
        "tz_offset": 5,
        "monthly_temp": [24, 25, 27, 29, 31, 29, 27, 27, 28, 28, 26, 25],
        "monthly_precip": [0, 1, 0, 1, 10, 480, 680, 550, 300, 65, 20, 5],
        "monthly_sun": [285, 285, 300, 300, 290, 120, 75, 90, 165, 270, 285, 280],
    },
    "toronto": {
        "name": "Toronto",
        "country": "CA",
        "lat": 43.7001,
        "lon": -79.4163,
        "koppen": "Dfb",
        "climate_zone": "Humid Continental",
        "tz_offset": -5,
        "monthly_temp": [-7, -6, -1, 6, 12, 18, 21, 20, 15, 9, 3, -3],
        "monthly_precip": [52, 44, 57, 64, 72, 72, 74, 77, 70, 68, 70, 57],
        "monthly_sun": [100, 115, 155, 170, 210, 245, 275, 255, 195, 145, 90, 80],
    },
    "nairobi": {
        "name": "Nairobi",
        "country": "KE",
        "lat": -1.2921,
        "lon": 36.8219,
        "koppen": "Cwb",
        "climate_zone": "Subtropical Highland",
        "tz_offset": 3,
        "monthly_temp": [19, 19, 19, 19, 18, 16, 15, 16, 17, 18, 18, 18],
        "monthly_precip": [65, 60, 100, 185, 155, 45, 15, 20, 30, 55, 110, 85],
        "monthly_sun": [220, 220, 185, 155, 165, 175, 185, 200, 210, 225, 215, 215],
    },
    "buenos aires": {
        "name": "Buenos Aires",
        "country": "AR",
        "lat": -34.6037,
        "lon": -58.3816,
        "koppen": "Cfa",
        "climate_zone": "Humid Subtropical",
        "tz_offset": -3,
        "monthly_temp": [24, 23, 20, 16, 13, 10, 10, 11, 13, 17, 20, 22],
        "monthly_precip": [120, 110, 120, 95, 90, 60, 65, 70, 80, 115, 100, 115],
        "monthly_sun": [260, 225, 210, 175, 155, 130, 140, 165, 175, 210, 220, 245],
    },
}

# Normalise keys
CITIES = {k.lower(): v for k, v in CITIES.items()}

# ---------------------------------------------------------------------------
# Condition codes
# ---------------------------------------------------------------------------

CONDITION_MATRIX: list[tuple[str, str]] = [
    ("clear_sky", "Clear Sky"),
    ("partly_cloudy", "Partly Cloudy"),
    ("mostly_cloudy", "Mostly Cloudy"),
    ("overcast", "Overcast"),
    ("light_rain", "Light Rain"),
    ("moderate_rain", "Moderate Rain"),
    ("heavy_rain", "Heavy Rain"),
    ("thunderstorm", "Thunderstorm"),
    ("drizzle", "Drizzle"),
    ("snow", "Snow"),
    ("sleet", "Sleet"),
    ("fog", "Foggy"),
    ("haze", "Hazy"),
    ("dust", "Dust / Sand"),
    ("hail", "Hail"),
]

WIND_DIRECTIONS = [
    (0, "N"),
    (45, "NE"),
    (90, "E"),
    (135, "SE"),
    (180, "S"),
    (225, "SW"),
    (270, "W"),
    (315, "NW"),
]

ALERT_TYPES = [
    "HEAT_WAVE",
    "COLD_SNAP",
    "FLOOD_WATCH",
    "FLOOD_WARNING",
    "SEVERE_THUNDERSTORM",
    "TORNADO_WATCH",
    "COASTAL_FLOOD",
    "WINTER_STORM",
    "DENSE_FOG",
    "HIGH_WIND",
    "FIRE_WEATHER",
    "AIR_QUALITY",
]

AGENCIES = [
    "National Weather Service",
    "Met Office",
    "Météo-France",
    "Deutscher Wetterdienst",
    "Japan Meteorological Agency",
    "Bureau of Meteorology",
    "Environment Canada",
    "IMD India",
    "WMO Regional Centre",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed(city: str, date_val: date | None = None, extra: str = "") -> int:
    """Stable integer seed from city + date + extra."""
    raw = f"{city.lower()}:{date_val}:{extra}"
    digest = hashlib.md5(raw.encode()).hexdigest()
    return int(digest[:8], 16)


def _rng(city: str, date_val: date | None = None, extra: str = "") -> random.Random:
    return random.Random(_seed(city, date_val, extra))


def _wind_label(deg: int) -> str:
    closest = min(WIND_DIRECTIONS, key=lambda x: abs(x[0] - deg % 360))
    return closest[1]


def _condition(rng: random.Random, precip_mm: float, cloud_pct: float) -> tuple[str, str]:
    if precip_mm > 15:
        code, label = rng.choice([("heavy_rain", "Heavy Rain"), ("thunderstorm", "Thunderstorm")])
    elif precip_mm > 5:
        code, label = "moderate_rain", "Moderate Rain"
    elif precip_mm > 1:
        code, label = rng.choice(
            [("light_rain", "Light Rain"), ("drizzle", "Drizzle")]
        )
    elif cloud_pct > 85:
        code, label = "overcast", "Overcast"
    elif cloud_pct > 60:
        code, label = "mostly_cloudy", "Mostly Cloudy"
    elif cloud_pct > 30:
        code, label = "partly_cloudy", "Partly Cloudy"
    else:
        code, label = "clear_sky", "Clear Sky"
    return code, label


def _lookup(city_name: str) -> dict[str, Any]:
    key = city_name.strip().lower()
    if key not in CITIES:
        raise LookupError(f"City '{city_name}' not found in climate database.")
    return CITIES[key]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_current_weather(city: str) -> CurrentWeather:
    profile = _lookup(city)
    now = datetime.now(tz=timezone.utc)
    month_idx = now.month - 1
    today = now.date()
    rng = _rng(city, today, str(now.hour))

    base_temp = profile["monthly_temp"][month_idx]
    temp = round(base_temp + rng.uniform(-3, 3), 1)
    feels = round(temp - rng.uniform(0, 3), 1)
    humidity = round(rng.uniform(45, 90), 1)
    dew = round(temp - (100 - humidity) / 5, 1)
    pressure = round(rng.uniform(1005, 1025), 1)
    visibility = round(rng.uniform(8, 20), 1)
    uv = round(rng.uniform(0, 10), 1)
    wind_spd = round(rng.uniform(5, 35), 1)
    wind_deg = rng.randint(0, 359)
    precip_mm = round(rng.uniform(0, profile["monthly_precip"][month_idx] / 30 * 2), 2)
    precip_prob = round(min(precip_mm * 20, 100), 1)
    cloud_pct = round(rng.uniform(10, 90), 1)
    is_day = 7 <= (now.hour + profile["tz_offset"]) % 24 <= 20

    code, label = _condition(rng, precip_mm, cloud_pct)

    return CurrentWeather(
        city=profile["name"],
        country=profile["country"],
        coordinates=Coordinates(lat=profile["lat"], lon=profile["lon"]),
        timestamp=now,
        temperature_c=temp,
        feels_like_c=feels,
        humidity_pct=humidity,
        dew_point_c=dew,
        pressure_hpa=pressure,
        visibility_km=visibility,
        uv_index=uv,
        wind=Wind(speed_kmh=wind_spd, direction_deg=wind_deg, direction_label=_wind_label(wind_deg)),
        precipitation=Precipitation(mm=precip_mm, probability_pct=precip_prob),
        condition=label,
        condition_code=code,
        cloud_cover_pct=cloud_pct,
        is_day=is_day,
    )


def get_forecast(city: str, days: int) -> tuple[dict[str, Any], list[DailyForecast]]:
    profile = _lookup(city)
    today = date.today()
    forecast: list[DailyForecast] = []

    for day_offset in range(days):
        d = today + timedelta(days=day_offset)
        month_idx = d.month - 1
        rng = _rng(city, d)

        base_temp = profile["monthly_temp"][month_idx]
        t_min = round(base_temp + rng.uniform(-5, -1), 1)
        t_max = round(base_temp + rng.uniform(1, 6), 1)
        t_avg = round((t_min + t_max) / 2, 1)
        humidity = round(rng.uniform(50, 85), 1)
        wind_spd = round(rng.uniform(5, 30), 1)
        wind_deg = rng.randint(0, 359)
        monthly_precip = profile["monthly_precip"][month_idx]
        precip_mm = round(rng.uniform(0, monthly_precip / 15), 2)
        precip_prob = round(min(precip_mm * 15, 100), 1)
        cloud_pct = round(rng.uniform(10, 85), 1)
        uv_max = round(rng.uniform(1, 9), 1)

        code, label = _condition(rng, precip_mm, cloud_pct)

        # Sunrise/sunset approximation
        sunrise_h = 6 + int(math.sin((d.month - 3) * math.pi / 6) * 1.5)
        sunset_h = 18 + int(math.sin((d.month - 3) * math.pi / 6) * 1.5)
        if profile["lat"] < 0:  # Southern hemisphere
            sunrise_h = 6 - int(math.sin((d.month - 3) * math.pi / 6) * 1.5)
            sunset_h = 18 - int(math.sin((d.month - 3) * math.pi / 6) * 1.5)

        hourly: list[HourlySlot] = []
        for hour in range(0, 24, 3):
            hrng = _rng(city, d, str(hour))
            # Temperature diurnal cycle
            diurnal = math.sin((hour - 6) * math.pi / 12)
            h_temp = round(t_avg + diurnal * (t_max - t_min) / 2, 1)
            h_feels = round(h_temp - hrng.uniform(0, 2), 1)
            h_humidity = round(humidity + hrng.uniform(-10, 10), 1)
            h_wind_spd = round(wind_spd + hrng.uniform(-5, 5), 1)
            h_wind_deg = (wind_deg + hrng.randint(-20, 20)) % 360
            h_precip_mm = round(hrng.uniform(0, precip_mm), 2)
            h_precip_prob = round(min(h_precip_mm * 15, 100), 1)
            h_cloud = round(cloud_pct + hrng.uniform(-15, 15), 1)
            h_code, h_label = _condition(hrng, h_precip_mm, h_cloud)

            hourly.append(
                HourlySlot(
                    hour=hour,
                    temperature_c=h_temp,
                    feels_like_c=h_feels,
                    humidity_pct=max(10.0, min(h_humidity, 100.0)),
                    wind=Wind(
                        speed_kmh=max(0.0, h_wind_spd),
                        direction_deg=h_wind_deg,
                        direction_label=_wind_label(h_wind_deg),
                    ),
                    precipitation=Precipitation(mm=h_precip_mm, probability_pct=h_precip_prob),
                    condition=h_label,
                    condition_code=h_code,
                    cloud_cover_pct=max(0.0, min(h_cloud, 100.0)),
                )
            )

        forecast.append(
            DailyForecast(
                date=d,
                temp_min_c=t_min,
                temp_max_c=t_max,
                temp_avg_c=t_avg,
                humidity_avg_pct=humidity,
                wind=Wind(speed_kmh=wind_spd, direction_deg=wind_deg, direction_label=_wind_label(wind_deg)),
                precipitation=Precipitation(mm=precip_mm, probability_pct=precip_prob),
                sunrise=f"{sunrise_h:02d}:00",
                sunset=f"{sunset_h:02d}:00",
                condition=label,
                condition_code=code,
                uv_index_max=uv_max,
                hourly=hourly,
            )
        )

    meta = {
        "name": profile["name"],
        "country": profile["country"],
        "lat": profile["lat"],
        "lon": profile["lon"],
    }
    return meta, forecast


def get_historical(city: str, query_date: date) -> HistoricalWeather:
    profile = _lookup(city)
    month_idx = query_date.month - 1
    rng = _rng(city, query_date, "hist")

    base_temp = profile["monthly_temp"][month_idx]
    t_min = round(base_temp + rng.uniform(-5, -1), 1)
    t_max = round(base_temp + rng.uniform(1, 6), 1)
    t_avg = round((t_min + t_max) / 2, 1)
    humidity = round(rng.uniform(50, 85), 1)
    wind_spd = round(rng.uniform(5, 30), 1)
    wind_deg = rng.randint(0, 359)
    precip = round(rng.uniform(0, profile["monthly_precip"][month_idx] / 12), 2)
    sunshine = round(profile["monthly_sun"][month_idx] / 30 + rng.uniform(-1, 1), 1)
    pressure = round(rng.uniform(1005, 1025), 1)
    cloud_pct = round(rng.uniform(10, 85), 1)
    code, label = _condition(rng, precip, cloud_pct)

    return HistoricalWeather(
        city=profile["name"],
        country=profile["country"],
        coordinates=Coordinates(lat=profile["lat"], lon=profile["lon"]),
        date=query_date,
        temp_min_c=t_min,
        temp_max_c=t_max,
        temp_avg_c=t_avg,
        humidity_avg_pct=humidity,
        wind=Wind(speed_kmh=wind_spd, direction_deg=wind_deg, direction_label=_wind_label(wind_deg)),
        precipitation_total_mm=precip,
        sunshine_hours=max(0.0, sunshine),
        pressure_avg_hpa=pressure,
        condition=label,
        condition_code=code,
    )


MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def get_monthly_climate(city: str) -> dict[str, Any]:
    profile = _lookup(city)
    averages: list[MonthlyAverage] = []

    for m in range(12):
        rng = _rng(city, None, f"monthly:{m}")
        temp = profile["monthly_temp"][m]
        precip = profile["monthly_precip"][m]
        sun = profile["monthly_sun"][m]

        averages.append(
            MonthlyAverage(
                month=m + 1,
                month_name=MONTH_NAMES[m],
                temp_min_avg_c=round(temp - rng.uniform(3, 7), 1),
                temp_max_avg_c=round(temp + rng.uniform(2, 6), 1),
                temp_mean_c=float(temp),
                precipitation_avg_mm=float(precip),
                humidity_avg_pct=round(rng.uniform(50, 80), 1),
                sunshine_hours_avg=round(sun / 30, 1),
                wind_speed_avg_kmh=round(rng.uniform(8, 25), 1),
                rainy_days_avg=round(precip / 8, 1),
                uv_index_avg=round(rng.uniform(1, 8), 1),
            )
        )

    return {
        "name": profile["name"],
        "country": profile["country"],
        "lat": profile["lat"],
        "lon": profile["lon"],
        "koppen": profile["koppen"],
        "climate_zone": profile["climate_zone"],
        "averages": averages,
    }


def get_alerts(region: str) -> list[WeatherAlert]:
    rng = _rng(region, date.today(), "alerts")
    n_alerts = rng.randint(0, 4)
    alerts: list[WeatherAlert] = []
    now = datetime.now(tz=timezone.utc)

    for i in range(n_alerts):
        issued = now - timedelta(hours=rng.randint(1, 12))
        expires = now + timedelta(hours=rng.randint(6, 72))
        alert_type = rng.choice(ALERT_TYPES)
        severity = rng.choice(["LOW", "MODERATE", "HIGH", "EXTREME"])
        agency = rng.choice(AGENCIES)

        alerts.append(
            WeatherAlert(
                alert_id=f"ALERT-{region.upper()[:3]}-{_seed(region, date.today(), str(i)):08X}",
                region=region,
                type=alert_type,
                severity=severity,
                headline=f"{severity.title()} {alert_type.replace('_', ' ').title()} Advisory for {region}",
                description=(
                    f"A {severity.lower()} {alert_type.lower().replace('_', ' ')} event is anticipated "
                    f"for the {region} region. Residents are advised to monitor conditions and follow "
                    f"guidance from local authorities."
                ),
                issued_at=issued,
                expires_at=expires,
                affected_area=f"{region} and surrounding areas",
                source_agency=agency,
            )
        )

    return alerts


def get_carbon_intensity(lat: float, lon: float) -> dict[str, Any]:
    # Derive a plausible region name from coordinates
    rng = _rng(f"{lat:.1f}:{lon:.1f}", date.today(), "carbon")

    # Map to rough geopolitical zones
    if lon < -30:
        country = "US" if lat > 20 else "BR"
        region = "North America East" if lon > -90 else "North America West"
    elif lon < 30:
        country = "DE" if lat > 45 else "ZA"
        region = "Western Europe" if lat > 35 else "Southern Africa"
    elif lon < 70:
        country = "IN"
        region = "South Asia"
    elif lon < 120:
        country = "CN"
        region = "East Asia"
    else:
        country = "AU" if lat < 0 else "JP"
        region = "Oceania" if lat < 0 else "Northeast Asia"

    # Carbon intensity varies by energy mix
    base_intensity = rng.uniform(50, 700)  # gCO2eq/kWh
    renewable_pct = round(rng.uniform(10, 80), 1)
    fossil_pct = round(max(0.0, 100 - renewable_pct - rng.uniform(0, 20)), 1)
    nuclear_pct = round(max(0.0, 100 - renewable_pct - fossil_pct), 1)
    solar_pct = round(renewable_pct * rng.uniform(0.2, 0.5), 1)
    wind_pct = round(renewable_pct * rng.uniform(0.2, 0.4), 1)
    hydro_pct = round(max(0.0, renewable_pct - solar_pct - wind_pct), 1)

    intensity = round(base_intensity * (fossil_pct / 50), 1)
    intensity = max(30.0, min(intensity, 750.0))

    if intensity < 100:
        carbon_index = "VERY_LOW"
    elif intensity < 200:
        carbon_index = "LOW"
    elif intensity < 400:
        carbon_index = "MODERATE"
    elif intensity < 600:
        carbon_index = "HIGH"
    else:
        carbon_index = "VERY_HIGH"

    forecast_next = round(intensity + rng.uniform(-30, 30), 1)
    best_hour = rng.randint(10, 16)

    return {
        "lat": lat,
        "lon": lon,
        "region_name": region,
        "country": country,
        "timestamp": datetime.now(tz=timezone.utc),
        "carbon_intensity_gco2_kwh": intensity,
        "carbon_index": carbon_index,
        "renewable_share_pct": renewable_pct,
        "energy_mix": EnergyMix(
            renewable_pct=renewable_pct,
            fossil_pct=fossil_pct,
            nuclear_pct=nuclear_pct,
            solar_pct=solar_pct,
            wind_pct=wind_pct,
            hydro_pct=hydro_pct,
        ),
        "forecast_next_hour_gco2_kwh": max(30.0, forecast_next),
        "best_time_today": f"{best_hour:02d}:00 UTC",
    }


def list_supported_cities() -> list[str]:
    """Return normalised display names of all supported cities."""
    return [v["name"] for v in CITIES.values()]
