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


class TestMealExperience(unittest.TestCase):
    """A cooking class over a meal slot IS that meal (optimizer + gate agree)."""

    def _class(self, pid="c1"):
        return StubPOI(pid, 180, 9 * H + 30, 16 * H, 5.0,
                       windows=((9 * H + 30, 12 * H + 30), (13 * H, 16 * H)), booking=True)

    def test_class_alone_satisfies_lunch(self):
        travel = {("depot", "c1"): 10}
        out = optimize([self._class()], travel, StubTrip(8 * H, 17 * H, "depot"),
                       lunch_required=True, must_visit=["c1"], timeout_s=5)
        self.assertEqual([a["poi_id"] for a in out["itinerary"]["activities"]], ["c1"])

    def test_no_second_lunch_when_class_covers_it(self):
        ids = ["c1", "r1"]
        travel = {(a, b): 10 for a in ["depot"] + ids for b in ids if a != b}
        trip = StubTrip(8 * H, 20 * H, "depot")
        # both sessions overlap 11-14 and the restaurant only opens 11-14: no room for it
        lunch_only = StubPOI("r1", 60, 11 * H, 14 * H, 5.0, restaurant=True, category="restaurant")
        out = optimize([self._class(), lunch_only], travel, trip, must_visit=["c1", "r1"], timeout_s=5)
        self.assertEqual(out["status"], "infeasible")
        # open until 20:00: it moves to the dinner slot, never a second lunch
        all_day = StubPOI("r1", 60, 11 * H, 20 * H, 5.0, restaurant=True, category="restaurant")
        out = optimize([self._class(), all_day], travel, trip, must_visit=["c1", "r1"], timeout_s=5)
        r = next(a for a in out["itinerary"]["activities"] if a["poi_id"] == "r1")
        r_start = int(r["start"][:2]) * H + int(r["start"][3:])
        self.assertFalse(11 * H <= r_start < 14 * H, r)

    def test_gate_counts_class_as_meal(self):
        from BE.app.services.gate import check_a1
        from BE.app.services.soft_rules import lunch_activity
        pois = {"c1": {"poi_id": "c1", "category": "paid_attraction", "hours": {"kind": "by_booking"}},
                "r1": {"poi_id": "r1", "category": "restaurant", "cat": "restaurant", "type": "restaurant"}}
        acts = [{"poi_id": "c1", "start": "09:30", "end": "12:30"},
                {"poi_id": "r1", "start": "12:45", "end": "13:45"}]
        self.assertFalse(check_a1({"activities": acts}, {}, pois, {})["passed"])
        self.assertTrue(check_a1({"activities": acts[:1]}, {}, pois, {})["passed"])
        self.assertEqual(lunch_activity(acts[:1], pois)["poi_id"], "c1")
