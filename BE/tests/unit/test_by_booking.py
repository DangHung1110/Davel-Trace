"""hours.kind = by_booking: session-based experiences (cooking classes)."""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from migrate_v2 import apply_booking  # noqa: E402
from BE.app.services.gate import (  # noqa: E402
    check_a1, check_rest_follows_lunch, check_vroh, rest_rule_violation)
from BE.app.services.optimizer import (  # noqa: E402
    StubPOI, StubTrip, optimize, poi_to_stub, poi_visit_min)
from BE.app.services.profiles import _gate_view  # noqa: E402
from BE.app.services.retrieval import retrieve, uncertainty, wants_booking  # noqa: E402
from BE.app.services.soft_rules import is_meal_experience  # noqa: E402
from BE.common import (  # noqa: E402
    day_sessions, day_spans, hhmm, is_by_booking, load_pois, poi_open_windows, session_windows,
    to_min)

H = 60
SNAPSHOT_V2 = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")


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


class TestGateSeesTheClassAsAMeal(unittest.TestCase):
    """The gate judges a plan on `_gate_view` copies, and a cooking class is a meal
    only through `hours.kind`. Without `hours` in the view a class over lunch read
    as a day with no lunch (REST_FOLLOWS_LUNCH failed the plan the solver made) and
    A1 missed the restaurant that doubled the lunch."""

    CLASS = _poi("c1", "by_booking")
    LUNCH = {"poi_id": "r1", "verified": True, "status": "active", "category": "restaurant",
             "cat": "restaurant", "type": "restaurant", "opening_hours": ["10:00-21:00"]}
    TRIP = {"start_time": "08:00", "end_time": "18:00",
            "profile": {"party_type": "couple", "pace": 2}}

    @staticmethod
    def views(*pois):
        return {p["poi_id"]: p for p in pois}, {p["poi_id"]: _gate_view(p) for p in pois}

    def test_the_view_keeps_the_class_a_meal(self):
        self.assertTrue(is_meal_experience(self.CLASS))
        self.assertTrue(is_meal_experience(_gate_view(self.CLASS)))

    def test_a_class_over_lunch_is_the_lunch_at_the_gate(self):
        plan = {"activities": [{"poi_id": "c1", "start": "09:30", "end": "12:30"}]}
        full, gate = self.views(self.CLASS)
        self.assertIsNone(rest_rule_violation(plan, self.TRIP, full))
        self.assertIsNone(rest_rule_violation(plan, self.TRIP, gate))
        self.assertTrue(check_rest_follows_lunch(plan, self.TRIP, gate, {})["passed"])

    def test_a_restaurant_on_top_of_the_class_is_a_second_lunch(self):
        plan = {"activities": [{"poi_id": "c1", "start": "09:30", "end": "12:30"},
                               {"poi_id": "r1", "start": "12:45", "end": "13:45"}]}
        full, gate = self.views(self.CLASS, self.LUNCH)
        self.assertFalse(check_a1(plan, self.TRIP, full, {})["passed"])
        self.assertFalse(check_a1(plan, self.TRIP, gate, {})["passed"])

    @unittest.skipUnless(os.path.exists(os.path.join(SNAPSHOT_V2, "pois.json")), "danang-v2 missing")
    def test_every_danang_v2_class_is_a_meal_at_the_gate(self):
        pois = load_pois(SNAPSHOT_V2)
        self.assertTrue([p["name"] for p in pois if is_meal_experience(p)])  # 7 on 2026-11-24
        self.assertEqual([p["name"] for p in pois
                          if is_meal_experience(_gate_view(p)) != is_meal_experience(p)], [])


class TestClassSessionsStayApart(unittest.TestCase):
    """A class sold in overlapping sessions is booked one whole session at a time.

    `opening_hours` holds every session in one element, and `day_spans` merges the
    overlapping ones (right for a shop open 09:00-13:30 and 12:00-16:30). For Apron Up
    that made one 09:00-20:30 window: the solver started the 4.5 h class at 10:23,
    across two sessions, and gate VROH (each session on its own) rejected the plan.
    """

    SPEC = "09:00-13:30, 12:00-16:30, 16:00-20:30"   # Apron Up on danang-v2
    SESSIONS = [(9 * H, 13 * H + 30), (12 * H, 16 * H + 30), (16 * H, 20 * H + 30)]

    def _class(self, kind="by_booking"):
        return {"poi_id": "c1", "verified": True, "status": "active", "category": "paid_attraction",
                "cat": "attraction", "type": "trải nghiệm", "plan_tier": "main",
                "opening_hours": [self.SPEC],
                "hours": {"kind": kind, "open": self.SPEC.split(", ")},
                "visit_min": {"p25": 270, "p50": 270, "p75": 270}}

    def _solve(self, leg: int, end: str):
        trip = {"start_time": "08:00", "end_time": end}
        stub = poi_to_stub(self._class(), trip)
        return optimize([stub], {("depot", "c1"): leg}, StubTrip(8 * H, to_min(end), "depot"),
                        must_visit=["c1"], timeout_s=5)

    def test_the_solver_sees_every_session_apart(self):
        self.assertEqual(poi_open_windows(self._class()), self.SESSIONS)
        stub = poi_to_stub(self._class(), {"start_time": "08:00", "end_time": "21:00"})
        self.assertEqual(stub.windows, tuple(self.SESSIONS))
        self.assertTrue(stub.booking)

    def test_ordinary_hours_still_merge(self):
        whole_day = [(9 * H, 20 * H + 30)]
        self.assertEqual(day_spans(self.SPEC), whole_day)
        self.assertEqual(day_sessions(self.SPEC), self.SESSIONS)
        self.assertEqual(poi_open_windows(self._class(kind="fixed")), whole_day)
        self.assertEqual(poi_open_windows({**self._class(), "hours": {}}), whole_day)

    def test_only_a_session_sold_on_every_variant(self):
        self.assertEqual(session_windows(["09:00-13:00, 15:00-19:00", "15:00-19:00"]),
                         [(15 * H, 19 * H)])
        self.assertEqual(session_windows(["09:00-13:00", "09:30-13:00"]), [])
        self.assertIsNone(session_windows([]))
        self.assertIsNone(session_windows(None))
        self.assertEqual(poi_open_windows({**self._class(), "closed_today": True}), [])

    def test_the_solver_books_one_whole_session(self):
        gate = {"c1": _gate_view(self._class())}
        for leg, end, want in ((0, "21:00", None), (120, "21:00", None),
                               (120, "17:00", ("12:00", "16:30"))):
            out = self._solve(leg, end)
            (act,) = out["itinerary"]["activities"]
            got = (act["start"], act["end"])
            self.assertIn(got, [(hhmm(o), hhmm(c)) for o, c in self.SESSIONS], (leg, end))
            if want:
                self.assertEqual(got, want)
            self.assertTrue(check_vroh(out["itinerary"], {}, gate, {})["passed"], got)

    def test_no_session_fits_means_no_class(self):
        # at 09:40 the 09:00 class has begun, and the 12:00 one ends after a 15:00 day
        out = self._solve(100, "15:00")
        self.assertEqual(out["status"], "infeasible")
        self.assertIsNone(out["itinerary"])

    def test_the_gate_rejects_a_class_between_sessions(self):
        gate = {"c1": _gate_view(self._class())}
        between = {"activities": [{"poi_id": "c1", "start": "10:23", "end": "14:53"}]}
        self.assertFalse(check_vroh(between, {}, gate, {})["passed"])

    def test_repair_and_replan_read_the_same_sessions(self):
        from BE.app.services.repair import _fits_slot
        from BE.app.services.replan import _stub
        self.assertTrue(_fits_slot(self._class(), 12 * H, 16 * H + 30))
        self.assertFalse(_fits_slot(self._class(), 10 * H + 23, 14 * H + 53))
        stub = _stub(self._class(), {"start_time": "08:00", "end_time": "21:00"}, {}, 1.0)
        self.assertEqual(stub.windows, tuple(self.SESSIONS))

    @unittest.skipUnless(os.path.exists(os.path.join(SNAPSHOT_V2, "pois.json")), "danang-v2 missing")
    def test_every_danang_v2_class_fits_only_on_its_sessions(self):
        classes = [p for p in load_pois(SNAPSHOT_V2) if is_by_booking(p)]
        self.assertTrue(classes)  # 7 on 2026-11-25, 2 of them with overlapping sessions
        for poi in classes:
            sessions = sorted(tuple(to_min(x) for x in s.split("-")) for s in poi["hours"]["open"])
            self.assertEqual(poi_open_windows(poi), sessions, poi["name"])
            dwell = poi_visit_min(poi)
            gate = {poi["poi_id"]: _gate_view(poi)}

            def plan(start):
                return {"activities": [{"poi_id": poi["poi_id"], "start": hhmm(start),
                                        "end": hhmm(start + dwell)}]}

            for o, c in sessions:
                # the dwell is the session: a visit fits a session only from its start
                self.assertEqual(c - o, dwell, poi["name"])
                self.assertTrue(check_vroh(plan(o), {}, gate, {})["passed"], (poi["name"], o))
            for (o1, c1), (o2, _c2) in zip(sessions, sessions[1:]):
                if o2 < c1:  # overlapping sessions: a visit between them is in neither
                    self.assertFalse(check_vroh(plan((o1 + o2) // 2), {}, gate, {})["passed"],
                                     poi["name"])
