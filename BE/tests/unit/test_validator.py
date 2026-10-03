"""Unit test for validator gate (T018). Fixture-based (no lane data).

Valid plan passes; each tamper fails its named gate with offenders listed.

Run from repo root: python BE/tests/unit/test_validator.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

POIS = {
    "musu": {"verified": True, "fee": 60000, "opening_hours": ["07:30-17:00"]},
    "beach": {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"]},
}
MATRIX = {"musu->beach": {"minutes": 10}, "beach->musu": {"minutes": 10}}
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00"}
GOOD = {"activities": [
    {"poi_id": "musu", "start": "08:00", "end": "09:30"},
    {"poi_id": "beach", "start": "10:00", "end": "12:00"}]}


class TestValidator(unittest.TestCase):
    def test_good_passes(self):
        rep = validate(GOOD, TRIP, POIS, MATRIX)
        self.assertEqual(rep["passed"], True)
        self.assertEqual(rep["violations"], [])
        self.assertEqual(set(rep["checks"]), {"FAR", "VROH", "B3", "BCS", "ETB"})
        print(f"\n good: {rep['checks']}")

    def test_ghost_poi(self):
        bad = {"activities": [{"poi_id": "ghost", "start": "08:00", "end": "09:00"}]}
        rep = validate(bad, TRIP, POIS, MATRIX)
        self.assertEqual(rep["violations"], ["FAR"])
        self.assertEqual(rep["details"]["FAR"], ["ghost"])

    def test_closed_hours(self):
        bad = {"activities": [{"poi_id": "musu", "start": "16:30", "end": "17:30"}]}
        rep = validate(bad, TRIP, POIS, MATRIX)
        self.assertEqual(rep["violations"], ["VROH"])
        self.assertEqual(rep["details"]["VROH"], ["musu"])

    def test_plan_ending_after_return_time_fails_ETB(self):
        late = {"activities": [
            {"poi_id": "beach", "start": "16:30", "end": "17:30"}]}
        rep = validate(late, dict(TRIP, return_time="17:00"), POIS, MATRIX)
        self.assertFalse(rep["checks"]["ETB"])
        self.assertEqual(rep["violations"], ["ETB"])
        self.assertEqual(rep["details"]["ETB"], ["beach"])

    def test_tight_gap(self):
        bad = {"activities": [
            {"poi_id": "musu", "start": "08:00", "end": "09:30"},
            {"poi_id": "beach", "start": "09:35", "end": "12:00"}]}
        rep = validate(bad, TRIP, POIS, MATRIX)
        self.assertEqual(rep["violations"], ["B3"])
        self.assertEqual(rep["details"]["B3"], ["musu->beach"])

    def test_over_budget(self):
        rep = validate(GOOD, dict(TRIP, budget=10000), POIS, MATRIX)
        self.assertEqual(rep["violations"], ["BCS"])
        self.assertTrue(rep["details"]["BCS"])

    def test_optimizer_output_validates(self):
        pois = [StubPOI("musu", 90, 450, 1020, 3.0), StubPOI("beach", 120, 360, 1140, 5.0)]
        travel = {("depot", "musu"): 10, ("depot", "beach"): 10,
                  ("musu", "beach"): 10, ("beach", "musu"): 10}
        out = optimize(pois, travel, StubTrip(420, 1080))
        self.assertIsNotNone(out["itinerary"])
        full_pois = {**POIS, "musu": {**POIS["musu"]}, "beach": {**POIS["beach"]}}
        rep = validate(out["itinerary"], TRIP, full_pois, MATRIX)
        self.assertTrue(rep["passed"], rep)


if __name__ == "__main__":
    unittest.main()
