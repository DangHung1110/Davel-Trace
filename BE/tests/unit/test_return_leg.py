"""A day that starts at the traveller's lodging pays the ride back to it.

Before, `profiles.build_plan` put only the legs FROM the base (hotel -> candidate) in
`travel`, so objective v1's T9 found no minutes on the last arc (stop -> depot) and
`objective.features` read 0 for (last stop, base): a hotel day could end far from the
hotel for free. Now the legs back to the base (the matrix column of the lodging) are
in `travel` too, for a lodging origin only: a day that starts somewhere the traveller
does not sleep (a replan that resumes at the stop just finished, a GPS fix, a place
they named) does not end there, so it pays no ride back to it.

Run: python -m pytest BE/tests/unit/test_return_leg.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import gate, matrix, objective  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.profiles import build_plan, sleeps_at  # noqa: E402
from BE.common import to_min  # noqa: E402

H = 60


def cells(minutes: dict) -> dict:
    return {f"{a}->{b}": {"minutes": m, "km": m / 3} for (a, b), m in minutes.items()}


class TestMatrixColumn(unittest.TestCase):
    LEGS = {("a", "h"): 5, ("b", "h"): 40, ("h", "a"): 6, ("a", "b"): 10}

    def test_dict_cells(self):
        self.assertEqual(matrix.legs_to(cells(self.LEGS), ["a", "b", "h", "zz"], "h"),
                         {("a", "h"): 5, ("b", "h"): 40})

    def test_dense_cells(self):
        dense = matrix.DenseCells(["h", "a", "b"],
                                  [[0, 6, 40], [5, 0, 10], [None, 10, 0]],
                                  [[0, 2, 9], [1, 0, 3], [None, 3, 0]])
        # b cannot ride back: absent, never 0.
        self.assertEqual(matrix.legs_to(dense, ["a", "b"], "h"), {("a", "h"): 5})


class TestWhereTheDayEnds(unittest.TestCase):
    BY_ID = {"hotel": {"role": "base"}, "cafe": {"role": "rest"}, "bridge": {"role": "attraction"}}

    def test_a_lodging(self):
        self.assertTrue(sleeps_at("hotel", self.BY_ID))

    def test_anywhere_else(self):
        for pid in ("cafe", "bridge", "@gps:16.06100,108.24300", "zz", None, ""):
            self.assertFalse(sleeps_at(pid, self.BY_ID), pid)


# X opens the day (the best stop, open only in the early morning). One more stop fits
# after it: NEAR (5 min from the hotel) or FAR (40 min), equally 10 min from X. FAR is
# rated a little higher, so a day that rides home for free ends at FAR.
POIS = [
    {"poi_id": "x", "verified": True, "visit_min": 60, "rating": 4.9, "fee": 0,
     "intensity": 2, "opening_hours": ["07:00-08:30"]},
    {"poi_id": "near", "verified": True, "visit_min": 60, "rating": 4.6, "fee": 0,
     "intensity": 2, "opening_hours": ["08:00-12:00"]},
    {"poi_id": "far", "verified": True, "visit_min": 60, "rating": 4.7, "fee": 0,
     "intensity": 2, "opening_hours": ["08:00-12:00"]},
]
IDS = [p["poi_id"] for p in POIS]
LEGS = {
    ("hotel", "x"): 10, ("x", "hotel"): 10,
    ("hotel", "near"): 5, ("near", "hotel"): 5,
    ("hotel", "far"): 40, ("far", "hotel"): 40,
    ("x", "near"): 10, ("near", "x"): 10, ("x", "far"): 10, ("far", "x"): 10,
    ("near", "far"): 40, ("far", "near"): 40,
}
TRIP = {"trip_id": "t1", "budget": 1000000, "start_time": "07:00", "end_time": "10:30"}


def plan(origin_role="base", **trip):
    by_id = {p["poi_id"]: dict(p) for p in POIS}
    by_id["hotel"] = {"poi_id": "hotel", "verified": True, "role": origin_role}
    return build_plan("balanced", {**TRIP, **trip}, [{"poi_id": pid} for pid in IDS],
                      by_id, cells(LEGS))


def stops(p):
    return [a["poi_id"] for a in p["activities"]]


class TestTheDayRidesBackToTheLodging(unittest.TestCase):
    def test_the_day_ends_near_the_hotel(self):
        p = plan(origin_id="hotel")
        self.assertTrue(p["passed"])
        self.assertEqual(stops(p), ["x", "near"])

    def test_an_open_tour_still_ends_where_the_stops_are_best(self):
        # No base: no ride back, the better-rated stop wins.
        self.assertEqual(stops(plan()), ["x", "far"])

    def test_the_stored_legs_ride_back_to_the_lodging(self):
        travel = plan(origin_id="hotel")["_context"]["travel"]
        self.assertEqual({pair: m for pair, m in travel.items() if pair[1] == "hotel"},
                         {("x", "hotel"): 10, ("near", "hotel"): 5, ("far", "hotel"): 40})

    def test_a_start_that_is_not_a_lodging_rides_back_nowhere(self):
        # A replan that resumes at a cafe it just left does not end there.
        p = plan(origin_role="rest", origin_id="hotel")
        self.assertEqual(stops(p), ["x", "far"])
        self.assertFalse([pair for pair in p["_context"]["travel"] if pair[1] == "hotel"])
        self.assertEqual(p["segments"][0]["from_id"], "hotel")  # it still starts there

    def test_a_gps_start_rides_back_nowhere(self):
        # feat/gps-origin: a fix gets a row of its own and no column; it is no place.
        fix = "@gps:16.06100,108.24300"
        legs = {**{(a, b): m for (a, b), m in LEGS.items() if "hotel" not in (a, b)},
                **{(fix, b): m for (a, b), m in LEGS.items() if a == "hotel"}}
        by_id = {p["poi_id"]: dict(p) for p in POIS}
        p = build_plan("balanced", {**TRIP, "origin_id": fix}, [{"poi_id": pid} for pid in IDS],
                       by_id, cells(legs))
        self.assertEqual(stops(p), ["x", "far"])
        self.assertFalse([pair for pair in p["_context"]["travel"] if pair[1] == fix])


def _poi(pid, score, visit=60, opens=7 * H, closes=21 * H, group="", zone=""):
    return StubPOI(pid, visit_min=visit, open_min=opens, close_min=closes, score=score,
                   category=group or pid, group=group, zone=zone)


def _spec():
    return objective.Spec(w=objective.weights("v1"), k0=6, pace=2, food_tour=False,
                          strict=frozenset(), breakfast=False)


class TestModelAndFeaturesAgree(unittest.TestCase):
    """CP-SAT's J and `objective.features` on the finished day, ride back included."""

    POIS = [_poi("museum", 5.0, group="history", zone="trung_tam"),
            _poi("beach", 4.8, visit=90, group="beach", zone="son_tra"),
            _poi("temple", 4.6, group="religious", zone="son_tra"),
            _poi("market", 4.4, group="market", zone="trung_tam")]
    OUT = {"museum": 8, "beach": 12, "temple": 25, "market": 6}
    BACK = {"museum": 9, "beach": 11, "temple": 58, "market": 7}  # temple: a long leg

    def travel(self, back=True):
        t = {(a.poi_id, b.poi_id): (10 if a.zone == b.zone else 25)
             for a in self.POIS for b in self.POIS if a.poi_id != b.poi_id}
        t.update({("hotel", pid): m for pid, m in self.OUT.items()})
        if back:
            t.update({(pid, "hotel"): m for pid, m in self.BACK.items()})
        return t

    def check(self, travel, start, end):
        spec = _spec()
        out = optimize(self.POIS, travel, StubTrip(start, end, "hotel"), workers=1,
                       timeout_s=30, objective=spec)
        self.assertEqual(out["status"], "optimal")
        acts = [{"poi_id": a["poi_id"], "start": to_min(a["start"])}
                for a in out["itinerary"]["activities"]]
        f = objective.features(acts, {p.poi_id: p for p in self.POIS}, travel, spec,
                               start, end, origin_id="hotel")
        self.assertAlmostEqual(out["objective"] / (1000.0 * out["unit"]),
                               objective.objective_value(f, spec), delta=0.01)
        return acts, f

    def test_with_the_ride_back(self):
        acts, f = self.check(self.travel(), 8 * H, 18 * H)
        legs = [self.OUT[acts[0]["poi_id"]], self.BACK[acts[-1]["poi_id"]]]
        self.assertGreaterEqual(f["ride"], sum(legs))

    def test_a_short_day_that_must_choose(self):
        self.check(self.travel(), 8 * H, 12 * H)

    def test_without_it(self):
        self.check(self.travel(back=False), 8 * H, 18 * H)


class TestTheRideBackIsACostNotAClock(unittest.TestCase):
    def test_the_day_may_end_at_end_time_and_ride_home_after_it(self):
        # One stop, 40 min from the hotel: 07:40-08:40 on a day to 08:40, home at 09:20.
        far = _poi("far", 1.0, opens=0, closes=24 * H)
        out = optimize([far], {("hotel", "far"): 40, ("far", "hotel"): 40},
                       StubTrip(7 * H, 8 * H + 40, "hotel"), workers=1, objective=_spec(),
                       min_stops=1)
        acts = out["itinerary"]["activities"]
        self.assertEqual([(a["poi_id"], a["end"]) for a in acts], [("far", "08:40")])

    def test_gate_b3_does_not_check_it(self):
        acts = [{"poi_id": "a", "start": "07:20", "end": "08:30"},
                {"poi_id": "b", "start": "08:45", "end": "09:30"}]
        no_way_back = cells({("h", "a"): 20, ("a", "b"): 10})
        self.assertTrue(gate.check_b3({"activities": acts},
                                      {"start_time": "07:00", "origin_id": "h"}, {},
                                      no_way_back)["passed"])


if __name__ == "__main__":
    unittest.main()
