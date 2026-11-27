"""POST /v1/itinerary with a GPS fix as `trip.origin` (specs/024-gps-origin).

A small temporary snapshot (a hotel and three stops in Da Nang, every leg in the
matrix) and the real planner: a fix near the hotel starts the day from a row of its
own (`@gps:...`, `source: gps_estimate`) and the plan says how (`gps_origin`); a fix
the planner cannot use starts the day at `fallback_poi_id` and the plan says why.
"""

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
from BE.app.services import trip_ctx  # noqa: E402
from BE.tests import conftest  # noqa: E402
from BE.tools.audit_plans import audit_day  # noqa: E402


def _poi(pid, name, kind, lat, lon, hours, visit, fee, rating):
    return {"poi_id": pid, "name": name, "type": kind, "lat": lat, "lon": lon,
            "opening_hours": [hours], "visit_min": {"p25": visit, "p50": visit, "p75": visit},
            "dur_source": "category_rule", "dur_confidence": "low", "price_level": 1,
            "fee": fee, "rating": rating, "tags": [], "intensity": 1, "ambience": "",
            "weather_sensitive": False, "pros": [], "cons": [], "source": "t",
            "fetched_at": "2026-09-28", "verified": True}


POIS = [
    _poi("hotel", "Khach san Bien", "lodging", 16.06900, 108.24500, "00:00-23:59", 30, 0, 4.0),
    _poi("beach", "Bai bien", "beach", 16.07000, 108.25000, "00:00-23:59", 90, 0, 4.6),
    _poi("museum", "Bao tang", "museum", 16.06000, 108.22300, "08:00-17:00", 60, 60000, 4.5),
    _poi("noodle", "Quan mi", "restaurant", 16.06500, 108.21500, "07:00-21:00", 45, 50000, 4.4),
]
MINUTES = {("hotel", "beach"): 4, ("hotel", "museum"): 12, ("hotel", "noodle"): 14,
           ("beach", "museum"): 13, ("beach", "noodle"): 15, ("museum", "noodle"): 6}
CELLS = {}
for (a, b), m in MINUTES.items():
    CELLS[f"{a}->{b}"] = {"minutes": m, "km": round(m / 2.5, 2)}
    CELLS[f"{b}->{a}"] = {"minutes": m, "km": round(m / 2.5, 2)}
TRIP = {"trip_id": "t1", "user_id": "u1", "city": "da-nang", "start_time": "08:00",
        "end_time": "13:00", "days": 1, "travelers": 2, "budget": 3000000,
        "transport": ["motorbike"], "activities": []}
client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestGpsOriginApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = conftest.write_snapshot(tempfile.mkdtemp(prefix="snap_gps_"), POIS, CELLS)
        cls._real = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=cls.tmp, snapshot_name="test")
        cls._weather = mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                                         side_effect=RuntimeError("offline"))
        cls._weather.start()

    @classmethod
    def tearDownClass(cls):
        cls._weather.stop()
        itinerary_mod.get_settings = cls._real

    def plan(self, origin):
        r = client.post("/v1/itinerary", json={"trip": {**TRIP, "origin": origin},
                                               "profiles": ["balanced"]})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["plans"][0]

    def test_a_fix_near_the_hotel_starts_the_day_there(self):
        plan = self.plan({"lat": 16.07170, "lon": 108.24500, "accuracy_m": 15})  # 300 m north
        report = plan["gps_origin"]
        self.assertTrue(report["used"])
        self.assertEqual((report["anchor_poi_id"], report["anchor_m"]), ("hotel", 300))
        first = plan["segments"][0]
        self.assertTrue(first["from_id"].startswith("@gps:"))
        self.assertEqual(first["from_id"], report["origin_id"])
        self.assertEqual(first["source"], "gps_estimate")
        self.assertTrue(plan["passed"])
        self.assertGreaterEqual(plan["activities"][0]["start"], "08:01")

    def test_a_fix_at_the_hotel_plans_like_the_hotel(self):
        at_hotel = self.plan({"lat": 16.06905, "lon": 108.24500})  # 6 m
        hotel = self.plan({"poi_id": "hotel"})
        self.assertEqual([(a["poi_id"], a["start"]) for a in at_hotel["activities"]],
                         [(a["poi_id"], a["start"]) for a in hotel["activities"]])
        self.assertEqual([s["minutes"] for s in at_hotel["segments"]],
                         [s["minutes"] for s in hotel["segments"]])

    def test_a_fix_at_a_summit_hotel_can_walk_after_the_last_ascent(self):
        timetable = {"gateway": "summit", "mode": "cable_car", "name": "Cable car",
                     "ride_min": 5, "board_min": 3, "go": "08:00-09:00", "back": "08:00-18:00",
                     "arrive_from": "08:05", "arrive_by": "09:05", "leave_by": "17:57"}
        places = [{**p, "transfer": timetable} if p["poi_id"] in ("hotel", "museum") else p
                  for p in POIS]
        legs = {**CELLS, "hotel->museum": {**CELLS["hotel->museum"], "mode": "walk"}}
        trip = {**TRIP, "origin": {"lat": 16.06900, "lon": 108.24500},
                "must_visit": ["museum"], "start_time": "09:30", "end_time": "10:55"}
        with tempfile.TemporaryDirectory() as tmp:
            conftest.write_snapshot(tmp, places, legs)
            with mock.patch.object(itinerary_mod, "get_settings",
                                   return_value=Settings(snapshot_dir=tmp, snapshot_name="test")):
                r = client.post("/v1/itinerary", json={"trip": trip, "profiles": ["balanced"]})
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertEqual([a["poi_id"] for a in plan["activities"]], ["museum"])
        self.assertEqual((plan["segments"][0]["mode"], plan["segments"][0]["source"]),
                         ("walk", "gps_estimate"))
        by_id = {p["poi_id"]: p for p in places}
        flags, _ = audit_day(plan["activities"], trip, by_id, legs, "", {"museum"}, None)
        self.assertFalse([f for f in flags if f.startswith("ERR_")], flags)
        from_road = {**trip, "origin": {"lat": POIS[1]["lat"], "lon": POIS[1]["lon"]}}
        flags, _ = audit_day(plan["activities"], from_road, by_id, legs, "", {"museum"}, None)
        self.assertTrue(any(f.startswith("ERR_TRANSFER") for f in flags), flags)

    def test_a_fix_far_away_falls_back_to_the_hotel(self):
        plan = self.plan({"lat": 21.0285, "lon": 105.8542, "fallback_poi_id": "hotel"})
        self.assertEqual(plan["gps_origin"]["used"], False)
        self.assertEqual(plan["gps_origin"]["origin_id"], "hotel")
        self.assertEqual(plan["segments"][0]["from_id"], "hotel")
        self.assertTrue(any("ngoai vung Da Nang" in w for w in plan.get("warnings") or []))

    def test_a_place_origin_has_no_gps_report(self):
        self.assertNotIn("gps_origin", self.plan({"poi_id": "hotel"}))


if __name__ == "__main__":
    unittest.main()
