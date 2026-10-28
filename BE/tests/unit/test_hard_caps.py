"""Unit tests for the two new HARD sequence rules: CAFE_CAP / NO_CONSECUTIVE.

Covered at all three layers so the solver and the gate can never disagree:
- gate.py: the canonical formula (cafe quota + daypart split, adjacency);
- validator.py: offender reporting / HCS mirroring;
- optimizer.py: the mirrored hard constraints (solver avoids, never just fails).

Run: python -m pytest BE/tests/unit/test_hard_caps.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import optimizer as opt  # noqa: E402
from BE.app.services.gate import (  # noqa: E402
    all_pass,
    check_cafe_cap,
    check_no_adjacent_food,
    check_no_consecutive,
    check_rest_follows_lunch,
)
from BE.app.services.validator import validate  # noqa: E402

H = 60
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00"}


def _poi(cat, *, fee=0):
    return {"verified": True, "fee": fee, "opening_hours": ["06:00-23:00"],
            "cat": cat, "type": cat}


CAFE_POIS = {f"c{i}": _poi("cafe") for i in range(4)}
CAFE_POIS.update({"r1": _poi("restaurant"), "m1": _poi("museum"),
                  "b1": _poi("beach")})
IDS = list(CAFE_POIS)
MATRIX = {f"{a}->{b}": {"minutes": 10} for a in IDS for b in IDS if a != b}


def _itin(*rows):
    """[(poi_id, start, end), ...] -> itinerary dict."""
    return {"activities": [{"poi_id": pid, "start": start, "end": end}
                           for pid, start, end in rows]}


def _cafe_stub(pid, start_win, score, cat="cafe", visit=60):
    return opt.StubPOI(pid, visit_min=visit, open_min=start_win[0],
                       close_min=start_win[1], score=score,
                       restaurant=(cat == "restaurant"), category=cat)


class TestCafeCapGate(unittest.TestCase):
    def test_one_cafe_passes(self):
        itin = _itin(("c0", "08:00", "08:45"), ("m1", "09:00", "10:00"))
        self.assertEqual(check_cafe_cap(itin, TRIP, CAFE_POIS, MATRIX),
                         {"passed": True, "score": 1.0})

    def test_two_morning_cafes_fail_even_with_a_cafe_need(self):
        """Same daypart is a HARD violation: two coffees before 11:00."""
        trip = dict(TRIP, profile={"food_prefs": ["cafe"], "pace": 2})
        itin = _itin(("c0", "07:30", "08:15"), ("c1", "09:00", "09:45"))
        result = check_cafe_cap(itin, trip, CAFE_POIS, MATRIX)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["score"], 0.5)

    def test_two_split_cafes_need_a_profile_cafe_need(self):
        itin = _itin(("c0", "08:00", "08:45"), ("c1", "15:00", "15:45"))
        # No cafe need -> the 2nd cafe is a violation.
        self.assertFalse(check_cafe_cap(itin, TRIP, CAFE_POIS, MATRIX)["passed"])
        # food_prefs says coffee -> allowed (different dayparts).
        need_prefs = dict(TRIP, profile={"food_prefs": ["coffee"], "pace": 2})
        self.assertTrue(check_cafe_cap(itin, need_prefs, CAFE_POIS,
                                       MATRIX)["passed"])
        # activities say cafe -> allowed.
        need_act = dict(TRIP, profile={"activities": ["cafe"], "pace": 2})
        self.assertTrue(check_cafe_cap(itin, need_act, CAFE_POIS,
                                       MATRIX)["passed"])
        # pace 3 is itself a cafe need.
        fast = dict(TRIP, profile={"pace": 3})
        self.assertTrue(check_cafe_cap(itin, fast, CAFE_POIS, MATRIX)["passed"])

    def test_midday_cafe_cannot_be_the_second(self):
        """11:00-13:00 is neither morning nor afternoon."""
        trip = dict(TRIP, profile={"food_prefs": ["cafe"]})
        itin = _itin(("c0", "08:00", "08:45"), ("c1", "12:00", "12:45"))
        self.assertFalse(check_cafe_cap(itin, trip, CAFE_POIS, MATRIX)["passed"])

    def test_three_cafes_always_fail(self):
        trip = dict(TRIP, profile={"food_prefs": ["cafe"], "pace": 3})
        itin = _itin(("c0", "07:30", "08:15"), ("c1", "12:00", "12:45"),
                     ("c2", "15:00", "15:45"))
        result = check_cafe_cap(itin, trip, CAFE_POIS, MATRIX)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["score"], 1 / 3, places=6)

    def test_fail_closes_hcs_and_lists_offenders(self):
        trip = dict(TRIP, profile={"food_prefs": ["cafe"]})
        # Non-adjacent (museum between) but both cafes are in the morning.
        # The r1 lunch keeps REST_FOLLOWS_LUNCH satisfied so this fixture
        # isolates the cafe quota.
        itin = _itin(("c0", "07:30", "08:15"), ("m1", "08:30", "09:30"),
                     ("c1", "09:50", "10:35"), ("r1", "11:30", "12:30"))
        rep = validate(itin, trip, CAFE_POIS, MATRIX)
        self.assertEqual(rep["violations"], ["CAFE_CAP", "HCS"])
        self.assertEqual(rep["details"]["CAFE_CAP"], ["c0", "c1"])
        self.assertEqual(rep["details"]["HCS"], ["c0", "c1"])


class TestNoConsecutiveGate(unittest.TestCase):
    def test_two_same_type_back_to_back_fail(self):
        # Two different beaches are still the same category.
        pois = {**CAFE_POIS, "b2": _poi("beach")}
        itin = _itin(("b1", "08:00", "09:00"), ("b2", "09:30", "10:30"))
        result = check_no_consecutive(itin, TRIP, pois, MATRIX)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["score"], 0.0)

    def test_cafe_to_cafe_is_not_exempt_anymore(self):
        itin = _itin(("c0", "07:30", "08:15"), ("c1", "08:30", "09:15"))
        self.assertFalse(check_no_consecutive(itin, TRIP, CAFE_POIS,
                                              MATRIX)["passed"])

    def test_different_types_pass(self):
        itin = _itin(("c0", "07:30", "08:15"), ("m1", "08:30", "09:30"),
                     ("r1", "11:00", "12:00"), ("b1", "13:00", "14:00"))
        self.assertEqual(check_no_consecutive(itin, TRIP, CAFE_POIS, MATRIX),
                         {"passed": True, "score": 1.0})

    def test_missing_category_is_not_consecutive(self):
        pois = {"x": {"verified": True, "fee": 0},
                "y": {"verified": True, "fee": 0}}
        itin = _itin(("x", "08:00", "09:00"), ("y", "09:30", "10:30"))
        self.assertTrue(check_no_consecutive(itin, TRIP, pois,
                                             {"x->y": {"minutes": 10}})["passed"])

    def test_validator_reports_the_offending_edge(self):
        pois = {**CAFE_POIS, "b2": _poi("beach")}
        matrix = {**MATRIX, "b1->b2": {"minutes": 10}}
        itin = _itin(("b1", "08:00", "09:00"), ("b2", "09:30", "10:30"))
        rep = validate(itin, TRIP, pois, matrix)
        self.assertEqual(rep["violations"],
                         ["CATEGORY_CAP", "NO_CONSECUTIVE", "HCS"])
        self.assertEqual(rep["details"]["NO_CONSECUTIVE"], ["b1->b2"])
        self.assertEqual(rep["details"]["CATEGORY_CAP"], ["b1", "b2"])
        self.assertEqual(rep["details"]["HCS"], ["b1", "b2", "b1->b2"])
        self.assertEqual(all_pass(itin, TRIP, pois, matrix)["failed"],
                         ["CATEGORY_CAP", "NO_CONSECUTIVE", "HCS"])


class TestOptimizerMirrorsTheCaps(unittest.TestCase):
    @staticmethod
    def _cafe_fixture():
        pois = [
            _cafe_stub("c_morning", (7 * H, 12 * H), 5.0),
            _cafe_stub("c_mid", (11 * H, 13 * H), 4.9),
            _cafe_stub("c_after", (13 * H + 30, 18 * H), 4.8),
            _cafe_stub("beach", (7 * H, 18 * H), 3.0, "beach", 120),
            _cafe_stub("museum", (8 * H, 17 * H), 3.0, "museum", 120),
        ]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 5 for a in ids for b in ids if a != b}
        return pois, travel, opt.StubTrip(7 * H, 18 * H, "")

    def _cafes(self, out):
        cats = {p.poi_id: p.category for p in self._cafe_fixture()[0]}
        return [a for a in out["itinerary"]["activities"]
                if cats[a["poi_id"]] == "cafe"]

    def test_cap_one_visits_at_most_one_cafe(self):
        pois, travel, trip = self._cafe_fixture()
        out = opt.optimize(pois, travel, trip, workers=1, cafe_cap=1,
                           no_consecutive=True)
        self.assertIsNotNone(out["itinerary"])
        self.assertLessEqual(len(self._cafes(out)), 1)

    def test_cap_two_splits_the_dayparts(self):
        pois, travel, trip = self._cafe_fixture()
        out = opt.optimize(pois, travel, trip, workers=1, cafe_cap=2,
                           no_consecutive=True)
        cafes = self._cafes(out)
        self.assertEqual(len(cafes), 2, cafes)
        starts = sorted(int(a["start"][:2]) * 60 + int(a["start"][3:])
                        for a in cafes)
        self.assertLess(starts[0], 11 * H)
        self.assertGreater(starts[1], 13 * H)

    def test_cap_two_without_an_afternoon_cafe_stays_at_one(self):
        pois, travel, trip = self._cafe_fixture()
        # Drop the only afternoon cafe: the 11:00-13:00 cafe cannot be the 2nd.
        pois = [p for p in pois if p.poi_id != "c_after"]
        travel = {(a, b): m for (a, b), m in travel.items()
                  if "c_after" not in (a, b)}
        out = opt.optimize(pois, travel, trip, workers=1, cafe_cap=2,
                           no_consecutive=True)
        self.assertIsNotNone(out["itinerary"])
        self.assertLessEqual(len(self._cafes(out)), 1)

    def test_no_consecutive_never_places_same_category_adjacent(self):
        pois = [
            _cafe_stub("b1", (7 * H, 18 * H), 5.0, "beach"),
            _cafe_stub("b2", (7 * H, 18 * H), 4.9, "beach"),
            _cafe_stub("b3", (7 * H, 18 * H), 4.8, "beach"),
            _cafe_stub("m1", (7 * H, 18 * H), 2.0, "museum"),
            _cafe_stub("r1", (7 * H, 18 * H), 2.0, "restaurant"),
        ]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 5 for a in ids for b in ids if a != b}
        trip = opt.StubTrip(7 * H, 18 * H, "")
        out = opt.optimize(pois, travel, trip, workers=1, no_consecutive=True)
        self.assertIsNotNone(out["itinerary"])
        cats = {p.poi_id: p.category for p in pois}
        acts = out["itinerary"]["activities"]
        for x, y in zip(acts, acts[1:]):
            self.assertNotEqual(cats[x["poi_id"]], cats[y["poi_id"]],
                                f"{x['poi_id']}->{y['poi_id']}")

    def test_optimizer_output_passes_the_new_gates(self):
        """The mirrored constraints and the gate agree on the same plan."""
        pois, travel, trip = self._cafe_fixture()
        out = opt.optimize(pois, travel, trip, workers=1, cafe_cap=2,
                           no_consecutive=True)
        gate_pois = {p.poi_id: {"verified": True, "fee": 0, "cat": p.category}
                     for p in pois}
        matrix = {f"{a}->{b}": {"minutes": m} for (a, b), m in travel.items()}
        trip_dict = {"budget": 3000000, "start_time": "07:00",
                     "end_time": "18:00",
                     "profile": {"food_prefs": ["cafe"]}}
        self.assertTrue(check_cafe_cap(out["itinerary"], trip_dict,
                                       gate_pois, matrix)["passed"])
        self.assertTrue(check_no_consecutive(out["itinerary"], trip_dict,
                                             gate_pois, matrix)["passed"])


class TestOptimizerAdjacentFoodAndRest(unittest.TestCase):
    """Solver mirrors: NO_ADJACENT_FOOD and rest tied to lunch end."""

    @staticmethod
    def _travel(ids):
        return {(a, b): 5 for a in ids for b in ids if a != b}

    def test_solver_never_places_two_restaurants_adjacent(self):
        """Even with the broader adjacency rule OFF, food stays apart."""
        pois = [
            _cafe_stub("r1", (10 * H, 22 * H), 5.0, "restaurant", 60),
            _cafe_stub("r2", (10 * H, 22 * H), 4.9, "restaurant", 60),
        ]
        ids = [p.poi_id for p in pois]
        out = opt.optimize(pois, self._travel(ids),
                           opt.StubTrip(7 * H, 20 * H, ""), workers=1,
                           no_adjacent_food=True)
        self.assertIsNotNone(out["itinerary"])
        chosen = [a["poi_id"] for a in out["itinerary"]["activities"]]
        self.assertLessEqual(len(chosen), 1, chosen)

    def test_solver_ties_rest_to_lunch_end(self):
        pois = [
            _cafe_stub("lunch", (10 * H, 14 * H), 5.0, "restaurant", 60),
            _cafe_stub("museum", (7 * H, 18 * H), 4.0, "museum", 60),
            _cafe_stub("cafe", (7 * H, 18 * H), 3.0, "cafe", 45),
        ]
        ids = [p.poi_id for p in pois]
        out = opt.optimize(pois, self._travel(ids),
                           opt.StubTrip(7 * H, 18 * H, ""), workers=1,
                           lunch_required=True, rest_after_lunch=45,
                           no_consecutive=True, no_adjacent_food=True)
        self.assertIsNotNone(out["itinerary"])
        acts = out["itinerary"]["activities"]
        lunch = next(a for a in acts if a["poi_id"] == "lunch")
        lunch_end = int(lunch["end"][:2]) * H + int(lunch["end"][3:])
        rest_end = lunch_end + 45
        for act in acts:
            if act["poi_id"] == "lunch":
                continue
            start = int(act["start"][:2]) * H + int(act["start"][3:])
            end = int(act["end"][:2]) * H + int(act["end"][3:])
            self.assertFalse(start < rest_end and end > lunch_end,
                             f"{act['poi_id']} overlaps the siesta")

    def test_optimizer_output_passes_new_gates(self):
        pois = [
            _cafe_stub("lunch", (10 * H, 14 * H), 5.0, "restaurant", 60),
            _cafe_stub("museum", (7 * H, 18 * H), 4.0, "museum", 60),
            _cafe_stub("cafe", (7 * H, 18 * H), 3.0, "cafe", 45),
            _cafe_stub("dinner", (17 * H, 22 * H), 3.5, "restaurant", 60),
        ]
        ids = [p.poi_id for p in pois]
        travel = self._travel(ids)
        out = opt.optimize(pois, travel, opt.StubTrip(7 * H, 21 * H, ""),
                           workers=1, lunch_required=True,
                           rest_after_lunch=45, no_consecutive=True,
                           no_adjacent_food=True)
        gate_pois = {p.poi_id: {"verified": True, "fee": 0, "cat": p.category}
                     for p in pois}
        matrix = {f"{a}->{b}": {"minutes": m}
                  for (a, b), m in travel.items()}
        trip = {"budget": 3000000, "start_time": "07:00", "end_time": "21:00",
                "profile": {"party_type": "solo", "pace": 2}}
        self.assertTrue(check_no_adjacent_food(out["itinerary"], trip,
                                               gate_pois, matrix)["passed"])
        self.assertTrue(check_rest_follows_lunch(out["itinerary"], trip,
                                                 gate_pois, matrix)["passed"])


if __name__ == "__main__":
    unittest.main()
