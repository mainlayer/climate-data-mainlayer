# Climate Data Mainlayer

Climate and weather data sold to AI agents via [Mainlayer](https://mainlayer.fr) payment infrastructure.

## Endpoints

| Method | Path | Price | Description |
|--------|------|-------|-------------|
| GET | `/weather/current?city=` | $0.001 | Current conditions |
| GET | `/weather/forecast?city=&days=` | $0.003 | Multi-day forecast |
| GET | `/weather/history?city=&date=` | $0.005 | Historical data |
| GET | `/climate/monthly?city=` | $0.002 | Monthly climate averages |
| GET | `/alerts?region=` | $0.001 | Active weather alerts |
| GET | `/carbon/footprint?lat=&lon=` | $0.002 | Grid carbon intensity |
| GET | `/health` | free | Health check |

## Authentication

All paid endpoints require a Mainlayer API key:

```
Authorization: Bearer <your_mainlayer_api_key>
```

Get your API key at [mainlayer.fr](https://mainlayer.fr).

## Quick Start

```python
import httpx

headers = {"Authorization": "Bearer YOUR_API_KEY"}

# Get current weather
weather = httpx.get(
    "https://climate-api.example.com/weather/current",
    params={"city": "London"},
    headers=headers,
).json()

print(f"Temperature: {weather['data']['temperature_c']}°C")
print(f"Condition: {weather['data']['condition']}")
```

## Running Locally

```bash
pip install -e ".[dev]"
MAINLAYER_DEV_MODE=true uvicorn src.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

## Development Mode

Set `MAINLAYER_DEV_MODE=true` to bypass payment validation during local development.

## Running Tests

```bash
pytest tests/ -v
```

## Examples

- [`examples/get_forecast.py`](examples/get_forecast.py) — Fetch weather forecasts
- [`examples/historical_analysis.py`](examples/historical_analysis.py) — Analyse historical weather data
