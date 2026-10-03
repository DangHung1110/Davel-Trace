"""Unit test for response builder (T019). Fixture-based.

Totals add up, status mirrors per-gate results, version threads through.

Run from repo root: python BE/tests/unit/test_response.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.response import build_plan  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

POIS = {
    "musu": {"verified": True, "fee": 60000, "opening_hours": ["07:30-17:00"]},
    "beach": {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"]},
}
MATRIX = {"musu->beach": {"minutes": 10, "km": 3.5},
          "beach->musu": {"minutes": 10, "km": 3.5}}
TRIP = {"trip_id": "t1", "budget": 3000000,
        "start_time": "07:00", "end_time": "18:00"}
OPT = {"status": "optimal",
       "itinerary": {"activities": [
           {"poi_id": "musu", "start": "08:00", "end": "09:30"},
           {"poi_id": "beach", "start": "10:00", "end": "12:00"}]}}


class TestResponse(unittest.TestCase):
    def test_totals_correct(self):
        plan = build_plan(OPT, validate(OPT["itinerary"], TRIP, POIS, MATRIX),
                          TRIP, POIS, MATRIX)
        self.assertEqual(plan["total_cost"], 60000)
        self.assertEqual(plan["total_km"], 3.5)
        self.assertEqual(plan["total_min"], 90 + 120 + 10)  # visit + travel
        self.assertEqual(len(plan["segments"]), 1)
        print(f"\n totals: {plan['total_cost']}d {plan['total_km']}km "
              f"{plan['total_min']}min")

    def test_status_reflects_gates(self):
        plan = build_plan(OPT, validate(OPT["itinerary"], TRIP, POIS, MATRIX),
                          TRIP, POIS, MATRIX)
        self.assertTrue(plan["passed"])
        self.assertEqual(plan["constraint_status"],
                         {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1, "ETB": 1})
        self.assertEqual(plan["violations"], [])

    def test_failed_status_mirrors(self):
        bad = {"status": "optimal", "itinerary": {"activities": [
            {"poi_id": "musu", "start": "16:30", "end": "17:30"}]}}
        plan = build_plan(bad, validate(bad["itinerary"], TRIP, POIS, MATRIX),
                          TRIP, POIS, MATRIX)
        self.assertFalse(plan["passed"])
        self.assertEqual(plan["constraint_status"]["VROH"], 0)
        self.assertEqual(plan["violations"], ["VROH"])

    def test_version_present_and_threaded(self):
        plan = build_plan(OPT, validate(OPT["itinerary"], TRIP, POIS, MATRIX),
                          TRIP, POIS, MATRIX)
        self.assertEqual(plan["version"], 1)
        plan2 = build_plan(OPT, validate(OPT["itinerary"], TRIP, POIS, MATRIX),
                           TRIP, POIS, MATRIX, version=3,
                           itinerary_id="it1")
        self.assertEqual(plan2["version"], 3)
        self.assertTrue(plan2["created_at"])


if __name__ == "__main__":
    unittest.main()
