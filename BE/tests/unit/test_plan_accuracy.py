"""The accuracy rules: docs/plan-accuracy.md.

Each class pins one thing the audit of 141 real plans found wrong: a wish met by the
wrong kind of place, a day without dinner, a stop at an hour it makes no sense, a
place closed that weekday, a route longer than the stops need, a plan that changes
between two identical requests. Fixtures are local; the last class reads the snapshot.

Run: python -m pytest BE/tests/unit/test_plan_accuracy.py -q
"""

import json
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import route_order, soft_rules  # noqa: E402
from BE.app.services.gate import check_dinner, check_time_fit, check_vroh  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, _greedy_hint, optimize  # noqa: E402
from BE.app.services.profiles import _activity_match, build_plan  # noqa: E402
from BE.app.services.rank import score_poi  # noqa: E402
from BE.app.services.retrieval import (  # noqa: E402
    activity_requirements, poi_fits_wish, retrieve)
from BE.app.services.templates import allows_wished, dinner_required  # noqa: E402
from BE.eval.gold.queries import build_queries  # noqa: E402
from BE.common import (  # noqa: E402
    closed_weekdays, effective_fee, poi_on_date, poi_open_windows, weekday_of)

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshots" / "danang-v1"


def mins(hhmm):
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def poi(pid, cat, *, hours=("06:00-23:00",), visit=60, rating=4.5, name=None, typ=None,
        tags=None, reviews=1000, **extra):
    return {"poi_id": pid, "name": name or pid, "cat": cat, "type": typ or cat,
            "lat": 16.05, "lon": 108.2, "opening_hours": list(hours), "visit_min": visit,
            "fee": 0, "rating": rating, "review_count": reviews, "tags": tags or [],
            "intensity": 1, "verified": True, "weather_sensitive": False, **extra}


class TestWishesMeanWhatTheySay(unittest.TestCase):
    def test_seafood_is_a_seafood_place_not_any_meal(self):
        seafood = poi("a", "restaurant", name="Quán Bé Mặn", typ="Nhà hàng hải sản")
        plain = poi("b", "restaurant", name="Cơm Gà")
        self.assertTrue(poi_fits_wish(seafood, "hải sản"))
        self.assertFalse(poi_fits_wish(plain, "hải sản"))

    def test_folding_does_not_invent_a_match(self):
        # Without accents "cửa hàng" holds a crab, "phố" a phở, "Khuê Mỹ" a noodle.
        shop_tag = poi("a", "restaurant", name="Mì Bà Mua", tags=["Cửa hàng bán đồ ăn nấu sẵn"])
        street = poi("b", "restaurant", name="Phố Nướng Tokyo")
        place = poi("c", "restaurant", name="Nhà Bếp Khuê Mỹ")
        self.assertFalse(poi_fits_wish(shop_tag, "hải sản"))
        self.assertFalse(poi_fits_wish(street, "phở"))
        self.assertFalse(poi_fits_wish(place, "mì"))
        self.assertTrue(poi_fits_wish(shop_tag, "mì"))

    def test_a_phrase_matches_a_name_typed_without_accents(self):
        plain = poi("a", "restaurant", name="Hai San Bien Dong")
        self.assertTrue(poi_fits_wish(plain, "hải sản"))

    def test_a_pagoda_is_not_a_church(self):
        pagoda = poi("a", "temple", name="Chùa Linh Ứng")
        church = poi("b", "temple", name="Nhà thờ Con Gà")
        self.assertTrue(poi_fits_wish(pagoda, "chùa"))
        self.assertFalse(poi_fits_wish(church, "chùa"))
        self.assertTrue(poi_fits_wish(church, "nhà thờ"))
        self.assertFalse(poi_fits_wish(pagoda, "nhà thờ"))

    def test_caves_are_inside_the_marble_mountains(self):
        self.assertTrue(poi_fits_wish(poi("a", "attraction", name="Ngũ Hành Sơn"), "hang động"))

    def test_each_reason_is_reported_as_itself(self):
        plain = poi("a", "restaurant", name="Cơm Gà")
        seafood = poi("b", "restaurant", name="Hải Sản Xóm Chài")
        groups, report = activity_requirements(
            ["hải sản", "đi chơi", "bảo tàng"], [plain], banned=[seafood])
        self.assertEqual(groups, [])
        self.assertEqual([row["status"] for row in report],
                         ["blocked_by_profile", "not_understood", "no_verified_poi"])

    def test_a_wish_only_the_budget_blocks_says_so(self):
        seafood = poi("b", "restaurant", name="Hải Sản Xóm Chài", fee=500_000)
        plain = poi("a", "restaurant", name="Cơm Gà")
        groups, report = activity_requirements(["hải sản"], [plain], unaffordable=[seafood])
        self.assertEqual(groups, [])
        self.assertEqual(report[0]["status"], "over_budget")

    def test_the_stop_that_met_the_wish_is_named(self):
        groups, report = activity_requirements(["hải sản"], [poi("b", "restaurant", name="Hải Sản A")])
        self.assertEqual(groups[0]["poi_ids"], ["b"])
        acts = [{"poi_id": "b", "start": "12:00", "end": "13:00"}]
        match = _activity_match(acts, report, {"b": poi("b", "restaurant")})
        self.assertEqual(match[0]["status"], "met")
        self.assertEqual(match[0]["poi_id"], "b")

    def test_a_wish_lifts_the_template_taste_not_the_fitness(self):
        hill = {"intensity": 3}
        self.assertTrue(allows_wished(hill, "couple-calm", {"fitness": 2}))
        self.assertFalse(allows_wished(hill, "family-slow", {"fitness": 1}))


class TestSunsetWish(unittest.TestCase):
    def setUp(self):
        self.pois = [
            poi("beach", "beach", hours=("00:00-23:59",)),
            poi("cafe", "cafe", visit=45),
            poi("rest", "restaurant"),
            poi("museum", "museum", hours=("08:00-17:00",)),
        ]
        self.by_id = {p["poi_id"]: p for p in self.pois}
        self.ranked = [{"poi_id": p["poi_id"]} for p in self.pois]
        self.cells = {f"{a}->{b}": {"minutes": 10, "km": 2.0}
                      for a in self.by_id for b in self.by_id if a != b}

    def trip(self, start="08:00", end="19:00"):
        return {"trip_id": "t", "budget": 3_000_000, "start_time": start, "end_time": end,
                "must_visit": [], "avoid": [], "activities": ["ngắm hoàng hôn"],
                "profile": {"party_type": "couple", "pace": 2, "fitness": 2}}

    def test_group_carries_the_hour(self):
        groups, report = activity_requirements(["ngắm hoàng hôn"], self.pois)
        self.assertEqual(groups[0]["start_between"], [16 * 60, 18 * 60])
        self.assertEqual(report[0]["start_between"], [16 * 60, 18 * 60])

    def test_the_beach_is_at_sunset(self):
        plan = build_plan("balanced", self.trip(), self.ranked, self.by_id, self.cells,
                          template="", workers=1)
        self.assertEqual(plan["activity_match"][0]["status"], "met", plan.get("warnings"))
        stop = next(a for a in plan["activities"] if a["poi_id"] == "beach")
        self.assertTrue(16 * 60 <= mins(stop["start"]) < 18 * 60, stop)

    def test_a_morning_beach_does_not_count(self):
        _, report = activity_requirements(["ngắm hoàng hôn"], self.pois)
        acts = [{"poi_id": "beach", "start": "09:00", "end": "10:00"}]
        self.assertEqual(_activity_match(acts, report, self.by_id)[0]["status"], "unmet")

    def test_a_day_over_before_sunset_says_so(self):
        plan = build_plan("balanced", self.trip(end="14:00"), self.ranked, self.by_id, self.cells,
                          template="", workers=1)
        self.assertEqual(plan["activity_match"][0]["status"], "outside_trip_hours")
        self.assertTrue(any("ngắm hoàng hôn" in w and "16:00-18:00" in w for w in plan["warnings"]))


class TestDinner(unittest.TestCase):
    def test_which_days_run_through_dinner(self):
        self.assertTrue(soft_rules.covers_dinner({"start_time": "08:00", "end_time": "20:00"}))
        self.assertFalse(soft_rules.covers_dinner({"start_time": "08:00", "end_time": "18:00"}))
        self.assertFalse(soft_rules.covers_dinner({"start_time": "19:00", "end_time": "23:00"}))

    def test_only_a_planned_day_requires_it(self):
        day = {"start_time": "08:00", "end_time": "20:00"}
        self.assertTrue(dinner_required({**day, "meals": True}))
        self.assertFalse(dinner_required(day))

    def test_gate_reads_the_stop(self):
        pois = {"r": {"cat": "restaurant"}, "c": {"cat": "cafe"}}
        trip = {"start_time": "08:00", "end_time": "20:00", "meals": True}
        with_dinner = {"activities": [{"poi_id": "r", "start": "18:00", "end": "19:00"}]}
        without = {"activities": [{"poi_id": "c", "start": "18:00", "end": "19:00"}]}
        self.assertTrue(check_dinner(with_dinner, trip, pois, {})["passed"])
        self.assertFalse(check_dinner(without, trip, pois, {})["passed"])
        self.assertTrue(check_dinner(without, {**trip, "meals": False}, pois, {})["passed"])

    def test_the_solver_books_a_second_meal(self):
        stubs = [StubPOI("r1", visit_min=60, open_min=10 * 60, close_min=22 * 60, restaurant=True,
                         score=1.0, category="restaurant"),
                 StubPOI("r2", visit_min=60, open_min=10 * 60, close_min=22 * 60, restaurant=True,
                         score=1.0, category="restaurant"),
                 StubPOI("a", visit_min=60, open_min=8 * 60, close_min=20 * 60, score=9.0,
                         category="museum"),
                 StubPOI("b", visit_min=60, open_min=8 * 60, close_min=20 * 60, score=9.0,
                         category="park")]
        travel = {(x.poi_id, y.poi_id): 10 for x in stubs for y in stubs if x is not y}
        out = optimize(stubs, travel, StubTrip(8 * 60, 20 * 60, None), workers=1,
                       deterministic_time=2.0, dinner_required=True, lunch_required=True)
        acts = out["itinerary"]["activities"]
        meals = sorted(mins(a["start"]) for a in acts if a["poi_id"] in ("r1", "r2"))
        self.assertEqual(len(meals), 2)
        self.assertTrue(soft_rules.DINNER_REQUIRED[0] <= meals[1] < soft_rules.DINNER_REQUIRED[1])


class TestTimeOfDay(unittest.TestCase):
    def snapshot_poi(self, cat, **extra):
        return {"cat": cat, "plan_tier": "main", **extra}

    def test_fixtures_and_fresh_crawls_carry_no_rule(self):
        self.assertIsNone(soft_rules.time_fit_windows({"cat": "bar"}))
        self.assertTrue(soft_rules.fits_time_of_day({"cat": "bar"}, 9 * 60, 10 * 60))

    def test_each_kind_has_its_hours(self):
        at = lambda p, hh, dur=60: soft_rules.fits_time_of_day(p, mins(hh), mins(hh) + dur)  # noqa: E731
        bar, beach, temple, restaurant = (self.snapshot_poi(c) for c in
                                          ("bar", "beach", "temple", "restaurant"))
        self.assertFalse(at(bar, "10:00"))
        self.assertTrue(at(bar, "19:00"))
        self.assertFalse(at(beach, "12:30"))
        self.assertTrue(at(beach, "16:00"))
        self.assertFalse(at(temple, "19:00"))
        self.assertTrue(at(temple, "08:00"))
        self.assertFalse(at(restaurant, "16:00"))
        self.assertTrue(at(restaurant, "12:00"))

    def test_the_finer_kind_wins(self):
        night = self.snapshot_poi("market", subcat="night_market")
        day = self.snapshot_poi("market", subcat="day_market")
        self.assertFalse(soft_rules.fits_time_of_day(night, mins("09:00"), mins("10:00")))
        self.assertTrue(soft_rules.fits_time_of_day(day, mins("09:00"), mins("10:00")))
        sunrise = self.snapshot_poi("viewpoint", subcat="sunrise")
        self.assertFalse(soft_rules.fits_time_of_day(sunrise, mins("16:00"), mins("17:00")))

    def test_opening_hours_are_cut_down_to_it(self):
        windows = soft_rules.clip_to_time_fit(self.snapshot_poi("beach"), [(0, 24 * 60)])
        self.assertEqual(windows, [(5 * 60, 11 * 60 + 30), (15 * 60, 18 * 60 + 30)])
        self.assertEqual(soft_rules.clip_to_time_fit(self.snapshot_poi("bar"), [(8 * 60, 12 * 60)]), [])

    def test_gate_is_soft_and_a_named_place_is_exempt(self):
        pois = {"b": self.snapshot_poi("bar")}
        plan = {"activities": [{"poi_id": "b", "start": "10:00", "end": "11:00"}]}
        self.assertFalse(check_time_fit(plan, {}, pois, {})["passed"])
        self.assertTrue(check_time_fit(plan, {"must_visit": ["b"]}, pois, {})["passed"])


class TestWeeklyHours(unittest.TestCase):
    WEEK = ["", "09:00-17:00", "09:00-17:00", "09:00-17:00", "09:00-17:00", "09:00-20:00", "09:00-20:00"]

    def test_weekday_is_monday_first(self):
        self.assertEqual(weekday_of("2026-11-02"), 0)
        self.assertEqual(weekday_of("2026-11-08"), 6)
        self.assertIsNone(weekday_of(None))
        self.assertIsNone(weekday_of("next tuesday"))

    def test_projection_reads_that_day(self):
        place = {"opening_hours": ["09:00-17:00"], "hours_by_day": self.WEEK}
        monday, saturday = poi_on_date(place, "2026-11-02"), poi_on_date(place, "2026-11-07")
        self.assertTrue(monday["closed_today"])
        self.assertEqual(poi_open_windows(monday), [])
        self.assertEqual(saturday["opening_hours"], ["09:00-20:00"])
        self.assertFalse(saturday["closed_today"])

    def test_no_date_or_no_table_leaves_the_poi_alone(self):
        place = {"opening_hours": ["09:00-17:00"], "hours_by_day": self.WEEK}
        self.assertIs(poi_on_date(place, None), place)
        plain = {"opening_hours": ["09:00-17:00"]}
        self.assertIs(poi_on_date(plain, "2026-11-02"), plain)

    def test_closed_weekdays(self):
        self.assertEqual(closed_weekdays({"hours_by_day": self.WEEK}), [0])
        self.assertEqual(closed_weekdays({}), [])

    def test_gate_refuses_a_closed_day(self):
        pois = {"m": {"opening_hours": [], "closed_today": True}}
        plan = {"activities": [{"poi_id": "m", "start": "10:00", "end": "11:00"}]}
        self.assertFalse(check_vroh(plan, {}, pois, {})["passed"])

    def _planned(self, date, **trip_extra):
        pois = [poi("museum", "museum", hours=("09:00-17:00",), hours_by_day=self.WEEK, rating=4.9),
                poi("park", "park", hours=("06:00-18:00",), rating=4.0),
                poi("rest", "restaurant", hours=("10:00-22:00",))]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {f"{a}->{b}": {"minutes": 10, "km": 2.0} for a in by_id for b in by_id if a != b}
        trip = {"trip_id": "t", "budget": 3_000_000, "start_time": "08:00", "end_time": "17:00",
                "must_visit": [], "avoid": [], "activities": [], "date": date, **trip_extra}
        return build_plan("balanced", trip, [{"poi_id": p} for p in by_id], by_id, cells,
                          template="", workers=1)

    def test_plan_on_the_closed_day_skips_it(self):
        ids = [a["poi_id"] for a in self._planned("2026-11-02")["activities"]]
        self.assertNotIn("museum", ids)
        self.assertIn("museum", [a["poi_id"] for a in self._planned("2026-11-03")["activities"]])

    def test_a_named_place_closed_that_day_is_dropped_with_a_warning(self):
        plan = self._planned("2026-11-02", must_visit=["museum"])
        self.assertNotIn("museum", [a["poi_id"] for a in plan["activities"]])
        self.assertTrue(any("museum" in w.lower() for w in plan.get("warnings") or []),
                        plan.get("warnings"))

    def test_no_date_warns_of_the_closed_weekday(self):
        plan = self._planned(None)
        self.assertIn("museum", [a["poi_id"] for a in plan["activities"]])
        self.assertTrue(any("thu 2" in w for w in plan.get("warnings") or []), plan.get("warnings"))


class TestRouteOrder(unittest.TestCase):
    def stubs(self, *rows):
        return {row.poi_id: row for row in rows}

    def test_finds_the_shortest_order(self):
        stubs = self.stubs(*(StubPOI(p, visit_min=30, open_min=8 * 60, close_min=20 * 60, category=p)
                             for p in "abcd"))
        place = {"a": 0, "b": 1, "c": 2, "d": 3}
        travel = {(x, y): 10 * abs(place[x] - place[y]) for x in place for y in place if x != y}
        acts = [{"poi_id": p, "start": f"{8 + i * 2:02d}:00", "end": f"{8 + i * 2:02d}:30"}
                for i, p in enumerate("cadb")]
        order = route_order.best_order(acts, stubs, travel, 8 * 60, 20 * 60, 5)
        ids = [a["poi_id"] for a in order]
        self.assertIn(ids, (list("abcd"), list("dcba")))

    def test_lunch_stays_lunch(self):
        stubs = self.stubs(
            StubPOI("r", visit_min=60, open_min=10 * 60, close_min=22 * 60, restaurant=True, category="restaurant"),
            StubPOI("a", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="park"),
            StubPOI("b", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="museum"))
        travel = {(x, y): 10 for x in stubs for y in stubs if x != y}
        acts = [{"poi_id": "a", "start": "08:00", "end": "08:30"},
                {"poi_id": "r", "start": "12:00", "end": "13:00"},
                {"poi_id": "b", "start": "14:00", "end": "14:30"}]
        order = {a["poi_id"]: a for a in route_order.best_order(acts, stubs, travel, 8 * 60, 18 * 60, 5)}
        self.assertTrue(soft_rules.LUNCH_REQUIRED[0] <= mins(order["r"]["start"]) < soft_rules.LUNCH_REQUIRED[1])

    def test_no_stop_waits_in_front_of_lunch(self):
        stubs = self.stubs(
            StubPOI("r", visit_min=60, open_min=10 * 60, close_min=22 * 60, restaurant=True, category="restaurant"),
            StubPOI("a", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="park"))
        travel = {("a", "r"): 10, ("r", "a"): 10}
        acts = [{"poi_id": "a", "start": "08:00", "end": "08:30"},
                {"poi_id": "r", "start": "11:30", "end": "12:30"}]
        order = {a["poi_id"]: a for a in route_order.best_order(acts, stubs, travel, 8 * 60, 18 * 60, 5)}
        gap = mins(order["r"]["start"]) - mins(order["a"]["end"])
        self.assertLessEqual(gap, 15)

    def test_a_free_gap_is_spent_inside_a_stop_up_to_its_longest_stay(self):
        stubs = self.stubs(
            StubPOI("m", visit_min=60, visit_max=90, open_min=8 * 60, close_min=20 * 60, category="museum"),
            StubPOI("s", visit_min=30, open_min=16 * 60, close_min=20 * 60, category="park"))
        travel = {("m", "s"): 10, ("s", "m"): 10}
        acts = [{"poi_id": "m", "start": "13:00", "end": "14:00"},
                {"poi_id": "s", "start": "16:00", "end": "16:30"}]
        order = {a["poi_id"]: a for a in route_order.best_order(acts, stubs, travel, 13 * 60, 18 * 60, 5)}
        self.assertEqual(mins(order["m"]["end"]) - mins(order["m"]["start"]), 90)

    def test_free_time_before_dinner_moves_behind_lunch(self):
        stubs = self.stubs(
            StubPOI("lunch", visit_min=60, open_min=10 * 60, close_min=22 * 60, restaurant=True, category="restaurant"),
            StubPOI("a", visit_min=30, visit_max=60, open_min=8 * 60, close_min=20 * 60, category="park"),
            StubPOI("b", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="museum"),
            StubPOI("dinner", visit_min=60, open_min=10 * 60, close_min=22 * 60, restaurant=True, category="restaurant"))
        travel = {(x, y): 10 for x in stubs for y in stubs if x != y}
        acts = [{"poi_id": "lunch", "start": "12:00", "end": "13:00"},
                {"poi_id": "a", "start": "13:30", "end": "14:00"},
                {"poi_id": "b", "start": "14:30", "end": "15:00"},
                {"poi_id": "dinner", "start": "18:00", "end": "19:00"}]
        rows = {a["poi_id"]: a for a in route_order.best_order(acts, stubs, travel, 12 * 60, 20 * 60, 5, rest_minutes=30)}
        # a stays its longest, both stops run up to dinner, the rest after lunch grows.
        self.assertEqual(mins(rows["a"]["end"]) - mins(rows["a"]["start"]), 60)
        self.assertLessEqual(mins(rows["dinner"]["start"]) - mins(rows["b"]["end"]), 15)
        self.assertLessEqual(mins(rows["b"]["start"]) - mins(rows["a"]["end"]), 15)
        self.assertGreater(mins(rows["a"]["start"]) - mins(rows["lunch"]["end"]), 60)

    def test_after_the_last_meal_stops_keep_their_earliest_times(self):
        stubs = self.stubs(
            StubPOI("dinner", visit_min=60, open_min=10 * 60, close_min=22 * 60, restaurant=True, category="restaurant"),
            StubPOI("bridge", visit_min=30, visit_max=30, open_min=6 * 60, close_min=22 * 60, category="landmark"))
        travel = {("dinner", "bridge"): 5, ("bridge", "dinner"): 5}
        acts = [{"poi_id": "dinner", "start": "18:00", "end": "19:00"},
                {"poi_id": "bridge", "start": "19:30", "end": "20:00"}]
        rows = {a["poi_id"]: a for a in route_order.best_order(acts, stubs, travel, 17 * 60, 22 * 60, 5)}
        self.assertEqual(rows["bridge"]["start"], "18:40")

    def test_asked_order_and_neighbour_rules_hold(self):
        stubs = self.stubs(
            StubPOI("a", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="park"),
            StubPOI("b", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="museum"),
            StubPOI("c", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="park"))
        travel = {("a", "b"): 50, ("b", "a"): 50, ("a", "c"): 5, ("c", "a"): 5, ("b", "c"): 50, ("c", "b"): 50}
        acts = [{"poi_id": "b", "start": "08:00", "end": "08:30"},
                {"poi_id": "a", "start": "10:00", "end": "10:30"},
                {"poi_id": "c", "start": "12:00", "end": "12:30"}]
        order = [a["poi_id"] for a in route_order.best_order(
            acts, stubs, travel, 8 * 60, 18 * 60, 5, precedence=[("c", "b")])]
        # The only order with c before b and the two parks apart, however far it drives.
        self.assertEqual(order, ["c", "b", "a"])

    def test_a_stop_held_to_an_hour_stays_there(self):
        stub = StubPOI("beach", visit_min=60, open_min=0, close_min=24 * 60, category="beach")
        held = route_order.held_to(stub, [16 * 60, 18 * 60])
        self.assertEqual(held.windows, ((16 * 60, 19 * 60),))

    def test_nothing_legal_keeps_the_solvers_plan(self):
        stubs = self.stubs(StubPOI("a", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="park"),
                           StubPOI("b", visit_min=30, open_min=8 * 60, close_min=20 * 60, category="park"))
        travel = {("a", "b"): 10, ("b", "a"): 10}
        acts = [{"poi_id": "a", "start": "08:00", "end": "08:30"}, {"poi_id": "b", "start": "10:00", "end": "10:30"}]
        self.assertIsNone(route_order.best_order(acts, stubs, travel, 8 * 60, 18 * 60, 5))


class TestNamedPlaces(unittest.TestCase):
    def test_fits_at_the_shortest_usual_stay_with_a_warning(self):
        # Two named places, 13:00-15:00: at p50 they need 3 hours, at p25 they fit.
        pois = [poi("a", "museum", visit={"p25": 45, "p50": 90, "p75": 120}),
                poi("b", "park", visit={"p25": 45, "p50": 90, "p75": 120})]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {"a->b": {"minutes": 5, "km": 1.0}, "b->a": {"minutes": 5, "km": 1.0}}
        trip = {"trip_id": "t", "budget": 3_000_000, "start_time": "13:00", "end_time": "15:00",
                "must_visit": ["a", "b"], "avoid": [], "activities": []}
        plan = build_plan("balanced", trip, [{"poi_id": "a"}, {"poi_id": "b"}], by_id, cells,
                          template="", workers=1)
        self.assertEqual(sorted(a["poi_id"] for a in plan["activities"]), ["a", "b"])
        self.assertTrue(plan["passed"], plan.get("violations"))
        self.assertTrue(any("rut ngan" in w for w in plan["warnings"]), plan["warnings"])

    def test_the_seed_keeps_the_asked_order_and_the_budget(self):
        stubs = [StubPOI("late", visit_min=30, open_min=9 * 60, close_min=20 * 60, category="spa", score=1.0),
                 StubPOI("early", visit_min=30, open_min=7 * 60, close_min=20 * 60, category="cafe", score=1.0),
                 StubPOI("dear", visit_min=30, open_min=7 * 60, close_min=20 * 60, category="museum",
                         score=9.0, fee=500),
                 StubPOI("cheap", visit_min=30, open_min=7 * 60, close_min=20 * 60, category="park",
                         score=1.0, fee=10)]
        travel = {(x.poi_id, y.poi_id): 5 for x in stubs for y in stubs if x is not y}
        names = [stubs[i - 1].poi_id for i, _start in _greedy_hint(
            stubs, travel, StubTrip(8 * 60, 18 * 60, None), {"late", "early"},
            precedence=[("late", "early")], max_fee=100)]
        self.assertLess(names.index("late"), names.index("early"))
        self.assertIn("cheap", names)
        self.assertNotIn("dear", names)


    def test_the_seed_leaves_room_for_the_next_named_place(self):
        # Filling the afternoon up to the first place's own limit would leave no time
        # for the second one, and the solver then has no seed on a very tight day.
        stubs = [StubPOI("first", visit_min=60, open_min=16 * 60, close_min=29 * 60, category="restaurant",
                         restaurant=True, score=1.0),
                 StubPOI("then", visit_min=15, open_min=7 * 60, close_min=22 * 60, category="shop", score=1.0)]
        stubs += [StubPOI(f"f{i}", visit_min=50, open_min=7 * 60, close_min=22 * 60, category=f"c{i}", score=5.0)
                  for i in range(6)]
        travel = {(x.poi_id, y.poi_id): 5 for x in stubs for y in stubs if x is not y}
        rows = _greedy_hint(stubs, travel, StubTrip(13 * 60, 18 * 60, None), {"first", "then"},
                            precedence=[("first", "then")])
        names = [stubs[i - 1].poi_id for i, _start in rows]
        self.assertIn("first", names)
        self.assertLess(names.index("first"), names.index("then"))


class TestGoldQueries(unittest.TestCase):
    def test_must_visit_is_what_the_party_could_be_planned(self):
        short = {"p25": 20, "p50": 30, "p75": 40}
        pois = [poi(f"spa{i}", "spa", visit=short, hours=("00:00-23:59",)) for i in range(20)]
        pois += [poi("clinic", "cafe", visit=short, hours=("00:00-23:59",), plan_tier="excluded")]
        pois += [poi(f"cafe{i}", "cafe", visit=short, hours=("00:00-23:59",)) for i in range(20)]
        for query in build_queries(pois, 12, 7):
            self.assertNotIn("clinic", query["trip"]["must_visit"])
            if query["profile"]["party_type"] == "family":
                self.assertFalse([m for m in query["trip"]["must_visit"] if m.startswith("spa")])


class TestReplanKeepsTheDayShape(unittest.TestCase):
    """A plan with lunch and dinner, replanned after lunch: dinner stays dinner."""

    def setUp(self):
        self.pois = [poi("lunch", "restaurant", plan_tier="main", hours=("10:00-22:00",)),
                     poi("dinner", "restaurant", plan_tier="main", hours=("10:00-22:00",)),
                     poi("park", "park", plan_tier="main", hours=("06:00-22:00",)),
                     poi("museum", "museum", plan_tier="main", hours=("08:00-17:00",))]
        ids = [p["poi_id"] for p in self.pois]
        self.travel = {(a, b): 10 for a in ids for b in ids if a != b}
        self.trip = {"trip_id": "t", "start_time": "08:00", "end_time": "20:00", "budget": 3_000_000,
                     "must_visit": [], "avoid": [], "travelers": 2, "meals": True}

    def state(self, remaining):
        return {"trip_id": "t", "version": 1, "now": "13:00", "remaining": remaining, "cancelled": [], "history": [],
                "completed": [{"poi_id": "lunch", "start": "12:00", "end": "13:00"}]}

    def test_dinner_is_not_moved_up_to_lunch(self):
        from BE.app.services.replan import replan
        remaining = [{"poi_id": "dinner", "start": "18:00", "end": "19:00"},
                     {"poi_id": "park", "start": "16:00", "end": "17:00"},
                     {"poi_id": "museum", "start": "14:00", "end": "15:00"}]
        out = replan(self.state(remaining), {"type": "drop_poi", "affected": ["museum"]},
                     self.pois, self.travel, self.trip)
        self.assertEqual(out["mode"], "plan", out)
        dinner = next(a for a in out["itinerary"]["activities"] if a["poi_id"] == "dinner")
        self.assertGreaterEqual(mins(dinner["start"]), 17 * 60)

    def test_a_stop_is_not_kept_at_a_senseless_hour(self):
        from BE.app.services.replan import _stub
        beach = poi("beach", "beach", plan_tier="main", hours=("00:00-23:59",))
        stub = _stub(beach, self.trip, {"now": "11:00"}, 1.0)
        self.assertEqual(stub.windows, ((5 * 60, 11 * 60 + 30), (15 * 60, 18 * 60 + 30)))
        named = _stub(beach, self.trip, {"now": "11:00"}, 1.0, named=True)
        self.assertEqual((named.open_min, named.close_min), (0, 23 * 60 + 59))


class TestRetrievalTiers(unittest.TestCase):
    TRIP = {"start_time": "08:00", "end_time": "20:00", "budget": 3_000_000, "activities": []}

    def pois(self):
        return [poi("main", "temple", name="Chùa A", plan_tier="main"),
                poi("local", "temple", name="Chùa B", plan_tier="local"),
                poi("wish", "attraction", name="Sun World Bà Nà", plan_tier="wish_only"),
                poi("clinic", "spa", name="Thẩm mỹ viện C", plan_tier="excluded")]

    def ids(self, **trip):
        return sorted(c["poi_id"] for c in retrieve({**self.TRIP, **trip}, self.pois())["candidates"])

    def test_a_default_day_uses_the_main_tier(self):
        self.assertEqual(self.ids(), ["main"])

    def test_a_wish_opens_the_tier_that_fits_it(self):
        self.assertEqual(self.ids(activities=["chùa"]), ["local", "main"])
        self.assertEqual(self.ids(activities=["cáp treo"]), ["main", "wish"])

    def test_excluded_never_comes_up_by_itself(self):
        self.assertNotIn("clinic", self.ids(activities=["spa"]))

    def test_a_named_place_always_does(self):
        self.assertIn("clinic", self.ids(must_visit=["clinic"]))


class TestRanking(unittest.TestCase):
    def test_a_known_place_ranks_above_an_unknown_one_of_the_same_rating(self):
        known = poi("a", "attraction", rating=4.5, reviews=30_000)
        obscure = poi("b", "attraction", rating=4.5, reviews=40)
        self.assertGreater(score_poi(known, {}, {})["score"], score_poi(obscure, {}, {})["score"])


class TestFees(unittest.TestCase):
    def test_no_ticket_flag(self):
        tags = {"price_band": "cheap", "ticket": False}
        self.assertEqual(effective_fee({"cat": "temple", "fee": 0, "smart_tags": tags}), 0)
        self.assertEqual(effective_fee({"cat": "attraction", "fee": 0, "smart_tags": tags}), 50000)


class TestTwoDayMoney(unittest.TestCase):
    def test_the_share_widens_only_as_far_as_the_floor_allows(self):
        from BE.app.services import multiday
        seen = []

        def solve(day_trip, used, diagnose):
            seen.append(day_trip["budget"])
            return {"activities": [{"poi_id": "x", "start": "12:00", "end": "13:00"}] if day_trip["budget"] >= 800_000 else [],
                    "passed": day_trip["budget"] >= 800_000, "total_cost": 800_000, "activity_match": [], "warnings": []}

        trip = {"budget": 1_000_000, "travelers": 2, "days": 2, "must_visit": [], "activities": []}
        multiday._solve_days(solve, trip, 2, True)
        self.assertEqual(seen[:2], [500_000, 800_000])  # 200k stays for the second day of two people


class TestSameRequestSamePlan(unittest.TestCase):
    SCRIPT = textwrap.dedent("""
        import json
        from BE.app.services.profiles import build_plan
        pois = [{"poi_id": f"p{i}", "name": f"p{i}", "cat": cat, "type": cat, "lat": 16.05, "lon": 108.2,
                 "opening_hours": ["06:00-23:00"], "visit_min": 45 + i % 4 * 15, "fee": 0,
                 "rating": 3.8 + (i * 7 % 12) / 10, "review_count": 100 + i * 13, "tags": [],
                 "intensity": 1, "verified": True, "weather_sensitive": False}
                for i, cat in enumerate(["restaurant", "cafe", "museum", "park", "beach", "market", "landmark"] * 5)]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {f"{a}->{b}": {"minutes": 5 + (int(a[1:]) * 7 + int(b[1:]) * 3) % 25, "km": 2.0}
                 for a in by_id for b in by_id if a != b}
        trip = {"trip_id": "t", "budget": 3000000, "start_time": "08:00", "end_time": "20:00", "must_visit": [],
                "avoid": [], "activities": [], "meals": True, "profile": {"party_type": "couple", "pace": 2}}
        plan = build_plan("balanced", trip, [{"poi_id": p} for p in by_id], by_id, cells, template="",
                          workers=1, deterministic_time=1.0, timeout_s=60.0)
        print(json.dumps(plan["activities"]))
    """)

    def run_with_hash_seed(self, seed):
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        out = subprocess.run([sys.executable, "-c", self.SCRIPT], capture_output=True, text=True,
                             env=env, cwd=str(SNAPSHOT.parents[3]), check=True, timeout=180)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_across_processes_and_hash_seeds(self):
        first = self.run_with_hash_seed(1)
        self.assertTrue(first)
        self.assertEqual(first, self.run_with_hash_seed(2))


class TestReviewPage(unittest.TestCase):
    def test_the_reviewer_sees_the_plan_and_no_machine_verdict(self):
        from BE.tools import build_plan_review as review
        plans = json.loads(review.PLANS_PATH.read_text(encoding="utf-8"))["plans"]
        self.assertGreaterEqual(len(plans), 20)
        self.assertEqual(len({plan["id"] for plan in plans}), len(plans))
        for plan in plans:
            self.assertTrue(plan["stops"], plan["id"])
            self.assertFalse({"passed", "violations", "soft_violations", "scores"} & set(plan), plan["id"])
        page = review.render(plans)
        self.assertNotIn("__PLANS_JSON__", page)
        self.assertNotIn('"soft_violations"', page)
        self.assertLess(page.index("<title>"), 200)


@unittest.skipUnless((SNAPSHOT / "pois.json").exists(), "snapshot absent")
class TestSnapshotContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pois = json.loads((SNAPSHOT / "pois.json").read_text(encoding="utf-8"))["pois"]
        cls.verified = [p for p in cls.pois if p.get("verified")]
        cls.matrix = json.loads((SNAPSHOT / "matrix.json").read_text(encoding="utf-8"))

    def test_every_verified_poi_has_a_tier_and_a_known_source_for_its_duration(self):
        for p in self.verified:
            self.assertIn(p.get("plan_tier"), ("main", "local", "wish_only", "excluded"), p["name"])
            if p.get("plan_tier") != "main":
                self.assertTrue(p.get("plan_tier_reason"), p["name"])
            self.assertIn(p.get("dur_source"), ("subcat_rule", "curated", "google_typical", "human"), p["name"])

    def test_weekly_tables_have_seven_days_monday_first(self):
        tables = [p for p in self.verified if p.get("hours_by_day")]
        self.assertGreater(len(tables), 300)
        for p in tables:
            self.assertEqual(len(p["hours_by_day"]), 7, p["name"])

    def test_medical_places_are_out(self):
        for p in self.verified:
            if p.get("type") in ("Spa y tế", "Thẩm mỹ viện", "Bác sĩ trị liệu xoa bóp"):
                self.assertEqual(p["plan_tier"], "excluded", p["name"])

    def test_a_poi_added_by_the_pass_claims_no_review_it_did_not_have(self):
        added = set(self.matrix["coverage"]["estimated_ids"])
        self.assertTrue(added)
        for p in self.pois:
            if p["poi_id"] in added:
                self.assertIsNone(p.get("io_label"), p["name"])
                self.assertNotEqual(p.get("space_source"), "audit", p["name"])
                self.assertEqual(p.get("verified_by"), "claude-google-maps-v1", p["name"])

    def test_estimated_matrix_rows_are_listed(self):
        estimated = self.matrix["coverage"]["estimated_ids"]
        self.assertTrue(estimated)
        self.assertLessEqual(set(estimated), set(self.matrix["ids"]))
        self.assertEqual(self.matrix["coverage"]["osrm"], (len(self.matrix["ids"]) - len(estimated)) ** 2)


if __name__ == "__main__":
    unittest.main()
