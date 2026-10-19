"""Contract test POST /v1/itinerary/select (T033e, lane C — closes US4).

Select a real (context-carrying) plan -> active_id correct, others kept for
compare; a plan the canonical gate rejects -> 422 GATE_FAILED; unknown id ->
404 envelope. Plans now carry `_context = {trip, pois, travel}` (the shape
POST /v1/itinerary registers), so select runs the real lane-B gate.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import select as select_mod  # noqa: E402

TRIP = {"trip_id": "t1", "start_time": "07:00", "end_time": "18:00",
        "budget": 3000000, "must_visit": [], "avoid": []}
POIS = [
    {"poi_id": "ba-na", "verified": True, "fee": 60000,
     "opening_hours": ["07:00-17:00"]},
    {"poi_id": "beach", "verified": True, "fee": 0,
     "opening_hours": ["00:00-23:59"]},
]
TRAVEL = {("ba-na", "beach"): 10}
ACTIVITIES = [
    {"poi_id": "ba-na", "start": "08:00", "end": "09:30"},
    {"poi_id": "beach", "start": "10:00", "end": "11:30"},
]


def _plan(itinerary_id: str, activities: list[dict], total_cost: int) -> dict:
    return {"itinerary_id": itinerary_id, "profile": "balanced",
            "total_cost": total_cost, "activities": activities,
            "_context": {"trip": TRIP, "pois": POIS, "travel": TRAVEL}}


PLANS = [
    _plan("it-savings", ACTIVITIES, 60000),
    _plan("it-balanced", ACTIVITIES, 200000),
    # Over budget -> BCS (and its HCS mirror) fail the real gate.
    _plan("it-experience", ACTIVITIES, 4000000),
]

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestSelectContract(unittest.TestCase):
    def setUp(self):
        select_mod.reset_store()
        select_mod.register(PLANS)

    def tearDown(self):
        select_mod.reset_store()

    def test_select_passing_plan(self):
        r = client.post("/v1/itinerary/select", json={"itinerary_id": "it-balanced"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"active_id": "it-balanced"})
        store = select_mod.get_store()
        self.assertEqual(store["active_id"], "it-balanced")
        self.assertEqual(store["selected"], "it-balanced")
        self.assertEqual(sorted(store["plans"]),
                         ["it-balanced", "it-experience", "it-savings"])
        report = store["gate"]
        self.assertIs(report["passed"], True)
        self.assertTrue(0.0 <= report["score"] <= 1.0)
        print(f"\n active: {store['active_id']} score: {report['score']} "
              f"kept: {sorted(store['plans'])}")

    def test_failed_gate_does_not_select_plan(self):
        r = client.post("/v1/itinerary/select", json={"itinerary_id": "it-experience"})

        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.json()), {"error", "message"})
        self.assertEqual(r.json()["error"], "GATE_FAILED")
        self.assertIn("BCS", r.json()["message"])
        self.assertIsNone(select_mod.get_store()["active_id"])
        self.assertIsNone(select_mod.get_store()["selected"])

    def test_unknown_id_404_envelope(self):
        r = client.post("/v1/itinerary/select", json={"itinerary_id": "it-ghost"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "UNKNOWN_ITINERARY")


if __name__ == "__main__":
    unittest.main()
