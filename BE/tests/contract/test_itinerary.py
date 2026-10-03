"""Contract test POST /v1/itinerary (T013, lane C). Shape per contracts/api.md.

Uses a tmp snapshot fixture (lane C has no seed): plans[0] carries
activities + totals + constraint_status + version, selected is None;
missing snapshot -> SNAPSHOT_MISSING envelope (no crash).
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402

POIS = [
    {"poi_id": "beach", "name": "Beach", "type": "beach", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["00:00-23:59"],
     "visit_min": {"p25": 60, "p50": 90, "p75": 120}, "dur_source": "category_rule",
     "dur_confidence": "low", "price_level": 1, "fee": 0, "rating": 4.6,
     "tags": ["biển"], "intensity": 2, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "2026-09-28", "verified": True},
    {"poi_id": "noodle", "name": "Noodle", "type": "restaurant", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["07:00-21:00"],
     "visit_min": {"p25": 30, "p50": 60, "p75": 90}, "dur_source": "category_rule",
     "dur_confidence": "low", "price_level": 2, "fee": 50000, "rating": 4.5,
     "tags": ["ăn"], "intensity": 1, "ambience": "", "weather_sensitive": False,
     "pros": [], "cons": [], "source": "t", "fetched_at": "2026-09-28", "verified": True},
]
CELLS = {"beach->noodle": {"minutes": 10, "km": 3.0},
         "noodle->beach": {"minutes": 10, "km": 3.0}}
TRIP = {"trip_id": "t1", "user_id": "u1", "city": "da-nang",
        "start_time": "07:00", "end_time": "18:00", "days": 1,
        "travelers": 2, "budget": 3000000, "transport": ["motorbike"],
        "must_visit": [], "avoid": [], "activities": ["biển"],
        "food_prefs": [], "order_prefs": []}

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestItineraryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="snap_")
        with open(os.path.join(cls.tmp, "pois.json"), "w", encoding="utf-8") as f:
            json.dump({"pois": POIS}, f, ensure_ascii=False)
        with open(os.path.join(cls.tmp, "matrix.json"), "w", encoding="utf-8") as f:
            json.dump({"ids": ["beach", "noodle"], "cells": CELLS}, f)
        cls._real = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=cls.tmp,
                                                      snapshot_name="test")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._real

    def test_itinerary_shape(self):
        r = client.post("/v1/itinerary", json={"trip": TRIP, "profiles": ["balanced"]})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("plans", body)
        self.assertIsNone(body["selected"])
        plan = body["plans"][0]
        for k in ("itinerary_id", "activities", "total_cost", "total_km",
                  "total_min", "constraint_status", "version"):
            self.assertIn(k, plan)
        self.assertTrue(plan["activities"])

    def test_missing_snapshot_envelope(self):
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir="/no/such/dir",
                                                      snapshot_name="x")
        try:
            r = client.post("/v1/itinerary", json={"trip": TRIP})
        finally:
            itinerary_mod.get_settings = lambda: Settings(snapshot_dir=self.tmp,
                                                          snapshot_name="test")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"], "SNAPSHOT_MISSING")


if __name__ == "__main__":
    unittest.main()
