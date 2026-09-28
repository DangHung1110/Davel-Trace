"""Unit test for multi-profile runs (T032, opens US4). Fixture-based.

One request -> >=2 feasible plans with clearly distinct scores/reasons.

Run from repo root: python BE/tests/unit/test_profiles.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.profiles import run_profiles  # noqa: E402

H = 60
POIS = [
    {"poi_id": "fancy", "visit_min": 90, "rating": 5.0, "fee": 500000,
     "intensity": 1, "opening_hours": ["10:00-22:00"]},
    {"poi_id": "hill", "visit_min": 120, "rating": 4.7, "fee": 0,
     "intensity": 3, "opening_hours": ["05:00-18:00"]},
    {"poi_id": "beach", "visit_min": 120, "rating": 4.6, "fee": 0,
     "intensity": 2, "opening_hours": ["00:00-23:59"]},
    {"poi_id": "noodle", "visit_min": 60, "rating": 4.5, "fee": 50000,
     "intensity": 1, "opening_hours": ["07:00-21:00"]},
]
IDS = [p["poi_id"] for p in POIS]
TRAVEL = {(a, b): 15 for a in IDS for b in IDS if a != b}
MATRIX = {f"{a}->{b}": {"minutes": 0 if a == b else 15, "km": 4.0}
          for a in IDS for b in IDS}
TRIP = {"trip_id": "t1", "budget": 1000000,
        "start_time": "07:00", "end_time": "16:00"}


class TestProfiles(unittest.TestCase):
    def test_three_profiles_feasible_distinct(self):
        pool = run_profiles(POIS, TRAVEL, TRIP, MATRIX)
        self.assertIsNone(pool["selected"])
        self.assertGreaterEqual(len(pool["plans"]), 2)
        sigs = {(tuple(a["poi_id"] for a in p["itinerary"]["activities"]))
                for p in pool["plans"]}
        costs = {p["total_cost"] for p in pool["plans"]}
        prefs = {p["preference"] for p in pool["plans"]}
        self.assertTrue(len(sigs) > 1 or len(costs) > 1,
                        "plans must differ in composition or cost")
        self.assertTrue(len(costs) > 1 or len(prefs) > 1,
                        "scores must differ")
        for p in pool["plans"]:
            self.assertTrue(p["reason"])
            self.assertEqual(p["constraint_status"],
                             {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1})
        print(f"\n pool: {[(p['profile'], p['total_cost'], p['preference']) for p in pool['plans']]}")

    def test_savings_cheapest(self):
        pool = run_profiles(POIS, TRAVEL, TRIP, MATRIX)
        by_prof = {p["profile"]: p for p in pool["plans"]}
        self.assertLessEqual(by_prof["savings"]["total_cost"],
                             by_prof["balanced"]["total_cost"])


if __name__ == "__main__":
    unittest.main()
