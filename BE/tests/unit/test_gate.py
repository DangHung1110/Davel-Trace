"""Unit test for gate primitives (T011). Fixture-based, no lane-A files.

Each tamper fails exactly its own check; the good plan passes all four.

Run from repo root: python BE/tests/unit/test_gate.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.gate import (  # noqa: E402
    all_pass,
    check_b3,
    check_bcs,
    check_far,
    check_vroh,
)

POIS = {
    "musu": {"verified": True, "fee": 60000, "opening_hours": ["07:30-17:00"]},
    "beach": {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"]},
    "draft": {"verified": False, "fee": 0, "opening_hours": ["00:00-23:59"]},
}
MATRIX = {"musu->beach": {"minutes": 10}, "beach->musu": {"minutes": 10}}
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00"}
GOOD = {"activities": [
    {"poi_id": "musu", "start": "08:00", "end": "09:30"},
    {"poi_id": "beach", "start": "10:00", "end": "12:00"}]}


class TestGate(unittest.TestCase):
    def test_good_passes_all(self):
        for fn in (check_far, check_vroh, check_b3, check_bcs):
            self.assertTrue(fn(GOOD, TRIP, POIS, MATRIX))
        self.assertEqual(all_pass(GOOD, TRIP, POIS, MATRIX),
                         {"passed": True, "failed": []})

    def test_unknown_poi_fails_far_only(self):
        bad = {"activities": [{"poi_id": "ghost", "start": "08:00", "end": "09:00"}]}
        self.assertFalse(check_far(bad, TRIP, POIS, MATRIX))
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"], ["FAR"])

    def test_unverified_poi_fails_far(self):
        bad = {"activities": [{"poi_id": "draft", "start": "08:00", "end": "09:00"}]}
        self.assertFalse(check_far(bad, TRIP, POIS, MATRIX))

    def test_closed_hours_fails_vroh_only(self):
        bad = {"activities": [{"poi_id": "musu", "start": "18:00", "end": "19:00"}]}
        self.assertFalse(check_vroh(bad, TRIP, POIS, MATRIX))
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"], ["VROH"])

    def test_tight_gap_fails_b3_only(self):
        bad = {"activities": [
            {"poi_id": "musu", "start": "08:00", "end": "09:30"},
            {"poi_id": "beach", "start": "09:35", "end": "12:00"}]}  # gap 5 < 10
        self.assertFalse(check_b3(bad, TRIP, POIS, MATRIX))
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"], ["B3"])

    def test_over_budget_fails_bcs_only(self):
        trip = dict(TRIP, budget=10000)
        self.assertFalse(check_bcs(GOOD, trip, POIS, MATRIX))
        self.assertEqual(all_pass(GOOD, trip, POIS, MATRIX)["failed"], ["BCS"])


if __name__ == "__main__":
    unittest.main()
