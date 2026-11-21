"""main's planner end to end on danang-v2.1 (A9 in docs/travelagent/ARCHITECTURE_BACKLOG.md).

Same API path and gates as test_real_snapshot_planning.py (danang-v1), with the
clean policy (`GOOGLE_POLICY=cach_ly`): no Google value reaches the planner.
"""

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
SNAPSHOT = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services import trip_ctx  # noqa: E402
from BE.app.services.retrieval import load_pois_json  # noqa: E402

FAMILY = {"party_type": "family", "pace": 1, "fitness": 1}
COUPLE = {"party_type": "couple", "pace": 2, "fitness": 2}

client = TestClient(main_mod.app)


@unittest.skipUnless(os.path.exists(os.path.join(SNAPSHOT, "matrix.json")), "danang-v2 missing")
class TestV2SnapshotPlanning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env = mock.patch.dict(os.environ, {"GOOGLE_POLICY": "cach_ly"})
        cls._env.start()
        cls.pois = {p["poi_id"]: p for p in load_pois_json(os.path.join(SNAPSHOT, "pois.json"))}
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=SNAPSHOT, snapshot_name="danang-v2")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._settings
        cls._env.stop()

    def plan(self, **trip):
        body = {"trip": {"start_time": "08:00", "end_time": "20:00", "budget": 2000000, **trip},
                "profiles": ["balanced"]}
        with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                               side_effect=RuntimeError("offline test")):
            r = client.post("/v1/itinerary", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["plans"][0]

    def stops(self, plan):
        return [self.pois[a["poi_id"]] for a in plan["activities"]]

    def test_every_stop_is_an_active_v21_stop(self):
        plan = self.plan(profile=COUPLE)
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertGreaterEqual(len(plan["activities"]), 4)
        for p in self.stops(plan):
            self.assertEqual(p["data_version"], "v2.1")
            self.assertEqual(p["status"], "active", p["name"])
            self.assertNotEqual(p["role"], "base", p["name"])
            self.assertTrue(p["verified"], p["name"])

    def test_beach_wish_family_day(self):
        plan = self.plan(activities=["tắm biển"], profile=FAMILY)
        self.assertTrue(plan["passed"], plan.get("violations"))
        cats = [p["category"] for p in self.stops(plan)]
        self.assertIn("beach", cats)
        self.assertIn("restaurant", cats)

    def test_budget_is_real(self):
        plan = self.plan(profile=COUPLE, budget=3000000, travelers=2)
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertGreater(plan["total_cost"], 0)
        tight = self.plan(profile=COUPLE, budget=600000, travelers=2)
        self.assertLessEqual(tight["total_cost"], 600000)

    def test_cooking_class_only_when_asked(self):
        plain = self.plan(profile=COUPLE)
        self.assertFalse([p for p in self.stops(plain) if p["hours"]["kind"] == "by_booking"])

    def test_closed_weekday_is_not_planned(self):
        # 2026-11-23 is a Monday: a POI with Mo in closed_days must not appear
        plan = self.plan(profile=COUPLE, date="2026-11-23", activities=["bảo tàng"])
        for p in self.stops(plan):
            self.assertNotIn("Mo", p["hours"]["closed_days"], p["name"])

    def test_local_tier_needs_a_wish(self):
        plan = self.plan(profile=COUPLE)
        self.assertFalse([p["name"] for p in self.stops(plan) if p["plan_tier"] == "local"])


if __name__ == "__main__":
    unittest.main()
