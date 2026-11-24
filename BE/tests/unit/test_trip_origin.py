"""A day can start at the traveller's base (a lodging) or where a replan resumes.

Before, every plan was an open tour: `profiles._to_trip` always passed no origin, so
the first stop started at the trip's start time wherever it was, the hotel leg was
neither driven, counted nor checked, and the order search and gate knew nothing of
it. Now `trip["origin_id"]` (a place with a matrix row, resolved by the router)
reaches the solver, the order search, gate B3 and the plan's segments.

Run: python -m pytest BE/tests/unit/test_trip_origin.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import ValidationError  # noqa: E402

from BE.app.routers.itinerary import _origin_id  # noqa: E402
from BE.app.schemas.trip import Origin, TripRequest  # noqa: E402
from BE.app.services import gate, matrix, route_order  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.app.services.response import plan_totals  # noqa: E402

H = 60


def mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def cells(minutes: dict) -> dict:
    return {f"{a}->{b}": {"minutes": m, "km": m / 3} for (a, b), m in minutes.items()}


class TestOriginSchema(unittest.TestCase):
    def test_a_place_alone_is_an_origin(self):
        self.assertEqual(Origin(poi_id="hotel").poi_id, "hotel")

    def test_a_position_alone_is_still_accepted(self):
        self.assertEqual(Origin(lat=16.06, lon=108.24).lat, 16.06)

    def test_an_origin_needs_a_place_or_a_full_position(self):
        with self.assertRaises(ValidationError):
            Origin(label="khach san")
        with self.assertRaises(ValidationError):
            Origin(lat=16.06)

    def test_a_trip_without_origin_is_unchanged(self):
        self.assertIsNone(TripRequest().origin)


class TestMatrixRows(unittest.TestCase):
    LEGS = {("h", "a"): 5, ("h", "b"): 40, ("a", "b"): 10}

    def test_dict_cells(self):
        c = cells(self.LEGS)
        self.assertTrue(matrix.has_row(c, "h"))
        self.assertFalse(matrix.has_row(c, "b"))
        self.assertEqual(matrix.legs_from(c, "h", ["a", "b", "h", "zz"]),
                         {("h", "a"): 5, ("h", "b"): 40})

    def test_dense_cells(self):
        dense = matrix.DenseCells(["h", "a", "b"],
                                  [[0, 5, 40], [5, 0, 10], [40, None, 0]],
                                  [[0, 1, 9], [1, 0, 3], [9, None, 0]])
        self.assertTrue(matrix.has_row(dense, "b"))
        self.assertFalse(matrix.has_row(dense, "zz"))
        self.assertEqual(matrix.legs_from(dense, "b", ["h", "a"]), {("b", "h"): 40})


class TestRouterResolvesTheOrigin(unittest.TestCase):
    BY_ID = {"h": {"name": "Khach san"}, "x": {"name": "Cho"}}
    CELLS = cells({("h", "x"): 7})

    def test_no_origin(self):
        self.assertEqual(_origin_id(None, self.BY_ID, self.CELLS), (None, None))

    def test_a_routable_place(self):
        self.assertEqual(_origin_id({"poi_id": "h"}, self.BY_ID, self.CELLS), ("h", None))

    def test_an_unknown_place_warns(self):
        pid, why = _origin_id({"poi_id": "zz"}, self.BY_ID, self.CELLS)
        self.assertIsNone(pid)
        self.assertIn("khong co trong du lieu", why)

    def test_a_place_without_a_matrix_row_warns(self):
        pid, why = _origin_id({"poi_id": "x"}, self.BY_ID, self.CELLS)
        self.assertIsNone(pid)
        self.assertIn("chua co ma tran", why)

    def test_a_bare_position_keeps_the_open_tour(self):
        self.assertEqual(_origin_id({"lat": 16.0, "lon": 108.2}, self.BY_ID, self.CELLS),
                         (None, None))


class TestOrderSearchStartsAtTheBase(unittest.TestCase):
    MUSEUM = StubPOI("museum", visit_min=60, open_min=8 * H, close_min=17 * H, category="museum")
    BRIDGE = StubPOI("bridge", visit_min=20, open_min=0, close_min=24 * H, category="landmark")
    STUBS = {"museum": MUSEUM, "bridge": BRIDGE}
    ACTS = [{"poi_id": "museum", "start": "08:00", "end": "09:00"},
            {"poi_id": "bridge", "start": "09:10", "end": "09:30"}]

    def travel(self, **origin_legs):
        legs = {("museum", "bridge"): 10, ("bridge", "museum"): 10}
        legs.update({("hotel", pid): m for pid, m in origin_legs.items()})
        return legs

    def test_the_stop_next_to_the_base_opens_the_day(self):
        rows = route_order.best_order(self.ACTS, self.STUBS, self.travel(museum=40, bridge=5),
                                      8 * H, 20 * H, 0, origin="hotel")
        self.assertEqual(rows[0]["poi_id"], "bridge")
        self.assertGreaterEqual(mins(rows[0]["start"]), 8 * H + 5)

    def test_the_first_stop_waits_for_the_drive(self):
        rows = route_order.best_order(self.ACTS, self.STUBS, self.travel(museum=5, bridge=50),
                                      8 * H, 20 * H, 0, origin="hotel")
        self.assertEqual(rows[0]["poi_id"], "museum")
        self.assertGreaterEqual(mins(rows[0]["start"]), 8 * H + 5)

    def test_a_stop_the_base_cannot_reach_never_opens_the_day(self):
        rows = route_order.best_order(self.ACTS, self.STUBS, self.travel(bridge=60),
                                      8 * H, 20 * H, 0, origin="hotel")
        self.assertEqual(rows[0]["poi_id"], "bridge")

    def test_the_drive_from_the_base_is_not_dead_time(self):
        rows = [{"poi_id": "museum", "start": "09:00", "end": "10:00"}]
        late = route_order.timing_cost(rows, [], 8 * H, {"museum": None}, None)
        driven = route_order.timing_cost(rows, [], 8 * H, {"museum": None}, None, first_leg=45)
        self.assertGreater(late, driven)


class TestGateChecksTheFirstDrive(unittest.TestCase):
    MATRIX = cells({("h", "a"): 20, ("a", "b"): 10})

    def b3(self, start, **trip):
        acts = [{"poi_id": "a", "start": start, "end": "08:30"},
                {"poi_id": "b", "start": "08:45", "end": "09:30"}]
        return gate.check_b3({"activities": acts}, {"start_time": "07:00", **trip}, {},
                             self.MATRIX)["passed"]

    def test_a_first_stop_before_the_drive_ends_fails(self):
        self.assertFalse(self.b3("07:05", origin_id="h"))

    def test_a_first_stop_after_the_drive_passes(self):
        self.assertTrue(self.b3("07:20", origin_id="h"))

    def test_an_open_tour_is_unchanged(self):
        self.assertTrue(self.b3("07:05"))

    def test_a_base_the_matrix_cannot_route_fails(self):
        self.assertFalse(self.b3("07:20", origin_id="nowhere"))


class TestSegmentsStartAtTheBase(unittest.TestCase):
    MATRIX = cells({("h", "a"): 20, ("a", "b"): 10, ("b", "c"): 30, ("h", "c"): 8})
    POIS = {"a": {}, "b": {}, "c": {}}

    def segments(self, acts, **trip):
        out = plan_totals(acts, {"travelers": 1, **trip}, self.POIS, self.MATRIX)
        return [(s["from_id"], s["to_id"]) for s in out["segments"]], out["travel_min"]

    def test_one_day(self):
        acts = [{"poi_id": "a", "start": "07:20", "end": "08:00"},
                {"poi_id": "b", "start": "08:10", "end": "09:00"}]
        self.assertEqual(self.segments(acts, origin_id="h"), ([("h", "a"), ("a", "b")], 30))
        self.assertEqual(self.segments(acts), ([("a", "b")], 10))

    def test_each_day_starts_at_the_base(self):
        acts = [{"poi_id": "a", "start": "07:20", "end": "08:00", "day": 1},
                {"poi_id": "b", "start": "08:10", "end": "09:00", "day": 1},
                {"poi_id": "c", "start": "07:10", "end": "08:00", "day": 2}]
        self.assertEqual(self.segments(acts, origin_id="h")[0], [("h", "a"), ("a", "b"), ("h", "c")])
        self.assertEqual(self.segments(acts)[0], [("a", "b"), ("b", "c")])


class TestSolverChargesTheFirstDrive(unittest.TestCase):
    NEAR = StubPOI("near", visit_min=60, score=1.0)
    FAR = StubPOI("far", visit_min=60, score=1.05)
    TRAVEL = {("hotel", "near"): 5, ("hotel", "far"): 50, ("near", "far"): 30, ("far", "near"): 30}

    def first(self, edges=None, origin="hotel"):
        out = optimize([self.NEAR, self.FAR], self.TRAVEL, StubTrip(7 * H, 9 * H, origin),
                       edge_scores=edges, workers=1)
        return out["itinerary"]["activities"][0]

    def test_the_first_stop_starts_after_the_drive(self):
        act = self.first()
        leg = self.TRAVEL[("hotel", act["poi_id"])]
        self.assertGreaterEqual(mins(act["start"]), 7 * H + leg)

    def test_a_score_on_the_base_prices_the_first_drive(self):
        # Only one stop fits. FAR is worth a little more, but 50 minutes away.
        edges = {("hotel", "near"): -5 * 0.3, ("hotel", "far"): -50 * 0.3}
        self.assertEqual(self.first(edges)["poi_id"], "near")
        self.assertEqual(self.first()["poi_id"], "far")


BASE_POIS = [
    {"poi_id": "hill", "verified": True, "visit_min": 120, "rating": 4.7, "fee": 0,
     "intensity": 3, "opening_hours": ["05:00-18:00"]},
    {"poi_id": "beach", "verified": True, "visit_min": 120, "rating": 4.6, "fee": 0,
     "intensity": 2, "opening_hours": ["00:00-23:59"]},
    {"poi_id": "noodle", "verified": True, "visit_min": 60, "rating": 4.5, "fee": 50000,
     "intensity": 1, "opening_hours": ["07:00-21:00"]},
]
BASE_IDS = [p["poi_id"] for p in BASE_POIS]
BASE_LEGS = {**{(a, b): 15 for a in BASE_IDS for b in BASE_IDS if a != b},
             ("hotel", "hill"): 40, ("hotel", "beach"): 5, ("hotel", "noodle"): 25}


class TestBuildPlanFromTheBase(unittest.TestCase):
    TRIP = {"trip_id": "t1", "budget": 1000000, "start_time": "07:00", "end_time": "16:00"}

    def plan(self, **trip):
        by_id = {p["poi_id"]: p for p in BASE_POIS}
        by_id["hotel"] = {"poi_id": "hotel", "verified": True, "role": "base"}
        ranked = [{"poi_id": pid} for pid in BASE_IDS]
        return build_plan("balanced", {**self.TRIP, **trip}, ranked, by_id, cells(BASE_LEGS))

    def test_the_day_opens_after_the_drive_from_the_base(self):
        plan = self.plan(origin_id="hotel")
        first = plan["activities"][0]
        self.assertTrue(plan["passed"])
        self.assertEqual(plan["segments"][0]["from_id"], "hotel")
        self.assertEqual(plan["segments"][0]["to_id"], first["poi_id"])
        self.assertGreaterEqual(mins(first["start"]), 7 * H + BASE_LEGS[("hotel", first["poi_id"])])

    def test_the_plan_counts_the_drive_from_the_base(self):
        with_base = self.plan(origin_id="hotel")
        open_tour = self.plan()
        self.assertNotEqual(open_tour["segments"][0]["from_id"], "hotel")
        first_leg = with_base["segments"][0]["minutes"]
        self.assertEqual(with_base["travel_min"],
                         first_leg + sum(s["minutes"] for s in with_base["segments"][1:]))


if __name__ == "__main__":
    unittest.main()
