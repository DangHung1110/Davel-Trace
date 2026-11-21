"""Contract test for POST /v1/evaluate (T052, contracts/api.md, S4).

A good itinerary passes the canonical gate and gets the six soft scores; a
tampered one fails with its NAMED violation and no soft scores
(``soft == {}``); missing snapshot -> 503 envelope. POIs/matrix come from
the configured snapshot dir (the same source POST /v1/itinerary reads).

Run: python BE/tests/contract/test_evaluate_api.py -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import evaluate as evaluate_mod  # noqa: E402
from BE.tests import conftest  # noqa: E402

POIS = [
    {"poi_id": "museum", "name": "M", "type": "museum",
     "opening_hours": ["07:30-17:00"], "fee": 60000, "rating": 4.4,
     "verified": True, "visit_min": {"p25": 45, "p50": 90, "p75": 135}},
    {"poi_id": "beach", "name": "B", "type": "beach",
     "opening_hours": ["00:00-23:59"], "fee": 0, "rating": 4.6,
     "verified": True, "visit_min": {"p25": 90, "p50": 120, "p75": 180}},
]
CELLS = {"museum->beach": {"minutes": 10, "km": 3.0},
         "beach->museum": {"minutes": 10, "km": 3.0}}
TRIP = {"trip_id": "t1", "start_time": "07:00", "end_time": "18:00",
        "budget": 3000000, "must_visit": [], "avoid": [], "order_prefs": []}
GOOD = {"activities": [
    {"poi_id": "museum", "start": "08:00", "end": "09:30",
     "explanation": {"evidence": ["seed:museum"]}},
    {"poi_id": "beach", "start": "10:00", "end": "11:30",
     "explanation": {"evidence": ["seed:beach"]}},
]}

client = TestClient(main_mod.app, raise_server_exceptions=False)


class TestEvaluateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="eval_"), POIS, CELLS)
        cls._real = evaluate_mod.get_settings
        evaluate_mod.get_settings = lambda: Settings(snapshot_dir=cls.tmp,
                                                     snapshot_name="eval")

    @classmethod
    def tearDownClass(cls):
        evaluate_mod.get_settings = cls._real

    def test_good_itinerary_passes_with_soft_scores(self):
        r = client.post("/v1/evaluate", json={"itinerary": GOOD, "trip": TRIP})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(set(body), {"gate", "soft", "reward"})
        self.assertEqual(body["gate"], {"passed": True, "violations": []})
        self.assertEqual(set(body["soft"]),
                         {"STR", "DTU", "SSR", "CSM", "EDI", "AQE"})
        self.assertEqual(body["reward"], 0.0)

    def test_closed_poi_fails_vroh_without_soft(self):
        bad = {"activities": [{"poi_id": "museum",
                               "start": "18:00", "end": "19:30"}]}
        r = client.post("/v1/evaluate",
                        json={"itinerary": bad,
                              "trip": dict(TRIP, end_time="20:00")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIs(body["gate"]["passed"], False)
        self.assertIn("VROH", body["gate"]["violations"])
        self.assertEqual(body["soft"], {})

    def test_over_budget_fails_bcs_without_soft(self):
        r = client.post("/v1/evaluate",
                        json={"itinerary": GOOD,
                              "trip": dict(TRIP, budget=50000)})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIs(body["gate"]["passed"], False)
        self.assertIn("BCS", body["gate"]["violations"])
        self.assertEqual(body["soft"], {})

    def test_missing_snapshot_envelope(self):
        evaluate_mod.get_settings = lambda: Settings(snapshot_dir="/no/such/dir",
                                                     snapshot_name="x")
        try:
            r = client.post("/v1/evaluate", json={"itinerary": GOOD, "trip": TRIP})
        finally:
            evaluate_mod.get_settings = lambda: Settings(snapshot_dir=self.tmp,
                                                         snapshot_name="eval")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(set(r.json()), {"error", "message"})
        self.assertEqual(r.json()["error"], "SNAPSHOT_MISSING")


if __name__ == "__main__":
    unittest.main()
