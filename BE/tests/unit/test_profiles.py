"""Unit test for multi-profile runs (T032, opens US4). Fixture-based.

One request -> >=2 feasible plans with clearly distinct scores/reasons.

Run from repo root: python BE/tests/unit/test_profiles.py -v
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import scorer  # noqa: E402
from BE.app.services.profiles import run_profiles, score_plan  # noqa: E402

H = 60
POIS = [
    {"poi_id": "fancy", "verified": True, "visit_min": 90, "rating": 5.0, "fee": 500000,
     "intensity": 1, "opening_hours": ["10:00-22:00"]},
    {"poi_id": "hill", "verified": True, "visit_min": 120, "rating": 4.7, "fee": 0,
     "intensity": 3, "opening_hours": ["05:00-18:00"]},
    {"poi_id": "beach", "verified": True, "visit_min": 120, "rating": 4.6, "fee": 0,
     "intensity": 2, "opening_hours": ["00:00-23:59"]},
    {"poi_id": "noodle", "verified": True, "visit_min": 60, "rating": 4.5, "fee": 50000,
     "intensity": 1, "opening_hours": ["07:00-21:00"]},
]
IDS = [p["poi_id"] for p in POIS]
TRAVEL = {(a, b): 15 for a in ["depot"] + IDS for b in IDS if a != b}
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
                             {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1,
                              "ETB": 1, "A1": 1, "CAFE_CAP": 1,
                              "CATEGORY_CAP": 1,
                              "NO_CONSECUTIVE": 1, "NO_ADJACENT_FOOD": 1,
                              "REST_FOLLOWS_LUNCH": 1, "TCS": 1, "HCS": 1})
        print(f"\n pool: {[(p['profile'], p['total_cost'], p['preference']) for p in pool['plans']]}")

    def test_plans_carry_t032s_scores(self):
        pool = run_profiles(POIS, TRAVEL, TRIP, MATRIX)
        self.assertIsNone(pool["selected"])
        self.assertGreaterEqual(len(pool["plans"]), 2)
        for p in pool["plans"]:
            self.assertIn("scores", p)
            self.assertEqual(p["scores"], score_plan(dict(p)))
            self.assertIs(type(p["scores"]["profit"]), float)
            self.assertIs(type(p["scores"]["utility"]), float)
            self.assertIs(p["scores"]["gate"], True)
        print(f"\n scores: {pool['plans'][0]['scores']}")

    def test_savings_cheapest(self):
        pool = run_profiles(POIS, TRAVEL, TRIP, MATRIX)
        by_prof = {p["profile"]: p for p in pool["plans"]}
        self.assertLessEqual(by_prof["savings"]["total_cost"],
                             by_prof["balanced"]["total_cost"])

    def test_unverified_poi_is_not_accepted(self):
        draft = dict(POIS[0], verified=False)
        pool = run_profiles([draft], TRAVEL, TRIP, MATRIX)
        self.assertEqual(pool["plans"], [])
        self.assertTrue(all("FAR" in item["reason"] for item in pool["dropped"]))

    def test_wires_q_ij_into_optimizer(self):
        with mock.patch.object(scorer, "edge_scores",
                               wraps=scorer.edge_scores) as m:
            pool = run_profiles(POIS, TRAVEL, TRIP, MATRIX)
        self.assertTrue(m.called)
        self.assertEqual(m.call_args[0][0], IDS)
        self.assertGreaterEqual(len(pool["plans"]), 2)

    def test_build_plan_forces_trip_must_visit(self):
        """T053 bug 2: build_plan wires trip.must_visit as a hard constraint."""
        from BE.app.services.profiles import build_plan

        by_id = {p["poi_id"]: p for p in POIS}
        # 07:00-10:00 cannot profitably hold noodle (rating 4.5) next to the
        # 5.0 fancy; the forced plan must still contain noodle.
        trip = dict(TRIP, start_time="07:00", end_time="10:00",
                    must_visit=["noodle"], avoid=[])
        ranked = [{"poi_id": pid} for pid in IDS]
        plan = build_plan("balanced", trip, ranked, by_id, MATRIX)
        ids = [a["poi_id"] for a in plan["activities"]]
        self.assertIn("noodle", ids)
        self.assertTrue(plan["constraint_status"]["HCS"] == 1)

    def test_router_build_plan_scores_are_not_degenerate(self):
        """T053 fix: scores built through the router seam must distinguish profiles.

        Regression: response.build_plan() did not emit `preference` /
        `travel_min`, so score_plan() read 0/0 and gave every profile
        profit=0.0 / utility=0.3. (balanced == experience remains a known
        limitation; at least savings must differ.)
        """
        from BE.app.services.profiles import build_plan

        by_id = {p["poi_id"]: p for p in POIS}
        ranked = [{"poi_id": pid} for pid in IDS]
        plans = {prof: build_plan(prof, TRIP, ranked, by_id, MATRIX)
                 for prof in ("savings", "balanced", "experience")}
        for prof, plan in plans.items():
            self.assertGreater(plan["preference"], 0.0, prof)
            self.assertGreaterEqual(plan["travel_min"], 0, prof)
            scores = plan["scores"]
            self.assertIs(scores["gate"], True, prof)
            self.assertGreater(scores["profit"], 0.0, prof)
            self.assertGreater(scores["utility"], 0.3, prof)
        pairs = {(round(p["scores"]["profit"], 4),
                  round(p["scores"]["utility"], 4))
                 for p in plans.values()}
        self.assertGreater(len(pairs), 1,
                           f"scores collapsed to one value: {pairs}")
        self.assertNotEqual(plans["savings"]["scores"],
                            plans["balanced"]["scores"])


if __name__ == "__main__":
    unittest.main()
