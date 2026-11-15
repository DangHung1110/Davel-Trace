"""Unit tests for the LLM-guided repair loop (test-local, no real LLM).

Pins the three invariants: only same-slot swaps, keep only when HARD gates
still pass, and never raise when the reviewer is unavailable. Also pins the
honest no-alternative path (F1 stays reported, not faked).

Run: PYTHONPATH=BE python -m unittest BE.tests.unit.test_repair
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.repair import repair_plan  # noqa: E402

TRIP = {"budget": 2000000, "start_time": "07:00", "end_time": "18:00",
        "return_time": None, "must_visit": [], "avoid": [],
        "food_prefs": ["hải sản"], "activities": []}

POIS = [
    {"poi_id": "food1", "cat": "restaurant", "name": "Quan Hai San",
     "verified": True, "fee": 0, "rating": 4.5, "opening_hours": ["07:00-22:00"]},
    {"poi_id": "food2", "cat": "cafe", "name": "Cafe Bien",
     "verified": True, "fee": 0, "rating": 4.6, "opening_hours": ["06:00-22:00"]},
    {"poi_id": "museum", "cat": "museum", "name": "Bao Tang",
     "verified": True, "fee": 0, "rating": 4.2, "opening_hours": ["08:00-17:00"]},
    {"poi_id": "beach", "cat": "beach", "name": "Bai Bien",
     "verified": True, "fee": 0, "rating": 4.1, "opening_hours": ["00:00-23:59"]},
]
MATRIX = {f"{a['poi_id']}->{b['poi_id']}": {"minutes": 10, "km": 1.0}
          for a in POIS for b in POIS if a["poi_id"] != b["poi_id"]}
PLAN = {
    "itinerary_id": "rep-1", "version": 1,
    "activities": [
        {"poi_id": "food1", "start": "11:30", "end": "12:30"},
        {"poi_id": "food2", "start": "14:00", "end": "15:00"},
    ],
    "total_cost": 0, "segments": [],
    "_context": {"trip": TRIP, "pois": POIS,
                 "travel": {("food1", "food2"): 10}},
}


def food_only_review(plan):
    ids = {a["poi_id"] for a in plan["activities"]}
    if ids & {"museum", "beach"}:
        return []
    return [{"issue": "ca ngay chi an uong", "severity": "high",
             "suggestion": "them diem tham quan"}]


def always_issue(plan):
    return [{"issue": "lap lai cung loai", "severity": "medium",
             "suggestion": "doi diem"}]


class TestRepairLoop(unittest.TestCase):
    def test_all_food_day_gets_a_safe_sightseeing_swap(self):
        result = repair_plan(PLAN, TRIP, {p["poi_id"]: p for p in POIS},
                             MATRIX, POIS, food_only_review)
        ids = [a["poi_id"] for a in result["plan"]["activities"]]
        self.assertTrue({"museum", "beach"} & set(ids))
        self.assertEqual(result["rounds"], 2)
        self.assertTrue(result["gate"]["passed"])
        self.assertEqual(result["gate"]["soft_violations"], [])
        self.assertEqual(len(result["repairs"]), 1)
        self.assertTrue(result["repairs"][0]["kept"])
        self.assertIn("swap", result["repairs"][0]["action"])

    def test_swap_keeps_the_exact_time_slot(self):
        before = {a["poi_id"]: (a["start"], a["end"])
                  for a in PLAN["activities"]}
        result = repair_plan(PLAN, TRIP, {p["poi_id"]: p for p in POIS},
                             MATRIX, POIS, food_only_review)
        for act in result["plan"]["activities"]:
            old = act["poi_id"]
            if old in before:
                self.assertEqual((act["start"], act["end"]), before[old])
        # the swapped activity inherited the replaced slot's times
        times = {(a["start"], a["end"]) for a in result["plan"]["activities"]}
        self.assertTrue({("11:30", "12:30"), ("14:00", "15:00")} & times)

    def test_totals_are_recomputed_not_hand_edited(self):
        result = repair_plan(PLAN, TRIP, {p["poi_id"]: p for p in POIS},
                             MATRIX, POIS, food_only_review)
        self.assertEqual(len(result["plan"]["segments"]), 1)
        self.assertEqual(result["plan"]["travel_min"], 10)
        self.assertEqual(result["plan"]["total_cost"], 0)

    def test_no_alternative_is_reported_honestly(self):
        food = [p for p in POIS if p["poi_id"].startswith("food")]
        matrix = {f"{a['poi_id']}->{b['poi_id']}": {"minutes": 10}
                  for a in food for b in food if a is not b}
        result = repair_plan(PLAN, TRIP, {p["poi_id"]: p for p in food},
                             matrix, food, food_only_review)
        self.assertFalse(result["repairs"][0]["kept"])
        self.assertIn("khong co lua chon an toan", result["repairs"][0]["action"])
        self.assertIn("F1", result["gate"]["soft_violations"])
        self.assertTrue(result["gate"]["passed"])  # hard gates still fine

    def test_unsafe_swap_is_reverted_by_the_gate(self):
        """A different-category POI that breaks BCS must not be kept."""
        pricey = {**POIS[2], "poi_id": "pricey", "fee": 9000000}
        pool = [POIS[0], POIS[1], pricey]
        matrix = {f"{a['poi_id']}->{b['poi_id']}": {"minutes": 10, "km": 1.0}
                  for a in pool for b in pool if a is not b}
        result = repair_plan(PLAN, TRIP, {p["poi_id"]: p for p in pool},
                             matrix, pool, food_only_review)
        ids = [a["poi_id"] for a in result["plan"]["activities"]]
        self.assertNotIn("pricey", ids)
        self.assertFalse(result["repairs"][0]["kept"])
        self.assertIn("F1", result["gate"]["soft_violations"])
        self.assertTrue(result["gate"]["passed"])

    def test_low_severity_issue_is_not_acted_on(self):
        mixed = {"activities": [
            {"poi_id": "food1", "start": "11:30", "end": "12:30"},
            {"poi_id": "museum", "start": "14:00", "end": "15:00"}]}
        low = lambda plan: [{"issue": "khong sao", "severity": "low",
                             "suggestion": ""}]
        result = repair_plan(mixed, TRIP, {p["poi_id"]: p for p in POIS},
                             MATRIX, POIS, low)
        self.assertEqual(result["repairs"], [])
        self.assertEqual(result["rounds"], 1)

    def test_llm_failure_returns_current_plan_with_note(self):
        def boom(_plan):
            raise RuntimeError("lm studio down")

        result = repair_plan(PLAN, TRIP, {p["poi_id"]: p for p in POIS},
                             MATRIX, POIS, boom)
        self.assertEqual(result["rounds"], 0)
        self.assertEqual(result["repairs"], [])
        self.assertIn("LLM_UNAVAILABLE", result["note"])
        self.assertEqual([a["poi_id"] for a in result["plan"]["activities"]],
                         ["food1", "food2"])

    def test_rounds_are_capped_at_two(self):
        result = repair_plan(PLAN, TRIP, {p["poi_id"]: p for p in POIS},
                             MATRIX, POIS, always_issue, max_rounds=5)
        self.assertLessEqual(result["rounds"], 2)

    def test_must_visit_is_not_swapped_for_f1(self):
        trip = dict(TRIP, must_visit=["food1"])
        result = repair_plan(PLAN, trip, {p["poi_id"]: p for p in POIS},
                             MATRIX, POIS, food_only_review)
        ids = [a["poi_id"] for a in result["plan"]["activities"]]
        self.assertIn("food1", ids)

    def test_a2_distance_repair_swaps_close_pair(self):
        """TASK-3: repair fixes a <2.5h restaurant pair even when the LLM
        reviewer reports nothing (deterministic A2 synthesis)."""
        plan = {"version": 1, "activities": [
            {"poi_id": "beach", "start": "07:00", "end": "08:00"},
            {"poi_id": "food1", "start": "10:49", "end": "11:49"},
            {"poi_id": "food3", "start": "12:00", "end": "13:00"},
        ]}
        pool = POIS + [
            {"poi_id": "food3", "cat": "restaurant", "name": "Quan Hai San 2",
             "verified": True, "fee": 0, "rating": 4.3,
             "opening_hours": ["07:00-22:00"]},
            {"poi_id": "museum2", "cat": "museum", "name": "Bao Tang 2",
             "verified": True, "fee": 0, "rating": 3.9,
             "opening_hours": ["08:00-17:00"]},
        ]
        matrix = {f"{a['poi_id']}->{b['poi_id']}": {"minutes": 10, "km": 1.0}
                  for a in pool for b in pool if a["poi_id"] != b["poi_id"]}
        result = repair_plan(plan, TRIP, {p["poi_id"]: p for p in pool},
                             matrix, pool, lambda _p: [])
        rules = [i["rule"] for i in
                 result["plan"]["soft_penalties"]["issues"]]
        self.assertNotIn("A2", rules)
        self.assertTrue(any("A2" in r["issue"] for r in result["repairs"]))
        self.assertTrue(result["gate"]["passed"])


if __name__ == "__main__":
    unittest.main()
