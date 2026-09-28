"""Unit test for NL parser (T014). Mock llm_fn only.

Covers: full info, missing city -> clarification, missing time ->
stated assumption, vague preference stays soft (FR-006).

Run from repo root: python BE/tests/unit/test_parser.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.parser import parse  # noqa: E402

FULL = {"city": "Đà Nẵng", "date": "2026-10-03", "start_time": "07:00",
        "end_time": "18:00", "days": 1, "travelers": 2, "budget": 3000000,
        "transport": ["motorbike"], "must_visit": ["son-tra"], "avoid": [],
        "activities": ["leo núi", "tắm biển"], "food_prefs": ["mì Quảng"],
        "order_prefs": [["son-tra", "my-khe"]],
        "hard_constraints": ["ngân sách 3 triệu"], "soft_prefs": ["yên tĩnh"],
        "uncertainties": []}
NO_CITY = dict(FULL, city="")
NO_TIME = dict(FULL, start_time="", end_time="", days=0)
VAGUE = dict(FULL, must_visit=[], avoid=[], activities=["đi biển"],
             soft_prefs=["thích biển"], hard_constraints=[])


def mock(slots):
    def run(prompt, schema):
        return dict(slots)
    return run


class TestParser(unittest.TestCase):
    def test_full_info(self):
        out = parse("cuối tuần đi Đà Nẵng 2 người 3 triệu", llm_fn=mock(FULL))
        trip = out["trip"]
        self.assertEqual(trip.city, "đà-nẵng")
        self.assertEqual((trip.budget, trip.travelers, trip.days), (3000000, 2, 1))
        self.assertEqual(trip.must_visit, ["son-tra"])
        self.assertEqual(out["assumptions"], [])
        self.assertNotIn("needs_clarification", out)

    def test_missing_city_clarifies(self):
        out = parse("đi chơi 2 người 3 triệu", llm_fn=mock(NO_CITY))
        self.assertEqual(out["needs_clarification"], ["city"])
        self.assertNotIn("trip", out)

    def test_missing_time_assumes_stated(self):
        out = parse("đi Đà Nẵng 2 người", llm_fn=mock(NO_TIME))
        trip = out["trip"]
        self.assertEqual((trip.start_time, trip.end_time, trip.days),
                         ("07:00", "18:00", 1))
        self.assertEqual(len(out["assumptions"]), 1)
        self.assertNotIn("needs_clarification", out)

    def test_vague_pref_stays_soft_fr006(self):
        out = parse("thích biển", llm_fn=mock(VAGUE))
        trip = out["trip"]
        self.assertEqual(trip.must_visit, [])
        self.assertEqual(trip.avoid, [])
        self.assertIn("thích biển", out["soft_prefs"])


if __name__ == "__main__":
    unittest.main()
