"""Unit test for gold suite builder (T051-BUILDER). Seed snapshot only.

Hermetic: every test here loads the LOCKED 7-POI seed at
`data/snapshots/danang-v1/` (repo root), never the big working snapshot
at `BE/data/snapshots/danang-v1/`. Gates: every feasible seed query
yields a gold that PASSES the T049 gate; must_visit present / avoid
absent / cost in budget; deterministic on seed; comma-packed hours parse;
missing matrix pairs / empty candidates fail closed as infeasible.

Run from repo root: python -m pytest BE/tests/unit/test_gold.py -q
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.eval.gold.approach_b import (  # noqa: E402
    _intervals,
    _overlaps,
    filter_pois,
    make_gold,
    tsp_order,
)
from BE.eval.gold.build import build_suite  # noqa: E402
from BE.eval.gold.queries import build_queries  # noqa: E402
from BE.eval.metrics import evaluate  # noqa: E402

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")
N, SEED = 5, 7
FULL_N = 30


class TestGold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SNAPSHOT_DIR, "pois.json"), encoding="utf-8") as f:
            cls.pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
        with open(os.path.join(SNAPSHOT_DIR, "matrix.json"), encoding="utf-8") as f:
            cls.matrix = json.load(f)["cells"]
        cls.queries = build_queries(list(cls.pois.values()), N, SEED)
        cls.golds = [make_gold(q, cls.pois, cls.matrix) for q in cls.queries]

    def test_queries_wellformed(self):
        self.assertEqual(len(self.queries), N)
        for q in self.queries:
            self.assertIn("prefs_text", q)
            for k in ("budget", "start_time", "end_time"):
                self.assertIn(k, q["trip"])

    def test_all_feasible_golds_pass_gate(self):
        feasible = [g for g in self.golds if g["itinerary"] is not None]
        self.assertGreater(len(feasible), 0, "seed must yield feasible golds")
        for g, q in zip(self.golds, self.queries):
            if g["itinerary"] is None:
                continue
            rep = evaluate(g["itinerary"], q["trip"], self.pois, self.matrix)
            self.assertTrue(rep["gate"]["passed"],
                            f"{g['query_id']}: {rep['gate']['violations']}")
            print(f"\n {g['query_id']}: {len(g['itinerary']['activities'])} acts "
                  f"soft {rep['soft']}")

    def test_golds_respect_hard_constraints(self):
        for g, q in zip(self.golds, self.queries):
            if g["itinerary"] is None:
                continue
            ids = [a["poi_id"] for a in g["itinerary"]["activities"]]
            for m in q["trip"]["must_visit"]:
                self.assertIn(m, ids)
            for a in q["trip"]["avoid"]:
                self.assertNotIn(a, ids)
            cost = sum(self.pois[i].get("fee", 0) for i in ids)
            self.assertLessEqual(cost, q["trip"]["budget"])

    def test_deterministic_on_seed(self):
        again = build_queries(list(self.pois.values()), N, SEED)
        self.assertEqual(again, self.queries)
        for q in self.queries:
            self.assertEqual(make_gold(q, self.pois, self.matrix)["itinerary"],
                             next(g["itinerary"] for g in self.golds
                                  if g["query_id"] == q["query_id"]))

    def test_tsp_starts_at_origin(self):
        cands, _ = filter_pois(self.queries[0]["trip"], self.pois)
        order = tsp_order(cands, self.matrix, cands[0])
        self.assertEqual(order[0], cands[0])
        self.assertEqual(sorted(order), sorted(cands))

    def test_comma_packed_hours_second_interval(self):
        # 15:00-18:00 overlaps ONLY the second packed interval 16:30-22:30.
        self.assertTrue(_overlaps(["10:30-14:00, 16:30-22:30"], 15 * 60, 18 * 60))
        # 14:30-16:00 sits in the gap between the two intervals.
        self.assertFalse(_overlaps(["10:30-14:00, 16:30-22:30"], 14 * 60 + 30, 16 * 60))
        self.assertEqual(list(_intervals(["10:30-14:00, 16:30-22:30"])),
                         [(10 * 60 + 30, 14 * 60), (16 * 60 + 30, 22 * 60 + 30)])
        pois = {
            "packed": {"poi_id": "packed", "verified": True, "fee": 0,
                       "opening_hours": ["10:30-14:00, 16:30-22:30"],
                       "visit_min": {"p50": 30}},
            "always": {"poi_id": "always", "verified": True, "fee": 0,
                       "opening_hours": ["00:00-23:59"],
                       "visit_min": {"p50": 30}},
        }
        trip = {"budget": 1000000, "start_time": "15:00", "end_time": "18:00",
                "must_visit": [], "avoid": []}
        cands, bad = filter_pois(trip, pois)
        self.assertEqual(bad, "")
        self.assertIn("packed", cands)

    def test_missing_matrix_pair_is_infeasible(self):
        pois = {
            "a": {"poi_id": "a", "verified": True, "fee": 0,
                  "opening_hours": ["00:00-23:59"], "visit_min": {"p50": 30}},
            "b": {"poi_id": "b", "verified": True, "fee": 0,
                  "opening_hours": ["00:00-23:59"], "visit_min": {"p50": 30}},
        }
        trip = {"budget": 1000000, "start_time": "08:00", "end_time": "18:00",
                "must_visit": [], "avoid": []}
        # self-pairs only: a->b / b->a are missing and must NOT be 0-minute.
        matrix = {"a->a": {"minutes": 0}, "b->b": {"minutes": 0}}
        gold = make_gold({"query_id": "x", "trip": trip}, pois, matrix)
        self.assertIsNone(gold["itinerary"])
        self.assertIn("missing matrix pair", gold["infeasible"])

    def test_empty_candidates_is_infeasible(self):
        trip = {"budget": 1000000, "start_time": "08:00", "end_time": "18:00",
                "must_visit": [], "avoid": []}
        gold = make_gold({"query_id": "x", "trip": trip}, {}, {})
        self.assertIsNone(gold["itinerary"])
        self.assertEqual(gold["infeasible"], "no candidates")

    def test_build_suite_30_records_seed(self):
        suite, bad, infeasible, cov = build_suite(self.pois, self.matrix,
                                                  FULL_N, SEED)
        self.assertEqual(len(suite), FULL_N)
        self.assertEqual(cov["total_pois"], 7)
        self.assertEqual(cov["verified"], 7)
        self.assertEqual(cov["eligible"], 7)
        self.assertEqual(cov["missing_verified"], 0)
        self.assertEqual(bad, 0, "no feasible seed query may fail the gate")
        self.assertEqual(sum(1 for r in suite if r["itinerary"] is None), infeasible)
        for rec in suite:
            if rec["itinerary"] is None:
                self.assertIsNone(rec["gate"])
                continue
            self.assertTrue(rec["gate"]["passed"], rec["query_id"])
            rep = evaluate(rec["itinerary"], rec["trip"], self.pois, self.matrix)
            self.assertTrue(rep["gate"]["passed"], rec["query_id"])
        # determinism of the whole builder path
        again, bad2, inf2, _ = build_suite(self.pois, self.matrix, FULL_N, SEED)
        self.assertEqual(again, suite)
        self.assertEqual((bad2, inf2), (bad, infeasible))


if __name__ == "__main__":
    unittest.main()
