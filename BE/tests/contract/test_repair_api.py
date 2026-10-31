"""Contract test for POST /v1/repair (NOTE(test-local) repair loop).

Pins both input shapes, the bounded rounds, the repair log, and the
"LLM failure is soft, never 500" rule. No real model is called.

Run: PYTHONPATH=BE python -m unittest BE.tests.contract.test_repair_api
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import review as review_mod  # noqa: E402
from BE.app.routers import select as select_mod  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)

TRIP = {"budget": 2000000, "start_time": "07:00", "end_time": "18:00",
        "must_visit": [], "avoid": [], "food_prefs": ["hải sản"],
        "activities": []}

POIS = [
    {"poi_id": "food1", "cat": "restaurant", "name": "Quan Hai San",
     "verified": True, "fee": 0, "rating": 4.5,
     "opening_hours": ["07:00-22:00"]},
    {"poi_id": "food2", "cat": "cafe", "name": "Cafe Bien",
     "verified": True, "fee": 0, "rating": 4.6,
     "opening_hours": ["06:00-22:00"]},
    {"poi_id": "museum", "cat": "museum", "name": "Bao Tang",
     "verified": True, "fee": 0, "rating": 4.2,
     "opening_hours": ["08:00-17:00"]},
]
TRAVEL = {(a["poi_id"], b["poi_id"]): 10
          for a in POIS for b in POIS if a is not b}
PLAN = {
    "itinerary_id": "rep-api-1", "version": 1,
    "activities": [
        {"poi_id": "food1", "start": "11:30", "end": "12:30"},
        {"poi_id": "food2", "start": "14:00", "end": "15:00"},
    ],
    "total_cost": 0, "_context": {"trip": TRIP, "pois": POIS,
                                  "travel": TRAVEL},
}


def _issue_for_variety(plan, *args):
    ids = {a["poi_id"] for a in plan["activities"]}
    if "museum" in ids:
        return []
    return [{"issue": "ca ngay chi an uong", "severity": "high",
             "suggestion": "them diem tham quan"}]


class TestRepairApi(unittest.TestCase):
    def setUp(self):
        select_mod.reset_store()

    def tearDown(self):
        select_mod.reset_store()

    def test_repair_by_itinerary_id_swaps_and_returns_gate(self):
        select_mod.register([PLAN])
        with mock.patch.object(review_mod, "review_plan",
                               side_effect=_issue_for_variety):
            r = client.post("/v1/repair", json={"itinerary_id": "rep-api-1"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(set(body), {"plan", "rounds", "repairs", "gate",
                                     "review_ms", "retrieval"})
        # FR-013/FR-024: what retrieval kept out reaches the client here too.
        self.assertIn("needs_verification", body["retrieval"])
        self.assertIn("excluded", body["retrieval"])
        ids = [a["poi_id"] for a in body["plan"]["activities"]]
        self.assertIn("museum", ids)
        self.assertEqual(body["rounds"], 2)
        self.assertEqual(len(body["repairs"]), 1)
        self.assertTrue(body["repairs"][0]["kept"])
        self.assertTrue(body["gate"]["passed"])
        self.assertEqual(body["gate"]["soft_violations"], [])
        self.assertNotIn("_context", body["plan"])

    def test_plan_plus_trip_input_uses_retrieval_pool(self):
        public = {
            "itinerary_id": "rep-api-2", "version": 1,
            "activities": [
                {"poi_id": "mi-quang-ba-mua", "start": "11:30",
                 "end": "12:30"},
                {"poi_id": "cham-museum", "start": "14:00", "end": "15:00"},
            ],
        }
        with mock.patch.object(review_mod, "review_plan", return_value=[]):
            r = client.post("/v1/repair", json={"plan": public, "trip": TRIP})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["gate"]["passed"])
        self.assertEqual(r.json()["rounds"], 1)

    def test_no_issue_means_one_review_round_zero_repairs(self):
        mixed = {**PLAN, "activities": [
            {"poi_id": "food1", "start": "11:30", "end": "12:30"},
            {"poi_id": "museum", "start": "14:00", "end": "15:00"}]}
        select_mod.register([mixed])
        with mock.patch.object(review_mod, "review_plan", return_value=[]):
            r = client.post("/v1/repair", json={"itinerary_id": "rep-api-1"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["rounds"], 1)
        self.assertEqual(r.json()["repairs"], [])

    def test_llm_failure_is_soft_never_500(self):
        select_mod.register([PLAN])
        with mock.patch.object(review_mod, "review_plan",
                               side_effect=RuntimeError("lm studio down")):
            r = client.post("/v1/repair", json={"itinerary_id": "rep-api-1"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["rounds"], 0)
        self.assertIn("LLM_UNAVAILABLE", body["note"])
        self.assertEqual([a["poi_id"] for a in body["plan"]["activities"]],
                         ["food1", "food2"])

    def test_unknown_itinerary_id_is_404(self):
        r = client.post("/v1/repair", json={"itinerary_id": "nope"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "UNKNOWN_ITINERARY")

    def test_missing_input_is_422(self):
        r = client.post("/v1/repair", json={})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"], "VALIDATION_ERROR")

    def test_plan_without_context_or_trip_is_422(self):
        public = {k: v for k, v in PLAN.items() if k != "_context"}
        r = client.post("/v1/repair", json={"plan": public})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
