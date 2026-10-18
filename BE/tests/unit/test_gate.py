"""Unit test for the canonical gate registry (T011). No lane-A files.

TCS mirrors VROH/B3/ETB; HCS mirrors all five concrete lane-B hard gates.
Both remain local boolean stubs until the T061 evaluator wiring PR.

Run from repo root: python BE/tests/unit/test_gate.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.gate import (  # noqa: E402
    CHECKS,
    all_pass,
    check_b3,
    check_bcs,
    check_etb,
    check_far,
    check_hcs,
    check_tcs,
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
        for _, fn in CHECKS:
            self.assertEqual(fn(GOOD, TRIP, POIS, MATRIX),
                             {"passed": True, "score": 1.0})
        self.assertEqual(all_pass(GOOD, TRIP, POIS, MATRIX),
                         {"passed": True, "failed": []})

    def test_registry_and_result_shape_are_canonical(self):
        self.assertEqual([name for name, _ in CHECKS],
                         ["FAR", "VROH", "B3", "BCS", "ETB", "TCS", "HCS"])
        for _, fn in CHECKS:
            result = fn(GOOD, TRIP, POIS, MATRIX)
            self.assertEqual(set(result), {"passed", "score"})
            self.assertIs(type(result["passed"]), bool)
            self.assertIs(type(result["score"]), float)

    def test_unknown_poi_fails_far_and_hcs(self):
        bad = {"activities": [{"poi_id": "ghost", "start": "08:00", "end": "09:00"}]}
        self.assertFalse(check_far(bad, TRIP, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"],
                         ["FAR", "HCS"])

    def test_unverified_poi_fails_far(self):
        bad = {"activities": [{"poi_id": "draft", "start": "08:00", "end": "09:00"}]}
        self.assertFalse(check_far(bad, TRIP, POIS, MATRIX)["passed"])

    def test_closed_hours_fails_vroh_and_mirrors(self):
        bad = {"activities": [{"poi_id": "musu", "start": "16:30", "end": "17:30"}]}
        self.assertFalse(check_vroh(bad, TRIP, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"],
                         ["VROH", "TCS", "HCS"])

    def test_tight_gap_fails_b3_and_mirrors(self):
        bad = {"activities": [
            {"poi_id": "musu", "start": "08:00", "end": "09:30"},
            {"poi_id": "beach", "start": "09:35", "end": "12:00"}]}  # gap 5 < 10
        self.assertFalse(check_b3(bad, TRIP, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"],
                         ["B3", "TCS", "HCS"])

    def test_over_budget_fails_bcs_and_hcs(self):
        trip = dict(TRIP, budget=10000)
        self.assertFalse(check_bcs(GOOD, trip, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(GOOD, trip, POIS, MATRIX)["failed"],
                         ["BCS", "HCS"])

    def test_tcs_and_hcs_mirror_the_lane_b_gates(self):
        self.assertTrue(check_tcs(GOOD, TRIP, POIS, MATRIX)["passed"])
        self.assertTrue(check_hcs(GOOD, TRIP, POIS, MATRIX)["passed"])

        over_budget_trip = dict(TRIP, budget=10000)
        self.assertTrue(check_tcs(GOOD, over_budget_trip, POIS, MATRIX)["passed"])
        self.assertEqual(check_hcs(GOOD, over_budget_trip, POIS, MATRIX),
                         {"passed": False, "score": 0.0})

    def test_return_time_is_hard_etb_deadline_and_uses_earlier_bound(self):
        late = {"activities": [
            {"poi_id": "beach", "start": "16:30", "end": "17:30"}]}
        return_deadline = dict(TRIP, return_time="17:00")
        self.assertEqual(check_etb(late, return_deadline, POIS, MATRIX),
                         {"passed": False, "score": 0.0})
        self.assertFalse(check_tcs(late, return_deadline, POIS, MATRIX)["passed"])
        self.assertFalse(check_hcs(late, return_deadline, POIS, MATRIX)["passed"])

        earlier_end = dict(TRIP, end_time="17:00", return_time="19:00")
        self.assertFalse(check_etb(late, earlier_end, POIS, MATRIX)["passed"])

        on_deadline = {"activities": [
            {"poi_id": "beach", "start": "16:00", "end": "17:00"}]}
        self.assertTrue(check_etb(on_deadline, return_deadline, POIS, MATRIX)["passed"])


if __name__ == "__main__":
    unittest.main()
