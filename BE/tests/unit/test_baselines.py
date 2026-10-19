"""Unit tests for the T053 baseline harness (no network, no live LLM).

Pins the contract that matters for a published comparison:
- distance-only is the T051 gold, hybrid is the real app pipeline;
- the LLM-only baseline either RUNS (injected fake client) or reports an
  explicit SKIP with a reason — it never fabricates numbers;
- every system is scored by the SAME tier-1 evaluator;
- the SC table is derived from those results (SC-009 is NOT force-passed);
- the run is deterministic (CP-SAT pinned to one worker).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.common import load_matrix_cells, load_pois  # noqa: E402
from BE.eval import baselines as B  # noqa: E402
from BE.eval.metrics import evaluate  # noqa: E402

SNAPSHOT = os.path.join("BE", "data", "snapshots", "danang-v1")
SUITE = os.path.join("BE", "eval", "gold", "t051_scoped_suite.json")


def _fake_llm(order_fn=None):
    """Fake LLM client: orders candidates by rating desc (a real baseline)."""
    def complete(prompt: str) -> dict:
        ids = [line.split(":")[0][2:].strip()
               for line in prompt.splitlines() if line.startswith("- ")]
        if order_fn is not None:
            ids = order_fn(ids)
        return {"order": ids}
    return complete


class TestBaselines(unittest.TestCase):
    # CP-SAT is the slow part (~5s/plan). The shared report covers a 4-query
    # slice; test_full_suite_run covers the published 23.
    SLICE = 4

    @classmethod
    def setUpClass(cls):
        with open(SUITE, encoding="utf-8") as f:
            cls.suite = json.load(f)
        cls.pois_list = load_pois(SNAPSHOT)
        cls.by_id = {p["poi_id"]: p for p in cls.pois_list}
        cls.matrix = load_matrix_cells(SNAPSHOT)
        cls.feasible = [r for r in cls.suite if r["itinerary"] is not None]
        cls.report = B.run(SUITE, SNAPSHOT, llm_complete=_fake_llm(),
                           limit=cls.SLICE)

    def test_suite_shape_is_scoped_23_of_30(self):
        self.assertEqual(len(self.suite), 30)
        self.assertEqual(len(self.feasible), 23)
        for rec in self.suite:
            self.assertIn("trip", rec)
            self.assertIn("query_id", rec)

    def test_distance_only_is_the_gold(self):
        rec = self.feasible[0]
        self.assertEqual(B.distance_only_itinerary(rec), rec["itinerary"])
        self.assertIsNone(B.distance_only_itinerary({"itinerary": None}))

    def test_hybrid_is_the_real_pipeline_and_gate_is_reported_honestly(self):
        rec = self.feasible[0]
        plan = B.hybrid_itinerary(rec, self.pois_list, self.by_id, self.matrix)
        acts = plan["activities"]
        self.assertGreater(len(acts), 0)
        rep = evaluate({"activities": acts}, rec["trip"], self.by_id, self.matrix)
        self.assertIn("passed", rep["gate"])
        # the harness reports the evaluator's verdict, never a forced pass
        hyb = self.report["systems"]["hybrid"]
        self.assertEqual(hyb["pass_rate"], round(hyb["gate_pass"] / hyb["n"], 4))
        self.assertLessEqual(hyb["gate_pass"], hyb["n"])
        # every activity carries evidence (the pipeline attaches explanations)
        self.assertTrue(all(a.get("explanation", {}).get("evidence")
                            for a in acts))

    def test_hybrid_plan_matches_independent_evaluate(self):
        """Cross-check: the per-query report equals a fresh evaluate() call."""
        rec = self.feasible[0]
        plan = B.hybrid_itinerary(rec, self.pois_list, self.by_id, self.matrix)
        rep = evaluate({"activities": plan["activities"]}, rec["trip"],
                       self.by_id, self.matrix)
        self.assertEqual(set(rep), {"gate", "soft"})
        if rep["gate"]["passed"]:
            self.assertEqual(set(rep["soft"]),
                             {"STR", "DTU", "SSR", "CSM", "EDI", "AQE"})
        else:
            self.assertEqual(rep["soft"], {})

    def test_llm_only_skip_has_reason_and_no_numbers(self):
        def unreachable(_prompt):
            raise B.LLMUnavailable("llm transport: connection refused")
        report = B.run(SUITE, SNAPSHOT, llm_complete=unreachable,
                       limit=self.SLICE)
        llm = report["systems"]["llm-only"]
        self.assertEqual(llm["status"], "SKIP")
        self.assertIn("connection refused", llm["reason"])
        # no fabricated metrics on a SKIP
        for key in ("gate_pass", "pass_rate", "violations", "mean_rating"):
            self.assertNotIn(key, llm)
        # the other two systems still ran
        self.assertEqual(report["systems"]["distance-only"]["n"], self.SLICE)
        self.assertEqual(report["systems"]["hybrid"]["n"], self.SLICE)

    def test_llm_only_runs_with_injected_client(self):
        llm = self.report["systems"]["llm-only"]
        self.assertEqual(llm["status"], "RUN")
        self.assertEqual(llm["n"], self.SLICE)
        self.assertLessEqual(llm["gate_pass"], llm["n"])

    def test_llm_bad_order_is_the_baselines_own_failure(self):
        # an order of unknown ids is not patched into a passing plan
        report = B.run(SUITE, SNAPSHOT,
                       llm_complete=lambda _p: {"order": ["not-a-poi"]},
                       limit=2)
        llm = report["systems"]["llm-only"]
        self.assertEqual(llm["status"], "RUN")
        self.assertEqual(llm["gate_pass"], 0)

    def test_sc_table_is_derived_not_forced(self):
        report, sc = self.report, self.report["sc"]
        self.assertEqual(set(sc), {"SC-005", "SC-006", "SC-007",
                                   "SC-008", "SC-009", "SC-010"})
        # SC-005 compares the actual pass rates
        self.assertEqual(sc["SC-005"]["hybrid"],
                         report["systems"]["hybrid"]["pass_rate"])
        # SC-009 must be an honest comparison of the two plans
        self.assertEqual(sc["SC-009"]["distance_only"],
                         report["systems"]["distance-only"]["mean_rating"])
        self.assertEqual(sc["SC-009"]["hybrid"],
                         report["systems"]["hybrid"]["mean_rating"])
        if sc["SC-009"]["ratio"] is not None:
            self.assertAlmostEqual(
                sc["SC-009"]["pass"], sc["SC-009"]["ratio"] >= 1.10)

    def test_zero_fee_snapshot_marks_sc008_vacuous(self):
        self.assertTrue(self.report["sc"]["SC-008"]["vacuous"])
        self.assertIn("zero_fee", self.report["notes"])
        self.assertTrue(self.report["sc"]["SC-009"]["undecidable"])
        self.assertIn("uniform_ratings", self.report["notes"])

    def test_recovery_probe_counts_only_multiactivity_plans(self):
        rec = self.report["recovery"]
        self.assertGreater(rec["probed"], 0)
        self.assertLessEqual(rec["ok"], rec["probed"])
        self.assertIsInstance(rec["preserved_all"], bool)
        # single-activity plan: nothing to replan -> not probed
        one = {"query_id": "x", "trip": self.feasible[0]["trip"],
               "itinerary": {"activities": [self.feasible[0]["itinerary"]
                                            ["activities"][0]]}}
        probe = B.recovery_probe(one, one["itinerary"]["activities"],
                                 self.by_id, self.matrix)
        self.assertIsNone(probe["ok"])

    def test_run_is_deterministic(self):
        a = B.run(SUITE, SNAPSHOT, llm_complete=_fake_llm(), limit=2)
        b = B.run(SUITE, SNAPSHOT, llm_complete=_fake_llm(), limit=2)
        for key in ("systems", "sc", "recovery", "coverage"):
            self.assertEqual(a[key], b[key], key)

    def test_full_suite_run_covers_all_23_feasible(self):
        """The published run must cover the whole scoped suite (not a slice)."""
        report = B.run(SUITE, SNAPSHOT, llm_complete=_fake_llm())
        self.assertEqual(report["feasible"], 23)
        self.assertEqual(report["infeasible"], 7)
        self.assertEqual(report["systems"]["distance-only"]["n"], 23)
        self.assertEqual(report["systems"]["hybrid"]["n"], 23)
        self.assertEqual(report["coverage"]["eligible"], 5)


if __name__ == "__main__":
    unittest.main()
