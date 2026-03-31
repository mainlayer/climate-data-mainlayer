"""
Example: Analyse historical weather data with the Climate Data API.

This example demonstrates how an AI agent can perform basic climate analysis
by querying historical data and calculating statistics over a date range.

Usage:
    export MAINLAYER_API_KEY=your_key_here
    python examples/historical_analysis.py
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import httpx

BASE_URL = os.getenv("CLIMATE_API_URL", "http://localhost:8000")
API_KEY = os.getenv("MAINLAYER_API_KEY", "your_api_key_here")

headers = {"Authorization": f"Bearer {API_KEY}"}


def get_historical(city: str, query_date: str) -> dict:
    resp = httpx.get(
        f"{BASE_URL}/weather/history",
        params={"city": city, "date": query_date},
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()


def get_monthly_climate(city: str) -> dict:
    resp = httpx.get(f"{BASE_URL}/climate/monthly", params={"city": city}, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_carbon_intensity(lat: float, lon: float) -> dict:
    resp = httpx.get(
        f"{BASE_URL}/carbon/footprint",
        params={"lat": lat, "lon": lon},
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()


def analyse_week(city: str, start_date: date) -> None:
    """Fetch 7 days of historical data and compute basic statistics."""
    temps = []
    total_precip = 0.0
    total_cost = 0.0

    print(f"=== Historical Analysis: {city} — Week of {start_date} ===")
    for i in range(7):
        d = (start_date + timedelta(days=i)).isoformat()
        data = get_historical(city, d)
        record = data["data"]
        temps.append(record["temp_avg_c"])
        total_precip += record["precipitation_total_mm"]
        total_cost += data["price_usd"]
        print(
            f"  {d}  avg {record['temp_avg_c']}°C  "
            f"precip {record['precipitation_total_mm']}mm  "
            f"{record['condition']}"
        )

    avg_temp = sum(temps) / len(temps)
    print(f"\nWeekly average temperature: {avg_temp:.1f}°C")
    print(f"Total precipitation:        {total_precip:.1f}mm")
    print(f"Total API cost:             ${total_cost:.3f}")


def main() -> None:
    # 1. Analyse a past week for London
    week_start = date(2024, 6, 10)
    analyse_week("London", week_start)
    print()

    # 2. Monthly climate normals
    print("=== Monthly Climate: Singapore ===")
    climate = get_monthly_climate("Singapore")
    print(f"City: {climate['city']}, {climate['country']}")
    print(f"Climate zone: {climate['climate_zone']} ({climate['koppen_classification']})")
    print()
    print(f"{'Month':<12} {'Temp (avg)':<14} {'Precip (mm)':<14} {'Sunshine (h)'}")
    for month in climate["averages"]:
        print(
            f"  {month['month_name']:<10} {month['temp_mean_c']:>6.1f}°C       "
            f"{month['precipitation_avg_mm']:>6.1f}mm        "
            f"{month['sunshine_hours_avg']:.1f}h"
        )
    print(f"\nCost: ${climate['price_usd']}")
    print()

    # 3. Carbon intensity for London
    print("=== Grid Carbon Intensity: London (51.5°N, -0.1°E) ===")
    carbon = get_carbon_intensity(51.5, -0.1)
    c = carbon["data"]
    print(f"Intensity:    {c['carbon_intensity_gco2_kwh']} gCO2eq/kWh [{c['carbon_index']}]")
    print(f"Renewables:   {c['renewable_share_pct']}%")
    mix = c["energy_mix"]
    print(f"Energy mix:   Solar {mix['solar_pct']}%  Wind {mix['wind_pct']}%  Hydro {mix['hydro_pct']}%")
    print(f"Best time:    {c['best_time_today']}")
    print(f"Cost:         ${carbon['price_usd']}")


if __name__ == "__main__":
    main()
