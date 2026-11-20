"""hours.kind = by_booking: session-based experiences (cooking classes)."""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from migrate_v2 import apply_booking  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize, poi_to_stub  # noqa: E402
from BE.app.services.retrieval import retrieve, uncertainty, wants_booking  # noqa: E402

H = 60


def _rec():
    return {"hours": {"open": [], "kind": "unknown", "closed_days": [], "access_window": None},
            "dwell": {"p25": 60, "p50": 90, "p75": 120},
            "provenance": {"hours": {}, "dwell": {}}}


def _poi(pid, kind, cat="paid_attraction"):
    return {"poi_id": pid, "verified": True, "status": "active", "role": "attraction",
            "category": cat, "cat": "attraction", "type": "trải nghiệm",
            "opening_hours": ["08:30-12:30, 14:00-18:00"],
            "hours": {"kind": kind, "open": ["08:30-12:30", "14:00-18:00"]}}


class TestApplyBooking(unittest.TestCase):
    def test_sessions_become_open_and_dwell_is_full_session(self):
        r = _rec()
        apply_booking(r, {"_file": "booking_x.json", "sessions": ["08:30-12:30", "14:00-18:00"],
                          "booking_url": "https://example.test/book", "closed_days": ["Su"]})
        self.assertEqual(r["hours"]["kind"], "by_booking")
        self.assertEqual(r["hours"]["open"], ["08:30-12:30", "14:00-18:00"])
        self.assertEqual(r["hours"]["closed_days"], ["Su"])
        self.assertEqual(r["dwell"], {"p25": 240, "p50": 240, "p75": 240})
        self.assertEqual(r["provenance"]["hours"]["verified_by"], "agent_web")

    def test_no_sessions_leaves_record_unknown(self):
        r = _rec()
        apply_booking(r, {"_file": "booking_x.json", "sessions": []})
        self.assertEqual(r["hours"]["kind"], "unknown")


class TestRetrievalGate(unittest.TestCase):
    def test_interest_words(self):
        self.assertTrue(wants_booking(["học nấu ăn"]))
        self.assertTrue(wants_booking(["văn hóa"]))
        self.assertFalse(wants_booking(["biển", "check-in"]))

    def test_only_suggested_on_food_or_culture_interest(self):
        pois = [_poi("c1", "by_booking")]
        base = {"start_time": "07:00", "end_time": "20:00", "budget": 10_000_000}
        out = retrieve({**base, "activities": ["biển"]}, pois)
        self.assertEqual([e["poi_id"] for e in out["excluded"]], ["c1"])
        out = retrieve({**base, "activities": ["ẩm thực"]}, pois)
        self.assertEqual([c["poi_id"] for c in out["candidates"]], ["c1"])
        self.assertIn("can dat truoc (theo suat)", out["candidates"][0]["uncertainty"])

    def test_must_visit_bypasses_interest(self):
        out = retrieve({"start_time": "07:00", "end_time": "20:00", "budget": 0,
                        "activities": [], "must_visit": ["c1"]}, [_poi("c1", "by_booking")])
        self.assertEqual([c["poi_id"] for c in out["candidates"]], ["c1"])

    def test_label(self):
        self.assertIn("can dat truoc (theo suat)", uncertainty(_poi("c1", "by_booking")))


class TestOptimizer(unittest.TestCase):
    def test_stub_flag(self):
        self.assertTrue(poi_to_stub({**_poi("c1", "by_booking"), "visit_min": 240}).booking)
        self.assertFalse(poi_to_stub(_poi("c2", "fixed")).booking)

    def test_at_most_one_booking_per_day(self):
        pois = [StubPOI("c1", 240, 8 * H + 30, 18 * H, 5.0, windows=((8 * H + 30, 12 * H + 30), (14 * H, 18 * H)), booking=True),
                StubPOI("c2", 240, 8 * H + 30, 18 * H, 5.0, windows=((8 * H + 30, 12 * H + 30), (14 * H, 18 * H)), booking=True)]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 10 for a in ["depot"] + ids for b in ids if a != b}
        out = optimize(pois, travel, StubTrip(7 * H, 20 * H, "depot"), timeout_s=5)
        # both would fit (morning + afternoon session); the cap keeps one
        self.assertEqual(len(out["itinerary"]["activities"]), 1)


if __name__ == "__main__":
    unittest.main()
