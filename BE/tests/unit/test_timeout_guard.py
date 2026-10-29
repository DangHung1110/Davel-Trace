"""D2 step 3 (N3): CP-SAT timeout guards.

Two guarantees:
1. Every solve has a wall-clock ceiling (`max_time_in_seconds`), including the
   solution-pool members (the deterministic budget used to be dropped there).
2. A timed-out solve returns its best-so-far plus a NAMED warning; a timeout
   before any solution returns an honest empty result + warning. Neither path
   crashes.

Run from repo root: python -m pytest BE/tests/unit/test_timeout_guard.py -q
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import optimizer  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402

H = 60


def _scale_fixture(n: int = 20):
    """A search-heavy-enough instance: 20 POIs, three categories, tight day."""
    pois = [StubPOI(f"p{i}", 45, 7 * H, 18 * H, 5.0 - i * 0.05,
                    category=("restaurant" if i % 3 == 0
                              else "cafe" if i % 3 == 1 else "beach"))
            for i in range(n)]
    ids = [p.poi_id for p in pois]
    travel = {(a, b): 5 for a in ["depot"] + ids for b in ids if a != b}
    return pois, travel, StubTrip(7 * H, 18 * H, "depot")


class TestTimeoutGuard(unittest.TestCase):
    def test_wall_clock_timeout_returns_best_found_with_warning(self):
        # 0.5 s is enough to place the greedy hint but not to prove optimal,
        # so the result is reliably FEASIBLE (best-so-far) + timeout warning.
        pois, travel, trip = _scale_fixture(25)
        out = optimize(pois, travel, trip, timeout_s=0.5, workers=1)
        self.assertEqual(out["status"], "feasible-timeout")
        self.assertIsNotNone(out["itinerary"])
        self.assertTrue(out["itinerary"]["activities"])
        self.assertIs(out.get("timed_out"), True)
        self.assertTrue(any(w.startswith("CP_SAT_TIMEOUT")
                            for w in out.get("warnings", [])),
                        out.get("warnings"))

    def test_no_solution_timeout_is_honest_not_a_crash(self):
        """UNKNOWN (budget spent before a solution) -> empty + named warning."""
        from ortools.sat.python import cp_model

        pois, travel, trip = _scale_fixture(5)
        with mock.patch.object(cp_model.CpSolver, "Solve",
                               return_value=cp_model.UNKNOWN):
            out = optimize(pois, travel, trip, timeout_s=0.1)
        self.assertEqual(out["status"], "infeasible")
        self.assertIsNone(out["itinerary"])
        self.assertIs(out.get("timed_out"), True)
        self.assertTrue(any(w.startswith("CP_SAT_TIMEOUT_NO_SOLUTION")
                            for w in out.get("warnings", [])),
                        out.get("warnings"))

    def test_none_timeout_is_normalised_to_a_ceiling(self):
        captured = {}

        def fake_pool(pois, travel, trip, *, k, band, budget, kwargs):
            captured.update(kwargs)
            return {"status": "stub", "itinerary": None}

        with mock.patch.object(optimizer, "_pool_search",
                               side_effect=fake_pool):
            optimize([], {}, StubTrip(), solution_pool=2, timeout_s=None)
        self.assertEqual(captured["timeout_s"], optimizer.TIMEOUT_S)

    def test_deterministic_time_reaches_pool_members(self):
        """Regression: _pool_search used to drop deterministic_time entirely."""
        captured = {}

        def fake_pool(pois, travel, trip, *, k, band, budget, kwargs):
            captured.update(kwargs)
            return {"status": "stub", "itinerary": None}

        with mock.patch.object(optimizer, "_pool_search",
                               side_effect=fake_pool):
            optimize([], {}, StubTrip(), solution_pool=3,
                     deterministic_time=0.5)
        self.assertEqual(captured["deterministic_time"], 0.5)

    def test_pool_budget_is_forwarded_to_every_member(self):
        """Every _pool_search re-solve gets the (normalised) wall ceiling."""
        calls = []

        def fake_solve(pois, travel, trip, **kwargs):
            calls.append(kwargs)
            # Member 0 must be feasible so the loop runs once more.
            acts = [{"poi_id": p.poi_id, "start": "08:00", "end": "08:45"}
                    for p in pois[:1]]
            return {"status": "optimal", "itinerary": {"activities": acts},
                    "objective": 1.0,
                    "pool": [{"activities": acts, "objective": 1.0,
                              "poi_ids": [a["poi_id"] for a in acts]}],
                    "pool_stats": {"best_status": "optimal"}}

        with mock.patch.object(optimizer, "optimize", side_effect=fake_solve):
            optimizer._pool_search([], {}, StubTrip(), k=2, band=0.95,
                                   budget=0.1, kwargs={"timeout_s": 2.0,
                                                       "deterministic_time": 0.5})
        self.assertTrue(calls)
        self.assertEqual(calls[0]["timeout_s"], 2.0)
        for call in calls:
            self.assertLessEqual(call["timeout_s"],
                                 optimizer.POOL_STEP_TIMEOUT_S)
            self.assertEqual(call["deterministic_time"], 0.5)


if __name__ == "__main__":
    unittest.main()
