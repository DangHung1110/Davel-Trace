"""POST /v1/itinerary on the REAL working snapshot (audit N7 + B1/B2).

Every other test pins the 7-POI seed, so the suite stayed green while the
742-POI pool was broken ("tắm biển" -> 0 candidates -> fallback to all 742
POIs -> unverified plan in 77 s). This boots `BE/data/snapshots/danang-v1`
and asserts the planner contract on it:

- an activity wish is met inside a full day (lunch kept), not used as a pool
  filter;
- a wish with no verified POI is reported, the day is still planned;
- an empty pool is an honest empty plan, never unverified/allergen POIs;
- an allergy is respected on the final plan (PROFILE_SAFE);
- the response lists what retrieval kept out (`retrieval`).

One profile per request keeps the run near 5 s/request. Weather is mocked
offline so the plans do not depend on the live forecast.

Run: python -m pytest BE/tests/integration/test_real_snapshot_planning.py -q
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services import profile_filter, trip_ctx  # noqa: E402
from BE.app.services.retrieval import load_pois_json  # noqa: E402
from BE.app.services.soft_rules import poi_category  # noqa: E402
from BE.common import FEW_REVIEWS  # noqa: E402

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                        "snapshots", "danang-v1")
FAMILY = {"party_type": "family", "pace": 1, "fitness": 1}
COUPLE = {"party_type": "couple", "pace": 2, "fitness": 2}

client = TestClient(main_mod.app)


@unittest.skipUnless(os.path.exists(os.path.join(SNAPSHOT, "matrix.json")),
                     "working snapshot BE/data/snapshots/danang-v1 missing")
class TestRealSnapshotPlanning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pois = {p["poi_id"]: p
                    for p in load_pois_json(os.path.join(SNAPSHOT, "pois.json"))}
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=SNAPSHOT,
                                                      snapshot_name="danang-v1")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._settings

    def plan(self, **trip):
        body = {"trip": {"start_time": "08:00", "end_time": "20:00",
                         "budget": 2000000, **trip},
                "profiles": ["balanced"]}
        with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                               side_effect=RuntimeError("offline test")):
            r = client.post("/v1/itinerary", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        return out, out["plans"][0]

    def stops(self, plan):
        return [self.pois[a["poi_id"]] for a in plan["activities"]]

    def assert_honest(self, plan):
        for poi in self.stops(plan):
            self.assertTrue(poi.get("verified"), poi["poi_id"])

    def test_beach_wish_family_day(self):
        _, plan = self.plan(activities=["tắm biển"], profile=FAMILY)
        self.assertTrue(plan["passed"], plan.get("violations"))
        cats = [poi_category(p) for p in self.stops(plan)]
        self.assertIn("beach", cats)
        self.assertIn("restaurant", cats)
        self.assertGreaterEqual(len(cats), 4)
        self.assertEqual(plan["activity_match"][0]["status"], "met")
        self.assert_honest(plan)

    def test_balanced_day_is_made_of_places_people_know(self):
        # Scoring on the raw rating filled this day with 5.0s from 2-13 reviews.
        _, plan = self.plan(profile=COUPLE)
        self.assertTrue(plan["passed"], plan.get("violations"))
        for poi in self.stops(plan):
            self.assertGreaterEqual(poi.get("review_count") or 0, FEW_REVIEWS, poi["name"])

    def test_budget_is_real(self):
        # Every price was 0, so this gate could not fail and restaurants were "free".
        _, roomy = self.plan(profile=COUPLE, budget=3000000, travelers=2)
        self.assertTrue(roomy["passed"], roomy.get("violations"))
        self.assertGreater(roomy["total_cost"], 0)
        self.assertTrue(roomy["cost_estimated"])
        _, tight = self.plan(profile=COUPLE, budget=600000, travelers=2)
        self.assertTrue(tight["passed"], tight.get("violations"))
        self.assertLessEqual(tight["total_cost"], 600000)

    def test_no_money_for_lunch_is_reported_not_hidden(self):
        _, plan = self.plan(profile=COUPLE, budget=0, travelers=2)
        self.assertEqual(plan["activities"], [])
        self.assertTrue(plan.get("warnings"))

    def test_beach_wish_without_profile(self):
        _, plan = self.plan(activities=["tắm biển"])
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertIn("beach", [poi_category(p) for p in self.stops(plan)])
        self.assertGreaterEqual(len(plan["activities"]), 4)

    def test_wish_without_verified_poi_is_reported(self):
        has_museum = any(p.get("verified") and poi_category(p) == "museum"
                         for p in self.pois.values())
        _, plan = self.plan(activities=["bảo tàng"], profile=COUPLE)
        self.assertTrue(plan["passed"], plan.get("violations"))
        status = plan["activity_match"][0]["status"]
        self.assertEqual(status, "met" if has_museum else "no_verified_poi")
        self.assert_honest(plan)

    def test_empty_pool_is_empty_plan(self):
        # 30 minutes: shorter than every verified visit (min p50 45), so no
        # stop fits. (23:00-23:50 now fits a 45-minute 24/7 bridge.)
        _, plan = self.plan(activities=["tắm biển"], start_time="23:20",
                            end_time="23:50",
                            profile=dict(COUPLE, allergy=["hải sản"]))
        self.assertFalse(plan["passed"])
        self.assert_honest(plan)
        profile = {"allergy": ["hải sản"]}
        for poi in self.stops(plan):
            self.assertIsNone(profile_filter.drop_reason(poi, profile))

    def test_allergy_respected_on_final_plan(self):
        profile = dict(COUPLE, allergy=["hải sản"])
        _, plan = self.plan(activities=["ăn hải sản"], profile=profile)
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertEqual(plan["constraint_status"]["PROFILE_SAFE"], 1)
        for poi in self.stops(plan):
            self.assertIsNone(profile_filter.drop_reason(poi, profile),
                              poi["name"])

    def test_retrieval_report(self):
        out, _ = self.plan(activities=["đi chơi"], profile=COUPLE)
        report = out["retrieval"]
        unverified = sum(1 for p in self.pois.values() if not p.get("verified"))
        self.assertEqual(report["needs_verification_total"], unverified)
        self.assertLessEqual(len(report["needs_verification"]),
                             itinerary_mod.MAX_NEEDS_VERIFICATION)
        self.assertEqual(report["unmatched_activities"], ["đi chơi"])
        self.assertGreater(report["candidates"], 0)


if __name__ == "__main__":
    unittest.main()
