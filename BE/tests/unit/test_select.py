"""Unit tests for the T033 select <-> canonical gate wiring (T061).

No mock registry: select evaluates plans with the real
`BE.app.services.gate.CHECKS` over the plan's `_context`.
"""

import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.routers import select as select_mod  # noqa: E402
from BE.app.services.gate import CHECKS  # noqa: E402

TRIP = {"trip_id": "t1", "start_time": "07:00", "end_time": "18:00",
        "budget": 3000000, "must_visit": [], "avoid": []}
POIS = [
    {"poi_id": "ba-na", "verified": True, "fee": 60000,
     "opening_hours": ["07:00-17:00"]},
    {"poi_id": "beach", "verified": True, "fee": 0,
     "opening_hours": ["00:00-23:59"]},
]


def _plan(activities, total_cost=60000, pois=None, trip=None, travel=None):
    return {
        "itinerary_id": "it-1", "profile": "balanced",
        "total_cost": total_cost, "activities": activities,
        "_context": {"trip": trip or TRIP,
                     "pois": pois if pois is not None else POIS,
                     "travel": travel if travel is not None
                     else {("ba-na", "beach"): 10}},
    }


PASSING = [{"poi_id": "ba-na", "start": "08:00", "end": "09:30"},
           {"poi_id": "beach", "start": "10:00", "end": "11:30"}]
UNKNOWN = [{"poi_id": "ghost", "start": "08:00", "end": "09:00"}]


class TestEvaluatePlan(unittest.TestCase):
    def test_passing_plan_uses_canonical_registry(self):
        report = select_mod.evaluate_plan(_plan(PASSING))
        self.assertIs(report["passed"], True)
        self.assertEqual(report["failed"], [])
        self.assertEqual(list(report["checks"]), [n for n, _ in CHECKS])
        self.assertTrue(all(isinstance(v, bool)
                            for v in report["checks"].values()))
        self.assertTrue(math.isfinite(report["score"]))
        self.assertTrue(0.0 <= report["score"] <= 1.0)
        for score in report["scores"].values():
            self.assertIs(type(score), float)
            self.assertTrue(0.0 <= score <= 1.0)

    def test_unknown_poi_fails_far_and_hcs(self):
        report = select_mod.evaluate_plan(_plan(UNKNOWN))
        self.assertIs(report["passed"], False)
        self.assertEqual(report["failed"], ["FAR", "HCS"])
        self.assertLess(report["score"], 1.0)

    def test_over_budget_fails_bcs(self):
        report = select_mod.evaluate_plan(_plan(PASSING, total_cost=4000000))
        self.assertIs(report["passed"], False)
        self.assertIn("BCS", report["failed"])

    def test_missing_context_is_not_evaluated(self):
        # A plan with no trip/pois (legacy stub) has no gate context -> None.
        self.assertIsNone(select_mod.evaluate_plan(
            {"itinerary_id": "it-x", "activities": []}))


class TestSelectUsesRealGate(unittest.TestCase):
    def setUp(self):
        select_mod.reset_store()

    def tearDown(self):
        select_mod.reset_store()

    def test_select_passing_plan_sets_gate_report(self):
        select_mod.register([_plan(PASSING)])
        result = select_mod.select(select_mod.SelectIn(itinerary_id="it-1"))
        self.assertEqual(result, {"active_id": "it-1"})
        store = select_mod.get_store()
        self.assertEqual(store["selected"], "it-1")
        self.assertIs(store["gate"]["passed"], True)

    def test_select_rejected_plan_returns_gate_failed(self):
        select_mod.register([_plan(PASSING, total_cost=4000000)])
        response = select_mod.select(select_mod.SelectIn(itinerary_id="it-1"))
        self.assertEqual(response.status_code, 422)
        body = json.loads(response.body)
        self.assertEqual(body["error"], "GATE_FAILED")
        self.assertIn("BCS", body["message"])
        self.assertIsNone(select_mod.get_store()["active_id"])

    def test_select_skips_gate_when_context_absent(self):
        select_mod.register([{"itinerary_id": "it-x", "activities": []}])
        result = select_mod.select(select_mod.SelectIn(itinerary_id="it-x"))
        self.assertEqual(result, {"active_id": "it-x"})
        self.assertIsNone(select_mod.get_store()["gate"])


if __name__ == "__main__":
    unittest.main()
