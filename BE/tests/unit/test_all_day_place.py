"""A place people spend most of a day at holds the day's lunch (soft_rules.ALL_DAY_MIN).

The planner asks every onboarded day for a restaurant lunch starting 11:00-13:00 and a
rest after it. A seven-hour hill park (Sun World Bà Nà Hills, the best-known attraction
of the snapshot) cannot sit next to that: lunch in town at 11:00, then the park until
after dinner time. Asked for by name or by wish ("cáp treo") the traveller got an EMPTY
plan. Such a stay that runs through the whole lunch window now IS the lunch, eaten and
rested on site; the solver, its seed, the gate and the order polish share that one rule.

Run: python -m pytest BE/tests/unit/test_all_day_place.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import gate, route_order, soft_rules, templates  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, _greedy_hint, optimize  # noqa: E402

H = 60
PARK = StubPOI("park", visit_min=420, open_min=8 * H, close_min=22 * H, score=5.0,
               category="attraction")
STOPS = [
    PARK,
    StubPOI("lunch", visit_min=60, open_min=10 * H, close_min=22 * H, score=4.0,
            restaurant=True, category="restaurant"),
    StubPOI("dinner", visit_min=60, open_min=10 * H, close_min=22 * H, score=4.5,
            restaurant=True, category="restaurant"),
    StubPOI("cafe", visit_min=45, open_min=7 * H, close_min=22 * H, score=4.0, category="cafe"),
    StubPOI("bridge", visit_min=20, open_min=0, close_min=24 * H, score=4.0, category="landmark"),
    StubPOI("museum", visit_min=60, open_min=8 * H, close_min=17 * H, score=4.0, category="museum"),
]
# The park is 50 minutes out of town; everything else is 10 minutes apart.
TRAVEL = {(a.poi_id, b.poi_id): (50 if "park" in (a.poi_id, b.poi_id) else 10)
          for a in STOPS for b in STOPS if a is not b}
DAY = StubTrip(8 * H, 20 * H, None)
RULES = dict(lunch_required=True, dinner_required=True, rest_after_lunch=45,
             no_consecutive=True, no_adjacent_food=True, category_cap=1, cafe_cap=1)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class TestHoldsLunch(unittest.TestCase):
    def test_a_long_stay_through_the_lunch_window(self):
        self.assertTrue(soft_rules.holds_lunch(8 * H, 15 * H))
        self.assertTrue(soft_rules.holds_lunch(11 * H, 18 * H))

    def test_too_short_or_beside_the_window(self):
        self.assertFalse(soft_rules.holds_lunch(9 * H, 13 * H + 30))  # 4.5 h: a long visit, no more
        self.assertFalse(soft_rules.holds_lunch(11 * H + 30, 19 * H))  # lunch could start before it
        self.assertFalse(soft_rules.holds_lunch(6 * H, 12 * H))        # ... or after it

    def test_lunch_on_site_names_the_stop(self):
        acts = [{"poi_id": "park", "start": "08:00", "end": "15:00"},
                {"poi_id": "dinner", "start": "17:30", "end": "18:30"}]
        pois = {"park": {"cat": "attraction"}, "dinner": {"cat": "restaurant"}}
        self.assertEqual(soft_rules.lunch_on_site(acts, pois)["poi_id"], "park")
        self.assertIsNone(soft_rules.lunch_on_site(acts[1:], pois))
        # Five hours in a restaurant is not an all-day place.
        self.assertIsNone(soft_rules.lunch_on_site(
            [{"poi_id": "dinner", "start": "08:00", "end": "15:00"}], pois))


class TestSolverSeatsAnAllDayPlace(unittest.TestCase):
    def test_named_park_is_planned_with_its_lunch_on_site(self):
        out = optimize(STOPS, TRAVEL, DAY, workers=1, must_visit=["park"], **RULES)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"), out.get("reason"))
        acts = {a["poi_id"]: a for a in out["itinerary"]["activities"]}
        self.assertIn("park", acts)
        self.assertTrue(soft_rules.holds_lunch(_minutes(acts["park"]["start"]),
                                               _minutes(acts["park"]["end"])))
        # No restaurant is driven to at noon; dinner in town still happens.
        starts = [_minutes(a["start"]) for pid, a in acts.items() if pid in ("lunch", "dinner")]
        self.assertTrue(all(start >= 17 * H + 30 for start in starts), acts)
        self.assertEqual(len(starts), 1)

    def test_a_day_without_one_still_needs_a_restaurant_lunch(self):
        out = optimize(STOPS[1:], TRAVEL, DAY, workers=1, **RULES)
        starts = [_minutes(a["start"]) for a in out["itinerary"]["activities"]
                  if a["poi_id"] in ("lunch", "dinner")]
        self.assertTrue(any(11 * H <= start < 13 * H for start in starts), starts)

    def test_no_restaurant_and_no_all_day_place_is_infeasible(self):
        out = optimize([STOPS[3], STOPS[4]], TRAVEL, DAY, workers=1, lunch_required=True)
        self.assertEqual(out["status"], "infeasible")

    def test_the_seed_starts_with_the_named_park(self):
        # By value per minute a cafe went first, then the park no longer fitted
        # before dinner: no seed, and the solve ran out of budget with nothing.
        groups = [{"count": 1, "categories": ["cafe"]}, {"count": 1, "categories": ["restaurant"]}]
        hint = _greedy_hint(STOPS, TRAVEL, DAY, {"park"}, required_any=groups, category_cap=1,
                            cafe_cap=1, no_consecutive=True, no_adjacent_food=True,
                            rest_after_lunch=45, lunch_required=True, dinner_required=True)
        placed = {STOPS[i - 1].poi_id: start for i, start in hint}
        self.assertIn("park", placed)
        self.assertLessEqual(placed["park"], soft_rules.LUNCH_REQUIRED[0])
        self.assertNotIn("lunch", [pid for pid, start in placed.items() if start < 13 * H])


GATE_POIS = {"park": {"cat": "attraction", "verified": True, "opening_hours": ["08:00-22:00"]},
             "dinner": {"cat": "restaurant", "verified": True, "opening_hours": ["10:00-22:00"]},
             "bridge": {"cat": "landmark", "verified": True, "opening_hours": ["00:00-23:59"]}}
GATE_MATRIX = {f"{a}->{b}": {"minutes": 50 if "park" in (a, b) else 10}
               for a in GATE_POIS for b in GATE_POIS if a != b}


class TestGateAcceptsLunchOnSite(unittest.TestCase):
    POIS = GATE_POIS
    TRIP = {"start_time": "08:00", "end_time": "20:00", "budget": 3_000_000,
            "profile": {"party_type": "couple", "pace": 2, "fitness": 2}}
    MATRIX = GATE_MATRIX

    def _rest(self, park_start: str, park_end: str) -> dict:
        plan = {"activities": [{"poi_id": "park", "start": park_start, "end": park_end},
                               {"poi_id": "dinner", "start": "18:00", "end": "19:00"},
                               {"poi_id": "bridge", "start": "19:15", "end": "19:35"}]}
        return gate.check_rest_follows_lunch(plan, self.TRIP, self.POIS, self.MATRIX)

    def test_a_park_through_lunch_needs_no_restaurant_and_no_rest(self):
        self.assertTrue(self._rest("08:00", "15:00")["passed"])

    def test_a_park_that_starts_after_lunch_time_still_fails(self):
        self.assertFalse(self._rest("11:30", "17:00")["passed"])

    def test_a_short_morning_stop_is_not_a_lunch(self):
        self.assertFalse(self._rest("10:00", "13:30")["passed"])


class TestPolishKeepsThePlaceThroughLunch(unittest.TestCase):
    def test_reordering_never_moves_it_off_the_lunch_window(self):
        stubs = {s.poi_id: s for s in STOPS}
        acts = [{"poi_id": "park", "start": "08:00", "end": "15:00"},
                {"poi_id": "cafe", "start": "16:02", "end": "16:47"},
                {"poi_id": "dinner", "start": "17:30", "end": "18:30"},
                {"poi_id": "bridge", "start": "18:52", "end": "19:12"}]
        better = route_order.best_order(acts, stubs, TRAVEL, 8 * H, 20 * H, 12, rest_minutes=45)
        self.assertIsNotNone(better)
        park = next(a for a in better if a["poi_id"] == "park")
        self.assertTrue(soft_rules.holds_lunch(_minutes(park["start"]), _minutes(park["end"])), better)


    def test_a_five_hour_stay_is_not_moved_so_early_that_lunch_falls_after_it(self):
        # 07:00-12:00 would be the shortest day, and a day with no lunch at all.
        tour = StubPOI("tour", visit_min=300, open_min=6 * H, close_min=20 * H, score=5.0,
                       category="attraction")
        stubs = {"tour": tour, "cafe": STOPS[3], "dinner": STOPS[2]}
        travel = {(a, b): 10 for a in stubs for b in stubs if a != b}
        acts = [{"poi_id": "cafe", "start": "07:00", "end": "07:45"},
                {"poi_id": "tour", "start": "08:10", "end": "13:10"},
                {"poi_id": "dinner", "start": "17:30", "end": "18:30"}]
        for start_min in (6 * H, 7 * H):
            rows = route_order.best_order(acts, stubs, travel, start_min, 20 * H, 12, rest_minutes=45)
            visit = next(a for a in rows if a["poi_id"] == "tour")
            self.assertTrue(soft_rules.holds_lunch(_minutes(visit["start"]), _minutes(visit["end"])), rows)


class TestPaceFloorAfterAnAllDayPlace(unittest.TestCase):
    TRIP = {"start_time": "08:00", "end_time": "20:00", "meals": True,
            "profile": {"party_type": "couple", "pace": 2, "fitness": 2}}

    def test_the_floor_counts_the_evening_that_is_left(self):
        whole = templates.template_constraints("couple-calm", self.TRIP)
        after_park = templates.template_constraints("couple-calm", self.TRIP, busy_min=420)
        self.assertEqual(whole["min_stops"], 6)
        self.assertEqual(after_park["min_stops"], 4)   # the park + 5 hours at 6 stops per 10
        self.assertEqual(after_park["max_stops"], whole["max_stops"])

    def test_a_day_with_no_profile_is_not_crammed_either(self):
        trip = {"start_time": "08:00", "end_time": "20:00", "meals": True}
        self.assertEqual(templates.universal_constraints(trip)["max_stops"], 8)
        self.assertEqual(templates.universal_constraints(trip, busy_min=420)["max_stops"], 4)


if __name__ == "__main__":
    unittest.main()
