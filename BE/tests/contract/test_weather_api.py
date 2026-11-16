"""Contract tests for GET /v1/weather (contracts/api.md)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestWeatherApi(unittest.TestCase):
    def test_get_weather_returns_cached_snapshot_shape(self):
        forecast = {"fetched_at": "2026-10-18T07:00:00", "hourly": [],
                    "source": "cache", "stale": True}
        with patch("BE.app.routers.weather.weather_svc.fetch_forecast",
                   return_value=forecast) as fetch:
            r = client.get("/v1/weather", params={"lat": 16.05, "lon": 108.2})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), forecast)
        fetch.assert_called_once_with(16.05, 108.2)

    def test_query_coordinates_are_required(self):
        r = client.get("/v1/weather")

        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.json()), {"error", "message"})
        self.assertEqual(r.json()["error"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
