"""Unit test for the canonical gate registry (T011). No lane-A files.

TCS mirrors VROH/B3/ETB; HCS mirrors all five concrete lane-B hard gates.
Both remain local boolean stubs until the T061 evaluator wiring PR.

Run from repo root: python BE/tests/unit/test_gate.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.common import total_fee  # noqa: E402
from BE.app.services.gate import (  # noqa: E402
    ACTIVE_RULES,
    CHECKS,
    DEPRECATED_RULES,
    HARD_CHECKS,
    RULE_FREEZE,
    SOFT_CHECKS,
    all_pass,
    check_a1,
    check_b3,
    check_bcs,
    check_etb,
    check_f1,
    check_far,
    check_hcs,
    check_no_adjacent_food,
    check_no_consecutive,
    check_profile_safe,
    check_rest_follows_lunch,
    check_tcs,
    check_vroh,
    freeze_drift,
    freeze_report,
    report,
    rest_rule_violation,
)

POIS = {
    "musu": {"verified": True, "fee": 60000, "opening_hours": ["07:30-17:00"]},
    "beach": {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"]},
    "draft": {"verified": False, "fee": 0, "opening_hours": ["00:00-23:59"]},
}
MATRIX = {"musu->beach": {"minutes": 10}, "beach->musu": {"minutes": 10}}
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00"}
GOOD = {"activities": [
    {"poi_id": "musu", "start": "08:00", "end": "09:30"},
    {"poi_id": "beach", "start": "10:00", "end": "12:00"}]}

# A1 (meal-slot rule) fixtures: `cat` is the snapshot's English category,
# `type` the Vietnamese label; older fixtures only carry `type`.
EAT_POIS = {
    "lunch-a": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
                "type": "restaurant"},
    "lunch-b": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
                "type": "restaurant"},
    "dinner": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
               "type": "restaurant"},
    "seafood": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
                "cat": "restaurant", "type": "Nhà hàng hải sản"},
    "cafe-a": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
               "type": "cafe"},
    "cafe-b": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
               "type": "cafe"},
    "dessert": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
                "type": "dessert"},
}
EAT_IDS = list(EAT_POIS)
EAT_MATRIX = {f"{a}->{b}": {"minutes": 10}
              for a in EAT_IDS for b in EAT_IDS if a != b}


class TestGate(unittest.TestCase):
    def test_good_passes_all_hard_gates(self):
        # F1 (soft) legitimately fails on this fixture: it has no category
        # data, so neither the food nor the sightseeing half can be met.
        for name, fn in HARD_CHECKS:
            self.assertEqual(fn(GOOD, TRIP, POIS, MATRIX),
                             {"passed": True, "score": 1.0}, name)
        self.assertEqual(check_f1(GOOD, TRIP, POIS, MATRIX),
                         {"passed": False, "score": 0.0})
        self.assertEqual(all_pass(GOOD, TRIP, POIS, MATRIX),
                         {"passed": True, "failed": []})

    def test_soft_registry_membership(self):
        self.assertEqual(SOFT_CHECKS, frozenset({"F1"}))
        self.assertNotIn("F1", [name for name, _ in HARD_CHECKS])
        self.assertEqual(len(HARD_CHECKS), len(CHECKS) - len(SOFT_CHECKS))

    def test_registry_and_result_shape_are_canonical(self):
        self.assertEqual([name for name, _ in CHECKS],
                         ["FAR", "PROFILE_SAFE", "VROH", "B3", "BCS", "ETB",
                          "A1", "CAFE_CAP",
                          "CATEGORY_CAP", "NO_CONSECUTIVE",
                          "NO_ADJACENT_FOOD",
                          "REST_FOLLOWS_LUNCH", "F1", "TCS", "HCS"])
        for _, fn in CHECKS:
            result = fn(GOOD, TRIP, POIS, MATRIX)
            self.assertEqual(set(result), {"passed", "score"})
            self.assertIs(type(result["passed"]), bool)
            self.assertIs(type(result["score"]), float)

    def test_unknown_poi_fails_far_and_hcs(self):
        bad = {"activities": [{"poi_id": "ghost", "start": "08:00", "end": "09:00"}]}
        self.assertFalse(check_far(bad, TRIP, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"],
                         ["FAR", "HCS"])

    def test_unverified_poi_fails_far(self):
        bad = {"activities": [{"poi_id": "draft", "start": "08:00", "end": "09:00"}]}
        self.assertFalse(check_far(bad, TRIP, POIS, MATRIX)["passed"])

    def test_closed_hours_fails_vroh_and_mirrors(self):
        bad = {"activities": [{"poi_id": "musu", "start": "16:30", "end": "17:30"}]}
        self.assertFalse(check_vroh(bad, TRIP, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"],
                         ["VROH", "TCS", "HCS"])

    def test_tight_gap_fails_b3_and_mirrors(self):
        bad = {"activities": [
            {"poi_id": "musu", "start": "08:00", "end": "09:30"},
            {"poi_id": "beach", "start": "09:35", "end": "12:00"}]}  # gap 5 < 10
        self.assertFalse(check_b3(bad, TRIP, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(bad, TRIP, POIS, MATRIX)["failed"],
                         ["B3", "TCS", "HCS"])

    def test_over_budget_fails_bcs_and_hcs(self):
        trip = dict(TRIP, budget=10000)
        self.assertFalse(check_bcs(GOOD, trip, POIS, MATRIX)["passed"])
        self.assertEqual(all_pass(GOOD, trip, POIS, MATRIX)["failed"],
                         ["BCS", "HCS"])

    def test_tcs_and_hcs_mirror_the_lane_b_gates(self):
        self.assertTrue(check_tcs(GOOD, TRIP, POIS, MATRIX)["passed"])
        self.assertTrue(check_hcs(GOOD, TRIP, POIS, MATRIX)["passed"])

        over_budget_trip = dict(TRIP, budget=10000)
        self.assertTrue(check_tcs(GOOD, over_budget_trip, POIS, MATRIX)["passed"])
        self.assertEqual(check_hcs(GOOD, over_budget_trip, POIS, MATRIX),
                         {"passed": False, "score": 0.0})

    def test_return_time_is_hard_etb_deadline_and_uses_earlier_bound(self):
        late = {"activities": [
            {"poi_id": "beach", "start": "16:30", "end": "17:30"}]}
        return_deadline = dict(TRIP, return_time="17:00")
        self.assertEqual(check_etb(late, return_deadline, POIS, MATRIX),
                         {"passed": False, "score": 0.0})
        self.assertFalse(check_tcs(late, return_deadline, POIS, MATRIX)["passed"])
        self.assertFalse(check_hcs(late, return_deadline, POIS, MATRIX)["passed"])

        earlier_end = dict(TRIP, end_time="17:00", return_time="19:00")
        self.assertFalse(check_etb(late, earlier_end, POIS, MATRIX)["passed"])

        on_deadline = {"activities": [
            {"poi_id": "beach", "start": "16:00", "end": "17:00"}]}
        self.assertTrue(check_etb(on_deadline, return_deadline, POIS, MATRIX)["passed"])

    def test_end_time_only_fails_etb_and_mirrors(self):
        """No return_time in TRIP: end_time alone is the ETB deadline."""
        late = {"activities": [
            {"poi_id": "beach", "start": "17:30", "end": "19:00"}]}
        self.assertNotIn("return_time", TRIP)
        self.assertEqual(check_etb(late, TRIP, POIS, MATRIX),
                         {"passed": False, "score": 0.0})
        self.assertEqual(all_pass(late, TRIP, POIS, MATRIX)["failed"],
                         ["ETB", "TCS", "HCS"])

        # Boundary: finishing exactly at end_time is allowed (<=).
        on_deadline = {"activities": [
            {"poi_id": "beach", "start": "16:00", "end": "18:00"}]}
        self.assertEqual(check_etb(on_deadline, TRIP, POIS, MATRIX),
                         {"passed": True, "score": 1.0})

    def test_etb_vacuous_without_activities(self):
        """Pins documented behavior: no activities -> ETB passes (nothing late)."""
        self.assertEqual(check_etb({"activities": []}, TRIP, POIS, MATRIX),
                         {"passed": True, "score": 1.0})

    def test_far_requires_at_least_one_activity(self):
        """Pins current semantics: FAR needs a non-empty plan (bool(acts))."""
        self.assertEqual(check_far({"activities": []}, TRIP, POIS, MATRIX),
                         {"passed": False, "score": 0.0})

    def test_missing_matrix_cell_fails_b3_and_mirrors(self):
        """B3: a transition with no matrix cell is infeasible, never 0/estimate."""
        no_pair = {"beach->musu": {"minutes": 10}}  # musu->beach cell absent
        self.assertFalse(check_b3(GOOD, TRIP, POIS, no_pair)["passed"])
        self.assertEqual(all_pass(GOOD, TRIP, POIS, no_pair)["failed"],
                         ["B3", "TCS", "HCS"])

    def test_bcs_itinerary_total_cost_overrides_fee_sum(self):
        """Pins: itinerary['total_cost'] wins over the POI fee sum when present."""
        # Fee-based sum would be 60000 (musu) > budget 10 -> override makes it pass.
        self.assertEqual(total_fee(GOOD["activities"], POIS), 60000)
        with_cost = dict(GOOD, total_cost=10)
        self.assertEqual(check_bcs(with_cost, dict(TRIP, budget=10), POIS, MATRIX),
                         {"passed": True, "score": 1.0})
        over_budget = dict(GOOD, total_cost=11)
        self.assertEqual(check_bcs(over_budget, dict(TRIP, budget=10), POIS, MATRIX),
                         {"passed": False, "score": 0.0})

    def test_vroh_tolerates_poi_without_opening_hours(self):
        """Unknown/empty hours are tolerated when the POI is verified."""
        pois = {**POIS,
                "nohours": {"verified": True, "fee": 0},
                "emptyhours": {"verified": True, "fee": 0, "opening_hours": []}}
        itin = {"activities": [
            {"poi_id": "nohours", "start": "08:00", "end": "09:00"},
            {"poi_id": "emptyhours", "start": "10:00", "end": "11:00"}]}
        matrix = {"nohours->emptyhours": {"minutes": 10}}
        self.assertEqual(check_vroh(itin, TRIP, pois, matrix),
                         {"passed": True, "score": 1.0})
        self.assertEqual(all_pass(itin, TRIP, pois, matrix),
                         {"passed": True, "failed": []})

    # --- A1: one restaurant per meal slot (hard, data-quality pass) -------

    def test_a1_two_restaurants_same_lunch_slot_fails(self):
        itin = {"activities": [
            {"poi_id": "lunch-a", "start": "11:10", "end": "12:10"},
            {"poi_id": "lunch-b", "start": "12:20", "end": "13:20"}]}
        self.assertFalse(check_a1(itin, TRIP, EAT_POIS, EAT_MATRIX)["passed"])
        # Two back-to-back restaurants are also NO_CONSECUTIVE and (stricter)
        # NO_ADJACENT_FOOD offenders.
        self.assertEqual(all_pass(itin, TRIP, EAT_POIS, EAT_MATRIX)["failed"],
                         ["A1", "NO_CONSECUTIVE", "NO_ADJACENT_FOOD", "HCS"])

    def test_a1_one_restaurant_per_slot_passes(self):
        itin = {"activities": [
            {"poi_id": "lunch-a", "start": "11:30", "end": "12:30"},
            {"poi_id": "dinner", "start": "18:00", "end": "19:00"}]}
        self.assertEqual(check_a1(itin, TRIP, EAT_POIS, EAT_MATRIX),
                         {"passed": True, "score": 1.0})

    def test_a1_only_restaurant_type_counts(self):
        """Cafes and dessert shops in the slot do not count as a meal."""
        itin = {"activities": [
            {"poi_id": "cafe-a", "start": "11:10", "end": "12:00"},
            {"poi_id": "cafe-b", "start": "12:05", "end": "13:00"},
            {"poi_id": "dessert", "start": "13:05", "end": "13:30"},
            {"poi_id": "lunch-a", "start": "13:35", "end": "14:00"}]}
        self.assertEqual(check_a1(itin, TRIP, EAT_POIS, EAT_MATRIX)["passed"], True)

    def test_a1_snapshot_category_field_is_understood(self):
        """`cat: restaurant` (with a Vietnamese `type`) is still a meal."""
        itin = {"activities": [
            {"poi_id": "lunch-a", "start": "12:00", "end": "13:00"},
            {"poi_id": "seafood", "start": "13:05", "end": "14:05"}]}
        self.assertFalse(check_a1(itin, TRIP, EAT_POIS, EAT_MATRIX)["passed"])

    def test_a1_start_time_keys_the_slot(self):
        """11:30 + 14:00 starts are different slots (14:00 is not lunch)."""
        itin = {"activities": [
            {"poi_id": "lunch-a", "start": "11:30", "end": "12:30"},
            {"poi_id": "lunch-b", "start": "14:00", "end": "15:00"}]}
        self.assertEqual(check_a1(itin, TRIP, EAT_POIS, EAT_MATRIX)["passed"], True)
        dinner = {"activities": [
            {"poi_id": "dinner", "start": "17:30", "end": "18:30"},
            {"poi_id": "seafood", "start": "19:00", "end": "20:00"}]}
        self.assertFalse(check_a1(dinner, TRIP, EAT_POIS, EAT_MATRIX)["passed"])


# F1 (SOFT category quota): at least 1 food AND 1 culture/nature/sightseeing.
F1_POIS = {
    "rest": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
             "cat": "restaurant", "type": "Nhà hàng"},
    "cafe": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
             "cat": "cafe", "type": "Quán cà phê"},
    "museum": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
               "cat": "museum", "type": "Bảo tàng"},
    "beach": {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"],
              "type": "beach"},  # legacy fixture: no `cat`, type fallback
    "spa": {"verified": True, "fee": 0, "opening_hours": ["06:00-23:00"],
            "cat": "spa", "type": "Spa"},
}
F1_IDS = list(F1_POIS)
F1_MATRIX = {f"{a}->{b}": {"minutes": 10}
             for a in F1_IDS for b in F1_IDS if a != b}


def _acts(*ids):
    return {"activities": [{"poi_id": pid, "start": f"{8 + 2 * i:02d}:00",
                            "end": f"{9 + 2 * i:02d}:00"}
                           for i, pid in enumerate(ids)]}


class TestF1CategoryQuota(unittest.TestCase):
    def test_f1_all_food_day_fails_soft(self):
        rep = check_f1(_acts("rest", "cafe"), TRIP, F1_POIS, F1_MATRIX)
        self.assertEqual(rep, {"passed": False, "score": 0.5})

    def test_f1_all_sightseeing_day_fails_soft(self):
        rep = check_f1(_acts("museum", "beach"), TRIP, F1_POIS, F1_MATRIX)
        self.assertEqual(rep, {"passed": False, "score": 0.5})

    def test_f1_food_plus_sightseeing_passes(self):
        self.assertEqual(
            check_f1(_acts("rest", "museum"), TRIP, F1_POIS, F1_MATRIX),
            {"passed": True, "score": 1.0})

    def test_f1_type_fallback_counts_as_sightseeing(self):
        """Legacy POIs only carry `type`: beach still satisfies the quota."""
        self.assertEqual(
            check_f1(_acts("cafe", "beach"), TRIP, F1_POIS, F1_MATRIX),
            {"passed": True, "score": 1.0})

    def test_f1_spa_alone_is_neither_half(self):
        self.assertEqual(
            check_f1(_acts("spa"), TRIP, F1_POIS, F1_MATRIX),
            {"passed": False, "score": 0.0})

    def test_f1_empty_plan_is_vacuously_ok(self):
        """FAR owns the non-empty rule; F1 does not double-report it."""
        self.assertEqual(check_f1({"activities": []}, TRIP, F1_POIS, F1_MATRIX),
                         {"passed": True, "score": 1.0})

    def test_f1_never_fail_closes_hard_gates(self):
        """An all-food day still passes all_pass (F1 is SOFT)."""
        trip = dict(TRIP, budget=3000000)
        self.assertEqual(all_pass(_acts("rest", "cafe"), trip, F1_POIS, F1_MATRIX),
                         {"passed": True, "failed": []})


class TestNoAdjacentFoodAndRest(unittest.TestCase):
    """TWO user-mandated HARD rules: no adjacent restaurants (any cuisine),
    and the siesta starts at the lunch restaurant's END."""

    POIS = {
        "bbq": {"verified": True, "fee": 0,
                "opening_hours": ["06:00-23:00"], "cat": "restaurant",
                "type": "Nhà hàng BBQ"},
        "vegan": {"verified": True, "fee": 0,
                  "opening_hours": ["06:00-23:00"], "cat": "restaurant",
                  "type": "Nhà hàng chay"},
        "museum": {"verified": True, "fee": 0,
                   "opening_hours": ["06:00-23:00"], "cat": "museum"},
        "cafe": {"verified": True, "fee": 0,
                 "opening_hours": ["06:00-23:00"], "cat": "cafe"},
    }
    MATRIX = {f"{a}->{b}": {"minutes": 10}
              for a in POIS for b in POIS if a != b}
    PROFILE = {"party_type": "solo", "pace": 2, "fitness": 2}

    def test_bbq_then_vegan_is_a_violation(self):
        itin = {"activities": [
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"},
            {"poi_id": "vegan", "start": "12:40", "end": "13:40"}]}
        self.assertFalse(check_no_adjacent_food(itin, TRIP, self.POIS,
                                                self.MATRIX)["passed"])
        self.assertEqual(check_no_adjacent_food(
            itin, TRIP, self.POIS, self.MATRIX)["score"], 0.0)

    def test_two_restaurants_with_a_stop_between_pass(self):
        itin = {"activities": [
            {"poi_id": "bbq", "start": "08:00", "end": "09:00"},
            {"poi_id": "museum", "start": "09:10", "end": "10:10"},
            {"poi_id": "vegan", "start": "11:30", "end": "12:30"}]}
        self.assertTrue(check_no_adjacent_food(itin, TRIP, self.POIS,
                                               self.MATRIX)["passed"])

    def test_rest_starts_at_lunch_end_and_blocks_pois(self):
        trip = dict(TRIP, profile=self.PROFILE)
        good = {"activities": [
            {"poi_id": "museum", "start": "09:00", "end": "10:00"},
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"},
            {"poi_id": "cafe", "start": "13:15", "end": "13:45"}]}
        self.assertTrue(check_rest_follows_lunch(good, trip, self.POIS,
                                                 self.MATRIX)["passed"])
        # 12:45 sits inside [12:30, 13:15) -> offender.
        bad = {"activities": [
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"},
            {"poi_id": "cafe", "start": "12:45", "end": "13:00"}]}
        self.assertFalse(check_rest_follows_lunch(bad, trip, self.POIS,
                                                  self.MATRIX)["passed"])

    def test_rest_without_lunch_fails(self):
        trip = dict(TRIP, profile=self.PROFILE)
        no_lunch = {"activities": [
            {"poi_id": "museum", "start": "09:00", "end": "10:00"}]}
        self.assertFalse(check_rest_follows_lunch(no_lunch, trip, self.POIS,
                                                  self.MATRIX)["passed"])

    def test_late_lunch_rest_is_shortened_but_blocks_nothing_after(self):
        """Lunch ends 15:10, trip ends 15:40 -> 30-min rest (45 requested)."""
        trip = dict(TRIP, end_time="15:40", profile=self.PROFILE)
        late = {"activities": [
            {"poi_id": "bbq", "start": "12:50", "end": "15:10"},
            {"poi_id": "museum", "start": "15:40", "end": "15:50"}]}
        self.assertTrue(check_rest_follows_lunch(late, trip, self.POIS,
                                                 self.MATRIX)["passed"])
        inside = {"activities": [
            {"poi_id": "bbq", "start": "12:50", "end": "15:10"},
            {"poi_id": "museum", "start": "15:20", "end": "15:30"}]}
        self.assertFalse(check_rest_follows_lunch(inside, trip, self.POIS,
                                                  self.MATRIX)["passed"])

    def test_declared_rest_start_within_15_minutes_is_allowed(self):
        trip = dict(TRIP, profile=self.PROFILE)
        itin = {"activities": [
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"}],
            "rest": {"start": "12:40", "end": "13:25"}}
        self.assertTrue(check_rest_follows_lunch(itin, trip, self.POIS,
                                                 self.MATRIX)["passed"])
        too_late = {"activities": itin["activities"],
                    "rest": {"start": "12:50", "end": "13:35"}}
        self.assertFalse(check_rest_follows_lunch(too_late, trip, self.POIS,
                                                  self.MATRIX)["passed"])
        wrong_len = {"activities": itin["activities"],
                     "rest": {"start": "12:30", "end": "13:00"}}
        self.assertFalse(check_rest_follows_lunch(wrong_len, trip, self.POIS,
                                                  self.MATRIX)["passed"])

    def test_legacy_plan_without_profile_is_vacuous(self):
        itin = {"activities": [
            {"poi_id": "museum", "start": "09:00", "end": "10:00"}]}
        self.assertTrue(check_rest_follows_lunch(itin, TRIP, self.POIS,
                                                 self.MATRIX)["passed"])


class TestRuleFreeze(unittest.TestCase):
    """Hướng 1: ONE canonical rule per group, duplicates deprecated not deleted.

    The registry is the audit surface; these tests pin the invariants that
    keep the overlap from growing back.
    """

    def test_every_gate_check_is_registered(self):
        names = [name for name, _ in CHECKS]
        self.assertEqual([n for n in names if n not in RULE_FREEZE], [])
        for name, meta in RULE_FREEZE.items():
            self.assertIn(meta["status"], {"active", "deprecated"}, name)
            self.assertTrue(meta["reason"], name)
            self.assertIn("family", meta, name)

    def test_soft_rules_are_registered_in_the_same_registry(self):
        # A2/B1/B2/E2 live in soft_rules.py but their status is declared once.
        for name in ("A2", "B1", "B2", "E2"):
            self.assertIn(name, RULE_FREEZE)

    def test_one_active_owner_per_family_and_deprecated_names_it(self):
        families = freeze_report()["families"]
        for family, members in families.items():
            owners = [n for n in members if RULE_FREEZE[n]["status"] == "active"]
            self.assertTrue(owners, f"{family} has no canonical rule")
            for name in members:
                if RULE_FREEZE[name]["status"] != "deprecated":
                    self.assertIsNone(RULE_FREEZE[name]["canonical"], name)
                    continue
                canonical = RULE_FREEZE[name]["canonical"]
                canonical = ((canonical,) if isinstance(canonical, str)
                             else tuple(canonical or ()))
                self.assertTrue(canonical, f"{name} deprecated without an owner")
                for owner in canonical:
                    self.assertIn(owner, members, f"{name} -> {owner} cross-family")
                    self.assertEqual(RULE_FREEZE[owner]["status"], "active",
                                     f"{name} points at a non-active owner")

    def test_deprecated_registry_is_explicit(self):
        self.assertEqual(set(DEPRECATED_RULES),
                         {"NO_ADJACENT_FOOD", "B1", "B2"})
        self.assertEqual(RULE_FREEZE["NO_ADJACENT_FOOD"]["canonical"],
                         "NO_CONSECUTIVE")
        self.assertIn("NO_ADJACENT_FOOD", [n for n, _ in CHECKS])
        self.assertIn("NO_ADJACENT_FOOD", ACTIVE_RULES + DEPRECATED_RULES)

    def test_deprecated_rule_never_fires_without_its_canonical_rule(self):
        """The strict-subset invariant: NO_ADJACENT_FOOD implies NO_CONSECUTIVE."""
        fixtures = [
            (GOOD, TRIP, POIS, MATRIX),
            ({"activities": [{"poi_id": "ghost", "start": "08:00", "end": "09:00"}]},
             TRIP, POIS, MATRIX),
            ({"activities": [{"poi_id": "musu", "start": "16:30", "end": "17:30"}]},
             TRIP, POIS, MATRIX),
            # bbq -> vegan: adjacent restaurants.
            ({"activities": [
                {"poi_id": "lunch-a", "start": "11:30", "end": "12:30"},
                {"poi_id": "lunch-b", "start": "12:40", "end": "13:40"}]},
             TRIP, EAT_POIS, EAT_MATRIX),
        ]
        for itin, trip, pois, matrix in fixtures:
            self.assertEqual(freeze_drift(itin, trip, pois, matrix), [])
            adjacent = check_no_adjacent_food(itin, trip, pois, matrix)["passed"]
            if not adjacent:
                self.assertFalse(
                    check_no_consecutive(itin, trip, pois, matrix)["passed"])

    def test_report_surfaces_deprecated_failures_additively(self):
        itin = {"activities": [
            {"poi_id": "lunch-a", "start": "11:30", "end": "12:30"},
            {"poi_id": "lunch-b", "start": "12:40", "end": "13:40"}]}
        rep = report(itin, TRIP, EAT_POIS, EAT_MATRIX)
        self.assertFalse(rep["passed"])
        for name in ("A1", "NO_CONSECUTIVE", "NO_ADJACENT_FOOD", "HCS"):
            self.assertIn(name, rep["failed"])
        # Deprecated names stay in `failed` (compat) but are called out.
        self.assertEqual(rep["deprecated_failed"], ["NO_ADJACENT_FOOD"])
        self.assertEqual(set(rep), {"passed", "failed", "soft_failed",
                                    "deprecated_failed", "score",
                                    "checks", "scores"})

    def test_report_deprecated_failed_is_empty_when_all_pass(self):
        self.assertEqual(report(GOOD, TRIP, POIS, MATRIX)["deprecated_failed"],
                         [])


class TestProfileSafe(unittest.TestCase):
    """PROFILE_SAFE re-checks the onboarding hard filter on the final plan."""

    SEAFOOD = {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"],
               "cat": "restaurant", "tags": ["Nhà hàng hải sản"]}
    PLAN = {"activities": [{"poi_id": "beach", "start": "08:00", "end": "09:00"},
                           {"poi_id": "sea", "start": "11:30", "end": "12:30"}]}

    def _pois(self):
        return {**POIS, "sea": self.SEAFOOD}

    def test_allergen_fails_and_hcs_mirrors_it(self):
        trip = dict(TRIP, profile={"allergy": ["hải sản"]})
        res = check_profile_safe(self.PLAN, trip, self._pois(), MATRIX)
        self.assertFalse(res["passed"])
        self.assertAlmostEqual(res["score"], 0.5)
        self.assertFalse(check_hcs(self.PLAN, trip, self._pois(), MATRIX)["passed"])
        self.assertIn("PROFILE_SAFE", report(self.PLAN, trip, self._pois(), MATRIX)["failed"])

    def test_no_profile_filter_passes(self):
        for trip in (TRIP, dict(TRIP, profile={"party_type": "couple"})):
            self.assertTrue(check_profile_safe(self.PLAN, trip, self._pois(),
                                               MATRIX)["passed"])

    def test_must_avoid_and_accessibility(self):
        bar = {"verified": True, "fee": 0, "opening_hours": [], "cat": "bar",
               "tags": ["quán bar"], "intensity": 1}
        plan = {"activities": [{"poi_id": "bar", "start": "20:00", "end": "21:00"}]}
        trip = dict(TRIP, profile={"must_avoid": ["nightlife"]})
        self.assertFalse(check_profile_safe(plan, trip, {"bar": bar}, MATRIX)["passed"])
        trek = {"verified": True, "cat": "nature", "intensity": 3}
        plan = {"activities": [{"poi_id": "trek", "start": "08:00", "end": "10:00"}]}
        trip = dict(TRIP, profile={"accessibility": ["wheelchair"]})
        self.assertFalse(check_profile_safe(plan, trip, {"trek": trek}, MATRIX)["passed"])

    def test_registered_as_active_safety_rule(self):
        self.assertEqual(RULE_FREEZE["PROFILE_SAFE"]["family"], "safety")
        self.assertIn("PROFILE_SAFE", [name for name, _ in HARD_CHECKS])


class TestRestRuleSingleDefinition(unittest.TestCase):
    """REST_FOLLOWS_LUNCH: gate score and validator offenders share one fn."""

    POIS = TestNoAdjacentFoodAndRest.POIS
    MATRIX = TestNoAdjacentFoodAndRest.MATRIX
    PROFILE = {"party_type": "solo", "pace": 2}

    def test_vacuous_cases_return_none(self):
        trip = dict(TRIP, profile=self.PROFILE)
        no_lunch = {"activities": [
            {"poi_id": "museum", "start": "09:00", "end": "10:00"}]}
        # No profile -> legacy plan, no rest need.
        self.assertIsNone(rest_rule_violation(no_lunch, TRIP, self.POIS))
        # Morning half-day: the trip cannot hold a lunch window.
        self.assertIsNone(rest_rule_violation(
            no_lunch, dict(TRIP, end_time="10:30", profile=self.PROFILE),
            self.POIS))

    def test_good_plan_returns_none(self):
        trip = dict(TRIP, profile=self.PROFILE)
        good = {"activities": [
            {"poi_id": "museum", "start": "09:00", "end": "10:00"},
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"}]}
        self.assertIsNone(rest_rule_violation(good, trip, self.POIS))

    def test_missing_lunch_and_bad_window_are_structural(self):
        trip = dict(TRIP, profile=self.PROFILE)
        no_lunch = {"activities": [
            {"poi_id": "museum", "start": "09:00", "end": "10:00"}]}
        reason, offenders = rest_rule_violation(no_lunch, trip, self.POIS)
        self.assertTrue(reason)
        self.assertEqual(offenders, [])

        wrong_len = {"activities": [
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"}],
            "rest": {"start": "12:30", "end": "13:00"}}  # 30 != pace 45
        reason, offenders = rest_rule_violation(wrong_len, trip, self.POIS)
        self.assertTrue(reason)
        self.assertEqual(offenders, [])

    def test_overlap_returns_the_offending_ids(self):
        trip = dict(TRIP, profile=self.PROFILE)
        inside = {"activities": [
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"},
            {"poi_id": "cafe", "start": "12:45", "end": "13:00"}]}
        reason, offenders = rest_rule_violation(inside, trip, self.POIS)
        self.assertEqual(reason, "")  # window is right; only the overlap is wrong
        self.assertEqual(offenders, ["cafe"])
        self.assertFalse(check_rest_follows_lunch(
            inside, trip, self.POIS, self.MATRIX)["passed"])

    def test_structural_failure_scores_zero_even_with_overlap(self):
        """Pins the old score: a wrong window is 0.0, not a ratio."""
        trip = dict(TRIP, profile=self.PROFILE)
        wrong_len = {"activities": [
            {"poi_id": "bbq", "start": "11:30", "end": "12:30"},
            {"poi_id": "cafe", "start": "12:45", "end": "13:00"}],
            "rest": {"start": "12:30", "end": "13:00"}}  # 30 != pace 45
        reason, offenders = rest_rule_violation(wrong_len, trip, self.POIS)
        self.assertTrue(reason)
        self.assertEqual(offenders, ["cafe"])
        self.assertEqual(check_rest_follows_lunch(
            wrong_len, trip, self.POIS, self.MATRIX),
            {"passed": False, "score": 0.0})


if __name__ == "__main__":
    unittest.main()
