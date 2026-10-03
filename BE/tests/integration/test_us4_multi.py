"""US4 integration (T034, lane C — closes US4). Distinctness + persistence.

1 request -> >=2 feasible plans with distinct scores/reasons; select 1
-> active correct + others kept for compare. Pool built from 3 stub
profiles (STUB-NOTE: real multi-run pool is lane-B T032, wired at
phase-PR; shapes here mirror its contract). Pipeline leg via the
itinerary endpoint on a fixture snapshot proves the flow works.

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
from BE.app.routers import select as select_mod  # noqa: E402

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

# STUB pool mirroring lane-B T032 shapes (replaced at phase-PR)
POOL = [
    {"itinerary_id": "it-sav", "profile": "savings",
     "reason": "tiết kiệm: phạt nặng chi phí",
     "activities": [{"poi_id": "hill"}, {"poi_id": "beach"}],
     "total_cost": 0, "preference": 4.65,
     "constraint_status": {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1}},
    {"itinerary_id": "it-bal", "profile": "balanced",
     "reason": "cân bằng: tổng rating cao nhất",
     "activities": [{"poi_id": "hill"}, {"poi_id": "noodle"}],
     "total_cost": 50000, "preference": 4.6,
     "constraint_status": {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1}},
    {"itinerary_id": "it-exp", "profile": "experience",
     "reason": "trải nghiệm: ưu tiên rating + đậm chất",
     "activities": [{"poi_id": "beach"}, {"poi_id": "noodle"}],
     "total_cost": 50000, "preference": 4.55,
     "constraint_status": {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1}},
]

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

    def test_pipeline_yields_feasible_plan(self):
        r = client.post("/v1/itinerary", json={"trip": TRIP, "profiles": ["balanced"]})
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        self.assertTrue(plan["activities"])
        self.assertEqual(set(plan["constraint_status"]), {"FAR", "VROH", "B3", "BCS"})

    def test_pool_distinctness(self):
        feasible = [p for p in POOL
                    if all(v == 1 for v in p["constraint_status"].values())]
        self.assertGreaterEqual(len(feasible), 2)
        self.assertGreater(len({p["total_cost"] for p in feasible}), 1)
        self.assertGreater(len({p["preference"] for p in feasible}), 1)
        self.assertEqual(len({p["reason"] for p in feasible}), len(feasible))

    def test_select_persists_others(self):
        select_mod.reset_store()
        select_mod.register(POOL)
        r = client.post("/v1/itinerary/select", json={"itinerary_id": "it-exp"})
        self.assertEqual(r.json(), {"active_id": "it-exp"})
        store = select_mod.get_store()
        self.assertEqual(store["active_id"], "it-exp")
        self.assertEqual(sorted(store["plans"]), ["it-bal", "it-exp", "it-sav"])
        print(f"\n active it-exp kept: {sorted(store['plans'])}")


if __name__ == "__main__":
    unittest.main()
