"""Contract test for POST /v1/replan (T061e wiring, quickstart S5).

Full path: POST /v1/itinerary -> plan registered with its replan context ->
POST /v1/replan rain event + one completed item -> version++, completed
preserved, outdoor remainder dropped. Unknown id -> 404 envelope.

Run: python BE/tests/contract/test_replan_api.py -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.routers import select as select_mod  # noqa: E402
from BE.tests import conftest  # noqa: E402

POIS = [
    {"poi_id": "hill", "name": "H", "type": "nature", "lat": 16.1, "lon": 108.2,
     "opening_hours": ["05:00-18:00"], "visit_min": {"p25": 60, "p50": 120, "p75": 180},
     "dur_source": "category_rule", "dur_confidence": "low", "price_level": 1, "fee": 0,
     "rating": 4.7, "tags": [], "intensity": 3, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
    {"poi_id": "beach", "name": "B", "type": "beach", "lat": 16.0, "lon": 108.2,
     "opening_hours": ["00:00-23:59"], "visit_min": {"p25": 60, "p50": 120, "p75": 180},
     "dur_source": "category_rule", "dur_confidence": "low", "price_level": 1, "fee": 0,
     "rating": 4.6, "tags": [], "intensity": 2, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
    {"poi_id": "museum", "name": "M", "type": "museum", "lat": 16.0, "lon": 108.2,
     "opening_hours": ["07:30-17:00"], "visit_min": {"p25": 45, "p50": 90, "p75": 135},
     "dur_source": "category_rule", "dur_confidence": "low", "price_level": 2, "fee": 60000,
     "rating": 4.4, "tags": [], "intensity": 1, "ambience": "", "weather_sensitive": False,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
    {"poi_id": "noodle", "name": "N", "type": "restaurant", "lat": 16.0, "lon": 108.2,
     "opening_hours": ["07:00-21:00"], "visit_min": {"p25": 30, "p50": 60, "p75": 90},
     "dur_source": "category_rule", "dur_confidence": "low", "price_level": 2, "fee": 50000,
     "rating": 4.5, "tags": [], "intensity": 1, "ambience": "", "weather_sensitive": False,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
]
CELLS = {f"{a}->{b}": {"minutes": 0 if a == b else 15, "km": 4.0}
         for a in ("hill", "beach", "museum", "noodle")
         for b in ("hill", "beach", "museum", "noodle")}
TRIP = {"trip_id": "t1", "user_id": "u1", "city": "da-nang",
        "start_time": "07:00", "end_time": "18:00", "days": 1,
        "travelers": 2, "budget": 3000000, "transport": ["motorbike"],
        "must_visit": [], "avoid": [], "activities": [],
        "food_prefs": [], "order_prefs": []}

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestReplanContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="replan_"), POIS, CELLS)
        cls._real = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=cls.tmp,
                                                      snapshot_name="replan")

    @classmethod
    def tearDownClass(cls):
        itinerary_mod.get_settings = cls._real
        select_mod.reset_store()

    def test_rain_replan_bumps_version_and_preserves_completed(self):
        select_mod.reset_store()
        r = client.post("/v1/itinerary", json={"trip": TRIP, "profiles": ["balanced"]})
        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        self.assertNotIn("_context", plan)  # private key stripped from response
        acts = plan["activities"]
        self.assertTrue(acts)
        done = acts[0]["poi_id"]

        rr = client.post("/v1/replan", json={
            "itinerary_id": plan["itinerary_id"],
            "event": {"type": "rain", "at": "13:00"},
            "completed": [done],
        })
        self.assertEqual(rr.status_code, 200, rr.text)
        body = rr.json()
        self.assertEqual(body["mode"], "plan")
        self.assertEqual(body["version"], 2)
        self.assertEqual(body["preserved_completed"], [done])
        kinds = {c["action"] for c in body["changes"]}
        self.assertIn("keep", kinds)
        # outdoor remainder (weather_sensitive) is dropped, never kept
        new_ids = [a["poi_id"] for a in body["itinerary"]["activities"]]
        self.assertNotIn("hill", new_ids)
        self.assertNotIn("beach", new_ids)

    def test_unknown_itinerary_404_envelope(self):
        rr = client.post("/v1/replan", json={"itinerary_id": "nope",
                                             "event": {"type": "rain"}})
        self.assertEqual(rr.status_code, 404)
        self.assertEqual(set(rr.json()), {"error", "message"})


if __name__ == "__main__":
    unittest.main()
