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

    def test_two_days_are_two_days(self):
        # FR-020: the planner never read `days`, so this returned one day.
        out, plan = self.plan(profile=COUPLE, days=2, budget=4000000, travelers=2,
                              date="2026-11-14", activities=["tắm biển", "bảo tàng"])
        self.assertTrue(plan["passed"], plan.get("violations"))
        by_day = {1: [], 2: []}
        for act in plan["activities"]:
            by_day[act["day"]].append(act["poi_id"])
        self.assertGreaterEqual(len(by_day[1]), 4)
        self.assertGreaterEqual(len(by_day[2]), 4)
        self.assertFalse(set(by_day[1]) & set(by_day[2]))
        self.assertEqual([d["date"] for d in plan["days"]], ["2026-11-14", "2026-11-15"])
        self.assertEqual(plan["total_cost"], sum(d["total_cost"] for d in plan["days"]))
        self.assertLessEqual(plan["total_cost"], 4000000)
        self.assertEqual({m["status"] for m in plan["activity_match"]}, {"met"})
        self.assert_honest(plan)
        # Each day holds its own lunch.
        for day in by_day:
            cats = [poi_category(self.pois[pid]) for pid in by_day[day]]
            self.assertIn("restaurant", cats)

    def test_two_days_on_a_low_budget(self):
        # The candidate cap used to keep dear places the day's share cannot pay for.
        for profile in ("savings", "balanced", "experience"):
            with self.subTest(profile=profile):
                body = {"trip": {"start_time": "08:00", "end_time": "20:00", "days": 2,
                                 "budget": 600000, "profile": COUPLE, "activities": ["chùa"]},
                        "profiles": [profile]}
                with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                                       side_effect=RuntimeError("offline test")):
                    plan = client.post("/v1/itinerary", json=body).json()["plans"][0]
                self.assertTrue(plan["passed"], plan.get("warnings"))
                self.assertLessEqual(plan["total_cost"], 600000)

    def test_two_days_too_little_money_says_so(self):
        _, plan = self.plan(profile=COUPLE, days=2, budget=100000, travelers=2)
        self.assertFalse(plan["passed"])
        self.assertIn("HCS", plan["violations"])
        self.assertTrue(any("1/2 ngay" in w for w in plan["warnings"]))

    def test_two_day_plan_can_be_selected_and_replanned(self):
        _, plan = self.plan(profile=COUPLE, days=2, budget=4000000, travelers=2)
        pid = plan["itinerary_id"]
        self.assertEqual(client.post("/v1/itinerary/select",
                                     json={"itinerary_id": pid}).status_code, 200)
        day_one = [a["poi_id"] for a in plan["activities"] if a["day"] == 1]
        day_two = [a["poi_id"] for a in plan["activities"] if a["day"] == 2]
        out = client.post("/v1/replan", json={"itinerary_id": pid, "event": {"type": "rain"},
                                              "completed": day_one[:1]}).json()
        self.assertEqual(out["mode"], "plan", out.get("reason"))
        self.assertEqual(out["day"], 1)
        self.assertEqual(out["preserved_completed"], day_one[:1])
        kept = [a["poi_id"] for a in out["itinerary"]["activities"] if a["day"] == 2]
        self.assertEqual(kept, day_two)  # the other day comes back unchanged
        # Day 1 done: the replan moves on to day 2 by itself.
        out = client.post("/v1/replan", json={"itinerary_id": pid, "event": {"type": "delay"},
                                              "completed": day_one}).json()
        self.assertEqual(out["day"], 2)
        missing = client.post("/v1/replan", json={"itinerary_id": pid, "event": {}, "day": 9})
        self.assertEqual(missing.status_code, 404)

    def test_replan_works_for_a_plan_with_a_profile(self):
        # Every onboarded plan failed here: the replan gate could not see the lunch.
        _, plan = self.plan(profile=COUPLE)
        first = plan["activities"][0]["poi_id"]
        out = client.post("/v1/replan", json={"itinerary_id": plan["itinerary_id"],
                                              "event": {"type": "rain"}, "completed": [first]}).json()
        self.assertEqual(out["mode"], "plan", out.get("reason"))

    def test_an_all_day_place_is_planned_with_its_lunch_on_site(self):
        # Bà Nà Hills (7 hours, the best-known attraction of the snapshot) gave an
        # EMPTY plan, asked for by name or by wish: lunch in town, then no time left.
        park = next(pid for pid, p in self.pois.items() if p["name"] == "Sun World Bà Nà Hills")
        for trip in ({"must_visit": [park]}, {"activities": ["cáp treo"]}):
            with self.subTest(trip=trip):
                _, plan = self.plan(profile=COUPLE, budget=3000000, travelers=2, **trip)
                self.assertTrue(plan["passed"], plan.get("warnings"))
                stops = {a["poi_id"]: a for a in plan["activities"]}
                self.assertIn(park, stops)
                self.assertLessEqual(stops[park]["start"], "11:00")
                self.assertGreaterEqual(stops[park]["end"], "13:00")
                self.assertEqual(plan["template"]["lunch_on_site"], park)
                self.assertIsNone(plan["template"]["lunch_restaurant"])
                self.assertGreaterEqual(len(stops), 4)   # the evening in town is planned too
                self.assertEqual(plan["template"]["relaxed_step"], 0)
                self.assertTrue(any("bua trua an tai" in w for w in plan["warnings"]))

    def test_each_day_of_a_trip_is_planned_on_its_own_forecast(self):
        # The forecast was matched by hour only: every day of every trip got the first
        # day's weather. Dry today, rain tomorrow: only day 2 is planned around the rain,
        # and an undated trip says which days of the forecast it assumed.
        def hours(date, rain):
            return [{"at": f"{date}T{h:02d}:00", "temp_c": 27.0, "rain_prob": rain} for h in range(24)]
        week = {"source": "open-meteo", "stale": False,
                "hourly": hours("2026-11-11", 0.0) + hours("2026-11-12", 0.9)}
        body = {"trip": {"start_time": "08:00", "end_time": "20:00", "budget": 4000000,
                         "travelers": 2, "days": 2, "profile": COUPLE},
                "profiles": ["balanced"]}
        with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast", return_value=week):
            plan = client.post("/v1/itinerary", json=body).json()["plans"][0]
        self.assertTrue(plan["passed"], plan.get("warnings"))
        rain = [w for w in plan["warnings"] if "du bao mua" in w]
        self.assertEqual(len(rain), 1, plan["warnings"])
        self.assertTrue(rain[0].startswith("ngay 2: du bao mua 08:00-20:00 (toi da 90%)"), rain)
        self.assertIn("chua co ngay di nen dung du bao ngay 2026-11-12", rain[0])
        # Nobody is sent to the beach or a park on the wet day; the dry day keeps the choice.
        open_air = [poi_category(self.pois[a["poi_id"]]) for a in plan["activities"]
                    if a["day"] == 2 and poi_category(self.pois[a["poi_id"]]) in ("beach", "park")]
        self.assertEqual(open_air, [])

    def test_spending_level_changes_what_the_days_tables_cost(self):
        # The same restaurants came back at spending 1, 2 and 3: the answer only fed
        # the rank list. A thrifty couple now eats at the cheap tables, a premium one
        # does not, and each is still a full passing day.
        def meal_levels(level):
            _, plan = self.plan(profile=dict(COUPLE, spending_level=level), budget=3000000, travelers=2)
            self.assertTrue(plan["passed"], plan.get("violations"))
            levels = [p.get("price_level") or 2 for p in self.stops(plan) if poi_category(p) == "restaurant"]
            self.assertGreaterEqual(len(levels), 2)             # lunch and dinner
            return levels

        thrifty, premium = meal_levels(1), meal_levels(3)
        self.assertEqual(set(thrifty), {1}, thrifty)
        self.assertGreater(sum(premium) / len(premium), sum(thrifty) / len(thrifty))

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
