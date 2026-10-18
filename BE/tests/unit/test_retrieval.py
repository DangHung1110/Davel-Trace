"""Unit test for POI retrieval (T015). Fixture-based (no seed in lane C).

Covers: type filter, closed/budget/unverified exclusion, must-visit
kept, avoid excluded.

Run from repo root: python BE/tests/unit/test_retrieval.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.retrieval import _overlaps, retrieve  # noqa: E402

POIS = [
    {"poi_id": "beach", "type": "beach", "fee": 0, "verified": True,
     "opening_hours": ["00:00-23:59"]},
    {"poi_id": "noodle", "type": "restaurant", "fee": 50000, "verified": True,
     "opening_hours": ["07:00-21:00"]},
    {"poi_id": "museum", "type": "museum", "fee": 60000, "verified": True,
     "opening_hours": ["07:30-17:00"]},
    {"poi_id": "draft", "type": "beach", "fee": 0, "verified": False,
     "opening_hours": ["00:00-23:59"]},
    {"poi_id": "fancy", "type": "restaurant", "fee": 5000000, "verified": True,
     "opening_hours": ["07:00-21:00"]},
]

TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00",
        "must_visit": [], "avoid": [], "activities": ["tắm biển", "ăn trưa"]}


def ids(result, key):
    return sorted(r["poi_id"] for r in result[key])


class TestRetrieval(unittest.TestCase):
    def test_multi_interval_hours_parse(self):
        hours = ["10:30-14:00, 16:30-22:30"]
        self.assertTrue(_overlaps(hours, 11 * 60, 12 * 60))
        self.assertTrue(_overlaps(hours, 17 * 60, 18 * 60))
        self.assertFalse(_overlaps(hours, 14 * 60, 16 * 60))
        self.assertTrue(_overlaps(
            ["09:00-12:00, 22:00-02:00"], 23 * 60, 23 * 60 + 30))
        self.assertFalse(_overlaps(["12:03"], 12 * 60, 13 * 60))
        self.assertTrue(_overlaps([], 12 * 60, 13 * 60))

    def test_type_filter(self):
        out = retrieve(TRIP, POIS)
        self.assertEqual(ids(out, "candidates"), ["beach", "noodle"])
        self.assertIn("khong khop loai", str(out["excluded"]))

    def test_closed_hours_excluded(self):
        trip = dict(TRIP, start_time="19:00", end_time="22:00",
                    activities=[])
        out = retrieve(trip, POIS)
        self.assertNotIn("museum", ids(out, "candidates"))  # 07:30-17:00
        self.assertIn("noodle", ids(out, "candidates"))  # 07:00-21:00 overlaps
        self.assertIn("beach", ids(out, "candidates"))

    def test_over_budget_excluded(self):
        out = retrieve(dict(TRIP, budget=10000), POIS)
        self.assertNotIn("fancy", ids(out, "candidates"))

    def test_unverified_excluded(self):
        out = retrieve(TRIP, POIS)
        self.assertNotIn("draft", ids(out, "candidates"))

    def test_must_visit_verified_kept(self):
        trip = dict(TRIP, must_visit=["beach"], activities=[])
        out = retrieve(trip, POIS)
        got = [c for c in out["candidates"] if c["poi_id"] == "beach"]
        self.assertEqual(len(got), 1)
        self.assertIn("must-visit", str(got[0]["reasons"]))

    def test_must_visit_unverified_outside_main_plan(self):
        trip = dict(TRIP, must_visit=["draft"], activities=[])
        out = retrieve(trip, POIS)
        self.assertNotIn("draft", [c["poi_id"] for c in out["candidates"]])
        got = [c for c in out["needs_verification"] if c["poi_id"] == "draft"]
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["must_visit"])

    def test_avoid_excluded(self):
        trip = dict(TRIP, avoid=["beach"])
        out = retrieve(trip, POIS)
        self.assertNotIn("beach", ids(out, "candidates"))
        self.assertIn("avoid", str(out["excluded"]))


if __name__ == "__main__":
    unittest.main()
