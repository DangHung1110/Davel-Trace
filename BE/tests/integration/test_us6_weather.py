"""US6 integration (T041, lane C). Mocked 80% afternoon rain.

Outdoor beach afternoon -> indoor swap + cited reason (spec US6
acceptance); dry morning activity untouched.

Run: python BE/tests/integration/test_us6_weather.py -v (or pytest)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.weather import apply_weather  # noqa: E402

BY_ID = {
    "beach": {"poi_id": "beach", "name": "Bai bien", "type": "beach",
              "rating": 4.6, "weather_sensitive": True},
    "museum": {"poi_id": "museum", "name": "Bao tang", "type": "museum",
               "rating": 4.4, "weather_sensitive": False},
    "noodle": {"poi_id": "noodle", "name": "Mi Quang", "type": "restaurant",
               "rating": 4.5, "weather_sensitive": False},
}
FORECAST = {"fetched_at": "2026-10-03T07:00:00", "source": "open-meteo",
            "stale": False,
            "hourly": [{"at": f"2026-10-03T{h:02d}:00", "temp_c": 33.0,
                        "rain_prob": 0.8 if h >= 14 else 0.1}
                       for h in range(24)]}
ACTS = [{"poi_id": "museum", "start": "09:00", "end": "10:30"},
        {"poi_id": "beach", "start": "15:30", "end": "17:30"}]


class TestUS6Weather(unittest.TestCase):
    def test_rain_triggers_indoor_swap(self):
        out = apply_weather(ACTS, BY_ID, FORECAST)
        self.assertEqual(len(out["swaps"]), 1)
        swap = out["swaps"][0]
        self.assertEqual(swap["from"], "beach")
        self.assertEqual(swap["to"], "noodle")  # best indoor by rating
        self.assertIn("80%", swap["reason"])
        self.assertIn("15:30", swap["reason"])
        ids = [a["poi_id"] for a in out["activities"]]
        self.assertNotIn("beach", ids)
        self.assertEqual(out["explanations"], [swap["reason"]])
        print(f"\n swap: {swap['reason']}")

    def test_dry_morning_untouched(self):
        out = apply_weather(ACTS, BY_ID, FORECAST)
        self.assertEqual(out["activities"][0]["poi_id"], "museum")


if __name__ == "__main__":
    unittest.main()
