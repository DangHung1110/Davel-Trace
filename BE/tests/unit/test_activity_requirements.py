"""Planner pool correctness (audit B1/B2): fixture POIs, no snapshot.

- Activities become optimizer `required_any` groups: the day keeps its lunch
  AND contains the wished category (old behaviour: pool filtered to beaches
  only -> no restaurant -> infeasible / one-stop day).
- A wish the pool cannot serve is reported, never silently dropped.
- An empty candidate list is an honest empty plan (EMPTY_POOL), never a
  fallback to every POI the caller passed in.

Run: python -m pytest BE/tests/unit/test_activity_requirements.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.profiles import build_plan  # noqa: E402
from BE.app.services.soft_rules import poi_category  # noqa: E402
from BE.tests.unit.test_template_wiring import (  # noqa: E402
    BY_ID, CELLS, RANKED, _poi, _trip)


def _cats(plan):
    return [poi_category(BY_ID[a["poi_id"]]) for a in plan["activities"]]


class TestActivityRequirement(unittest.TestCase):
    def test_wish_kept_with_lunch(self):
        trip = _trip("08:00", "18:00", activities=["tắm biển"])
        plan = build_plan("balanced", trip, RANKED, BY_ID, CELLS, template="",
                          workers=1)
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertIn("beach", _cats(plan))
        self.assertIn("restaurant", _cats(plan))
        self.assertEqual(plan["activity_match"],
                         [{"activity": "tắm biển", "categories": ["beach"],
                           "status": "met", "poi_id": "beach1"}])

    def test_wish_not_in_pool_reported(self):
        ranked = [r for r in RANKED if r["poi_id"] != "mus1"]
        trip = _trip("08:00", "18:00", activities=["bảo tàng", "đi chơi"])
        plan = build_plan("balanced", trip, ranked, BY_ID, CELLS, template="",
                          workers=1)
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertEqual([m["status"] for m in plan["activity_match"]],
                         ["no_verified_poi", "not_understood"])
        warnings = " | ".join(plan.get("warnings") or [])
        self.assertIn("chua co diem da xac minh phu hop voi hoat dong 'bảo tàng'", warnings)
        self.assertIn("chua hieu hoat dong 'đi chơi'", warnings)

    def test_unreachable_wish_relaxed_not_fatal(self):
        # The only beach closes before the trip starts: the wish must be
        # dropped with a warning, the day itself must still be planned.
        by_id = dict(BY_ID, beach1=_poi("beach1", "beach", hours=("05:00-06:00",)))
        trip = _trip("08:00", "18:00", activities=["tắm biển"])
        plan = build_plan("balanced", trip, RANKED, by_id, CELLS, template="",
                          workers=1)
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertNotIn("beach1", [a["poi_id"] for a in plan["activities"]])
        self.assertEqual(plan["activity_match"][0]["status"], "unmet")
        self.assertTrue(any("khong xep duoc hoat dong 'tắm biển'" in w
                            for w in plan.get("warnings") or []))


class TestFailClosedPool(unittest.TestCase):
    def test_empty_ranked_never_falls_back(self):
        plan = build_plan("balanced", _trip(), [], BY_ID, CELLS, template="",
                          workers=1)
        self.assertEqual(plan["activities"], [])
        self.assertFalse(plan["passed"])
        self.assertEqual(plan["infeasible_by"]["rule"], "EMPTY_POOL")

    def test_pool_is_exactly_the_ranked_ids(self):
        ranked = [{"poi_id": pid} for pid in ("rest1", "lm1", "cafe1")]
        plan = build_plan("balanced", _trip(), ranked, BY_ID, CELLS, template="",
                          workers=1)
        self.assertLessEqual({a["poi_id"] for a in plan["activities"]},
                             {"rest1", "lm1", "cafe1"})


if __name__ == "__main__":
    unittest.main()
