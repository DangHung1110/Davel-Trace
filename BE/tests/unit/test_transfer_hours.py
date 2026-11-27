"""Boat and cable-car timetables for the places behind a gateway (transfers.py `service`).

A toy day, minutes door to door (road + board + ride for a leg into or out of a gateway):

    hotel -> town 10      hotel / town -> top1, top2 30      top1 <-> top2 5 (walk)
    hotel -> isle 60      town <-> isle 55

- top1, top2 sit behind `cable` (ride 5, board 3): cars go up 08:00-09:00 and come
  down 08:00-18:00, so a stop up there starts from 08:05, is reached from below by
  09:05 (the last car up + 5) and ends by 17:57 (the last car down - 3).
- isle sits behind `boat` (ride 20, board 10): out 07:30-09:00, back 13:00-14:30,
  only March to August.

Run from repo root: python -m pytest BE/tests/unit/test_transfer_hours.py -q
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import transfers  # noqa: E402
from BE.app.services.gate import b3_legs, check_b3  # noqa: E402
from BE.app.services.matrix import DenseCells  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, _hint_place, optimize  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.app.services.route_order import best_order, rides_in_time  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402
from BE.common import load_transfer_places, poi_on_date, to_min, view_pois  # noqa: E402

SPEC = {
    "format": transfers.FORMAT,
    "gateways": [
        {"id": "cable", "name": "Cáp treo", "mode": "cable_car", "road_end": {"poi_id": "base"},
         "ride_min": 5, "board_min": 3, "km": 2.0, "inside": "walk",
         "service": {"go": {"first": "08:00", "last": "09:00"},
                     "back": {"first": "08:00", "last": "18:00"}},
         "places": [{"poi_id": "top1"}, {"poi_id": "top2"}, {"poi_id": "top0"}]},
        {"id": "boat", "name": "Cano", "mode": "boat", "road_end": {"poi_id": "pier"},
         "ride_min": 20, "board_min": 10, "km": 9.0,
         "service": {"go": {"first": "07:30", "last": "09:00"},
                     "back": {"first": "13:00", "last": "14:30"},
                     "months": [3, 4, 5, 6, 7, 8]},
         "places": [{"poi_id": "isle"}]},
        {"id": "trail", "name": "Đường mòn", "mode": "walk", "road_end": {"own_row": True},
         "ride_min": 7, "board_min": 0, "km": 0.5, "places": [{"poi_id": "beach"}]},
    ],
}
PLACES = transfers.place_service(SPEC)
CABLE, BOAT = transfers.service(PLACES["top1"]), transfers.service(PLACES["isle"])

LEGS = {("hotel", "town"): 10, ("hotel", "top1"): 30, ("hotel", "top2"): 30,
        ("town", "top1"): 30, ("town", "top2"): 30, ("top1", "top2"): 5,
        ("hotel", "isle"): 60, ("town", "isle"): 55, ("top0", "top1"): 5, ("top0", "town"): 30}
TRAVEL = {**LEGS, **{(b, a): m for (a, b), m in LEGS.items()}}
MATRIX = {f"{a}->{b}": {"minutes": m, "km": 1.0} for (a, b), m in TRAVEL.items()}
MATRIX.update({f"{p}->{p}": {"minutes": 0, "km": 0.0} for p in ("hotel", "town", "top1", "top2", "isle")})


def at(hhmm: str) -> int:
    return to_min(hhmm)


def stub(pid: str, visit: int, window=("07:00", "20:00"), ride=None) -> StubPOI:
    return StubPOI(pid, visit, at(window[0]), at(window[1]), 1.0, category=pid, transfer=ride)


def one_place_cable(**change) -> dict:
    """The cable gateway with top1 only, for a three-row toy matrix."""
    return {**SPEC, "gateways": [{**SPEC["gateways"][0], "places": [{"poi_id": "top1"}], **change}]}


class TestTimetable(unittest.TestCase):
    def test_places_inherit_three_clock_times(self):
        top, isle = PLACES["top1"], PLACES["isle"]
        self.assertEqual((top["arrive_from"], top["arrive_by"], top["leave_by"]),
                         ("08:05", "09:05", "17:57"))
        self.assertEqual((isle["arrive_from"], isle["arrive_by"], isle["leave_by"]),
                         ("07:50", "09:20", "14:20"))
        self.assertEqual((isle["go"], isle["back"], isle["months"]),
                         ("07:30-09:00", "13:00-14:30", [3, 4, 5, 6, 7, 8]))
        self.assertIsNone(top["months"])
        self.assertNotIn("beach", PLACES)          # a walk runs whenever

    def test_a_timetable_that_cannot_be_read_gives_none(self):
        for service in ({"go": {"first": "09:00", "last": "08:00"}, "back": {"first": "08:00", "last": "18:00"}},
                        {"go": {"first": "08:00", "last": "25:00"}, "back": {"first": "08:00", "last": "18:00"}},
                        {"go": {"first": "08:00", "last": "09:00"}},
                        {"go": {"first": "08:00", "last": "09:00"}, "back": {"first": "08:00", "last": "18:00"},
                         "months": [13]},
                        {"go": {"first": "08:00", "last": "09:00"}, "back": {"first": "06:00", "last": "07:00"}}):
            spec = {**SPEC, "gateways": [{**SPEC["gateways"][0], "service": service}]}
            self.assertEqual(transfers.place_service(spec), {}, service)

    def test_cells_name_the_departures_of_the_leg_direction(self):
        ids = ["town", "base", "top1"]
        pos = {"town": 0, "base": 10, "top1": 40}
        minutes = [[abs(pos[a] - pos[b]) for b in ids] for a in ids]
        km = [[m / 2 for m in row] for row in minutes]
        via, summary = transfers.apply_dense(ids, minutes, km, one_place_cable())
        self.assertEqual(summary["skipped"], [])
        cells = DenseCells(ids, minutes, km, via)
        up, down = cells["town->top1"]["transfers"][0], cells["top1->town"]["transfers"][0]
        self.assertEqual((up["runs"], down["runs"]), ("08:00-09:00", "08:00-18:00"))
        self.assertEqual(cells["town->top1"]["minutes"], 10 + 8)

    def test_a_bad_timetable_keeps_the_minutes(self):
        spec = one_place_cable(service={"go": "08:00"})
        ids = ["town", "base", "top1"]
        minutes = [[0, 10, 40], [10, 0, 30], [40, 30, 0]]
        km = [[m / 2 for m in row] for row in minutes]
        via, summary = transfers.apply_dense(ids, minutes, km, spec)
        self.assertEqual(summary["skipped"], [])
        cell = DenseCells(ids, minutes, km, via)["town->top1"]
        self.assertEqual(cell["minutes"], 18)
        self.assertNotIn("runs", cell["transfers"][0])


class TestLegMath(unittest.TestCase):
    def test_the_leg_up_must_leave_in_time_for_the_last_car(self):
        # 30 min door to door, the last 5 on the car: board by 09:00 = leave by 08:35.
        self.assertEqual(transfers.leg_bounds(30, None, CABLE), (at("08:35"), at("08:05"), True))
        self.assertEqual(transfers.leg_arrival(at("08:35"), 30, None, CABLE), at("09:05"))
        self.assertIsNone(transfers.leg_arrival(at("08:36"), 30, None, CABLE))
        self.assertEqual(transfers.leg_arrival(at("07:00"), 30, None, CABLE), at("08:05"))  # waits

    def test_the_leg_back_waits_for_the_first_boat_and_misses_after_the_last(self):
        self.assertEqual(transfers.leg_arrival(at("14:20"), 55, BOAT, None), at("15:15"))
        self.assertIsNone(transfers.leg_arrival(at("14:21"), 55, BOAT, None))
        self.assertEqual(transfers.leg_arrival(at("11:00"), 55, BOAT, None), at("13:45"))

    def test_island_to_summit_rides_both(self):
        # Leave the island, boat back 13:00 at the earliest, then up by car before 09:00: never.
        latest, earliest, possible = transfers.leg_bounds(120, BOAT, CABLE)
        self.assertFalse(possible)
        self.assertIsNone(transfers.leg_arrival(at("08:00"), 120, BOAT, CABLE))

    def test_inside_one_gateway_is_a_walk(self):
        self.assertEqual(transfers.crossing(CABLE, CABLE), (None, None))
        self.assertEqual(transfers.leg_arrival(at("17:00"), 5, *transfers.crossing(CABLE, CABLE)), at("17:05"))
        self.assertEqual(transfers.open_start(CABLE), (at("08:05"), at("09:05")))


class TestSolver(unittest.TestCase):
    def solve(self, stubs, trip, must, **kw):
        out = optimize(stubs, TRAVEL, trip, must_visit=must, workers=1, timeout_s=10.0, **kw)
        return [(a["poi_id"], a["start"], a["end"]) for a in (out.get("itinerary") or {}).get("activities", [])]

    def test_the_summit_goes_first_when_the_last_car_would_be_missed(self):
        trip = StubTrip(at("08:00"), at("12:00"), "hotel")
        bonus = {("town", "top1"): 5.0}          # the solver would rather go town -> top1
        plain = self.solve([stub("town", 60), stub("top1", 30)], trip, ["town", "top1"], edge_scores=bonus)
        self.assertEqual([p for p, _s, _e in plain], ["town", "top1"])
        timed = self.solve([stub("town", 60), stub("top1", 30, ride=CABLE)], trip, ["town", "top1"],
                           edge_scores=bonus)
        self.assertEqual([p for p, _s, _e in timed], ["top1", "town"])
        self.assertLessEqual(at(timed[0][1]), at("09:05"))

    def test_a_walk_from_another_summit_stop_may_start_after_the_last_car(self):
        trip = StubTrip(at("08:00"), at("13:00"), "hotel")
        got = self.solve([stub("top1", 120, ride=CABLE), stub("top2", 30, ride=CABLE)], trip,
                         ["top1", "top2"], precedence=[("top1", "top2")])
        self.assertEqual([p for p, _s, _e in got], ["top1", "top2"])
        self.assertGreater(at(got[1][1]), at("09:05"))

    def test_an_open_tour_cannot_begin_up_there_after_the_last_car(self):
        late = StubTrip(at("09:30"), at("12:00"), None)
        self.assertEqual(self.solve([stub("top1", 30, ride=CABLE)], late, ["top1"]), [])
        early = StubTrip(at("08:00"), at("12:00"), None)
        got = self.solve([stub("top1", 30, ride=CABLE)], early, ["top1"])
        self.assertTrue(at("08:05") <= at(got[0][1]) <= at("09:05"))

    def test_the_island_is_left_in_time_for_the_last_boat(self):
        # Hours all day long (no access_window): the timetable alone must bound the visit.
        trip = StubTrip(at("07:00"), at("18:00"), "hotel")
        got = self.solve([stub("isle", 380, ("00:00", "23:59"), BOAT)], trip, ["isle"])
        self.assertEqual(got, [("isle", "08:00", "14:20")])
        self.assertEqual(self.solve([stub("isle", 400, ("00:00", "23:59"), BOAT)], trip, ["isle"]), [])
        both = self.solve([stub("isle", 300, ("00:00", "23:59"), BOAT), stub("town", 60)], trip,
                          ["isle", "town"], precedence=[("isle", "town")])
        isle_end, town_start = at(both[0][2]), at(both[1][1])
        self.assertLessEqual(isle_end, at("14:20"))
        self.assertGreaterEqual(town_start, at("13:45"))      # the first boat back is 13:00

    def test_a_base_up_there_walks_to_its_stops(self):
        trip = StubTrip(at("10:00"), at("12:00"), "top0", origin_transfer=CABLE)
        got = self.solve([stub("top1", 30, ride=CABLE), stub("town", 60)], trip, ["top1"])
        self.assertIn(("top1", "10:05", "10:35"), got)

    def test_the_seed_does_not_place_a_stop_behind_a_missed_car(self):
        trip = StubTrip(at("08:00"), at("12:00"), "hotel")
        top1 = stub("top1", 30, ride=CABLE)
        self.assertIsNone(_hint_place(top1, "town", at("09:22"), trip, TRAVEL, set()))
        self.assertEqual(_hint_place(top1, "top2", at("10:00"), trip, TRAVEL, set(),
                                     prev_transfer=CABLE)[0], at("10:05"))
        self.assertEqual(_hint_place(top1, None, at("08:00"), trip, TRAVEL, set())[0], at("08:30"))


class TestGateB3(unittest.TestCase):
    POIS = {"hotel": {}, "town": {"verified": True},
            "top1": {"verified": True, "transfer": PLACES["top1"]},
            "top2": {"verified": True, "transfer": PLACES["top2"]},
            "isle": {"verified": True, "transfer": PLACES["isle"]}}

    def plan(self, *acts):
        return {"activities": [{"poi_id": p, "start": s, "end": e} for p, s, e in acts]}

    def test_a_leg_up_after_the_last_car_fails_b3(self):
        trip = {"origin_id": "hotel", "start_time": "08:00", "end_time": "12:00"}
        late = self.plan(("town", "08:10", "09:10"), ("top1", "09:52", "10:22"))
        self.assertFalse(check_b3(late, trip, self.POIS, MATRIX)["passed"])
        report = validate(late, trip, self.POIS, MATRIX)
        self.assertEqual(report["details"]["B3"], ["town->top1"])
        early = self.plan(("top1", "08:30", "09:00"), ("town", "09:42", "10:42"))
        self.assertTrue(check_b3(early, trip, self.POIS, MATRIX)["passed"])

    def test_a_walk_up_there_after_the_last_car_passes(self):
        trip = {"origin_id": "hotel", "start_time": "08:00", "end_time": "12:00"}
        day = self.plan(("top1", "08:30", "10:30"), ("top2", "10:47", "11:17"))
        self.assertTrue(check_b3(day, trip, self.POIS, MATRIX)["passed"])

    def test_an_open_tour_begins_where_a_car_arrives(self):
        trip = {"start_time": "08:00", "end_time": "12:00"}
        for start, ok in (("08:10", True), ("09:05", True), ("09:30", False), ("08:00", False)):
            day = self.plan(("top1", start, f"{at(start) // 60 + 1:02d}:{at(start) % 60:02d}"))
            self.assertEqual(check_b3(day, trip, self.POIS, MATRIX)["passed"], ok, start)
        self.assertEqual(b3_legs(self.plan(("top1", "09:30", "10:00")), trip, self.POIS, MATRIX),
                         [("->top1", False)])

    def test_the_first_boat_back_is_waited_for(self):
        trip = {"start_time": "07:00", "end_time": "18:00"}
        day = self.plan(("isle", "08:00", "11:00"), ("town", "12:00", "13:00"))   # 60 min > 55, but no boat
        self.assertFalse(check_b3(day, trip, self.POIS, MATRIX)["passed"])
        day = self.plan(("isle", "08:00", "11:00"), ("town", "13:45", "14:45"))
        self.assertTrue(check_b3(day, trip, self.POIS, MATRIX)["passed"])


class TestBestOrder(unittest.TestCase):
    def test_the_order_search_does_not_drive_past_the_last_car(self):
        stubs = {"town": stub("town", 60), "top1": stub("top1", 30, ride=CABLE)}
        acts = [{"poi_id": "top1", "start": "08:30", "end": "09:00"},
                {"poi_id": "town", "start": "09:42", "end": "10:42"}]
        plain = {"town": stub("town", 60), "top1": stub("top1", 30)}
        shorter = best_order(acts, plain, TRAVEL, at("08:00"), at("12:00"), 12, origin="hotel")
        self.assertEqual(shorter[0]["poi_id"], "town")      # 40 min of driving instead of 60
        rows = best_order(acts, stubs, TRAVEL, at("08:00"), at("12:00"), 12, origin="hotel")
        self.assertEqual([r["poi_id"] for r in rows], ["top1", "town"])
        self.assertTrue(rides_in_time(rows, stubs, TRAVEL, at("08:00"), "hotel"))
        self.assertFalse(rides_in_time(shorter, stubs, TRAVEL, at("08:00"), "hotel"))


def legacy(pid, visit, hours, rating=4.0, transfer=None, cat="attraction"):
    poi = {"poi_id": pid, "name": pid, "verified": True, "visit_min": visit, "rating": rating,
           "fee": 0, "intensity": 1, "opening_hours": [hours], "cat": cat}
    if transfer:
        poi["transfer"] = transfer
    return poi


class TestPlanner(unittest.TestCase):
    """build_plan: the season of the boats and the named places no run can reach."""

    BY_ID = {"hotel": {"poi_id": "hotel", "name": "Khach san"},
             "town": legacy("town", 60, "07:00-20:00", 3.5),
             "top1": legacy("top1", 30, "08:05-17:57", 4.8, PLACES["top1"], cat="viewpoint"),
             "isle": legacy("isle", {"p25": 300, "p50": 330, "p75": 360}, "07:50-14:20", 5.0,
                            PLACES["isle"])}
    TRIP = {"trip_id": "t", "budget": 1_000_000, "start_time": "07:00", "end_time": "18:00"}

    def plan(self, ranked, **trip):
        return build_plan("balanced", {**self.TRIP, **trip}, [{"poi_id": p} for p in ranked],
                          self.BY_ID, MATRIX)

    def ids(self, plan):
        return [a["poi_id"] for a in plan["activities"]]

    def test_out_of_season_the_island_is_not_picked_on_its_own(self):
        december = self.plan(["isle"], date="2026-12-09")
        self.assertEqual(self.ids(december), [])
        may = self.plan(["isle"], date="2027-05-12")
        self.assertEqual(self.ids(may), ["isle"])
        self.assertFalse(any("thang 3-8" in w for w in may.get("warnings") or []))

    def test_a_named_island_out_of_season_stays_with_a_warning(self):
        plan = self.plan(["isle"], date="2026-12-09", must_visit=["isle"])
        self.assertEqual(self.ids(plan), ["isle"])
        self.assertTrue(any("thang 3-8" in w and "2026-12-09" in w for w in plan["warnings"]))

    def test_without_a_date_the_plan_says_the_boats_run_by_season(self):
        plan = self.plan(["isle"], must_visit=["isle"])
        self.assertTrue(any("thang 3-8" in w and "chon ngay di" in w for w in plan["warnings"]))

    def test_a_named_summit_stop_after_the_last_car_leaves_with_the_reason(self):
        plan = self.plan(["town", "top1"], must_visit=["top1"], origin_id="hotel", start_time="08:40")
        self.assertNotIn("top1", self.ids(plan))
        self.assertTrue(any("lo chuyen cap treo cuoi (09:00)" in w for w in plan["warnings"]))
        self.assertTrue(plan["passed"])
        self.assertEqual(plan["_dropped_must"], ["top1"])     # a longer trip is judged without it
        open_tour = self.plan(["town", "top1"], must_visit=["top1"], start_time="09:30")
        self.assertTrue(any("sau chuyen cap treo cuoi (09:00)" in w for w in open_tour["warnings"]))
        in_time = self.plan(["town", "top1"], must_visit=["top1"], origin_id="hotel", start_time="08:00")
        self.assertIn("top1", self.ids(in_time))
        top1 = next(a for a in in_time["activities"] if a["poi_id"] == "top1")
        self.assertLessEqual(at(top1["start"]), at("09:05"))

    def test_a_named_island_whose_stay_cannot_fit_the_boats_leaves_with_the_reason(self):
        by_id = dict(self.BY_ID, isle={**self.BY_ID["isle"],
                                       "visit_min": {"p25": 400, "p50": 420, "p75": 480}})
        plan = build_plan("balanced", {**self.TRIP, "must_visit": ["isle"]},
                          [{"poi_id": "isle"}, {"poi_id": "town"}], by_id, MATRIX)
        self.assertNotIn("isle", self.ids(plan))
        self.assertTrue(any("chi o duoc 390 phut (it nhat 400)" in w for w in plan["warnings"]))


def v21(pid, name="X"):
    return {"poi_id": pid, "name": name, "data_version": "v2.1", "category": "viewpoint",
            "role": "attraction", "status": "active",
            "hours": {"open": ["08:20-18:30"], "kind": "fixed", "closed_days": [],
                      "access_window": None, "archetype": "ngoai_troi_tu_nhien"},
            "price": {"tier": "free"}, "dwell": {"p25": 15, "p50": 30, "p75": 50},
            "tags": {}, "popularity": {}, "provenance": {}}


class TestPoiView(unittest.TestCase):
    def test_views_carry_the_timetable_and_the_season(self):
        with tempfile.TemporaryDirectory() as snap:
            with open(os.path.join(snap, transfers.TRANSFERS_FILE), "w", encoding="utf-8") as f:
                json.dump(SPEC, f)
            self.assertEqual(sorted(load_transfer_places(snap)), ["isle", "top0", "top1", "top2"])
            views = {v["poi_id"]: v for v in view_pois([v21("top1"), v21("isle"), v21("town")], snap)}
        self.assertEqual(views["top1"]["transfer"]["arrive_by"], "09:05")
        self.assertNotIn("transfer", views["town"])
        self.assertTrue(poi_on_date(views["isle"], "2026-12-09").get("off_season"))
        self.assertIsNone(poi_on_date(views["isle"], "2027-05-12").get("off_season"))
        self.assertIsNone(poi_on_date(views["isle"], None).get("off_season"))
        self.assertIsNone(poi_on_date(views["top1"], "2026-12-09").get("off_season"))

    def test_a_malformed_file_never_breaks_loading(self):
        with tempfile.TemporaryDirectory() as snap:
            with open(os.path.join(snap, transfers.TRANSFERS_FILE), "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertEqual(load_transfer_places(snap), {})
            self.assertEqual(load_transfer_places(os.path.join(snap, "missing")), {})

    def test_season_label(self):
        self.assertEqual(transfers.season_label([3, 4, 5, 6, 7, 8]), "thang 3-8")
        self.assertEqual(transfers.season_label([12, 1]), "thang 1, 12")


class TestMigrate(unittest.TestCase):
    def test_migrate_bounds_the_hours_of_the_places_behind(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ml", "data"))
        from BE.ml.data import migrate_v2
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(migrate_v2.transfer_access(out), {})
            with open(os.path.join(out, transfers.TRANSFERS_FILE), "w", encoding="utf-8") as f:
                json.dump(SPEC, f)
            access = migrate_v2.transfer_access(out)
        self.assertEqual(access["isle"], [(at("07:50"), at("14:20"))])
        self.assertEqual(access["top1"], [(at("08:05"), at("17:57"))])
        self.assertNotIn("beach", access)


if __name__ == "__main__":
    unittest.main()
