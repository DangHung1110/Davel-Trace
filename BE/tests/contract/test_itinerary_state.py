"""Contract test: POST /v1/itinerary wires the dynamic state end-to-end.

No live service is touched: the weather forecast is mocked (success and
offline) and the snapshot is a temp fixture. This is the deterministic
replacement for the seafood E2E while LM Studio is off -- the itinerary
path itself never calls the LLM, and /v1/review is already pinned by
test_review_api.py with mocked transports.

Pins:
- `trip_ctx` reaches rank with per-hour rain + max rain (the dead branch),
- the plan carries `user_state` (meal slots, bands, weather source) and a
  per-activity `state`,
- an offline forecast degrades to the planning prior with a warning, never
  to a 5xx, and the hard gate still passes.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services import rank as rank_mod  # noqa: E402
from BE.app.services import trip_ctx  # noqa: E402
from BE.tests import conftest  # noqa: E402


def _poi(pid, cat, *, tags=None, hours=("08:00-22:00",), visit=60,
         intensity=1):
    return {"poi_id": pid, "name": pid.upper(), "cat": cat, "type": cat,
            "lat": 16.05, "lon": 108.2, "opening_hours": list(hours),
            "visit_min": visit, "fee": 0, "rating": 4.5,
            "tags": tags or [cat], "intensity": intensity,
            "weather_sensitive": cat in ("beach", "nature", "park",
                                         "viewpoint", "market"),
            "verified": True}


POIS = [
    _poi("sea1", "restaurant", tags=["Nhà hàng hải sản"]),
    _poi("veg1", "restaurant", tags=["Nhà hàng chay"]),
    _poi("cafe1", "cafe", tags=["Quán cà phê"]),
    _poi("attr1", "attraction", tags=["Điểm thu hút"]),
    _poi("mus1", "museum", tags=["Bảo tàng"]),
    _poi("mkt1", "market", tags=["Chợ"]),
    _poi("park1", "park", tags=["Công viên"]),
]

TRIP = {
    "trip_id": "state-1", "city": "da-nang", "start_time": "07:00",
    "end_time": "21:00", "days": 1, "travelers": 1, "budget": 2000000,
    "transport": ["motorbike"], "must_visit": [], "avoid": [],
    "activities": [], "food_prefs": [], "order_prefs": [],
    "profile": {"party_type": "solo", "pace": 2, "fitness": 2,
                "food_prefs": ["hải sản"], "activities": ["nature"],
                "outdoor_bias": 0.8},
}

FORECAST = {
    "fetched_at": "2026-10-27T06:00:00", "source": "open-meteo",
    "stale": False,
    "hourly": [
        {"at": f"2026-10-27T{h:02d}:00", "temp_c": t, "rain_prob": r}
        for h, t, r in [
            (7, 27.0, 0.0), (8, 28.0, 0.0), (9, 29.0, 0.0), (10, 30.0, 0.1),
            (11, 31.0, 0.2), (12, 33.0, 0.4), (13, 34.0, 0.6),
            (14, 35.0, 0.8), (15, 34.0, 0.5), (16, 33.0, 0.2),
            (17, 31.0, 0.1), (18, 30.0, 0.0), (19, 29.0, 0.0),
            (20, 28.0, 0.0), (21, 27.0, 0.0),
        ]
    ],
}


class TestItineraryStateWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = [p["poi_id"] for p in POIS]
        cells = {f"{a}->{b}": {"minutes": 10, "km": 2.0}
                 for a in cls.ids for b in cls.ids if a != b}
        cls.tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="state_"), POIS, cells)
        cls.client = TestClient(main_mod.app, raise_server_exceptions=False)
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(
            snapshot_dir=cls.tmp, snapshot_name="state")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._settings

    def _post(self, trip=None):
        return self.client.post(
            "/v1/itinerary",
            json={"trip": trip or TRIP, "profiles": ["balanced"]})

    def test_plan_carries_state_evidence_and_gates_pass(self):
        with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                               return_value=FORECAST):
            with mock.patch.object(rank_mod, "rank",
                                   wraps=rank_mod.rank) as spy:
                r = self._post()
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        # Rain is wired into rank per hour and as the trip max (dead branch).
        ctx = spy.call_args[0][2]
        self.assertAlmostEqual(ctx["rain_prob"], 0.8, places=2)
        self.assertAlmostEqual(ctx["temp_c"], 35.0, places=1)
        self.assertEqual(len(ctx["hourly"]), 15)
        self.assertTrue(ctx["dynamic_state"])
        # Plan evidence.
        state = plan["user_state"]
        self.assertEqual(state["weather_source"], "open-meteo")
        self.assertEqual(state["heat_band"], "cuc doan")
        self.assertEqual([s["name"] for s in state["meal_slots"]],
                         ["breakfast", "snack_morning", "lunch",
                          "snack_afternoon", "dinner"])
        self.assertTrue(state["bands"])
        for act in plan["activities"]:
            self.assertIn("state", act)
            self.assertIn("satiety", act["state"])
            self.assertIn("heat_effective", act["state"])
        self.assertTrue(all(v == 1 for v in
                            plan["constraint_status"].values()),
                        plan["constraint_status"])
        self.assertFalse(any("khong lay duoc du bao" in w
                             for w in plan.get("warnings") or []))

    def test_offline_weather_degrades_with_warning_and_keeps_gates(self):
        with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                               side_effect=RuntimeError("offline test")):
            r = self._post()
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        self.assertEqual(plan["user_state"]["weather_source"], "none")
        self.assertEqual(plan["user_state"]["temp_c"], trip_ctx.DEFAULT_TEMP_C)
        self.assertEqual(plan["user_state"]["rain_prob"], 0.0)
        self.assertTrue(any("khong lay duoc du bao thoi tiet" in w
                            for w in plan.get("warnings") or []),
                        plan.get("warnings"))
        self.assertTrue(all(v == 1 for v in
                            plan["constraint_status"].values()),
                        plan["constraint_status"])

    def test_morning_half_day_has_no_forced_lunch_through_the_api(self):
        trip = {**TRIP, "end_time": "12:00"}
        with mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                               return_value=FORECAST):
            r = self._post(trip)
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        self.assertFalse(plan["template"]["lunch_required"])
        self.assertIsNone(plan["template"]["rest_block"])
        self.assertFalse(any(s["name"] == "lunch"
                             for s in plan["user_state"]["meal_slots"]))
        self.assertTrue(all(v == 1 for v in
                            plan["constraint_status"].values()),
                        plan["constraint_status"])


if __name__ == "__main__":
    unittest.main()
