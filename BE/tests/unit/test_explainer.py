"""Unit test for explanation builder (T042). Fact/inference split.

Every sample-plan decision has >=1 evidenced reason; unverified claims
get flagged and never slip as fact.

Run from repo root: python BE/tests/unit/test_explainer.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.explainer import (  # noqa: E402
    build_decision,
    explain_plan,
    from_ranked,
    validate_plan,
)


class TestExplainer(unittest.TestCase):
    def test_sample_plan_all_evidenced(self):
        ranked = {"score": 0.95, "reasons": ["rating cao 4.6", "mien phi"],
                  "fired": []}
        fired = [{"rule": "dating", "reason": "ambience yen tinh + rating 4.6"}]
        plan = [from_ranked("cove", "Cove", ranked, fired, True),
                from_ranked("noodle", "Noodle",
                            {"score": 0.8, "reasons": ["gio an"]}, None, True)]
        rep = explain_plan(plan)
        self.assertEqual(rep["violations"], [])
        for e in rep["explanations"]:
            self.assertTrue(e["facts"])
            self.assertTrue(e["inference_marked"])

    def test_unverified_flagged_never_fact(self):
        e = build_decision("chon X", ["rating 5.0 (nguon moc)"],
                           "hop gu bien", "mock", verified=False)
        self.assertTrue(e["uncertainty"])
        self.assertIn("FR-026", e["uncertainty"][0])
        self.assertEqual(validate_plan([e]), [])

    def test_reasonless_caught(self):
        bad = build_decision("chon Y", [], "", "mock", True)
        violations = validate_plan([bad])
        self.assertEqual(len(violations), 1)
        self.assertIn("FR-023", violations[0])

    def test_unflagged_unverified_caught(self):
        sneaky = {"claim": "mo cua ca ngay", "facts": ["gio 00-23"],
                  "inference": "", "inference_marked": False,
                  "uncertainty": [], "source": "x", "verified": False}
        violations = validate_plan([sneaky])
        self.assertEqual(len(violations), 1)
        self.assertIn("FR-026", violations[0])


if __name__ == "__main__":
    unittest.main()
