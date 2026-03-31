# climate-data-mainlayer

Climate, weather, and carbon data sold to AI agents per query via [Mainlayer](https://mainlayer.fr).

## Overview

Comprehensive climate API: real-time weather, multi-day forecasts, historical analysis, and grid carbon intensity. Pay-per-query for climate intelligence.

**API Docs:** https://climate-api.example.com/docs

## Pricing

| Endpoint | Cost | Use Case |
|----------|------|----------|
| `/weather/current` | $0.001 | Current conditions by city |
| `/weather/forecast` | $0.003 | 7-day forecast with hourly detail |
| `/weather/history` | $0.005 | Historical data (30+ years) |
| `/climate/monthly` | $0.002 | Monthly climate normals + averages |
| `/alerts` | $0.001 | Active weather alerts by region |
| `/carbon/footprint` | $0.002 | Grid carbon intensity (CO2/kWh) |
| `/health` | FREE | Health check |

## Agent Example: Weather & Climate Queries

```python
from mainlayer import MainlayerClient
import httpx

client = MainlayerClient(api_key="sk_test_...")
token = client.get_access_token("climate-data-mainlayer")
headers = {"Authorization": f"Bearer {token}"}

# Current weather ($0.001)
weather = httpx.get(
    "https://climate-api.example.com/weather/current",
    params={"city": "London"},
    headers=headers
).json()
print(f"Temp: {weather['temperature_c']}°C")

# 7-day forecast ($0.003)
forecast = httpx.get(
    "https://climate-api.example.com/weather/forecast",
    params={"city": "London", "days": 7},
    headers=headers
).json()
```

## Install & Run

```bash
pip install -e ".[dev]"
MAINLAYER_DEV_MODE=true uvicorn src.main:app --reload
pytest tests/ -v
```

## Environment Variables

```
MAINLAYER_API_KEY      # Your Mainlayer API key
MAINLAYER_DEV_MODE     # Set true to bypass payment (local dev)
```

📚 [Mainlayer Docs](https://docs.mainlayer.fr) | [mainlayer.fr](https://mainlayer.fr)
