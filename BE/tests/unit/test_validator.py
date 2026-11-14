"""Unit test for validator gate (T018). Fixture-based (no lane data).

Valid plan passes; each tamper fails its named gate with offenders listed.

Run from repo root: python BE/tests/unit/test_validator.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.gate import rest_rule_violation  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

POIS = {
    "musu": {"verified": True, "fee": 60000, "opening_hours": ["07:30-17:00"]},
    "beach": {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"]},
}
MATRIX = {"musu->beach": {"minutes": 10}, "beach->musu": {"minutes": 10}}
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00"}
GOOD = {"activities": [
    {"poi_id": "musu", "start": "08:00", "end": "09:30"},
    {"poi_id": "beach", "start": "10:00", "end": "12:00"}]}


class TestValidator(unittest.TestCase):
    def test_good_passes(self):
        rep = validate(GOOD, TRIP, POIS, MATRIX)
        self.assertEqual(rep["passed"], True)
        self.assertEqual(rep["violations"], [])
        # The fixture has no category data, so the SOFT F1 quota is listed
        # separately and never fail-closes.
        self.assertEqual(rep["soft_violations"], ["F1"])
        self.assertEqual(rep["details"]["F1"], ["musu", "beach"])
        self.assertEqual(set(rep["checks"]),
                         {"FAR", "PROFILE_SAFE", "VROH", "B3", "BCS", "ETB", "A1",
                          "CAFE_CAP", "CATEGORY_CAP", "NO_CONSECUTIVE",
                          "NO_ADJACENT_FOOD",
                          "REST_FOLLOWS_LUNCH", "F1", "TIME_FIT", "DINNER", "TCS", "HCS"})
        print(f"\n good: {rep['checks']}")

    def test_ghost_poi(self):
        bad = {"activities": [{"poi_id": "ghost", "start": "08:00", "end": "09:00"}]}
        rep = validate(bad, TRIP, POIS, MATRIX)
        self.assertEqual(rep["violations"], ["FAR", "HCS"])
        self.assertEqual(rep["details"]["FAR"], ["ghost"])
        self.assertEqual(rep["details"]["HCS"], ["ghost"])

    def test_closed_hours(self):
        bad = {"activities": [{"poi_id": "musu", "start": "16:30", "end": "17:30"}]}
        rep = validate(bad, TRIP, POIS, MATRIX)
        self.assertEqual(rep["violations"], ["VROH", "TCS", "HCS"])
        self.assertEqual(rep["details"]["VROH"], ["musu"])
        self.assertEqual(rep["details"]["TCS"], ["musu"])
        self.assertEqual(rep["details"]["HCS"], ["musu"])

    def test_plan_ending_after_return_time_fails_ETB(self):
        late = {"activities": [
            {"poi_id": "beach", "start": "16:30", "end": "17:30"}]}
        rep = validate(late, dict(TRIP, return_time="17:00"), POIS, MATRIX)
        self.assertFalse(rep["checks"]["ETB"])
        self.assertEqual(rep["violations"], ["ETB", "TCS", "HCS"])
        self.assertEqual(rep["details"]["ETB"], ["beach"])
        self.assertEqual(rep["details"]["TCS"], ["beach"])
        self.assertEqual(rep["details"]["HCS"], ["beach"])

    def test_tight_gap(self):
        bad = {"activities": [
            {"poi_id": "musu", "start": "08:00", "end": "09:30"},
            {"poi_id": "beach", "start": "09:35", "end": "12:00"}]}
        rep = validate(bad, TRIP, POIS, MATRIX)
        self.assertEqual(rep["violations"], ["B3", "TCS", "HCS"])
        self.assertEqual(rep["details"]["B3"], ["musu->beach"])
        self.assertEqual(rep["details"]["TCS"], ["musu->beach"])
        self.assertEqual(rep["details"]["HCS"], ["musu->beach"])

    def test_over_budget(self):
        rep = validate(GOOD, dict(TRIP, budget=10000), POIS, MATRIX)
        self.assertEqual(rep["violations"], ["BCS", "HCS"])
        self.assertTrue(rep["details"]["BCS"])
        self.assertEqual(rep["details"]["HCS"], rep["details"]["BCS"])

    def test_plan_ending_after_end_time_only_fails_ETB(self):
        """No return_time: end_time alone is the deadline (mirrors ETB/TCS/HCS)."""
        late = {"activities": [
            {"poi_id": "beach", "start": "17:30", "end": "19:00"}]}
        self.assertNotIn("return_time", TRIP)
        rep = validate(late, TRIP, POIS, MATRIX)
        self.assertFalse(rep["checks"]["ETB"])
        self.assertEqual(rep["violations"], ["ETB", "TCS", "HCS"])
        self.assertEqual(rep["details"]["ETB"], ["beach"])
        self.assertEqual(rep["details"]["TCS"], ["beach"])
        self.assertEqual(rep["details"]["HCS"], ["beach"])

    def test_missing_matrix_cell_fails_B3(self):
        """A transition with no matrix cell is a B3 violation, never 0/estimate."""
        no_pair = {"beach->musu": {"minutes": 10}}  # musu->beach cell absent
        rep = validate(GOOD, TRIP, POIS, no_pair)
        self.assertFalse(rep["checks"]["B3"])
        self.assertEqual(rep["violations"], ["B3", "TCS", "HCS"])
        self.assertEqual(rep["details"]["B3"], ["musu->beach"])
        self.assertEqual(rep["details"]["TCS"], ["musu->beach"])
        self.assertEqual(rep["details"]["HCS"], ["musu->beach"])

    def test_optimizer_output_validates(self):
        pois = [StubPOI("musu", 90, 450, 1020, 3.0), StubPOI("beach", 120, 360, 1140, 5.0)]
        travel = {("depot", "musu"): 10, ("depot", "beach"): 10,
                  ("musu", "beach"): 10, ("beach", "musu"): 10}
        out = optimize(pois, travel, StubTrip(420, 1080))
        self.assertIsNotNone(out["itinerary"])
        full_pois = {**POIS, "musu": {**POIS["musu"]}, "beach": {**POIS["beach"]}}
        rep = validate(out["itinerary"], TRIP, full_pois, MATRIX)
        self.assertTrue(rep["passed"], rep)

    def test_a1_offenders_list_every_restaurant_in_the_slot(self):
        """Two restaurants at lunch -> both A1 offenders; HCS mirrors both."""
        restaurant = {"verified": True, "fee": 0,
                      "opening_hours": ["06:00-23:00"], "type": "restaurant"}
        pois = {"r1": restaurant, "r2": restaurant}
        matrix = {"r1->r2": {"minutes": 10}}
        bad = {"activities": [
            {"poi_id": "r1", "start": "11:15", "end": "12:15"},
            {"poi_id": "r2", "start": "12:25", "end": "13:25"}]}
        rep = validate(bad, TRIP, pois, matrix)
        self.assertEqual(rep["violations"],
                         ["A1", "NO_CONSECUTIVE", "NO_ADJACENT_FOOD", "HCS"])
        self.assertEqual(rep["details"]["A1"], ["r1", "r2"])
        self.assertEqual(rep["details"]["NO_CONSECUTIVE"], ["r1->r2"])
        self.assertEqual(rep["details"]["NO_ADJACENT_FOOD"], ["r1->r2"])
        self.assertEqual(rep["details"]["HCS"], ["r1", "r2", "r1->r2"])
        self.assertTrue(rep["checks"]["TCS"])  # TCS is the time mirror, not A1

    def test_f1_all_food_day_is_listed_but_soft(self):
        """F1 offenders are reported under soft_violations, plan passes."""
        pois = {
            "r1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "restaurant"},
            "c1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "cafe"},
        }
        matrix = {"r1->c1": {"minutes": 10}}
        all_food = {"activities": [
            {"poi_id": "r1", "start": "08:00", "end": "09:00"},
            {"poi_id": "c1", "start": "09:10", "end": "10:00"}]}
        rep = validate(all_food, TRIP, pois, matrix)
        self.assertTrue(rep["passed"])
        self.assertEqual(rep["violations"], [])
        self.assertEqual(rep["soft_violations"], ["F1"])
        self.assertEqual(rep["details"]["F1"], ["r1", "c1"])
        self.assertFalse(rep["checks"]["F1"])

    def test_f1_food_plus_sightseeing_passes(self):
        pois = {
            "r1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "restaurant"},
            "m1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "museum"},
        }
        matrix = {"r1->m1": {"minutes": 10}}
        mixed = {"activities": [
            {"poi_id": "r1", "start": "08:00", "end": "09:00"},
            {"poi_id": "m1", "start": "09:10", "end": "10:00"}]}
        rep = validate(mixed, TRIP, pois, matrix)
        self.assertTrue(rep["passed"])
        self.assertEqual(rep["soft_violations"], [])
        self.assertTrue(rep["checks"]["F1"])


    def test_rest_gate_reports_the_poi_inside_the_siesta(self):
        """REST_FOLLOWS_LUNCH offender = the activity inside lunch+rest."""
        pois = {
            "r1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "restaurant"},
            "c1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "cafe"},
        }
        matrix = {"r1->c1": {"minutes": 5}}
        trip = dict(TRIP, profile={"party_type": "solo", "pace": 2})
        itin = {"activities": [
            {"poi_id": "r1", "start": "11:30", "end": "12:30"},
            {"poi_id": "c1", "start": "12:45", "end": "13:00"}]}
        rep = validate(itin, trip, pois, matrix)
        self.assertEqual(rep["violations"], ["REST_FOLLOWS_LUNCH", "HCS"])
        self.assertEqual(rep["details"]["REST_FOLLOWS_LUNCH"], ["c1"])
        self.assertEqual(rep["details"]["HCS"], ["c1"])


    def test_no_adjacent_food_offenders_are_the_restaurant_subset(self):
        """Deprecated view: same scan, restaurant-only (never a 2nd predicate)."""
        pois = {
            "r1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "restaurant"},
            "r2": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "restaurant"},
            "b1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "beach"},
            "b2": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "beach"},
        }
        matrix = {f"{a}->{b}": {"minutes": 10}
                  for a in pois for b in pois if a != b}
        # beach->beach is a NO_CONSECUTIVE (and CATEGORY_CAP) defect, not food.
        itin = {"activities": [
            {"poi_id": "b1", "start": "08:00", "end": "09:00"},
            {"poi_id": "b2", "start": "09:10", "end": "10:10"}]}
        rep = validate(itin, TRIP, pois, matrix)
        self.assertEqual(rep["details"]["NO_CONSECUTIVE"], ["b1->b2"])
        self.assertNotIn("NO_ADJACENT_FOOD", rep["violations"])
        self.assertNotIn("NO_ADJACENT_FOOD", rep["details"])

        # restaurants: both names report the SAME pair (subset invariant).
        itin = {"activities": [
            {"poi_id": "r1", "start": "11:30", "end": "12:30"},
            {"poi_id": "r2", "start": "12:40", "end": "13:40"}]}
        rep = validate(itin, TRIP, pois, matrix)
        self.assertEqual(rep["details"]["NO_ADJACENT_FOOD"], ["r1->r2"])
        self.assertEqual(rep["details"]["NO_ADJACENT_FOOD"],
                         [p for p in rep["details"]["NO_CONSECUTIVE"]
                          if p.startswith("r")])

    def test_bcs_detail_uses_the_shared_cost_formula(self):
        """`details.BCS` = plan_cost (explicit total_cost wins), same as BCS."""
        rep = validate(dict(GOOD, total_cost=11), dict(TRIP, budget=10),
                       POIS, MATRIX)
        self.assertEqual(rep["details"]["BCS"], ["cost 11"])
        self.assertEqual(rep["details"]["BCS"], rep["details"]["HCS"])

    def test_etb_detail_uses_the_shared_deadline_helper(self):
        """`details.ETB` uses min(end_time, return_time), same as check_etb."""
        late = {"activities": [
            {"poi_id": "beach", "start": "16:30", "end": "17:30"}]}
        rep = validate(late, dict(TRIP, return_time="17:00"), POIS, MATRIX)
        self.assertEqual(rep["details"]["ETB"], ["beach"])

    def test_rest_details_and_gate_share_one_definition(self):
        """The rest offenders the validator prints are the gate's own list."""
        pois = {
            "r1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "restaurant"},
            "c1": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "cafe"},
        }
        matrix = {"r1->c1": {"minutes": 5}}
        trip = dict(TRIP, profile={"party_type": "solo", "pace": 2})
        itin = {"activities": [
            {"poi_id": "r1", "start": "11:30", "end": "12:30"},
            {"poi_id": "c1", "start": "12:45", "end": "13:00"}]}
        rep = validate(itin, trip, pois, matrix)
        hit = rest_rule_violation(itin, trip, pois)
        self.assertIsNotNone(hit)
        self.assertEqual(rep["details"]["REST_FOLLOWS_LUNCH"], hit[1])

    def test_rest_vacuous_plan_never_reports_a_reason(self):
        """Morning half-day: the gate passes, so no offender list is invented."""
        trip = dict(TRIP, end_time="10:30",
                    profile={"party_type": "solo", "pace": 2})
        itin = {"activities": [
            {"poi_id": "beach", "start": "08:00", "end": "09:00"}]}
        rep = validate(itin, trip, POIS, MATRIX)
        self.assertTrue(rep["checks"]["REST_FOLLOWS_LUNCH"])
        self.assertNotIn("REST_FOLLOWS_LUNCH", rep["details"])


if __name__ == "__main__":
    unittest.main()
