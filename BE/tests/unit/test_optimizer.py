"""Unit test for CP-SAT optimizer (T017). Fixture POIs/matrix (no lane data).

Covers: feasible schedule respects windows/gaps, timeout still returns
best-found, infeasible (require_all, contradictory windows) has reason.

Run from repo root: python BE/tests/unit/test_optimizer.py -v
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.matrix import MatrixService, load_matrix_doc  # noqa: E402
from BE.app.services.optimizer import (  # noqa: E402
    StubPOI, StubTrip, optimize, travel_from_matrix)

H = 60
_REPO = os.path.join(os.path.dirname(__file__), "..", "..", "..")
_REAL_MATRIX = os.path.join(_REPO, "BE", "data", "snapshots", "danang-v1", "matrix.json")

# Real-route fixture (metadata constants lifted from lane A snapshot danang-v1;
# travel minutes themselves come from the committed OSRM artifact).
DEPOT = "ChIJ03jTTgAXQjERpVQunmJHv2c"  # Sontra Sea Hotel — trip origin only
FIXTURE = [  # (poi_id, visit_min p50, open_min, close_min, rating)
    ("ChIJ5QtSVAAZQjERwKdjEbXi6wk", 72, 540, 1410, 5.0),
    ("ChIJ8aa8NQAZQjERRM8-aOoNZ30", 72, 0, 1439, 5.0),
    ("ChIJr_MgSAAZQjERnbnJDAtASZM", 72, 900, 1380, 5.0),
    ("ChIJo5HJeVg9QjERxLqGaMYHXCw", 54, 420, 1140, 5.0),
    ("ChIJKSs6ZVYZQjERSuj5bQ10t0M", 54, 390, 1020, 5.0),
    ("ChIJE4CAepEXQjERg75wrYIZk2Q", 54, 360, 1170, 5.0),
    ("ChIJM2DzGgAZQjERp54q-gVvu-g", 54, 420, 1140, 5.0),
    ("ChIJfQr_phEZQjER5leh47CfKTQ", 108, 450, 1050, 5.0),
    ("ChIJDxZNtxMZQjERJDjAHhQgcEc", 72, 600, 840, 5.0),
    ("ChIJ8VYU_wQRQjER1lJ6MdGSHjg", 72, 360, 1170, 5.0),
    ("ChIJg-cynKIXQjERyE7ZIaTaCO8", 144, 0, 1439, 5.0),
]
REAL_TRIP = StubTrip(7 * 60, 18 * 60, DEPOT)
POIS = [
    StubPOI("musu", visit_min=90, open_min=7 * H + 30, close_min=17 * H, score=3.0),
    StubPOI("beach", visit_min=120, open_min=6 * H, close_min=19 * H, score=5.0),
    StubPOI("noodle", visit_min=60, open_min=7 * H, close_min=21 * H, score=2.0),
    StubPOI("hill", visit_min=150, open_min=5 * H, close_min=18 * H, score=4.0),
    StubPOI("market", visit_min=60, open_min=6 * H, close_min=22 * H, score=1.0),
    StubPOI("bridge", visit_min=30, open_min=0, close_min=24 * H, score=1.0),
]
IDS = [p.poi_id for p in POIS]
TRAVEL = {(a, b): 10 for a in ["depot"] + IDS for b in IDS if a != b}
TRIP = StubTrip(start_min=7 * H, end_min=18 * H, origin_id="depot")


def to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


class TestOptimizer(unittest.TestCase):
    def test_feasible_respects_windows(self):
        out = optimize(POIS, TRAVEL, TRIP)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        acts = out["itinerary"]["activities"]
        self.assertGreater(len(acts), 0)
        by_id = {p.poi_id: p for p in POIS}
        prev_end = TRIP.start_min
        for k, a in enumerate(acts):
            p = by_id[a["poi_id"]]
            s, e = to_min(a["start"]), to_min(a["end"])
            self.assertGreaterEqual(s, p.open_min)
            self.assertLessEqual(e, min(p.close_min, TRIP.end_min))
            self.assertEqual(e - s, p.visit_min)
            if k:
                gap = s - prev_end
                need = TRAVEL[(acts[k - 1]["poi_id"], a["poi_id"])]
                self.assertGreaterEqual(gap, need)
            prev_end = e
        print(f"\n {out['status']}: {len(acts)} acts score "
              f"{out['itinerary']['total_score']} in {out['elapsed_s']}s")

    def test_timeout_returns_best_found(self):
        t0 = time.monotonic()
        out = optimize(POIS, TRAVEL, TRIP, timeout_s=5.0)
        dt = time.monotonic() - t0
        self.assertLess(dt, 8.0)
        self.assertIsNotNone(out["itinerary"])

    def test_infeasible_has_reason(self):
        bad = [StubPOI("x", visit_min=300, open_min=7 * H, close_min=8 * H),
               StubPOI("y", visit_min=300, open_min=9 * H, close_min=10 * H)]
        t = {("depot", pid): 120 for pid in ("x", "y")}
        t.update({(a, b): 120 for a in ("x", "y")
                  for b in ("x", "y") if a != b})
        out = optimize(bad, t, StubTrip(7 * H, 12 * H), require_all=True)
        self.assertEqual(out["status"], "infeasible")
        self.assertTrue(out["reason"])
        self.assertIsNone(out["itinerary"])

    def test_missing_travel_pair_is_infeasible_not_zero(self):
        poi = StubPOI("x", visit_min=60, open_min=7 * H, close_min=12 * H)
        out = optimize([poi], {("x", "depot"): 0},
                       StubTrip(7 * H, 12 * H), require_all=True)
        self.assertEqual(out["status"], "infeasible")
        self.assertIsNone(out["itinerary"])

    def test_origin_leg_uses_matrix(self):
        poi = StubPOI("x", visit_min=60, open_min=7 * H, close_min=12 * H)
        out = optimize([poi], {("depot", "x"): 45},
                       StubTrip(7 * H, 12 * H), require_all=True)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        self.assertGreaterEqual(to_min(out["itinerary"]["activities"][0]["start"]),
                                7 * H + 45)

    # --- T053 bug 2: must_visit is a HARD constraint (gate HCS) ----------
    def test_must_visit_is_hard_not_soft(self):
        """A low-score POI the day cannot profitably reach is still forced."""
        pois = [StubPOI("a", 60, 7 * H, 10 * H, 5.0),
                StubPOI("b", 60, 7 * H, 10 * H, 4.0),
                StubPOI("m", 30, 7 * H, 10 * H, 1.0)]
        ids = [p.poi_id for p in pois]
        travel = {(x, y): 15 for x in ["depot"] + ids for y in ids if x != y}
        trip = StubTrip(7 * H, 10 * H, "depot")
        base = optimize(pois, travel, trip)
        self.assertNotIn("m", [a["poi_id"]
                               for a in base["itinerary"]["activities"]])
        forced = optimize(pois, travel, trip, must_visit=["m"])
        self.assertIn("m", [a["poi_id"]
                            for a in forced["itinerary"]["activities"]])

    def test_must_visit_absent_from_candidates_is_infeasible(self):
        out = optimize(POIS, TRAVEL, TRIP, must_visit=["ghost"])
        self.assertEqual(out["status"], "infeasible")
        self.assertIsNone(out["itinerary"])
        self.assertIn("ghost", out["reason"])

    def test_must_visit_that_cannot_fit_is_infeasible(self):
        """300 min of visit inside a 60-min window -> honest no_solution."""
        poi = StubPOI("m", visit_min=300, open_min=7 * H, close_min=8 * H)
        out = optimize([poi], {("depot", "m"): 10},
                       StubTrip(7 * H, 12 * H, "depot"), must_visit=["m"])
        self.assertEqual(out["status"], "infeasible")
        self.assertIsNone(out["itinerary"])


class TestMealSlotA1(unittest.TestCase):
    """Gate A1 (HARD): at most one restaurant per meal slot (11-14, 17-21)."""

    def _fixture(self):
        # Three high-score restaurants around lunch + a low-score cafe; without
        # the A1 constraint the objective packs two restaurants into lunch.
        pois = [
            StubPOI("r_early", visit_min=60, open_min=10 * H, close_min=14 * H,
                    score=5.0, restaurant=True),
            StubPOI("r_late", visit_min=60, open_min=11 * H, close_min=14 * H,
                    score=5.0, restaurant=True),
            StubPOI("r_noon", visit_min=60, open_min=11 * H, close_min=13 * H,
                    score=5.0, restaurant=True),
            StubPOI("cafe", visit_min=30, open_min=7 * H, close_min=18 * H,
                    score=0.1),
        ]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 5 for a in ["depot"] + ids for b in ids if a != b}
        return pois, travel, StubTrip(7 * H, 18 * H, "depot")

    def test_at_most_one_restaurant_per_lunch_slot(self):
        pois, travel, trip = self._fixture()
        out = optimize(pois, travel, trip)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        lunch = [a for a in out["itinerary"]["activities"]
                 if a["poi_id"].startswith("r_")
                 and 11 * H <= to_min(a["start"]) < 14 * H]
        self.assertLessEqual(len(lunch), 1, lunch)

    def test_restaurant_flag_comes_from_category(self):
        from BE.app.services.optimizer import poi_to_stub
        self.assertTrue(poi_to_stub({"poi_id": "x", "cat": "restaurant"})
                        .restaurant)
        self.assertFalse(poi_to_stub({"poi_id": "y", "cat": "beach"}).restaurant)
        self.assertFalse(poi_to_stub({"poi_id": "z", "cat": "market"}).restaurant)

    def test_greedy_hint_respects_meal_slot(self):
        from BE.app.services.optimizer import _greedy_hint
        pois, travel, trip = self._fixture()
        hint = _greedy_hint(pois, travel, trip, set())
        by_id = {p.poi_id: p for p in pois}
        lunch = [i for i, start in hint
                 if by_id[pois[i - 1].poi_id].restaurant
                 and 11 * H <= start < 14 * H]
        self.assertLessEqual(len(lunch), 1, hint)


class TestDiversityObjective(unittest.TestCase):
    """TASK-1: category diversity in the CP-SAT objective."""

    @staticmethod
    def _fixture():
        # Capacity is exactly 4 stops (150-min visits), so the solver must
        # trade: four cafes vs two cafes + beach + market.
        pois = [StubPOI(f"cafe{i}", 150, 7 * H, 18 * H, 4.0,
                        category="cafe") for i in range(3)]
        pois += [StubPOI("beach", 150, 7 * H, 18 * H, 3.9, category="beach"),
                 StubPOI("market", 150, 7 * H, 18 * H, 2.9,
                         category="market")]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 5 for a in ids for b in ids if a != b}
        return pois, travel, StubTrip(7 * H, 18 * H, "")

    def test_f1_objective_adds_a_sightseeing_stop(self):
        """A rating-only objective packs cafes; diversity must add culture."""
        from BE.app.services import optimizer as opt
        pois, travel, trip = self._fixture()
        out = opt.optimize(pois, travel, trip, workers=1)
        cats = [p.category for p in pois
                if p.poi_id in {a["poi_id"] for a in out["itinerary"]["activities"]}]
        self.assertIn("beach", cats)
        self.assertGreaterEqual(len(set(cats)), 2)
        self.assertLessEqual(cats.count("cafe"), opt.CATEGORY_SOFT_CAP)

    def test_f1_objective_penalizes_third_same_category(self):
        """3rd cafe is penalized enough that a weaker other category wins."""
        from BE.app.services import optimizer as opt
        pois, travel, trip = self._fixture()
        out = opt.optimize(pois, travel, trip, workers=1)
        visited = {a["poi_id"] for a in out["itinerary"]["activities"]}
        self.assertIn("market", visited)
        self.assertLessEqual(sum(1 for v in visited if v.startswith("cafe")),
                             opt.CATEGORY_SOFT_CAP)

    def test_diversity_knob_zero_restores_rating_only(self):
        """DIVERSITY_WEIGHT is the single tuning knob (0 = off)."""
        from unittest import mock
        from BE.app.services import optimizer as opt
        pois, travel, trip = self._fixture()
        with mock.patch.object(opt, "DIVERSITY_WEIGHT", 0.0):
            out = opt.optimize(pois, travel, trip, workers=1)
        visited = {a["poi_id"] for a in out["itinerary"]["activities"]}
        self.assertNotIn("market", visited)
        self.assertEqual(sum(1 for v in visited if v.startswith("cafe")), 3)


class TestPacing(unittest.TestCase):
    """TASK-2: model-only rest/overhead between stops caps density."""

    @staticmethod
    def _fixture():
        pois = [StubPOI(f"p{i}", 60, 7 * H, 18 * H, 5.0 - i * 0.1,
                        category="cafe" if i % 2 else "market")
                for i in range(10)]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 5 for a in ids for b in ids if a != b}
        return pois, travel, StubTrip(7 * H, 18 * H, "")

    def test_pacing_caps_stops_per_day(self):
        from BE.app.services import optimizer as opt
        pois, travel, trip = self._fixture()
        dense = opt.optimize(pois, travel, trip, workers=1, overhead_min=0)
        paced = opt.optimize(pois, travel, trip, workers=1)
        n_dense = len(dense["itinerary"]["activities"])
        n_paced = len(paced["itinerary"]["activities"])
        self.assertGreater(n_dense, n_paced)
        self.assertLessEqual(n_paced, 8)  # ~7-8 stops, not 9-10

    def test_pacing_reserves_gap_between_stops(self):
        from BE.app.services import optimizer as opt
        pois, travel, trip = self._fixture()
        out = opt.optimize(pois, travel, trip, workers=1)
        acts = sorted(out["itinerary"]["activities"], key=lambda a: a["start"])
        for x, y in zip(acts, acts[1:]):
            gap = to_min(y["start"]) - to_min(x["end"])
            need = travel[(x["poi_id"], y["poi_id"])]
            self.assertGreaterEqual(gap, need + opt.STOP_OVERHEAD_MIN)

    def test_pacing_keeps_b3_green(self):
        from BE.app.services import optimizer as opt
        from BE.app.services.gate import check_b3
        pois, travel, trip = self._fixture()
        out = opt.optimize(pois, travel, trip, workers=1)
        acts = out["itinerary"]["activities"]
        matrix = {f"{a}->{b}": {"minutes": m} for (a, b), m in travel.items()}
        self.assertTrue(check_b3({"activities": acts}, {}, {}, matrix)["passed"])


class TestA2InterMealDistance(unittest.TestCase):
    """TASK-3: two restaurants <2.5h apart are penalized by time distance."""

    @staticmethod
    def _fixture():
        # 10:49 (outside the 11:00 lunch slot) vs 11:05 (inside it): gate A1
        # sees one restaurant, so only the A2 time distance can catch it.
        pois = [
            StubPOI("r_early", 60, 10 * H, 22 * H, 5.0, restaurant=True,
                    category="restaurant"),
            StubPOI("r_late", 60, 10 * H, 22 * H, 5.0, restaurant=True,
                    category="restaurant"),
            StubPOI("beach", 60, 7 * H, 18 * H, 3.0, category="beach"),
            StubPOI("cafe", 60, 7 * H, 18 * H, 2.0, category="cafe"),
        ]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 5 for a in ids for b in ids if a != b}
        return pois, travel, StubTrip(7 * H, 18 * H, "")

    def test_a2_distance_keeps_restaurants_apart(self):
        from BE.app.services import optimizer as opt
        pois, travel, trip = self._fixture()
        out = opt.optimize(pois, travel, trip, workers=1)
        acts = {a["poi_id"]: a for a in out["itinerary"]["activities"]}
        if "r_early" in acts and "r_late" in acts:
            gap = abs(to_min(acts["r_late"]["start"])
                      - to_min(acts["r_early"]["start"]))
            self.assertGreaterEqual(gap, opt.RESTAURANT_PAIR_MAX_GAP)

    def test_a2_distance_penalty_off_would_pack_both(self):
        """Counterfactual: A2 weight 0 lets the 10:49/11:05 pair through."""
        from unittest import mock
        from BE.app.services import optimizer as opt
        pois, travel, trip = self._fixture()
        with mock.patch.object(opt, "A2_PAIR_WEIGHT", 0.0):
            out = opt.optimize(pois, travel, trip, workers=1)
        visited = {a["poi_id"] for a in out["itinerary"]["activities"]}
        self.assertIn("r_early", visited)
        self.assertIn("r_late", visited)

    def test_a2_plan_check_ignores_slot_labels(self):
        """10:00 + 10:30 are both outside a meal slot, still A2."""
        from BE.app.services import soft_rules
        pois = {p.poi_id: {"poi_id": p.poi_id, "cat": "restaurant"}
                for p in self._fixture()[0] if p.restaurant}
        acts = [{"poi_id": "r_early", "start": "10:00", "end": "11:00"},
                {"poi_id": "r_late", "start": "10:30", "end": "11:30"}]
        report = soft_rules.plan_penalties(acts, pois)
        self.assertIn("A2", [i["rule"] for i in report["issues"]])


@unittest.skipUnless(os.path.exists(_REAL_MATRIX), "matrix snapshot not built")
class TestOptimizerRealMatrix(unittest.TestCase):
    """TOPTW over the committed OSRM MLD artifact (travel minutes, never haversine)."""

    @classmethod
    def setUpClass(cls):
        cls.svc = MatrixService(os.path.dirname(_REAL_MATRIX))
        cls.doc = load_matrix_doc(_REAL_MATRIX)  # dense-v1 since Phase 3

    def test_travel_from_matrix_matches_artifact(self):
        ids = [DEPOT, FIXTURE[0][0], FIXTURE[1][0]]
        travel = travel_from_matrix(self.svc, ids)
        self.assertEqual(len(travel), 6)
        for a in ids:
            for b in ids:
                if a == b:
                    continue
                cell = int(self.doc["cells"][f"{a}->{b}"]["minutes"])
                self.assertEqual(travel[(a, b)], cell)
                self.assertEqual(travel[(a, b)], self.svc.minutes(a, b)[0])

    def test_real_schedule_respects_windows_and_travel(self):
        stubs = [StubPOI(pid, dur, o, c, r)
                 for (pid, dur, o, c, r) in FIXTURE]
        ids = [DEPOT] + [p.poi_id for p in stubs]
        travel = travel_from_matrix(self.svc, ids)
        t0 = time.monotonic()
        out = optimize(stubs, travel, REAL_TRIP)
        wall = time.monotonic() - t0
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        acts = out["itinerary"]["activities"]
        self.assertTrue(acts)
        self.assertLess(wall, 8.0)
        by_id = {row[0]: row for row in FIXTURE}
        visited = [a["poi_id"] for a in acts]
        self.assertNotIn(DEPOT, visited)
        prev_id, prev_end = None, None
        for k, act in enumerate(acts):
            _, dur, opn, cls_, _ = by_id[act["poi_id"]]
            s, e = to_min(act["start"]), to_min(act["end"])
            self.assertGreaterEqual(s, opn)
            self.assertLessEqual(e, min(cls_, REAL_TRIP.end_min))
            self.assertEqual(e - s, dur)
            if k == 0:
                need = self.svc.minutes(DEPOT, act["poi_id"])[0]
                self.assertGreaterEqual(s, REAL_TRIP.start_min + need)
            else:
                need = self.svc.minutes(prev_id, act["poi_id"])[0]
                self.assertGreaterEqual(s - prev_end, need)
            prev_id, prev_end = act["poi_id"], e
        print(f"\n real matrix {out['status']}: {len(acts)} acts "
              f"score {out['itinerary']['total_score']} in {wall:.2f}s")

    def test_scale_best_found_within_timeout(self):
        # 25 candidates is the largest deterministic slice that yields a
        # best-found itinerary here; all 150 is outside the basic envelope.
        others = [i for i in self.svc.ids[:25] if i != DEPOT]
        ids = [DEPOT] + others
        stubs = [StubPOI(i, 60, 7 * H, 18 * H, 1.0) for i in ids]
        travel = travel_from_matrix(self.svc, ids)
        t0 = time.monotonic()
        out = optimize(stubs, travel, REAL_TRIP)
        wall = time.monotonic() - t0
        self.assertIsNotNone(out["itinerary"])
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        self.assertLess(wall, 8.0)
        print(f"\n scale {len(ids) - 1} pois {out['status']}: "
              f"{len(out['itinerary']['activities'])} acts in {wall:.2f}s")


if __name__ == "__main__":
    unittest.main()
