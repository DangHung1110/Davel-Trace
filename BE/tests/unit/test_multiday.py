"""Trips of several days (FR-020): budget, repeats, must_visit, wishes, merge.

Run from repo root: python -m pytest BE/tests/unit/test_multiday.py -q
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import gate, multiday  # noqa: E402


def stop(pid, start="08:00", end="09:00"):
    return {"poi_id": pid, "start": start, "end": end}


class FakeSolver:
    """Plans `per_day` stops from a list, honouring what build_trip passes it."""

    def __init__(self, pool, fee=100000, per_day=2, meets=(), must_fails_on_day=None):
        self.pool, self.fee, self.per_day, self.meets = pool, fee, per_day, set(meets)
        self.must_fails_on_day = must_fails_on_day
        self.calls = []

    def __call__(self, trip, used, diagnose):
        self.calls.append({"trip": trip, "used": used, "diagnose": diagnose})
        must = list(trip.get("must_visit") or [])
        spendable = trip["budget"] // max(1, trip.get("travelers") or 1)
        free = [p for p in self.pool if p not in used and p not in must]
        ids = (must + free)[:self.per_day]
        fail = (self.fee * len(ids) > spendable
                or (self.must_fails_on_day is not None and len(must) > self.must_fails_on_day))
        if fail:
            return {"activities": [], "passed": False, "total_cost": 0, "warnings": ["vo nghiem"],
                    "activity_match": [], "_context": {"trip": trip, "pois": [], "travel": {}}}
        return {
            "activities": [stop(p, f"{8 + i:02d}:00", f"{8 + i:02d}:30") for i, p in enumerate(ids)],
            "segments": [{"from_id": ids[0], "to_id": ids[1], "minutes": 10}] if len(ids) > 1 else [],
            "total_cost": self.fee * len(ids) * max(1, trip.get("travelers") or 1),
            "total_km": 2.5, "total_min": 70, "travel_min": 10, "preference": 4.5,
            "cost_estimated": True, "passed": True, "violations": [], "soft_violations": [],
            "constraint_status": {"FAR": 1, "HCS": 1}, "template": {"name": None},
            "soft_penalties": {"penalty": 0.5, "issues": [{"rule": "A2"}]},
            "diversity": {"objective": "rating_first", "categories": ["cafe"], "novelty": 0.2,
                          "novel_stops": 1},
            "warnings": ["chi phi la uoc tinh"], "_rung": 0,
            "activity_match": [{"activity": w, "categories": [],
                                "status": "met" if w in self.meets else "unmet"}
                               for w in trip.get("activities") or []],
            "_context": {"trip": trip, "pois": [{"poi_id": p} for p in ids],
                         "travel": {(ids[0], ids[-1]): 10}},
        }


def passing(itinerary, trip):
    ids = [a["poi_id"] for a in itinerary["activities"]]
    ok = len(ids) == len(set(ids)) and all(m in ids for m in trip.get("must_visit") or [])
    return {"passed": ok, "failed": [] if ok else ["HCS"], "soft_failed": [],
            "checks": {"FAR": True, "HCS": ok}}


TRIP = {"days": 2, "budget": 1000000, "travelers": 1, "date": "2026-11-14",
        "start_time": "08:00", "end_time": "20:00", "must_visit": [], "activities": []}
POOL = ["a", "b", "c", "d", "e", "f"]


class TestOneDay(unittest.TestCase):
    def test_goes_straight_to_the_solver_untouched(self):
        trip = {**TRIP, "days": 1}
        solver = FakeSolver(POOL)
        plan = multiday.build_trip(solver, trip, passing)
        self.assertIs(solver.calls[0]["trip"], trip)
        self.assertNotIn("days", plan)
        self.assertNotIn("day", plan["activities"][0])


class TestTwoDays(unittest.TestCase):
    def plan(self, solver=None, **trip):
        solver = solver or FakeSolver(POOL)
        return multiday.build_trip(solver, {**TRIP, **trip}, passing), solver

    def test_days_are_numbered_and_no_poi_repeats(self):
        plan, solver = self.plan()
        self.assertEqual([(a["poi_id"], a["day"]) for a in plan["activities"]],
                         [("a", 1), ("b", 1), ("c", 2), ("d", 2)])
        self.assertEqual(solver.calls[1]["used"], {"a", "b"})
        self.assertTrue(plan["passed"])

    def test_each_day_has_its_date_and_summary(self):
        plan, solver = self.plan()
        self.assertEqual([c["trip"]["date"] for c in solver.calls], ["2026-11-14", "2026-11-15"])
        self.assertEqual([(d["day"], d["date"], d["stops"], d["total_cost"]) for d in plan["days"]],
                         [(1, "2026-11-14", 2, 200000), (2, "2026-11-15", 2, 200000)])

    def test_totals_cover_the_whole_trip(self):
        plan, _ = self.plan()
        self.assertEqual(plan["total_cost"], 400000)
        self.assertEqual(plan["travel_min"], 20)
        self.assertEqual(plan["total_km"], 5.0)
        self.assertEqual(plan["soft_penalties"]["penalty"], 1.0)
        self.assertEqual(len(plan["soft_penalties"]["issues"]), 2)
        self.assertEqual([s["day"] for s in plan["segments"]], [1, 2])
        self.assertEqual(plan["warnings"], ["chi phi la uoc tinh"])
        self.assertEqual({p["poi_id"] for p in plan["_context"]["pois"]}, {"a", "b", "c", "d"})
        self.assertEqual(plan["_context"]["trip"]["days"], 2)

    def test_budget_is_shared_day_by_day(self):
        _, solver = self.plan()
        # Half for day 1, then all that day 1 left.
        self.assertEqual([c["trip"]["budget"] for c in solver.calls], [500000, 800000])

    def test_a_tight_share_retries_but_keeps_the_next_days_meals(self):
        solver = FakeSolver(POOL, fee=300000)
        plan, _ = self.plan(solver, budget=700000)
        self.assertEqual(solver.calls[0]["trip"]["budget"], 350000)
        self.assertFalse(solver.calls[0]["diagnose"])
        self.assertEqual(solver.calls[1]["trip"]["budget"], 600000)  # 100k stays for day 2
        self.assertFalse(solver.calls[1]["diagnose"])
        self.assertFalse(plan["passed"])  # 2 stops at 300k leave 100k: day 2 cannot be planned

    def test_the_last_try_of_a_day_spends_all_and_explains_itself(self):
        solver = FakeSolver(POOL, fee=300000)
        self.plan(solver, budget=650000)
        self.assertEqual([c["trip"]["budget"] for c in solver.calls[:2]], [325000, 550000])
        self.assertEqual(solver.calls[2]["trip"]["budget"], 650000)
        self.assertTrue(solver.calls[2]["diagnose"])

    def test_a_day_that_cannot_be_planned_is_reported(self):
        plan, _ = self.plan(FakeSolver(POOL, fee=450000), budget=900000)
        self.assertFalse(plan["passed"])
        self.assertEqual(len(plan["days"]), 2)
        self.assertEqual(plan["days"][1]["stops"], 0)
        self.assertTrue(any("1/2 ngay" in w for w in plan["warnings"]))

    def test_must_visit_is_spread_over_the_days(self):
        plan, solver = self.plan(must_visit=["e", "f"])
        self.assertEqual(solver.calls[0]["trip"]["must_visit"], ["e"])
        self.assertEqual(solver.calls[1]["trip"]["must_visit"], ["f"])
        self.assertTrue(plan["passed"])

    def test_must_visit_are_packed_when_spreading_fails(self):
        # Day 2 holds no must_visit here, so only "all on day 1" can work.
        class Solver(FakeSolver):
            def __call__(self, trip, used, diagnose):
                if used and trip.get("must_visit"):
                    return super().__call__({**trip, "budget": 0}, used, diagnose)
                return super().__call__(trip, used, diagnose)
        plan, _ = self.plan(Solver(POOL), must_visit=["e", "f"])
        self.assertTrue(plan["passed"], plan.get("warnings"))
        self.assertEqual({a["poi_id"] for a in plan["activities"] if a["day"] == 1}, {"e", "f"})

    def test_a_wish_met_once_is_not_asked_again(self):
        plan, solver = self.plan(FakeSolver(POOL, meets={"tam bien"}),
                                 activities=["tam bien", "bao tang"])
        self.assertEqual(solver.calls[1]["trip"]["activities"], ["bao tang"])
        status = {m["activity"]: m["status"] for m in plan["activity_match"]}
        self.assertEqual(status, {"tam bien": "met", "bao tang": "unmet"})

    def test_no_date_stays_empty(self):
        self.assertEqual(multiday.day_date("", 1), "")
        self.assertEqual(multiday.day_date("2026-12-31", 1), "2027-01-01")


class TestGateOverDays(unittest.TestCase):
    """Clock times repeat across days, and each day has its own caps."""

    pois = {pid: {"verified": True, "cat": cat, "opening_hours": ["00:00-23:59"], "fee": 0}
            for pid, cat in (("b1", "beach"), ("b2", "beach"), ("m1", "museum"), ("m2", "market"))}
    matrix = {f"{a}->{b}": {"minutes": 5} for a in ("b1", "b2", "m1", "m2")
              for b in ("b1", "b2", "m1", "m2")}
    trip = {"budget": 100, "start_time": "08:00", "end_time": "18:00", "days": 2}

    def act(self, pid, day, start="08:00", end="09:00"):
        return {"poi_id": pid, "start": start, "end": end, "day": day}

    def checks(self, acts):
        return gate.report({"activities": acts}, self.trip, self.pois, self.matrix)

    def test_same_hours_on_two_days_pass(self):
        report = self.checks([self.act("b1", 1), self.act("b2", 2)])
        self.assertTrue(report["passed"], report["failed"])

    def test_the_cap_applies_to_each_day(self):
        report = self.checks([self.act("b1", 1), self.act("m1", 1, "10:00", "11:00"),
                              self.act("b2", 1, "12:00", "13:00"), self.act("m2", 2)])
        self.assertIn("CATEGORY_CAP", report["failed"])

    def test_overlap_inside_one_day_still_fails(self):
        report = self.checks([self.act("b1", 1), self.act("m1", 1), self.act("m2", 2)])
        self.assertIn("TCS", report["failed"])

    def test_a_poi_on_two_days_fails(self):
        report = self.checks([self.act("b1", 1), self.act("b1", 2)])
        self.assertIn("HCS", report["failed"])

    def test_a_missing_day_fails(self):
        self.assertIn("HCS", self.checks([self.act("b1", 1)])["failed"])

    def test_budget_is_the_whole_trip(self):
        pois = {**self.pois, "b1": {**self.pois["b1"], "fee": 60}, "m2": {**self.pois["m2"], "fee": 60}}
        report = gate.report({"activities": [self.act("b1", 1), self.act("m2", 2)]},
                             self.trip, pois, self.matrix)
        self.assertIn("BCS", report["failed"])


class TestReplanScope(unittest.TestCase):
    acts = [{"poi_id": "a", "day": 1}, {"poi_id": "b", "day": 1}, {"poi_id": "c", "day": 2}]

    def test_active_day_is_the_first_with_stops_to_do(self):
        self.assertEqual(multiday.active_day(self.acts, set()), 1)
        self.assertEqual(multiday.active_day(self.acts, {"a", "b"}), 2)
        self.assertEqual(multiday.active_day(self.acts, {"a", "b", "c"}), 2)

    def test_day_scope_takes_the_other_days_out_of_the_budget(self):
        trip = {"budget": 1000000, "travelers": 2, "days": 2, "must_visit": ["a", "c"]}
        pois = {"c": {"fee": 100000}}
        scope = multiday.day_scope(trip, [self.acts[2]], self.acts[:2], pois)
        self.assertEqual(scope["budget"], 800000)
        self.assertEqual(scope["must_visit"], ["a"])
        self.assertEqual(scope["days"], 1)


if __name__ == "__main__":
    unittest.main()
