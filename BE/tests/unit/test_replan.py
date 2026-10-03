"""Unit test for rolling replan (T046). Rain/clarify/no-solution.

Run from repo root: python BE/tests/unit/test_replan.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import state as store  # noqa: E402
from BE.app.services.replan import replan  # noqa: E402

H = 60
POIS = [
    {"poi_id": "hill", "verified": True, "visit_min": 120, "fee": 0, "intensity": 3,
     "weather_sensitive": True, "opening_hours": ["05:00-18:00"]},
    {"poi_id": "beach", "verified": True, "visit_min": 120, "fee": 0, "intensity": 2,
     "weather_sensitive": True, "opening_hours": ["00:00-23:59"]},
    {"poi_id": "museum", "verified": True, "visit_min": 90, "fee": 60000, "intensity": 1,
     "weather_sensitive": False, "opening_hours": ["07:30-17:00"]},
    {"poi_id": "noodle", "verified": True, "visit_min": 60, "fee": 50000, "intensity": 1,
     "weather_sensitive": False, "opening_hours": ["07:00-21:00"]},
]
IDS = [p["poi_id"] for p in POIS]
TRAVEL = {(a, b): 10 for a in ["depot"] + IDS for b in IDS if a != b}
TRIP = {"trip_id": "t1", "budget": 3000000, "avoid": [],
        "start_time": "07:00", "end_time": "18:00"}


def fresh_state():
    s = store.new_state("t1", [{"poi_id": "hill", "start": "07:30", "end": "09:30"},
                               {"poi_id": "beach", "start": "10:00", "end": "12:00"},
                               {"poi_id": "noodle", "start": "12:30", "end": "13:30"}],
                        "07:00", "hotel")
    return store.complete(store.complete(s, "hill", "09:30"), "beach", "12:00")


class TestReplan(unittest.TestCase):
    def test_rain_replans_remaining_keeps_completed(self):
        s = fresh_state()
        out = replan(s, {"type": "rain", "at": "13:00"}, POIS, TRAVEL, TRIP)
        self.assertEqual(out["mode"], "plan")
        self.assertEqual(out["preserved_completed"], ["hill", "beach"])
        self.assertEqual(out["version"], s["version"] + 1)
        drops = [c["poi_id"] for c in out["changes"] if c["action"] == "drop"]
        self.assertNotIn("hill", drops + [a["poi_id"] for a in out["itinerary"]["activities"]]
                         if out["itinerary"]["activities"] else drops)
        print(f"\n rain: mode {out['mode']} v{out['version']} changes {out['changes']}")

    def test_replan_twice_no_duplicates(self):
        s = fresh_state()
        event = {"type": "rain", "at": "13:00"}
        first = replan(s, event, POIS, TRAVEL, TRIP)
        self.assertEqual(first["mode"], "plan")
        s2 = store.load("t1")
        second = replan(s2, event, POIS, TRAVEL, TRIP)
        self.assertEqual(second["mode"], "plan")
        s3 = store.load("t1")
        ids = [a["poi_id"] for a in s3["remaining"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual((s["version"], first["version"], second["version"]),
                         (1, 2, 3))

    def test_hard_conflict_clarifies(self):
        s = fresh_state()
        out = replan(s, {"type": "add_req", "delta": {"must_keep": ["hill"]}},
                     POIS, TRAVEL, dict(TRIP, avoid=["hill"]))
        self.assertEqual(out["mode"], "clarify")
        self.assertIn("hill", out["question"])
        self.assertEqual(out["version"], s["version"])

    def test_infeasible_no_solution(self):
        s = store.new_state("t9", [{"poi_id": "a", "start": "07:00", "end": "08:00"}])
        pois = [{"poi_id": "a", "visit_min": 300, "fee": 0, "intensity": 1,
                 "weather_sensitive": False, "opening_hours": ["07:00-08:00"]},
                {"poi_id": "b", "visit_min": 300, "fee": 0, "intensity": 1,
                 "weather_sensitive": False, "opening_hours": ["09:00-10:00"]}]
        travel = {("a", "b"): 120, ("b", "a"): 120}
        out = replan(s, {"type": "delay", "delta": {"must_keep_all": True}},
                     pois, travel,
                     {"trip_id": "t9", "budget": 100, "avoid": [],
                      "start_time": "07:00", "end_time": "08:30"})
        self.assertEqual(out["mode"], "no_solution")
        self.assertIn("preserved_completed", out)

    def test_unverified_poi_fails_FAR_in_replan(self):
        trip = dict(TRIP, trip_id="unverified")
        state = store.new_state("unverified", [{"poi_id": "draft"}],
                                "07:00", "depot")
        draft = {"poi_id": "draft", "verified": False, "visit_min": 60,
                 "fee": 0, "intensity": 1, "weather_sensitive": False,
                 "opening_hours": ["07:00-18:00"]}
        out = replan(state, {"type": "delay"}, [draft],
                     {("depot", "draft"): 5}, trip)
        self.assertEqual(out["mode"], "no_solution")
        self.assertIn("FAR", out["reason"])


if __name__ == "__main__":
    unittest.main()
