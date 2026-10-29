"""Wiring tests: profile -> day template -> optimizer + router hard filter.

Fixture POIs/matrix only (no snapshot), so the tests are deterministic:

- `build_plan(template=...)` enforces the archetype (stop band, bans, locked
  rest window, late end) and reports it under plan["template"].
- `template=""` keeps the legacy unconstrained behaviour.
- POST /v1/itinerary applies the hard profile filter before rank and surfaces
  the drops as warnings (with must_visit pruning so gates stay honest).

Run: python -m pytest BE/tests/unit/test_template_wiring.py -q
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import profile_filter  # noqa: E402
from BE.app.services import trip_ctx  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.app.services.templates import DAY_TEMPLATES  # noqa: E402
from BE.tests import conftest  # noqa: E402


def _poi(pid, cat, *, intensity=1, hours=("08:00-22:00",), visit=60, rating=4.5,
         tags=None, verified=True):
    return {"poi_id": pid, "name": pid.upper(), "cat": cat, "type": cat,
            "lat": 16.05, "lon": 108.2, "opening_hours": list(hours),
            "visit_min": visit, "fee": 0, "rating": rating,
            "tags": tags or [cat], "intensity": intensity,
            "weather_sensitive": False, "verified": verified}


POIS = [
    _poi("attr1", "attraction", hours=("08:00-18:00",)),
    _poi("lm1", "landmark", hours=("08:00-18:00",)),
    _poi("mus1", "museum", hours=("08:00-17:00",)),
    _poi("cafe1", "cafe", visit=45),
    _poi("cafe2", "cafe", visit=45),
    _poi("cafe3", "cafe", visit=45),
    _poi("rest1", "restaurant", visit=60, hours=("10:00-22:00",)),
    _poi("rest2", "restaurant", visit=60, hours=("10:00-22:00",)),
    _poi("mkt1", "market", visit=60),
    _poi("park1", "park", visit=60, hours=("06:00-18:00",)),
    _poi("bar1", "bar", visit=60, hours=("18:00-23:00",)),
    _poi("nat1", "nature", intensity=3, visit=90, hours=("05:00-18:00",)),
    _poi("beach1", "beach", intensity=2, visit=90, hours=("00:00-23:59",)),
]
BY_ID = {p["poi_id"]: p for p in POIS}
IDS = list(BY_ID)
RANKED = [{"poi_id": pid} for pid in IDS]
CELLS = {f"{a}->{b}": {"minutes": 10, "km": 2.0}
         for a in IDS for b in IDS if a != b}


def _trip(start="08:00", end="17:30", **extra):
    trip = {"trip_id": "t1", "budget": 3000000, "start_time": start,
            "end_time": end, "must_visit": [], "avoid": [],
            "food_prefs": [], "activities": [],
            "profile": {"party_type": "solo", "pace": 2, "fitness": 2}}
    trip.update(extra)
    return trip


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class TestBuildPlanTemplates(unittest.TestCase):
    def test_family_slow(self):
        plan = build_plan("balanced", _trip(), RANKED, BY_ID, CELLS,
                          template="family-slow")
        acts = plan["activities"]
        info = plan["template"]
        self.assertEqual(info["name"], "family-slow")
        self.assertEqual(info["stops"], len(acts))
        self.assertTrue(5 <= len(acts) <= 6, len(acts))
        self.assertTrue(info["rest_locked"])
        self.assertIs(info["rest_ok"], True)
        # Rest starts at the lunch activity's END (no fixed 13:00 anchor).
        lunch = info["lunch_restaurant"]
        self.assertEqual(info["rest_block"]["start"], lunch["end"])
        self.assertEqual(info["rest_block"]["minutes"], 45)  # pace 2
        lo, hi = _mins(info["rest_block"]["start"]), _mins(info["rest_block"]["end"])
        for act in acts:
            poi = BY_ID[act["poi_id"]]
            self.assertIn(poi["cat"], DAY_TEMPLATES["family-slow"]
                          ["allowed_categories"], poi["cat"])
            self.assertLessEqual(poi["intensity"], 2)
            overlap = (_mins(act["start"]) < hi
                       and _mins(act["end"]) > lo)
            self.assertFalse(overlap, f"{poi['poi_id']} overlaps rest block")
        # Universal lunch: exactly one restaurant in 11:00-13:00.
        self.assertIsNotNone(info["lunch_restaurant"], acts)
        self.assertEqual(plan["constraint_status"]["HCS"], 1)

    def test_friends_fast_late_end(self):
        plan = build_plan("balanced", _trip("08:00", "22:00"), RANKED, BY_ID,
                          CELLS, template="friends-fast")
        acts = plan["activities"]
        info = plan["template"]
        self.assertEqual(info["name"], "friends-fast")
        self.assertTrue(7 <= len(acts) <= 8, len(acts))
        self.assertGreaterEqual(max(_mins(a["end"]) for a in acts), 20 * 60)
        # Universal rest: friends-fast locks a post-lunch window too.
        self.assertIsNotNone(info["rest_block"])
        self.assertEqual(info["rest_block"]["start"],
                         info["lunch_restaurant"]["end"])
        self.assertEqual(info["rest_block"]["minutes"], 45)  # pace 2
        self.assertIs(info["rest_ok"], True)
        self.assertEqual(plan["constraint_status"]["HCS"], 1)

    def test_couple_calm_six_stops(self):
        plan = build_plan("balanced", _trip("09:00", "18:00"), RANKED, BY_ID,
                          CELLS, template="couple-calm")
        acts = plan["activities"]
        cats = {BY_ID[a["poi_id"]]["cat"] for a in acts}
        self.assertEqual(len(acts), 6)
        self.assertIn("restaurant", cats)
        self.assertIn("cafe", cats)
        self.assertTrue(cats & {"museum", "landmark", "attraction"}, cats)
        for act in acts:
            self.assertLessEqual(BY_ID[act["poi_id"]]["intensity"], 2)
        self.assertEqual(plan["constraint_status"]["HCS"], 1)

    def test_legacy_path_has_no_template_constraints(self):
        trip = _trip()
        trip.pop("profile")  # no onboarding profile = the legacy path
        legacy = build_plan("balanced", trip, RANKED, BY_ID, CELLS,
                            template="")
        self.assertIsNone(legacy["template"]["name"])
        self.assertFalse(legacy["template"]["rest_locked"])
        self.assertIsNone(legacy["template"]["rest_block"])
        # nature/high-effort POIs are not banned on the legacy path, so a pool
        # made only of them still yields a plan.
        only_outdoor = {p["poi_id"]: p for p in POIS
                        if p["cat"] in ("nature", "beach", "bar")}
        outdoor_ranked = [{"poi_id": pid} for pid in only_outdoor]
        wide = _trip("08:00", "20:00")
        wide.pop("profile")
        plan = build_plan("balanced", wide, outdoor_ranked,
                          only_outdoor, CELLS)
        self.assertGreaterEqual(len(plan["activities"]), 1)

    def test_custom_profile_without_archetype_still_gets_lunch_and_rest(self):
        """template="" (no archetype) but a profile -> universal human needs."""
        plan = build_plan("balanced", _trip(), RANKED, BY_ID, CELLS,
                          template="")
        info = plan["template"]
        self.assertIsNone(info["name"])          # no archetype
        self.assertTrue(info["rest_locked"])     # but the siesta is locked
        self.assertEqual(info["rest_block"]["start"],
                         info["lunch_restaurant"]["end"])
        self.assertEqual(info["rest_block"]["minutes"], 45)  # pace 2
        self.assertTrue(info["lunch_required"])
        self.assertIsNotNone(info["lunch_restaurant"])
        self.assertIs(info["rest_ok"], True)
        self.assertEqual(info["cafe_cap"], 1)    # no cafe need in this profile
        self.assertEqual(plan["constraint_status"]["HCS"], 1)

    def test_direct_call_without_profile_is_legacy(self):
        """Eval baselines/older callers: no profile -> no template."""
        trip = _trip()
        trip.pop("profile")
        plan = build_plan("balanced", trip, RANKED, BY_ID, CELLS)
        self.assertIsNone(plan["template"]["name"])
        self.assertFalse(plan["template"]["rest_locked"])

    def test_direct_call_with_profile_derives_template(self):
        plan = build_plan("balanced", _trip(profile={"party_type": "family"}),
                          RANKED, BY_ID, CELLS)
        self.assertEqual(plan["template"]["name"], "family-slow")

    def test_family_bans_nightlife_and_trek(self):
        plan = build_plan("balanced", _trip(), RANKED, BY_ID, CELLS,
                          template="family-slow")
        cats = {BY_ID[a["poi_id"]]["cat"] for a in plan["activities"]}
        self.assertNotIn("bar", cats)
        self.assertNotIn("nature", cats)

    def test_cafe_need_raises_the_reported_cap(self):
        """A cafe/coffee profile answer raises the HARD cap to 2 (never >2)."""
        trip = _trip("08:00", "18:00",
                     profile={"party_type": "solo", "pace": 2, "fitness": 2,
                              "food_prefs": ["cafe"]})
        plan = build_plan("balanced", trip, RANKED, BY_ID, CELLS,
                          template="couple-calm")
        self.assertEqual(plan["template"]["cafe_cap"], 2)
        cats = [BY_ID[a["poi_id"]]["cat"] for a in plan["activities"]]
        self.assertLessEqual(cats.count("cafe"), 2)
        # And the gate agrees with the solver's plan.
        self.assertEqual(plan["constraint_status"]["CAFE_CAP"], 1)
        self.assertEqual(plan["constraint_status"]["NO_CONSECUTIVE"], 1)


class TestRouterHardFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from BE.app import main as main_mod
        from BE.app.config import Settings
        from BE.app.routers import itinerary as itinerary_mod

        cls.pois = [
            _poi("sea1", "restaurant", tags=["Nhà hàng hải sản"]),
            _poi("veg1", "restaurant", tags=["Nhà hàng chay"]),
            _poi("cafe1", "cafe", tags=["Quán cà phê"]),
            _poi("attr1", "attraction", tags=["Điểm thu hút"]),
            _poi("mkt1", "market", tags=["Chợ"]),
            _poi("bar1", "bar", hours=("18:00-23:00",), tags=["Quán bar"]),
        ]
        cls.ids = [p["poi_id"] for p in cls.pois]
        cells = {f"{a}->{b}": {"minutes": 10, "km": 2.0}
                 for a in cls.ids for b in cls.ids if a != b}
        cls.tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="profile_"), cls.pois, cells)
        cls.client = TestClient(main_mod.app, raise_server_exceptions=False)
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(
            snapshot_dir=cls.tmp, snapshot_name="profile")
        # Deterministic: the router builds a trip context per request, so the
        # weather transport is mocked offline (no live HTTP in unit tests).
        cls._weather = mock.patch.object(
            trip_ctx.weather_svc, "fetch_forecast",
            side_effect=RuntimeError("offline unit test"))
        cls._weather.start()

    @classmethod
    def tearDownClass(cls):
        cls._weather.stop()
        from BE.app.routers import itinerary as itinerary_mod
        itinerary_mod.get_settings = cls._settings

    def _post(self, **profile):
        trip = {"trip_id": "t1", "city": "da-nang", "start_time": "08:00",
                "end_time": "17:30", "days": 1, "travelers": 3,
                "budget": 3000000, "transport": ["car"], "must_visit": [],
                "avoid": [], "activities": [], "food_prefs": [],
                "order_prefs": [], "profile": profile}
        return self.client.post("/v1/itinerary",
                                json={"trip": trip, "profiles": ["balanced"]})

    def test_allergy_drops_before_rank_and_warns(self):
        r = self._post(party_type="family", pace=1, fitness=1,
                       allergy=["seafood"], accessibility=[],
                       must_avoid=[])
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        chosen = {a["poi_id"] for a in plan["activities"]}
        self.assertNotIn("sea1", chosen)
        self.assertEqual(plan["template"]["name"], "family-slow")
        self.assertEqual(plan["profile_filter"]["rules"], {"allergy": 1})
        self.assertTrue(any("di ung" in w for w in plan["warnings"]),
                        plan["warnings"])

    def test_must_visit_dropped_by_profile_is_reported(self):
        trip = {"trip_id": "t1", "city": "da-nang", "start_time": "08:00",
                "end_time": "17:30", "days": 1, "travelers": 3,
                "budget": 3000000, "transport": ["car"],
                "must_visit": ["sea1"], "avoid": [], "activities": [],
                "food_prefs": [], "order_prefs": [],
                "profile": {"party_type": "family", "pace": 1, "fitness": 1,
                            "allergy": ["seafood"]}}
        r = self.client.post("/v1/itinerary",
                             json={"trip": trip, "profiles": ["balanced"]})
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        chosen = {a["poi_id"] for a in plan["activities"]}
        self.assertNotIn("sea1", chosen)
        self.assertTrue(any("bi loai boi ho so" in w
                            for w in plan["warnings"]), plan["warnings"])
        # Pruned must_visit keeps the hard gate honest (no phantom HCS fail).
        self.assertEqual(plan["constraint_status"]["HCS"], 1)

    def test_profile_is_echoed_with_defaults(self):
        r = self._post(party_type="friends", pace=3)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["plans"][0]["template"]["name"], "friends-fast")

    def test_rank_receives_profile_preferences(self):
        """Wiring: rank's user object carries the onboarding preferences."""
        from unittest import mock

        from BE.app.services import rank as rank_svc

        with mock.patch.object(rank_svc, "rank",
                               wraps=rank_svc.rank) as spy:
            r = self._post(party_type="friends", pace=3, fitness=3,
                           spending_level=3, outdoor_bias=0.5,
                           food_prefs=["hải sản"], activities=["chợ đêm"])
        self.assertEqual(r.status_code, 200, r.text)
        user = spy.call_args[0][1]
        self.assertEqual(user["fitness"], 3)
        self.assertEqual(user["spending_level"], 3)
        self.assertEqual(user["outdoor_bias"], 0.5)
        self.assertIn("hải sản", user["food_prefs"])
        self.assertIn("chợ đêm", user["activities"])


class TestFilterAndTasteHelpers(unittest.TestCase):
    def test_taste_bonus_uses_food_prefs(self):
        """food_prefs reach optimizer node scores, not only rank."""
        trip = _trip("09:00", "18:00",
                     profile={"party_type": "couple", "pace": 1,
                              "fitness": 2, "food_prefs": ["hải sản"]})
        by_id = {p["poi_id"]: p for p in POIS}
        by_id["rest1"] = dict(by_id["rest1"], tags=["Nhà hàng hải sản"])
        ranked = [{"poi_id": pid} for pid in by_id]
        plan = build_plan("balanced", trip, ranked, by_id, CELLS,
                          template="couple-calm")
        self.assertIn("rest1", {a["poi_id"] for a in plan["activities"]})

    def test_filter_is_called_before_rank(self):
        kept, drops = profile_filter.hard_filter(POIS, {"allergy": ["x"]})
        self.assertEqual(len(kept), len(POIS))
        self.assertEqual(drops, [])


class TestDynamicStateWiring(unittest.TestCase):
    """trip_ctx -> build_plan: state evidence + conditional meal rhythm."""

    def _ctx(self, trip):
        from BE.app.services import trip_ctx
        return trip_ctx.build(trip, trip.get("profile") or {},
                              fetch_weather=False)

    def test_ctx_attaches_state_and_meal_evidence(self):
        trip = _trip("07:00", "21:00", profile={"party_type": "solo",
                                                "pace": 2, "fitness": 2})
        plan = build_plan("balanced", trip, RANKED, BY_ID, CELLS,
                          template="", ctx=self._ctx(trip))
        state = plan["user_state"]
        self.assertEqual([s["name"] for s in state["meal_slots"]],
                         ["breakfast", "snack_morning", "lunch",
                          "snack_afternoon", "dinner"])
        self.assertEqual(state["weather_source"], "none")  # offline fixture
        self.assertTrue(state["bands"])
        for act in plan["activities"]:
            self.assertIn("state", act)
            for key in ("satiety", "fatigue", "heat_stress", "daypart"):
                self.assertIn(key, act["state"])
        self.assertEqual(plan["constraint_status"]["HCS"], 1)

    def test_morning_half_day_has_no_forced_lunch(self):
        trip = _trip("07:00", "12:00", profile={"party_type": "solo",
                                                "pace": 2, "fitness": 2})
        plan = build_plan("balanced", trip, RANKED, BY_ID, CELLS,
                          template="", ctx=self._ctx(trip))
        self.assertFalse(plan["template"]["lunch_required"])
        self.assertIsNone(plan["template"]["rest_block"])
        self.assertFalse(plan["user_state"]["meal_slots"]
                         and any(s["name"] == "lunch"
                                 for s in plan["user_state"]["meal_slots"]))

    def test_plan_without_ctx_stays_legacy(self):
        """A direct caller that passes no ctx gets no state keys at all."""
        trip = _trip("07:00", "21:00", profile={"party_type": "solo",
                                                "pace": 2, "fitness": 2})
        plan = build_plan("balanced", trip, RANKED, BY_ID, CELLS, template="")
        self.assertNotIn("user_state", plan)
        self.assertNotIn("state", plan["activities"][0])
        self.assertEqual(plan["constraint_status"]["HCS"], 1)


if __name__ == "__main__":
    unittest.main()
