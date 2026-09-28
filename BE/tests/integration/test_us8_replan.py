"""US8 integration (T048, lane B — closes US8). quickstart S5.

State with 2 completed + rain DynamicEvent (STUB-NOTE: stub dict per
data-model; real event_clf T044 classifies text at phase-PR) -> replan:
version 1->2, completed preserved, remaining re-optimized, changes list
keep/drop/replace/reorder.

Run from repo root: python BE/tests/integration/test_us8_replan.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import state as store  # noqa: E402
from BE.app.services.replan import replan  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

H = 60
POIS = [
    {"poi_id": "hill", "visit_min": 120, "fee": 0, "intensity": 3,
     "weather_sensitive": True, "opening_hours": ["05:00-18:00"]},
    {"poi_id": "beach", "visit_min": 120, "fee": 0, "intensity": 2,
     "weather_sensitive": True, "opening_hours": ["00:00-23:59"]},
    {"poi_id": "park", "visit_min": 90, "fee": 0, "intensity": 2,
     "weather_sensitive": True, "opening_hours": ["06:00-20:00"]},
    {"poi_id": "museum", "visit_min": 90, "fee": 60000, "intensity": 1,
     "weather_sensitive": False, "opening_hours": ["07:30-17:00"]},
    {"poi_id": "noodle", "visit_min": 60, "fee": 50000, "intensity": 1,
     "weather_sensitive": False, "opening_hours": ["07:00-21:00"]},
]
IDS = [p["poi_id"] for p in POIS]
TRAVEL = {(a, b): 10 for a in IDS for b in IDS if a != b}
MATRIX = {f"{a}->{b}": {"minutes": 0 if a == b else 10} for a in IDS for b in IDS}
TRIP = {"trip_id": "t1", "budget": 3000000, "avoid": [],
        "start_time": "07:00", "end_time": "18:00"}
RAIN = {"type": "rain", "at": "13:00", "source": "mock-gps",
        "affected": [], "delta": {}, "severity": "high"}


class TestUS8Replan(unittest.TestCase):
    def test_s5_rain_replan(self):
        s = store.new_state("t1", [{"poi_id": "hill", "start": "07:30", "end": "09:30"},
                                   {"poi_id": "beach", "start": "10:00", "end": "12:00"},
                                   {"poi_id": "park", "start": "13:30", "end": "15:00"},
                                   {"poi_id": "noodle", "start": "15:30", "end": "16:30"}],
                            "07:00", "hotel")
        s = store.complete(store.complete(s, "hill", "09:30"), "beach", "12:00")
        self.assertEqual(s["version"], 1)
        out = replan(s, RAIN, POIS, TRAVEL, TRIP)
        self.assertEqual(out["mode"], "plan")
        self.assertEqual(out["version"], 2)
        self.assertEqual(out["preserved_completed"], ["hill", "beach"])
        kinds = {c["action"] for c in out["changes"]}
        self.assertTrue(kinds <= {"keep", "drop", "add", "replace", "reorder"})
        self.assertIn("keep", kinds)
        self.assertIn("drop", kinds)
        drops = [c["poi_id"] for c in out["changes"] if c["action"] == "drop"]
        self.assertIn("park", drops)  # outdoor remainder replaced
        new_ids = [a["poi_id"] for a in out["itinerary"]["activities"]]
        self.assertNotIn("park", new_ids)
        by_id = {p["poi_id"]: {"verified": True, "fee": p["fee"],
                               "opening_hours": p["opening_hours"]} for p in POIS}
        done_acts = [{"poi_id": a["poi_id"], "start": a["start"], "end": a["end"]}
                     for a in s["completed"]]
        full = done_acts + out["itinerary"]["activities"]
        rep = validate({"activities": full}, TRIP, by_id, MATRIX)
        self.assertTrue(rep["passed"], rep)
        print(f"\n S5: v2 kept hill+beach, drops {drops}, new {[a['poi_id'] for a in out['itinerary']['activities']]}")


if __name__ == "__main__":
    unittest.main()
