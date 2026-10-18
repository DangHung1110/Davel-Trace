"""Unit test for gold suite builder (T051-BUILDER). Seed trials only.

Gates: every feasible seed query yields a gold that PASSES the T049
gate; must_visit present / avoid absent / cost in budget; deterministic
on seed. Full 30-50-query suite runs LATER on the full snapshot.

Run from repo root: python BE/tests/unit/test_gold.py -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.eval.gold.approach_b import filter_pois, make_gold, tsp_order  # noqa: E402
from BE.eval.gold.queries import build_queries  # noqa: E402
from BE.eval.metrics import evaluate  # noqa: E402

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")
N, SEED = 5, 7


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


if __name__ == "__main__":
    unittest.main()
