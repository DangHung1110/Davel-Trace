"""Climate prior, time-of-day travel factors, exposure + u(t) coverage of all 1000 POIs."""

import datetime as dt
import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)

from BE.app.services import climate, travel_time  # noqa: E402
from BE.app.services.time_utility import load_profiles  # noqa: E402

with open(os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2", "pois.json"), encoding="utf-8") as f:
    POIS = json.load(f)["pois"]
ZONES = {p["zone"] for p in POIS}


class TestClimate(unittest.TestCase):
    def test_every_zone_month_hour(self):
        z = climate.load()["zones"]
        self.assertTrue(ZONES <= set(z), ZONES - set(z))
        for zone in z.values():
            self.assertEqual(sorted(map(int, zone["months"])), list(range(1, 13)))
            for m in zone["months"].values():
                self.assertEqual([h["hour"] for h in m["hours"]], list(range(24)))
                for h in m["hours"]:
                    self.assertTrue(0 <= h["rain_prob"] <= 1 and 5 < h["temp_c"] < 45)

    def test_known_seasons(self):
        # June midday hotter than January; Oct/Nov wetter than April; Ba Na (867 m) cooler
        self.assertGreater(climate.climate_at("trung_tam", 6, 13 * 60)["feels_c"],
                           climate.climate_at("trung_tam", 1, 13 * 60)["feels_c"] + 8)
        self.assertGreater(climate.rainy_day_prob("trung_tam", 11), 3 * climate.rainy_day_prob("trung_tam", 4))
        self.assertLess(climate.climate_at("ba_na_tay", 6, 13 * 60)["temp_c"],
                        climate.climate_at("trung_tam", 6, 13 * 60)["temp_c"] - 4)

    def test_as_forecast_shape(self):
        fc = climate.as_forecast(dt.date(2026, 11, 15), "hoi_an")
        self.assertEqual(len(fc["hourly"]), 24)
        self.assertEqual(fc["hourly"][13]["at"], "2026-11-15T13:00")
        self.assertEqual(fc["source"], "climate_prior")


class TestTravelFactor(unittest.TestCase):
    def test_every_zone_has_factors(self):
        self.assertTrue(ZONES <= set(travel_time.load()["factors"]))

    def test_peak_slower_than_day_slower_than_night(self):
        f = lambda t: travel_time.factor("trung_tam", "trung_tam", t)
        self.assertGreater(f(17 * 60 + 30), f(10 * 60))
        self.assertGreater(f(10 * 60), f(23 * 60))

    def test_cross_zone_takes_larger_and_unknown_is_free_flow(self):
        t = 7 * 60 + 30
        self.assertEqual(travel_time.factor("trung_tam", "ba_na_tay", t),
                         travel_time.factor("trung_tam", "trung_tam", t))
        self.assertEqual(travel_time.factor("x", None, t), 1.0)
        self.assertEqual(travel_time.travel_at(20, "trung_tam", "trung_tam", 17 * 60 + 30), 28)


class TestAllPoisCovered(unittest.TestCase):
    def test_time_profile_for_all_1000(self):
        profiles = load_profiles()
        self.assertEqual([p["poi_id"] for p in POIS if p["time_profile"] not in profiles], [])

    def test_exposure_for_all_1000(self):
        for p in POIS:
            t = p["tags"]
            self.assertIn(t.get("rain_cover"), ("open", "mixed", "enclosed"), p["poi_id"])
            self.assertIsNotNone(t.get("sun_exposure"), p["poi_id"])
            self.assertIn(t.get("exposure_source"), ("explicit", "category_prior"), p["poi_id"])


if __name__ == "__main__":
    unittest.main()
