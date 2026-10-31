"""Phase 2 latency paths: parallel profiles, constrained refill, batched PATM,
stratified solver candidate cap.

- `build_plan(distinct_from=...)` returns a day whose POI-set Jaccard to every
  given set is <= pool.MAX_PAIRWISE_JACCARD (hard solver constraint); the
  ladder stops at `max_rung` and no infeasibility diagnosis runs.
- POST /v1/itinerary solves the profiles in parallel (core split per solve)
  and replaces a too-similar option with ONE constrained re-solve against the
  plans it must differ from, instead of enumerating a solution pool.
- scorer.edge_scores' batched predict equals the per-pair scores.
- profiles._cap_candidates keeps must_visit + a per-category floor + the best
  by the profile's own score, and build_plan solves on exactly that pool.

Fixture POIs/matrix only (no snapshot) except the router test, which stubs
the planner. Run: python -m pytest BE/tests/unit/test_parallel_planning.py -q
"""

import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402
from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services import pool as pool_svc  # noqa: E402
from BE.app.services import profiles as profiles_mod  # noqa: E402
from BE.app.services import scorer  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.tests.unit.test_template_wiring import (  # noqa: E402
    BY_ID, CELLS, IDS, POIS, RANKED, _poi, _trip)


def _set(plan):
    return frozenset(pool_svc.poi_set(plan))


class TestDistinctSolve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trip = _trip("08:00", "18:00")
        cls.base = build_plan("balanced", cls.trip, RANKED, BY_ID, CELLS,
                              template="", workers=1)

    def test_base_plan_reports_its_rung(self):
        self.assertTrue(self.base["passed"], self.base.get("violations"))
        self.assertEqual(self.base["_rung"], 0)

    def test_distinct_plan_clears_ceiling(self):
        alt = build_plan("balanced", self.trip, RANKED, BY_ID, CELLS,
                         template="", workers=1,
                         distinct_from=[_set(self.base)],
                         max_rung=self.base["_rung"])
        self.assertTrue(alt["passed"], alt.get("violations"))
        self.assertLessEqual(pool_svc.jaccard(_set(alt), _set(self.base)),
                             pool_svc.MAX_PAIRWISE_JACCARD)
        self.assertLessEqual(alt["_rung"], self.base["_rung"])

    def test_ids_outside_the_pool_only_grow_the_union(self):
        ghosts = frozenset(f"ghost{i}" for i in range(len(_set(self.base))))
        alt = build_plan("balanced", self.trip, RANKED, BY_ID, CELLS,
                         template="", workers=1,
                         distinct_from=[_set(self.base) | ghosts], max_rung=0)
        self.assertTrue(alt["passed"], alt.get("violations"))
        self.assertLessEqual(
            pool_svc.jaccard(_set(alt), _set(self.base) | ghosts),
            pool_svc.MAX_PAIRWISE_JACCARD)

    def test_impossible_distinctness_is_empty_without_diagnosis(self):
        # Ceiling 0 against the whole pool: no day can avoid every POI, so
        # the only honest answer is "no alternative", from ONE solve (the
        # 7-trial diagnosis would cost seconds and answer the wrong question).
        calls = []
        real = profiles_mod.optimize

        def counted(*args, **kwargs):
            calls.append(kwargs.get("distinct_from"))
            return real(*args, **kwargs)

        with mock.patch.object(pool_svc, "MAX_PAIRWISE_JACCARD", 0.0), \
                mock.patch.object(profiles_mod, "optimize", counted):
            alt = build_plan("balanced", self.trip, RANKED, BY_ID, CELLS,
                             template="", workers=1,
                             distinct_from=[frozenset(IDS)], max_rung=0)
        self.assertEqual(alt["activities"], [])
        self.assertNotIn("infeasible_by", alt)
        self.assertNotIn("_rung", alt)
        self.assertEqual(len(calls), 1)


class TestSolverBudget(unittest.TestCase):
    def test_plans_are_decided_by_work_not_by_the_clock(self):
        self.assertEqual(itinerary_mod.PLAN_WORKERS, 1)
        self.assertGreater(itinerary_mod.PLAN_DETERMINISTIC_TIME, 0)
        self.assertGreater(itinerary_mod.DISTINCT_DETERMINISTIC_TIME, 0)
        # The wall limit is a guard for an overloaded machine, far past the budget.
        self.assertGreater(itinerary_mod.PLAN_WALL_LIMIT_S,
                           5 * itinerary_mod.PLAN_DETERMINISTIC_TIME)


class TestRouterParallelRefill(unittest.TestCase):
    """Stub planner: every profile first returns the SAME day (Jaccard 1.0)."""

    TRIP = {"trip_id": "t-par", "start_time": "08:00", "end_time": "18:00",
            "budget": 2000000}

    def setUp(self):
        self.lock = threading.Lock()
        self.calls = []
        self.fresh = iter(["fghij", "klmno", "pqrst", "uvwxy"])

    def _plan(self, ids, utility):
        return {"activities": [{"poi_id": pid, "start": "08:00",
                                "end": "09:00"} for pid in ids],
                "passed": True, "_rung": 0, "scores": {"utility": utility},
                "total_cost": 0, "total_km": 0, "total_min": 0,
                "constraint_status": {}}

    def _builder(self, **kwargs):
        with self.lock:
            self.calls.append(kwargs)
            if kwargs.get("distinct_from") is not None:
                return self._plan(next(self.fresh), 0.5)
        utility = {"savings": 0.9, "balanced": 0.8, "experience": 0.7}
        return self._plan("abcde", utility[kwargs["profile"]])

    def test_conflicts_are_resolved_by_constrained_resolves(self):
        client = TestClient(main_mod.app)
        with mock.patch.object(itinerary_mod, "_get_plan_builder",
                               return_value=self._builder):
            r = client.post("/v1/itinerary", json={"trip": self.TRIP})
        self.assertEqual(r.status_code, 200, r.text)
        plans = r.json()["plans"]
        self.assertEqual([p["profile"] for p in plans],
                         ["savings", "balanced", "experience"])
        sets = [frozenset(pool_svc.poi_set(p)) for p in plans]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertLessEqual(pool_svc.jaccard(sets[i], sets[j]),
                                     pool_svc.MAX_PAIRWISE_JACCARD)

        first = [c for c in self.calls if c.get("distinct_from") is None]
        refills = [c for c in self.calls if c.get("distinct_from") is not None]
        self.assertEqual(len(first), 3)
        self.assertEqual({c["workers"] for c in first}, {itinerary_mod.PLAN_WORKERS})
        self.assertEqual({c["deterministic_time"] for c in first},
                         {itinerary_mod.PLAN_DETERMINISTIC_TIME})
        # The two losers (balanced, experience) are re-solved once each,
        # against the plans kept beside them at that moment.
        self.assertEqual([c["profile"] for c in refills],
                         ["balanced", "experience"])
        self.assertEqual(refills[0]["distinct_from"],
                         [frozenset("abcde"), frozenset("abcde")])
        self.assertEqual(refills[1]["distinct_from"],
                         [frozenset("abcde"), frozenset("fghij")])
        for call in refills:
            self.assertEqual(call["max_rung"], 0)
            self.assertEqual(call["deterministic_time"], itinerary_mod.DISTINCT_DETERMINISTIC_TIME)
            self.assertEqual(call["timeout_s"], itinerary_mod.PLAN_WALL_LIMIT_S)
        self.assertEqual(len(r.json()["solution_pool"]["replaced"]), 2)


class TestBatchedEdgeScores(unittest.TestCase):
    def test_batched_equals_per_pair(self):
        ctx = {"hour": 9}
        batched = scorer.edge_scores(IDS, BY_ID, ctx=ctx)
        per_pair = {
            (a, b): round(scorer.score_transition(BY_ID[a], BY_ID[b], None, ctx)
                          + scorer.edge_penalty(BY_ID[a], BY_ID[b], ctx), 4)
            for a in IDS for b in IDS if a != b}
        self.assertEqual(batched, per_pair)

    def test_single_poi_has_no_edges(self):
        self.assertEqual(scorer.edge_scores(IDS[:1], BY_ID), {})


class TestCandidateCap(unittest.TestCase):
    def _pool(self):
        # 3 categories x 10, rating = score; rank order = list order.
        return [_poi(f"{cat}{i}", cat, rating=3.0 + i / 10)
                for cat in ("cafe", "restaurant", "beach") for i in range(10)]

    def test_small_pool_is_untouched(self):
        self.assertIs(profiles_mod._cap_candidates(POIS, lambda p: 0, []),
                      POIS)

    def test_floor_must_and_best_in_rank_order(self):
        pool = self._pool()
        kept = profiles_mod._cap_candidates(
            pool, lambda p: p["rating"], must=["cafe0"], limit=12, floor=2)
        ids = [p["poi_id"] for p in kept]
        self.assertEqual(len(ids), 12)
        self.assertIn("cafe0", ids)              # must_visit, lowest score
        for cat in ("cafe", "restaurant", "beach"):
            self.assertIn(f"{cat}9", ids)        # floor: best two per cat
            self.assertIn(f"{cat}8", ids)
        self.assertEqual(ids, [p["poi_id"] for p in pool if p["poi_id"] in ids])

    def test_floor_can_exceed_the_limit(self):
        kept = profiles_mod._cap_candidates(
            self._pool(), lambda p: p["rating"], must=[], limit=2, floor=1)
        self.assertEqual({p["poi_id"] for p in kept},
                         {"cafe9", "restaurant9", "beach9"})

    def test_build_plan_solves_on_the_capped_pool(self):
        seen, real_cap, real_opt = {}, profiles_mod._cap_candidates, profiles_mod.optimize

        def cap(candidates, score, must, **kwargs):
            out = real_cap(candidates, score, must, limit=6, floor=0, **kwargs)
            seen["capped"] = {p["poi_id"] for p in out}
            return out

        def opt(stubs, *args, **kwargs):
            seen.setdefault("solved", {s.poi_id for s in stubs})
            return real_opt(stubs, *args, **kwargs)

        trip = _trip("08:00", "18:00", must_visit=["mus1"])
        with mock.patch.object(profiles_mod, "_cap_candidates", cap), \
                mock.patch.object(profiles_mod, "optimize", opt):
            build_plan("balanced", trip, RANKED, BY_ID, CELLS, template="",
                       workers=1)
        self.assertEqual(seen["solved"], seen["capped"])
        self.assertEqual(len(seen["capped"]), 6)
        self.assertIn("mus1", seen["capped"])


if __name__ == "__main__":
    unittest.main()
