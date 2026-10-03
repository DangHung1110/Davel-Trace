"""US1 parser and planning boundary via TestClient.

Fixed prompt -> parse -> real retrieval fixture -> explicit planner
unavailable envelope until lane B's feasibility service is present;
missing-info prompt -> clarification. Fixture snapshot (lane C has no seed).

Run: python BE/tests/integration/test_us1_flow.py -v  (or pytest)
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.config import Settings  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services import parser as parser_svc  # noqa: E402
from BE.app.services import retrieval as retrieval_svc  # noqa: E402

POIS = [
    {"poi_id": "hill", "name": "Hill", "type": "nature", "lat": 16.1,
     "lon": 108.2, "opening_hours": ["05:00-18:00"],
     "visit_min": {"p25": 120, "p50": 180, "p75": 240}, "dur_source": "category_rule",
     "dur_confidence": "low", "price_level": 1, "fee": 0, "rating": 4.7,
     "tags": ["leo núi"], "intensity": 3, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
    {"poi_id": "noodle", "name": "Noodle", "type": "restaurant", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["07:00-21:00"],
     "visit_min": {"p25": 30, "p50": 60, "p75": 90}, "dur_source": "category_rule",
     "dur_confidence": "low", "price_level": 2, "fee": 50000, "rating": 4.5,
     "tags": ["ăn"], "intensity": 1, "ambience": "", "weather_sensitive": False,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
    {"poi_id": "beach", "name": "Beach", "type": "beach", "lat": 16.0,
     "lon": 108.2, "opening_hours": ["00:00-23:59"],
     "visit_min": {"p25": 90, "p50": 120, "p75": 180}, "dur_source": "category_rule",
     "dur_confidence": "low", "price_level": 1, "fee": 0, "rating": 4.6,
     "tags": ["biển"], "intensity": 2, "ambience": "", "weather_sensitive": True,
     "pros": [], "cons": [], "source": "t", "fetched_at": "s", "verified": True},
]
CELLS = {}
for _a in ("hill", "noodle", "beach"):
    for _b in ("hill", "noodle", "beach"):
        CELLS[f"{_a}->{_b}"] = {"minutes": 0 if _a == _b else 15, "km": 4.0}

SLOTS = {"city": "Đà Nẵng", "date": "", "start_time": "07:00",
         "end_time": "18:00", "days": 1, "travelers": 2, "budget": 3000000,
         "transport": ["motorbike"], "must_visit": [], "avoid": [],
         "activities": ["leo núi", "biển"], "food_prefs": [],
         "order_prefs": [["hill", "beach"]],
         "hard_constraints": [], "soft_prefs": [], "uncertainties": []}

client = TestClient(main_mod.app, raise_server_exceptions=False)


def _mock_slots(prompt, schema):
    return dict(SLOTS)


def to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


class TestUS1Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="us1_")
        with open(os.path.join(cls.tmp, "pois.json"), "w", encoding="utf-8") as f:
            json.dump({"pois": POIS}, f, ensure_ascii=False)
        with open(os.path.join(cls.tmp, "matrix.json"), "w", encoding="utf-8") as f:
            json.dump({"ids": ["hill", "noodle", "beach"], "cells": CELLS}, f)
        cls._llm = parser_svc.llm_gateway.complete_json
        parser_svc.llm_gateway.complete_json = _mock_slots
        cls._settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(snapshot_dir=cls.tmp,
                                                      snapshot_name="us1")

    @classmethod
    def tearDownClass(cls):
        parser_svc.llm_gateway.complete_json = cls._llm
        itinerary_mod.get_settings = cls._settings

    def test_s2_parse_fixed_prompt(self):
        r = client.post("/v1/parse", json={"text": "cuối tuần đi Đà Nẵng leo núi rồi đi biển",
                                           "user_id": "u1"})
        self.assertEqual(r.status_code, 200)
        trip = r.json()
        self.assertEqual(trip["city"], "đà-nẵng")
        self.assertEqual(trip["budget"], 3000000)
        TestUS1Flow.trip = trip

    def test_s3_planning_boundary(self):
        r = client.post("/v1/parse", json={"text": "cuối tuần đi Đà Nẵng"})
        trip = {k: v for k, v in r.json().items()
                if k in ("trip_id", "user_id", "city", "start_time", "end_time", "days",
                         "travelers", "budget", "transport", "must_visit", "avoid",
                         "activities", "food_prefs", "order_prefs")}
        pool = retrieval_svc.retrieve(trip, POIS)["candidates"]
        self.assertEqual({candidate["poi_id"] for candidate in pool}, {"hill", "beach"})
        r = client.post("/v1/itinerary", json={"trip": trip, "profiles": ["balanced"]})
        if r.status_code == 501:
            self.assertEqual(set(r.json()), {"error", "message"})
            self.assertEqual(r.json()["error"], "PLANNER_UNAVAILABLE")
            return

        self.assertEqual(r.status_code, 200, r.text)
        plan = r.json()["plans"][0]
        acts = plan["activities"]
        self.assertGreaterEqual(len(acts), 2)
        for a in acts:  # required fields (spec US1 acceptance)
            for k in ("poi_id", "start", "end", "explanation"):
                self.assertIn(k, a)
            self.assertTrue(a["explanation"].get("evidence"))  # >=1 reason
        ordered = sorted(acts, key=lambda a: a["start"])
        for x, y in zip(ordered, ordered[1:]):  # no overlap + travel fits
            self.assertLessEqual(to_min(x["end"]), to_min(y["start"]))
        for k in ("total_cost", "total_km", "total_min", "constraint_status",
                  "version"):
            self.assertIn(k, plan)
        self.assertEqual(plan["constraint_status"],
                         {"FAR": 1, "VROH": 1, "B3": 1, "BCS": 1})

    def test_missing_info_clarifies(self):
        parser_svc.llm_gateway.complete_json = lambda prompt, schema: dict(SLOTS, city="")
        try:
            r = client.post("/v1/parse", json={"text": "đi chơi 2 người"})
        finally:
            parser_svc.llm_gateway.complete_json = _mock_slots
        self.assertEqual(r.json()["needs_clarification"], ["city"])


if __name__ == "__main__":
    unittest.main()
