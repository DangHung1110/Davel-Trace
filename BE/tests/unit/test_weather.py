"""Unit test for weather service (T039). Mock transport + cache/offline.

Run from repo root: python BE/tests/unit/test_weather.py -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.weather import fetch_forecast  # noqa: E402

HOURS = [f"2026-10-03T{h:02d}:00" for h in range(24)]
RAIN = [0.0] * 24


def mock_transport(url: str) -> dict:
    assert "open-meteo" in url
    return {"hourly": {"time": HOURS, "temperature_2m": [30.0] * 24,
                       "precipitation_probability": [int(r * 100) for r in RAIN]}}


def down_transport(url: str) -> dict:
    raise ConnectionError("no network")


class TestWeather(unittest.TestCase):
    def setUp(self):
        self.cache = os.path.join(tempfile.mkdtemp(prefix="wx_"), "w.json")

    def test_fetch_shape_and_labels(self):
        snap = fetch_forecast(transport=mock_transport, cache_path=self.cache)
        self.assertEqual(snap["source"], "open-meteo")
        self.assertFalse(snap["stale"])
        self.assertTrue(snap["fetched_at"])
        self.assertEqual(len(snap["hourly"]), 24)
        self.assertIn("rain_prob", snap["hourly"][0])
        self.assertTrue(os.path.exists(self.cache))

    def test_offline_uses_labeled_cache(self):
        fetch_forecast(transport=mock_transport, cache_path=self.cache)
        snap = fetch_forecast(transport=down_transport, cache_path=self.cache)
        self.assertEqual(snap["source"], "cache")
        self.assertTrue(snap["stale"])
        self.assertTrue(snap["fetched_at"])

    def test_offline_no_cache_clear_error(self):
        with self.assertRaises(RuntimeError):
            fetch_forecast(transport=down_transport,
                           cache_path=os.path.join(self.cache + ".missing"))


if __name__ == "__main__":
    unittest.main()
