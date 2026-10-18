"""US4 multi-profile API boundary using a real retrieval fixture.

The former hand-authored plan pool is removed: lane B's profile optimizer
is absent here, so the route must return an explicit 501 until that seam is
available. When present, one request must return one plan per requested profile.

Run: python BE/tests/integration/test_us4_multi.py -v (or pytest)
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services import retrieval as retrieval_svc  # noqa: E402

POIS = [
    {"poi_id": "hill", "name": "H", "type": "nature", "lat": 16.1,
     "lon": 108.2, "opening_hours": ["05:00-18:00"],
     "visit_min": {"p25": 60, "p50": 120, "p75": 180}, "dur_source": "c",
     "dur_confidence": "low", "price_level": 1, "fee": 0, "rating": 4.7,
     "tags": [], "intensity": 3, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
    {"poi_id": "beach", "name": "B", "type": "beach", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["00:00-23:59"],
     "visit_min": {"p25": 60, "p50": 120, "p75": 180}, "dur_source": "c",
     "dur_confidence": "low", "price_level": 1, "fee": 0, "rating": 4.6,
     "tags": [], "intensity": 2, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
    {"poi_id": "noodle", "name": "N", "type": "restaurant", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["07:00-21:00"],
     "visit_min": {"p25": 30, "p50": 60, "p75": 90}, "dur_source": "c",
     "dur_confidence": "low", "price_level": 2, "fee": 50000, "rating": 4.5,
     "tags": [], "intensity": 1, "ambience": "", "weather_sensitive": False,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
]
CELLS = {f"{a}->{b}": {"minutes": 0 if a == b else 15, "km": 4.0}
         for a in ("hill", "beach", "noodle") for b in ("hill", "beach", "noodle")}
TRIP = {"trip_id": "t1", "user_id": "u1", "city": "da-nang",
        "start_time": "07:00", "end_time": "18:00", "days": 1,
        "travelers": 2, "budget": 3000000, "transport": ["motorbike"],
        "must_visit": [], "avoid": [], "activities": ["leo núi", "biển"],
        "food_prefs": [], "order_prefs": []}

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestUS4Multi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="us4_")
        with open(os.path.join(cls.tmp, "pois.json"), "w", encoding="utf-8") as f:
            json.dump({"pois": POIS}, f, ensure_ascii=False)
        with open(os.path.join(cls.tmp, "matrix.json"), "w", encoding="utf-8") as f:
            json.dump({"ids": ["hill", "beach", "noodle"], "cells": CELLS}, f)
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=cls.tmp,
                                                      snapshot_name="us4")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._settings

    def test_three_profiles_yield_three_plans_or_501(self):
        pool = retrieval_svc.retrieve(TRIP, POIS)["candidates"]
        self.assertEqual({candidate["poi_id"] for candidate in pool},
                         {"hill", "beach"})

        profiles = ["savings", "balanced", "experience"]
        r = client.post("/v1/itinerary", json={"trip": TRIP, "profiles": profiles})
        if r.status_code == 501:
            self.assertEqual(set(r.json()), {"error", "message"})
            self.assertEqual(r.json()["error"], "PLANNER_UNAVAILABLE")
            return

        self.assertEqual(r.status_code, 200, r.text)
        plans = r.json()["plans"]
        self.assertEqual([plan["profile"] for plan in plans], profiles)
        self.assertEqual(len(plans), 3)


if __name__ == "__main__":
    unittest.main()
