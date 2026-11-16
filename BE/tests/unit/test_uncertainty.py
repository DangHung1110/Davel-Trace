"""Unit test for uncertainty labels (T024). FR-013/FR-024/FR-026.

Verified -> main plan; unverified -> separate section; missing fields
labeled, never used as fact.

Run from repo root: python BE/tests/unit/test_uncertainty.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.retrieval import retrieve, uncertainty  # noqa: E402

POIS = [
    {"poi_id": "ok", "type": "beach", "fee": 0, "rating": 4.6,
     "verified": True, "opening_hours": ["00:00-23:59"], "tags": ["biển"]},
    {"poi_id": "raw", "type": "beach", "fee": 0, "rating": None,
     "verified": False, "opening_hours": [], "tags": []},
    {"poi_id": "nohours", "type": "museum", "fee": 10000, "rating": 4.0,
     "verified": True, "opening_hours": [], "tags": ["văn hóa"]},
]
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00",
        "must_visit": [], "avoid": [], "activities": []}


class TestUncertainty(unittest.TestCase):
    def test_verified_in_main_plan(self):
        out = retrieve(TRIP, POIS)
        got = [c for c in out["candidates"] if c["poi_id"] == "ok"]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["uncertainty"], [])

    def test_unverified_in_separate_section(self):
        out = retrieve(TRIP, POIS)
        self.assertNotIn("raw", [c["poi_id"] for c in out["candidates"]])
        got = [c for c in out["needs_verification"] if c["poi_id"] == "raw"]
        self.assertEqual(len(got), 1)
        self.assertIn("poi chua xac minh", got[0]["uncertainty"])

    def test_missing_fields_labeled(self):
        labels = uncertainty(POIS[1])
        self.assertIn("gio mo cua chua xac minh", labels)
        self.assertIn("rating chua xac minh", labels)
        self.assertIn("tags chua xac minh", labels)
        partial = uncertainty(POIS[2])
        self.assertIn("gio mo cua chua xac minh", partial)
        self.assertNotIn("rating chua xac minh", partial)


if __name__ == "__main__":
    unittest.main()
