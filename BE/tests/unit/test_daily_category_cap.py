"""TASK-1: HARD one-non-food-POI-per-category-per-day cap (CATEGORY_CAP).

Three layers must agree, exactly like CAFE_CAP/A1:
- gate.py: the canonical check (a second market/landmark/beach/... fails);
- validator.py: offender reporting + HCS mirroring;
- optimizer.py + profiles.build_plan: the solver cap and the honest
  "which cap killed it" warning when the verified pool cannot satisfy it.

Meals are exempt: restaurants keep A1, cafes keep CAFE_CAP.

Run: python -m pytest BE/tests/unit/test_daily_category_cap.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import optimizer as opt  # noqa: E402
from BE.app.services import soft_rules  # noqa: E402
from BE.app.services.gate import (  # noqa: E402
    check_a1,
    check_cafe_cap,
    check_category_cap,
    check_hcs,
)
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

H = 60
TRIP = {"budget": 3000000, "start_time": "07:00", "end_time": "19:00"}


def _poi(cat, *, rating=4.5, tags=None, hours=("06:00-23:00",), visit=45,
         intensity=1):
    return {"poi_id": f"{cat}-{abs(hash((cat, rating, tags, hours))) % 9999}",
            "name": f"{cat} place", "cat": cat, "type": cat,
            "opening_hours": list(hours), "visit_min": visit, "fee": 0,
            "rating": rating, "tags": tags or [cat], "intensity": intensity,
            "verified": True}


def _itin(*rows):
    return {"activities": [{"poi_id": pid, "start": s, "end": e}
                           for pid, s, e in rows]}


class TestCategoryCapGate(unittest.TestCase):
    def test_capped_categories_are_the_non_food_sights(self):
        self.assertEqual(
            soft_rules.NON_FOOD_CAPPED,
            frozenset({"market", "landmark", "beach", "attraction", "temple",
                       "museum", "park", "viewpoint"}))
        # Meals are NOT capped here (A1 / CAFE_CAP own them).
        self.assertFalse(soft_rules.is_capped_category("restaurant"))
        self.assertFalse(soft_rules.is_capped_category("cafe"))

    def test_one_of_each_passes(self):
        pois = {"m1": {"verified": True, "cat": "market"},
                "l1": {"verified": True, "cat": "landmark"},
                "b1": {"verified": True, "cat": "beach"}}
        itin = _itin(("m1", "08:00", "09:00"), ("l1", "09:30", "10:30"),
                     ("b1", "15:00", "16:00"))
        self.assertEqual(check_category_cap(itin, TRIP, pois, {}),
                         {"passed": True, "score": 1.0})

    def test_two_markets_fail_the_day(self):
        pois = {"m1": {"verified": True, "cat": "market"},
                "m2": {"verified": True, "cat": "market"},
                "l1": {"verified": True, "cat": "landmark"}}
        itin = _itin(("m1", "08:00", "09:00"), ("l1", "09:30", "10:30"),
                     ("m2", "15:00", "16:00"))
        result = check_category_cap(itin, TRIP, pois, {})
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["score"], 2 / 3)

    def test_two_cafes_two_restaurants_are_not_this_cap(self):
        """Meals stay on CAFE_CAP/A1: this cap must not double-punish them."""
        pois = {"c1": {"verified": True, "cat": "cafe"},
                "c2": {"verified": True, "cat": "cafe"},
                "r1": {"verified": True, "cat": "restaurant"},
                "r2": {"verified": True, "cat": "restaurant"},
                "m1": {"verified": True, "cat": "market"}}
        itin = _itin(("c1", "08:00", "08:45"), ("m1", "09:00", "10:00"),
                     ("r1", "11:30", "12:30"), ("c2", "15:00", "15:45"),
                     ("r2", "18:00", "19:00"))
        self.assertTrue(check_category_cap(itin, TRIP, pois, {})["passed"])
        self.assertTrue(check_a1(itin, TRIP, pois, {})["passed"])
        # Two cafes are legal only with a cafe need and split dayparts.
        need = dict(TRIP, profile={"food_prefs": ["cafe"]})
        self.assertTrue(check_cafe_cap(itin, need, pois, {})["passed"])

    def test_missing_category_is_ignored(self):
        pois = {"x": {"verified": True}, "y": {"verified": True}}
        itin = _itin(("x", "08:00", "09:00"), ("y", "09:30", "10:30"))
        self.assertTrue(check_category_cap(itin, TRIP, pois, {})["passed"])

    def test_fail_closes_hcs_and_lists_every_offender(self):
        pois = {"m1": {"verified": True, "cat": "market", "fee": 0,
                       "opening_hours": ["00:00-23:59"]},
                "m2": {"verified": True, "cat": "market", "fee": 0,
                       "opening_hours": ["00:00-23:59"]}}
        matrix = {"m1->m2": {"minutes": 10}}
        itin = _itin(("m1", "08:00", "09:00"), ("m2", "10:00", "11:00"))
        rep = validate(itin, TRIP, pois, matrix)
        self.assertIn("CATEGORY_CAP", rep["violations"])
        self.assertEqual(rep["details"]["CATEGORY_CAP"], ["m1", "m2"])
        self.assertIn("m1", rep["details"]["HCS"])
        self.assertIn("m2", rep["details"]["HCS"])
        self.assertFalse(check_hcs(itin, TRIP, pois, matrix)["passed"])


class TestOptimizerMirrorsTheCap(unittest.TestCase):
    @staticmethod
    def _pois():
        return [
            opt.StubPOI("m1", visit_min=60, open_min=7 * H,
                        close_min=19 * H, score=5.0, category="market"),
            opt.StubPOI("m2", visit_min=60, open_min=7 * H,
                        close_min=19 * H, score=4.9, category="market"),
            opt.StubPOI("m3", visit_min=60, open_min=7 * H,
                        close_min=19 * H, score=4.8, category="market"),
            opt.StubPOI("l1", visit_min=60, open_min=7 * H,
                        close_min=19 * H, score=3.0, category="landmark"),
            opt.StubPOI("b1", visit_min=60, open_min=7 * H,
                        close_min=19 * H, score=3.0, category="beach"),
        ]

    @staticmethod
    def _travel(pois):
        ids = [p.poi_id for p in pois]
        return {(a, b): 10 for a in ids for b in ids if a != b}

    def test_solver_visits_at_most_one_of_a_category(self):
        pois = self._pois()
        out = opt.optimize(pois, self._travel(pois),
                           opt.StubTrip(7 * H, 19 * H, None), workers=1,
                           category_cap=1, no_consecutive=True)
        self.assertIsNotNone(out["itinerary"])
        chosen = [a["poi_id"] for a in out["itinerary"]["activities"]]
        self.assertLessEqual(sum(1 for pid in chosen if pid.startswith("m")),
                             1, chosen)
        # The weaker landmark/beach still get their (single) slot.
        self.assertIn("l1", chosen)
        self.assertIn("b1", chosen)

    def test_cap_off_keeps_the_old_dense_markets(self):
        """The cap is opt-in at the model layer (build_plan always passes 1)."""
        pois = self._pois()
        out = opt.optimize(pois, self._travel(pois),
                           opt.StubTrip(7 * H, 19 * H, None), workers=1)
        chosen = [a["poi_id"] for a in out["itinerary"]["activities"]]
        self.assertEqual(sum(1 for pid in chosen if pid.startswith("m")), 3)

    def test_solver_output_passes_the_gate(self):
        pois = self._pois()
        out = opt.optimize(pois, self._travel(pois),
                           opt.StubTrip(7 * H, 19 * H, None), workers=1,
                           category_cap=1, no_consecutive=True)
        gate_pois = {p.poi_id: {"verified": True, "fee": 0, "cat": p.category}
                     for p in pois}
        matrix = {f"{a}->{b}": {"minutes": m}
                  for (a, b), m in self._travel(pois).items()}
        self.assertTrue(check_category_cap(out["itinerary"], TRIP, gate_pois,
                                           matrix)["passed"])


class TestBuildPlanMirrorsTheCap(unittest.TestCase):
    """The router seam: cap always on, and an honest infeasibility warning."""

    @staticmethod
    def _fixture():
        pois = [
            _poi("market", rating=4.9, visit=60),
            _poi("market", rating=4.8, visit=60),
            _poi("cafe", rating=4.6, visit=45),
            _poi("restaurant", rating=4.7, visit=60),
        ]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {f"{a}->{b}": {"minutes": 10, "km": 1.0}
                 for a in by_id for b in by_id if a != b}
        ranked = [{"poi_id": pid} for pid in by_id]
        return pois, by_id, cells, ranked

    def test_two_markets_never_both_scheduled(self):
        pois, by_id, cells, ranked = self._fixture()
        trip = {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
                "end_time": "18:00", "must_visit": [], "avoid": [],
                "profile": {"party_type": "solo", "pace": 2}}
        plan = build_plan("balanced", trip, ranked, by_id, cells, template="")
        markets = [a["poi_id"] for a in plan["activities"]
                   if by_id[a["poi_id"]]["cat"] == "market"]
        self.assertLessEqual(len(markets), 1, markets)
        self.assertEqual(plan["constraint_status"]["CATEGORY_CAP"], 1)

    def test_warning_names_the_cap_and_never_relaxes_it(self):
        """A pool with only bad options cannot satisfy the cap: the plan is
        empty, the warning names CATEGORY_CAP, and the cap stays enforced."""
        pois = [_poi("market", rating=4.9, visit=90),
                _poi("market", rating=4.8, visit=90),
                _poi("restaurant", rating=4.7, visit=60),
                _poi("cafe", rating=4.6, visit=45)]
        by_id = {p["poi_id"]: p for p in pois}
        cells = {f"{a}->{b}": {"minutes": 10, "km": 1.0}
                 for a in by_id for b in by_id if a != b}
        ranked = [{"poi_id": pid} for pid in by_id]
        markets = [p["poi_id"] for p in pois if p["cat"] == "market"]
        # Both markets are must_visit (HARD) and both are capped (HARD): the
        # only way out is the cap, and the cap is not on the table.
        trip = {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
                "end_time": "18:00", "must_visit": markets, "avoid": [],
                "profile": {"party_type": "solo", "pace": 2}}
        plan = build_plan("balanced", trip, ranked, by_id, cells, template="")
        self.assertEqual(plan["activities"], [])
        self.assertEqual(plan["infeasible_by"]["rule"], "CATEGORY_CAP")
        self.assertEqual(plan["infeasible_by"]["categories"], ["market"])
        self.assertTrue(any("cap HARD 1 diem/loai/ngay" in w
                            for w in plan["warnings"]), plan["warnings"])
        self.assertTrue(any("can 2 diem loai market" in w
                            for w in plan["warnings"]), plan["warnings"])
        self.assertTrue(any("khong tu noi long cap" in w
                            for w in plan["warnings"]), plan["warnings"])
        # And no silent weakening: a plan WITHOUT the cap would be feasible, so
        # this empty plan is the cap being enforced, not a missing candidate.
        from BE.app.services.optimizer import optimize, stubs_from_pois
        travel = {(a, b): 10 for a in by_id for b in by_id if a != b}
        relaxed = optimize(
            stubs_from_pois([by_id[m] for m in markets] + [by_id[k] for k in
                                                           by_id
                                                           if k not in markets],
                            trip, lambda p: float(p["rating"])),
            travel, opt.StubTrip(8 * 60, 18 * 60, None), workers=1,
            must_visit=markets, lunch_required=True, rest_after_lunch=45,
            no_consecutive=True, no_adjacent_food=True, cafe_cap=1)
        self.assertIsNotNone(relaxed["itinerary"])


if __name__ == "__main__":
    unittest.main()
