"""
Test suite for the Climate Data API.

Uses pytest + httpx's AsyncClient via FastAPI's test client.
Runs in MAINLAYER_DEV_MODE=true so no real payment calls are made.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

# Set dev mode before importing the app so MainlayerAuth skips real auth.
os.environ["MAINLAYER_DEV_MODE"] = "true"

from src.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


AUTH = {"Authorization": "Bearer test-agent-key"}


# ---------------------------------------------------------------------------
# Root / health
# ---------------------------------------------------------------------------


class TestMeta:
    def test_root_returns_200(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_lists_endpoints(self, client: TestClient) -> None:
        body = resp = client.get("/")
        data = resp.json()
        assert "endpoints" in data
        assert "GET /weather/current" in data["endpoints"]
        assert "GET /carbon/footprint" in data["endpoints"]

    def test_root_lists_supported_cities(self, client: TestClient) -> None:
        data = client.get("/").json()
        assert isinstance(data["supported_cities"], list)
        assert len(data["supported_cities"]) >= 10

    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Current weather
# ---------------------------------------------------------------------------


class TestCurrentWeather:
    def test_returns_200_for_known_city(self, client: TestClient) -> None:
        resp = client.get("/weather/current", params={"city": "London"}, headers=AUTH)
        assert resp.status_code == 200

    def test_response_structure(self, client: TestClient) -> None:
        resp = client.get("/weather/current", params={"city": "Tokyo"}, headers=AUTH)
        body = resp.json()
        assert "data" in body
        d = body["data"]
        assert d["city"] == "Tokyo"
        assert d["country"] == "JP"
        assert isinstance(d["temperature_c"], float)
        assert isinstance(d["humidity_pct"], float)
        assert 0 <= d["humidity_pct"] <= 100
        assert "wind" in d
        assert "precipitation" in d
        assert "coordinates" in d
        assert "lat" in d["coordinates"]
        assert "lon" in d["coordinates"]

    def test_price_field(self, client: TestClient) -> None:
        resp = client.get("/weather/current", params={"city": "Paris"}, headers=AUTH)
        assert resp.json()["price_usd"] == pytest.approx(0.001)

    def test_unknown_city_returns_404(self, client: TestClient) -> None:
        resp = client.get("/weather/current", params={"city": "Atlantis"}, headers=AUTH)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "CITY_NOT_FOUND"

    def test_missing_auth_returns_401(self, client: TestClient) -> None:
        os.environ["MAINLAYER_DEV_MODE"] = "false"
        try:
            resp = client.get("/weather/current", params={"city": "London"})
            assert resp.status_code == 401
        finally:
            os.environ["MAINLAYER_DEV_MODE"] = "true"

    def test_case_insensitive_city(self, client: TestClient) -> None:
        r1 = client.get("/weather/current", params={"city": "london"}, headers=AUTH)
        r2 = client.get("/weather/current", params={"city": "LONDON"}, headers=AUTH)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["data"]["city"] == r2.json()["data"]["city"]

    def test_wind_has_direction_label(self, client: TestClient) -> None:
        resp = client.get("/weather/current", params={"city": "Dubai"}, headers=AUTH)
        wind = resp.json()["data"]["wind"]
        assert "direction_label" in wind
        assert wind["direction_label"] in {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}

    def test_is_day_field_is_bool(self, client: TestClient) -> None:
        resp = client.get("/weather/current", params={"city": "Singapore"}, headers=AUTH)
        assert isinstance(resp.json()["data"]["is_day"], bool)


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------


class TestForecast:
    def test_returns_200_default_7_days(self, client: TestClient) -> None:
        resp = client.get("/weather/forecast", params={"city": "New York"}, headers=AUTH)
        assert resp.status_code == 200

    def test_forecast_count_matches_requested_days(self, client: TestClient) -> None:
        for days in [1, 3, 7, 14]:
            resp = client.get(
                "/weather/forecast",
                params={"city": "Berlin", "days": days},
                headers=AUTH,
            )
            body = resp.json()
            assert len(body["forecast"]) == days, f"Expected {days} days"

    def test_each_day_has_hourly_slots(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/forecast", params={"city": "Sydney", "days": 2}, headers=AUTH
        )
        for day in resp.json()["forecast"]:
            assert len(day["hourly"]) == 8  # 24h / 3h = 8

    def test_days_must_be_at_least_1(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/forecast", params={"city": "London", "days": 0}, headers=AUTH
        )
        assert resp.status_code == 422

    def test_days_capped_at_14(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/forecast", params={"city": "London", "days": 15}, headers=AUTH
        )
        assert resp.status_code == 422

    def test_price_field(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/forecast", params={"city": "London", "days": 7}, headers=AUTH
        )
        assert resp.json()["price_usd"] == pytest.approx(0.003)

    def test_dates_are_sequential(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/forecast", params={"city": "Moscow", "days": 5}, headers=AUTH
        )
        dates = [day["date"] for day in resp.json()["forecast"]]
        for i in range(1, len(dates)):
            d_prev = date.fromisoformat(dates[i - 1])
            d_curr = date.fromisoformat(dates[i])
            assert d_curr == d_prev + timedelta(days=1)

    def test_unknown_city_returns_404(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/forecast", params={"city": "Oz"}, headers=AUTH
        )
        assert resp.status_code == 404

    def test_temp_range_is_valid(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/forecast", params={"city": "Cairo", "days": 3}, headers=AUTH
        )
        for day in resp.json()["forecast"]:
            assert day["temp_min_c"] <= day["temp_max_c"]
            assert day["temp_min_c"] <= day["temp_avg_c"] <= day["temp_max_c"]


# ---------------------------------------------------------------------------
# Historical
# ---------------------------------------------------------------------------


class TestHistory:
    def _yesterday(self) -> str:
        return (date.today() - timedelta(days=1)).isoformat()

    def test_returns_200_for_past_date(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/history",
            params={"city": "London", "date": self._yesterday()},
            headers=AUTH,
        )
        assert resp.status_code == 200

    def test_response_contains_expected_fields(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/history",
            params={"city": "Paris", "date": "2024-06-15"},
            headers=AUTH,
        )
        d = resp.json()["data"]
        assert d["city"] == "Paris"
        assert d["country"] == "FR"
        assert "temp_min_c" in d
        assert "temp_max_c" in d
        assert "precipitation_total_mm" in d
        assert "sunshine_hours" in d

    def test_price_field(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/history",
            params={"city": "Tokyo", "date": "2023-01-01"},
            headers=AUTH,
        )
        assert resp.json()["price_usd"] == pytest.approx(0.005)

    def test_today_returns_400(self, client: TestClient) -> None:
        today = date.today().isoformat()
        resp = client.get(
            "/weather/history",
            params={"city": "London", "date": today},
            headers=AUTH,
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "DATE_NOT_HISTORICAL"

    def test_invalid_date_format_returns_422(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/history",
            params={"city": "London", "date": "15-06-2024"},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_unknown_city_returns_404(self, client: TestClient) -> None:
        resp = client.get(
            "/weather/history",
            params={"city": "Narnia", "date": "2023-06-01"},
            headers=AUTH,
        )
        assert resp.status_code == 404

    def test_deterministic_for_same_inputs(self, client: TestClient) -> None:
        params = {"city": "Sydney", "date": "2023-03-15"}
        r1 = client.get("/weather/history", params=params, headers=AUTH)
        r2 = client.get("/weather/history", params=params, headers=AUTH)
        assert r1.json()["data"]["temp_avg_c"] == r2.json()["data"]["temp_avg_c"]


# ---------------------------------------------------------------------------
# Monthly climate
# ---------------------------------------------------------------------------


class TestMonthlyClimate:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/climate/monthly", params={"city": "Singapore"}, headers=AUTH)
        assert resp.status_code == 200

    def test_returns_12_months(self, client: TestClient) -> None:
        resp = client.get("/climate/monthly", params={"city": "London"}, headers=AUTH)
        averages = resp.json()["averages"]
        assert len(averages) == 12

    def test_month_numbers_1_to_12(self, client: TestClient) -> None:
        resp = client.get("/climate/monthly", params={"city": "London"}, headers=AUTH)
        months = [a["month"] for a in resp.json()["averages"]]
        assert months == list(range(1, 13))

    def test_koppen_classification_present(self, client: TestClient) -> None:
        resp = client.get("/climate/monthly", params={"city": "Dubai"}, headers=AUTH)
        body = resp.json()
        assert "koppen_classification" in body
        assert body["koppen_classification"] == "BWh"

    def test_price_field(self, client: TestClient) -> None:
        resp = client.get("/climate/monthly", params={"city": "Cairo"}, headers=AUTH)
        assert resp.json()["price_usd"] == pytest.approx(0.002)

    def test_unknown_city_returns_404(self, client: TestClient) -> None:
        resp = client.get("/climate/monthly", params={"city": "Wakanda"}, headers=AUTH)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class TestAlerts:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/alerts", params={"region": "California"}, headers=AUTH)
        assert resp.status_code == 200

    def test_response_structure(self, client: TestClient) -> None:
        resp = client.get("/alerts", params={"region": "Texas"}, headers=AUTH)
        body = resp.json()
        assert "region" in body
        assert "active_alerts" in body
        assert isinstance(body["active_alerts"], int)
        assert isinstance(body["alerts"], list)

    def test_alert_count_matches_list(self, client: TestClient) -> None:
        resp = client.get("/alerts", params={"region": "Florida"}, headers=AUTH)
        body = resp.json()
        assert body["active_alerts"] == len(body["alerts"])

    def test_alert_has_required_fields(self, client: TestClient) -> None:
        # Try multiple regions to ensure we get at least one with alerts.
        for region in ["North Sea", "Gulf Coast", "Great Plains"]:
            resp = client.get("/alerts", params={"region": region}, headers=AUTH)
            alerts = resp.json()["alerts"]
            if alerts:
                a = alerts[0]
                assert "alert_id" in a
                assert "type" in a
                assert "severity" in a
                assert a["severity"] in {"LOW", "MODERATE", "HIGH", "EXTREME"}
                assert "headline" in a
                assert "issued_at" in a
                assert "expires_at" in a
                break

    def test_price_field(self, client: TestClient) -> None:
        resp = client.get("/alerts", params={"region": "London"}, headers=AUTH)
        assert resp.json()["price_usd"] == pytest.approx(0.001)

    def test_deterministic_for_same_region(self, client: TestClient) -> None:
        r1 = client.get("/alerts", params={"region": "Pacific Northwest"}, headers=AUTH)
        r2 = client.get("/alerts", params={"region": "Pacific Northwest"}, headers=AUTH)
        assert r1.json()["active_alerts"] == r2.json()["active_alerts"]


# ---------------------------------------------------------------------------
# Carbon footprint
# ---------------------------------------------------------------------------


class TestCarbonFootprint:
    def test_returns_200_for_valid_coords(self, client: TestClient) -> None:
        resp = client.get(
            "/carbon/footprint", params={"lat": 51.5, "lon": -0.1}, headers=AUTH
        )
        assert resp.status_code == 200

    def test_response_structure(self, client: TestClient) -> None:
        resp = client.get(
            "/carbon/footprint", params={"lat": 40.7, "lon": -74.0}, headers=AUTH
        )
        d = resp.json()["data"]
        assert "carbon_intensity_gco2_kwh" in d
        assert "carbon_index" in d
        assert d["carbon_index"] in {"VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH"}
        assert "renewable_share_pct" in d
        assert "energy_mix" in d
        assert "forecast_next_hour_gco2_kwh" in d

    def test_energy_mix_sums_to_100(self, client: TestClient) -> None:
        resp = client.get(
            "/carbon/footprint", params={"lat": 35.7, "lon": 139.7}, headers=AUTH
        )
        mix = resp.json()["data"]["energy_mix"]
        total = mix["renewable_pct"] + mix["fossil_pct"] + mix["nuclear_pct"]
        # Allow small floating-point tolerance
        assert abs(total - 100.0) < 2.0

    def test_price_field(self, client: TestClient) -> None:
        resp = client.get(
            "/carbon/footprint", params={"lat": 0.0, "lon": 0.0}, headers=AUTH
        )
        assert resp.json()["price_usd"] == pytest.approx(0.002)

    def test_lat_out_of_range_returns_422(self, client: TestClient) -> None:
        resp = client.get(
            "/carbon/footprint", params={"lat": 95.0, "lon": 0.0}, headers=AUTH
        )
        assert resp.status_code == 422

    def test_lon_out_of_range_returns_422(self, client: TestClient) -> None:
        resp = client.get(
            "/carbon/footprint", params={"lat": 0.0, "lon": 200.0}, headers=AUTH
        )
        assert resp.status_code == 422

    def test_southern_hemisphere(self, client: TestClient) -> None:
        resp = client.get(
            "/carbon/footprint", params={"lat": -33.9, "lon": 151.2}, headers=AUTH
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["carbon_intensity_gco2_kwh"] > 0

    def test_deterministic(self, client: TestClient) -> None:
        params = {"lat": 48.85, "lon": 2.35}
        r1 = client.get("/carbon/footprint", params=params, headers=AUTH)
        r2 = client.get("/carbon/footprint", params=params, headers=AUTH)
        assert r1.json()["data"]["carbon_intensity_gco2_kwh"] == r2.json()["data"]["carbon_intensity_gco2_kwh"]
