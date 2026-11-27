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
