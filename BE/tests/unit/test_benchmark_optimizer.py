"""Unit tests for the T030 gap-vs-exact benchmark (BE/tools/benchmark_optimizer).

Hermetic: tiny synthetic TOPTW instances prove the brute-force oracle agrees
with CP-SAT and that the objective expressions match. One real-matrix parity
test (skipped when the snapshot artifacts are absent) runs the same check on
the committed OSRM matrix with the PATM q_ij wired (rule backend also works).

Run from repo root: python BE/tests/unit/test_benchmark_optimizer.py -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import scorer  # noqa: E402
from BE.app.services.matrix import MatrixService  # noqa: E402
from BE.app.services.optimizer import (  # noqa: E402
    StubPOI, StubTrip, optimize)
from BE.tools.benchmark_optimizer import build_instance, exact_optimum  # noqa: E402

H = 60
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MATRIX_DIR = os.path.join(_REPO_ROOT, "BE", "data", "snapshots", "danang-v1")
MATRIX = os.path.join(MATRIX_DIR, "matrix.json")
POIS_JSON = os.path.join(MATRIX_DIR, "pois.json")
DEPOT = "ChIJ03jTTgAXQjERpVQunmJHv2c"  # Sontra Sea Hotel — trip origin


class TestExactOptimumHermetic(unittest.TestCase):
    def test_exact_matches_cp_tiny(self):
        """5 POIs that all fit: objective parity incl. a few POI->POI q arcs."""
        pois = [
            StubPOI("p0", visit_min=60, open_min=7 * H, close_min=18 * H, score=5.0),
            StubPOI("p1", visit_min=60, open_min=7 * H, close_min=18 * H, score=4.0),
            StubPOI("p2", visit_min=60, open_min=7 * H, close_min=18 * H, score=3.0),
            StubPOI("p3", visit_min=60, open_min=7 * H, close_min=18 * H, score=2.0),
            StubPOI("p4", visit_min=60, open_min=7 * H, close_min=18 * H, score=1.0),
        ]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 10 for a in ["depot"] + ids for b in ids
                  if a != b}
        trip = StubTrip(start_min=7 * H, end_min=18 * H, origin_id="depot")
        q = {("p0", "p1"): 0.4, ("p1", "p2"): -0.2, ("p2", "p3"): 0.9,
             ("p3", "p4"): 0.1, ("p0", "p4"): 0.7}

        out = optimize(pois, travel, trip, edge_scores=q, timeout_s=5)
        self.assertEqual(out["status"], "optimal")
        self.assertEqual(int(out["objective"]),
                         exact_optimum(pois, travel, trip, edge_scores=q))

    def test_exact_hand_case(self):
        """2 POIs where each alone fits but both cannot: best = better single."""
        # A: 10h visit inside the full window. B: only 17:00-18:00.
        # A->B ends 18:20 (late); B->A arrives 18:10 (past A's close).
        long_stay = StubPOI("long", visit_min=600, open_min=7 * H,
                            close_min=18 * H, score=5.0)
        late_only = StubPOI("late", visit_min=60, open_min=17 * H,
                            close_min=18 * H, score=2.0)
        pois = [long_stay, late_only]
        ids = [p.poi_id for p in pois]
        travel = {(a, b): 10 for a in ["depot"] + ids for b in ids
                  if a != b}
        trip = StubTrip(start_min=7 * H, end_min=18 * H, origin_id="depot")
        q = {("long", "late"): 0.9, ("late", "long"): 0.9}

        expected = int(long_stay.score * 1000)  # 5000 beats 2000
        exact = exact_optimum(pois, travel, trip, edge_scores=q)
        self.assertEqual(exact, expected)

        out = optimize(pois, travel, trip, edge_scores=q, timeout_s=5)
        self.assertEqual(out["status"], "optimal")
        self.assertEqual(int(out["objective"]), exact)
        self.assertEqual([a["poi_id"] for a in out["itinerary"]["activities"]],
                         ["long"])


class TestRealMatrixParity(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(MATRIX) and os.path.exists(POIS_JSON),
                         "matrix/pois snapshot not built")
    def test_real_matrix_parity_k4(self):
        svc = MatrixService(MATRIX_DIR)
        with open(POIS_JSON, encoding="utf-8") as f:
            doc = json.load(f)
        by_id = {p["poi_id"]: p for p in doc["pois"]}

        candidates, stubs, travel = build_instance(
            svc, by_id, 4, DEPOT, 7 * H, 18 * H)
        self.assertEqual(len(candidates), 4)
        trip = StubTrip(start_min=7 * H, end_min=18 * H, origin_id=DEPOT)
        q = scorer.edge_scores(candidates, by_id)

        out = optimize(stubs, travel, trip, edge_scores=q, timeout_s=5)
        self.assertEqual(out["status"], "optimal")
        self.assertEqual(int(out["objective"]),
                         exact_optimum(stubs, travel, trip, edge_scores=q))


if __name__ == "__main__":
    unittest.main()
