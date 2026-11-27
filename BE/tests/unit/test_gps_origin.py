"""A GPS fix as the place a day starts from (services/gps_origin.py, design A).

Before, a bare `origin = {lat, lon}` was ignored and the day became an open tour; the
app's replan started from the last finished stop whatever the device said. Now a fix
borrows the matrix rows of the places nearest to it (its anchors) plus the short ride
to them: the solver, the order search, gate B3 and the segments read that row through
`matrix.with_starts`. A fix too far from every place (or too vague) is not used: the
day starts at `fallback_poi_id` or stays an open tour, with a warning.

Run: python -m pytest BE/tests/unit/test_gps_origin.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from pydantic import ValidationError  # noqa: E402

from BE.app.routers.itinerary import _gps_report, _origin_id  # noqa: E402
from BE.app.schemas.trip import Origin, TripRequest  # noqa: E402
from BE.app.services import gate, gps_origin, matrix  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402

H = 60
# Real Da Nang coordinates: a hotel near My Khe, a cafe 600 m north of it, a market
# 3.3 km west. "norow" is a place 400 m south of the hotel that has no matrix row.
HOTEL = (16.06900, 108.24500)
CAFE = (16.07440, 108.24500)
MARKET = (16.06800, 108.21400)


def mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def north_of(point, metres):
    """A point `metres` due north of `point` (a fix near a place)."""
    return point[0] + metres / 111_195.0, point[1]


def cells(minutes: dict) -> dict:
    return {f"{a}->{b}": {"minutes": m, "km": m / 3} for (a, b), m in minutes.items()}


NOROW = north_of(HOTEL, -400)
BY_ID = {
    "hotel": {"poi_id": "hotel", "name": "Khach san", "lat": HOTEL[0], "lon": HOTEL[1]},
    "cafe": {"poi_id": "cafe", "name": "Ca phe", "lat": CAFE[0], "lon": CAFE[1]},
    "market": {"poi_id": "market", "name": "Cho", "lat": MARKET[0], "lon": MARKET[1]},
    "norow": {"poi_id": "norow", "name": "Chua co hang", "lat": NOROW[0], "lon": NOROW[1]},
}
LEGS = {("hotel", "cafe"): 3, ("hotel", "market"): 12, ("cafe", "hotel"): 3,
        ("cafe", "market"): 13, ("market", "hotel"): 12, ("market", "cafe"): 13}
DENSE = matrix.DenseCells(["hotel", "cafe", "market"],
                          [[0, 3, 12], [3, 0, 13], [12, None, 0]],
                          [[0, 1.0, 4.0], [1.0, 0, 4.2], [4.0, None, 0]])


class TestLocate(unittest.TestCase):
    def locate(self, point, **kw):
        return gps_origin.locate(point[0], point[1], BY_ID, DENSE, **kw)

    def test_a_fix_at_the_hotel_is_at_the_hotel(self):
        start, why = self.locate(north_of(HOTEL, 10))
        self.assertIsNone(why)
        self.assertEqual([a.poi_id for a in start.anchors], ["hotel"])
        self.assertLess(start.nearest.access_min, 0.1)
        self.assertFalse(start.far)
        self.assertTrue(gps_origin.is_start(start.start_id))

    def test_away_from_every_place_the_nearest_ones_are_tried(self):
        start, _ = self.locate(north_of(MARKET, 600))
        self.assertEqual([a.poi_id for a in start.anchors], ["market", "cafe", "hotel"])
        self.assertEqual(len(start.anchors), gps_origin.ANCHORS)

    def test_the_ride_is_road_km_at_motorbike_speed(self):
        start, _ = self.locate(north_of(MARKET, 600))
        nearest = start.nearest
        self.assertAlmostEqual(nearest.km, 0.6, places=2)
        self.assertAlmostEqual(nearest.access_km, 0.6 * gps_origin.ROAD_FACTOR, places=2)
        self.assertAlmostEqual(nearest.access_min,
                               0.6 * gps_origin.ROAD_FACTOR / gps_origin.SPEED_KMH * 60, places=2)

    def test_only_a_place_with_a_matrix_row_anchors(self):
        start, _ = self.locate(north_of(NOROW, 5))  # 5 m from "norow", 395 m from the hotel
        self.assertEqual(start.nearest.poi_id, "hotel")
        self.assertNotIn("norow", [a.poi_id for a in start.anchors])

    def test_far_from_every_place_warns(self):
        start, why = self.locate(north_of(MARKET, 1500))
        self.assertIsNone(why)
        self.assertTrue(start.far)
        self.assertIn("1.5 km", gps_origin.far_warning(start, BY_ID))

    def test_too_far_is_not_used(self):
        start, why = self.locate(north_of(MARKET, 4000))
        self.assertIsNone(start)
        self.assertIn("toi da 3 km", why)

    def test_outside_da_nang_says_so(self):
        start, why = self.locate((21.0285, 105.8542))  # Ha Noi
        self.assertIsNone(start)
        self.assertIn("ngoai vung Da Nang", why)

    def test_a_vague_fix_is_not_used(self):
        start, why = self.locate(north_of(HOTEL, 10), accuracy_m=1500)
        self.assertIsNone(start)
        self.assertIn("sai so 1500 m", why)
        self.assertIsNotNone(self.locate(north_of(HOTEL, 10), accuracy_m=40)[0])

    def test_no_place_with_coordinates_and_a_row(self):
        start, why = gps_origin.locate(*HOTEL, {}, DENSE)
        self.assertIsNone(start)
        self.assertIn("chua co dia diem", why)

    def test_the_same_fix_is_the_same_start(self):
        a, _ = self.locate(north_of(HOTEL, 10))
        b, _ = self.locate(north_of(HOTEL, 10))
        self.assertEqual(a.start_id, b.start_id)
        self.assertNotEqual(a.start_id, self.locate(north_of(HOTEL, 30))[0].start_id)

    def test_dict_cells_work_too(self):
        start, _ = gps_origin.locate(*north_of(CAFE, 20), BY_ID, cells(LEGS))
        self.assertEqual(start.nearest.poi_id, "cafe")


class TestStartCells(unittest.TestCase):
    START = "@gps:16.07000,108.24500"

    def view(self, *anchors, base=DENSE):
        return matrix.with_starts(base, {self.START: anchors or (("hotel", 1.4, 0.7),)})

    def test_a_leg_is_the_ride_plus_the_anchor_leg(self):
        cell = self.view().get(f"{self.START}->market")
        self.assertEqual(cell["minutes"], 13)  # round(1.4 + 12)
        self.assertAlmostEqual(cell["km"], 4.7)
        self.assertEqual(cell["source"], matrix.GPS_ESTIMATE)

    def test_the_anchor_itself_is_the_ride(self):
        self.assertEqual(self.view().get(f"{self.START}->hotel")["minutes"], 1)
        at_hotel = self.view(("hotel", 0.02, 0.01))
        self.assertEqual(at_hotel.get(f"{self.START}->hotel")["minutes"], 1)
        self.assertEqual(at_hotel.get(f"{self.START}->market")["minutes"], 12)

    def test_the_best_way_through_an_anchor_wins(self):
        view = self.view(("cafe", 1.0, 0.5), ("hotel", 1.2, 0.6))
        market = view.get(f"{self.START}->market")
        self.assertEqual((market["minutes"], market["km"]), (13, 4.6))  # 1.2 + 12 < 1.0 + 13
        self.assertEqual(self.view(("cafe", 1.0, 0.5)).get(f"{self.START}->market")["minutes"], 14)
        self.assertEqual(view.get(f"{self.START}->hotel")["minutes"], 1)  # its own ride, 1.2
        self.assertEqual(view.get(f"{self.START}->cafe")["minutes"], 1)

    def test_what_no_anchor_reaches_stays_absent(self):
        view = self.view(("market", 1.0, 0.5))
        self.assertIsNone(view.get(f"{self.START}->cafe"))
        self.assertNotIn(f"{self.START}->cafe", view)
        self.assertEqual(self.view(("market", 1.0, 0.5), ("hotel", 3.0, 1.5))
                         .get(f"{self.START}->cafe")["minutes"], 6)

    def test_nothing_leads_to_a_start(self):
        self.assertIsNone(self.view().get(f"hotel->{self.START}"))

    def test_the_places_are_unchanged(self):
        view = self.view()
        self.assertEqual(view.get("hotel->market"), DENSE.get("hotel->market"))
        self.assertEqual(view["cafe->market"]["minutes"], 13)
        self.assertNotIn("source", view.get("hotel->market"))

    def test_the_start_owns_a_row(self):
        view = self.view()
        self.assertTrue(matrix.has_row(view, self.START))
        self.assertTrue(matrix.has_row(view, "hotel"))
        self.assertFalse(matrix.has_row(view, "zz"))
        self.assertIn(self.START, view.row_ids)
        self.assertEqual(matrix.legs_from(view, self.START, ["cafe", "market"]),
                         {(self.START, "cafe"): 4, (self.START, "market"): 13})

    def test_travel_minutes_reads_the_base_for_places(self):
        view = self.view()
        ids = ["hotel", "cafe", "market"]
        self.assertEqual(matrix.travel_minutes(view, ids), matrix.travel_minutes(DENSE, ids))
        self.assertEqual(matrix.travel_minutes(view, [self.START, "cafe"]),
                         {(self.START, "cafe"): 4})

    def test_dict_base_and_iteration(self):
        view = self.view(("cafe", 0.4, 0.2), base=cells(LEGS))
        keys = set(view)
        self.assertIn(f"{self.START}->market", keys)
        self.assertIn("hotel->cafe", keys)
        self.assertEqual(len(view), len(LEGS) + 3)  # start -> cafe, hotel, market

    def test_no_start_is_the_matrix_itself(self):
        self.assertIs(matrix.with_starts(DENSE, {}), DENSE)


class TestRouterResolvesAFix(unittest.TestCase):
    def resolve(self, origin):
        starts = {}
        pid, why = _origin_id(origin, BY_ID, DENSE, starts)
        return pid, why, starts

    def test_a_fix_near_a_place_starts_the_day(self):
        lat, lon = north_of(CAFE, 300)
        pid, why, starts = self.resolve({"lat": lat, "lon": lon})
        self.assertIsNone(why)
        self.assertEqual(list(starts), [pid])
        self.assertEqual(starts[pid].nearest.poi_id, "cafe")

    def test_a_far_fix_starts_the_day_with_a_warning(self):
        lat, lon = north_of(MARKET, 1800)
        pid, why, starts = self.resolve({"lat": lat, "lon": lon})
        self.assertIn(pid, starts)
        self.assertIn("uoc luong", why)

    def test_an_unusable_fix_falls_back_to_the_place(self):
        pid, why, starts = self.resolve({"lat": 21.0285, "lon": 105.8542,
                                         "fallback_poi_id": "cafe"})
        self.assertEqual((pid, starts), ("cafe", {}))
        self.assertIn("ngoai vung Da Nang", why)
        self.assertIn("bat dau tu 'Ca phe'", why)

    def test_an_unusable_fix_without_fallback_is_an_open_tour(self):
        pid, why, _ = self.resolve({"lat": 21.0285, "lon": 105.8542})
        self.assertIsNone(pid)
        self.assertIn("khong dung vi tri GPS", why)

    def test_a_fallback_the_matrix_cannot_route_says_so(self):
        pid, why, _ = self.resolve({"lat": 21.0285, "lon": 105.8542,
                                    "fallback_poi_id": "norow"})
        self.assertIsNone(pid)
        self.assertIn("chua co ma tran", why)

    def test_a_named_place_wins_over_its_coordinates(self):
        pid, why, starts = self.resolve({"poi_id": "hotel", "lat": MARKET[0], "lon": MARKET[1]})
        self.assertEqual((pid, why, starts), ("hotel", None, {}))

    def test_the_report_of_a_used_fix(self):
        lat, lon = north_of(CAFE, 300)
        pid, why, starts = self.resolve({"lat": lat, "lon": lon})
        report = _gps_report({"lat": lat, "lon": lon}, pid, why, starts, BY_ID)
        self.assertEqual(report["used"], True)
        self.assertEqual(report["origin_id"], pid)
        self.assertEqual((report["anchor_poi_id"], report["anchor_name"]), ("cafe", "Ca phe"))
        self.assertEqual(report["anchor_m"], 300)
        self.assertTrue(report["estimate"])

    def test_the_report_of_an_unused_fix(self):
        origin = {"lat": 21.0285, "lon": 105.8542, "fallback_poi_id": "cafe"}
        pid, why, starts = self.resolve(origin)
        report = _gps_report(origin, pid, why, starts, BY_ID)
        self.assertEqual((report["used"], report["origin_id"]), (False, "cafe"))
        self.assertEqual(report["reason"], why)

    def test_a_place_has_no_gps_report(self):
        self.assertIsNone(_gps_report({"poi_id": "hotel"}, "hotel", None, {}, BY_ID))
        self.assertIsNone(_gps_report(None, None, None, {}, BY_ID))


class TestOriginSchema(unittest.TestCase):
    def test_a_fix_carries_its_accuracy_and_fallback(self):
        origin = Origin(lat=16.07, lon=108.24, accuracy_m=25, fallback_poi_id="hotel")
        self.assertEqual((origin.accuracy_m, origin.fallback_poi_id), (25, "hotel"))

    def test_impossible_coordinates_are_refused(self):
        with self.assertRaises(ValidationError):
            Origin(lat=96.0, lon=108.2)
        with self.assertRaises(ValidationError):
            Origin(lat=16.0, lon=208.2)
        with self.assertRaises(ValidationError):
            Origin(lat=16.0, lon=108.2, accuracy_m=-1)

    def test_a_resume_can_start_at_a_fix(self):
        trip = TripRequest(days=2, resume={"start_time": "14:05",
                                           "origin": {"lat": 16.07, "lon": 108.24}})
        self.assertEqual(trip.resume.origin.lat, 16.07)


DAY_POIS = [
    {"poi_id": "hill", "verified": True, "visit_min": 120, "rating": 4.7, "fee": 0,
     "intensity": 3, "opening_hours": ["05:00-18:00"], "lat": 16.10, "lon": 108.27},
    {"poi_id": "beach", "verified": True, "visit_min": 120, "rating": 4.6, "fee": 0,
     "intensity": 2, "opening_hours": ["00:00-23:59"], "lat": 16.07, "lon": 108.25},
    {"poi_id": "noodle", "verified": True, "visit_min": 60, "rating": 4.5, "fee": 50000,
     "intensity": 1, "opening_hours": ["07:00-21:00"], "lat": 16.06, "lon": 108.22},
]
DAY_IDS = [p["poi_id"] for p in DAY_POIS]
DAY_LEGS = {**{(a, b): 15 for a in DAY_IDS for b in DAY_IDS if a != b},
            ("hotel", "hill"): 40, ("hotel", "beach"): 5, ("hotel", "noodle"): 25}


class TestBuildPlanFromAFix(unittest.TestCase):
    """The whole day from a fix 600 m north of the hotel."""

    TRIP = {"trip_id": "t1", "budget": 1000000, "start_time": "07:00", "end_time": "16:00"}

    def plan(self):
        by_id = {p["poi_id"]: p for p in DAY_POIS}
        by_id["hotel"] = {"poi_id": "hotel", "verified": True, "role": "base",
                          "lat": HOTEL[0], "lon": HOTEL[1]}
        lat, lon = north_of(HOTEL, 600)
        starts = {}
        origin_id, why = _origin_id({"lat": lat, "lon": lon}, by_id, cells(DAY_LEGS), starts)
        self.assertIsNone(why)
        view = matrix.with_starts(cells(DAY_LEGS), {sid: s.row() for sid, s in starts.items()})
        ranked = [{"poi_id": pid} for pid in DAY_IDS]
        trip = {**self.TRIP, "origin_id": origin_id}
        return build_plan("balanced", trip, ranked, by_id, view), trip, view, origin_id

    def test_the_day_opens_after_the_estimated_ride(self):
        plan, trip, view, start = self.plan()
        first = plan["activities"][0]
        leg = view.get(f"{start}->{first['poi_id']}")["minutes"]
        self.assertTrue(plan["passed"])
        self.assertGreaterEqual(mins(first["start"]), 7 * H + leg)
        self.assertTrue(gate.check_b3(plan, trip, {}, view)["passed"])

    def test_the_first_segment_says_it_is_an_estimate(self):
        plan, _trip, _view, start = self.plan()
        first = plan["segments"][0]
        self.assertEqual(first["from_id"], start)
        self.assertEqual(first["source"], matrix.GPS_ESTIMATE)
        self.assertTrue(all(s["source"] == "cache" for s in plan["segments"][1:]))

    def test_the_stored_context_keeps_the_first_leg(self):
        plan, _trip, _view, start = self.plan()
        self.assertIn((start, plan["activities"][0]["poi_id"]), plan["_context"]["travel"])


if __name__ == "__main__":
    unittest.main()
