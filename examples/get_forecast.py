"""
Example: Get weather forecasts via the Climate Data API.

Usage:
    export MAINLAYER_API_KEY=your_key_here
    python examples/get_forecast.py
"""

import os
import httpx

BASE_URL = os.getenv("CLIMATE_API_URL", "http://localhost:8000")
API_KEY = os.getenv("MAINLAYER_API_KEY", "your_api_key_here")

headers = {"Authorization": f"Bearer {API_KEY}"}


def get_current_weather(city: str) -> dict:
    resp = httpx.get(f"{BASE_URL}/weather/current", params={"city": city}, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_forecast(city: str, days: int = 7) -> dict:
    resp = httpx.get(
        f"{BASE_URL}/weather/forecast",
        params={"city": city, "days": days},
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()


def get_alerts(region: str) -> dict:
    resp = httpx.get(f"{BASE_URL}/alerts", params={"region": region}, headers=headers)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    # 1. Current conditions
    print("=== Current Weather: London ===")
    current = get_current_weather("London")
    w = current["data"]
    print(f"Temperature:  {w['temperature_c']}°C (feels like {w['feels_like_c']}°C)")
    print(f"Condition:    {w['condition']}")
    print(f"Humidity:     {w['humidity_pct']}%")
    print(f"Wind:         {w['wind']['speed_kmh']} km/h {w['wind']['direction_label']}")
    print(f"UV Index:     {w['uv_index']}")
    print(f"Cost:         ${current['price_usd']}")
    print()

    # 2. 5-day forecast
    print("=== 5-Day Forecast: Tokyo ===")
    forecast = get_forecast("Tokyo", days=5)
    for day in forecast["forecast"]:
        print(
            f"  {day['date']}  {day['temp_min_c']}–{day['temp_max_c']}°C  "
            f"{day['condition']}  rain: {day['precipitation']['probability_pct']}%"
        )
    print(f"Cost: ${forecast['price_usd']}")
    print()

    # 3. Active alerts
    print("=== Weather Alerts: California ===")
    alerts = get_alerts("California")
    print(f"Active alerts: {alerts['active_alerts']}")
    for alert in alerts["alerts"][:2]:
        print(f"  [{alert['severity']}] {alert['type']}: {alert['headline']}")
    print(f"Cost: ${alerts['price_usd']}")


if __name__ == "__main__":
    main()
