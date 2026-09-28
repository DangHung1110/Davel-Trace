"""Unit test for replan budget feed (T036b). Overspend/negative/light.

Run from repo root: python BE/tests/unit/test_budget.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.budget import tighten_budget  # noqa: E402

STATE = {"trip_id": "t1", "budget": 3000000, "spent": 2500000, "left": 500000,
         "by_kind": {"food": 1500000, "ticket": 200000, "transport": 800000,
                     "other": 0}, "alert": "80%"}


class TestBudget(unittest.TestCase):
    def test_morning_heavy_tightens(self):
        out = tighten_budget(STATE, {"trip_id": "t1"})
        self.assertTrue(out["tightened"])
        self.assertEqual(out["allowed_remaining"], 500000)
        self.assertEqual(sum(out["per_kind_cap"].values()), 500000)
        self.assertEqual(out["per_kind_cap"]["food"], 300000)
        print(f"\n tightened: {out['reason']}")

    def test_negative_left_zeroed(self):
        out = tighten_budget({**STATE, "spent": 3200000, "left": -200000})
        self.assertEqual(out["allowed_remaining"], 0)
        self.assertTrue(all(v == 0 for v in out["per_kind_cap"].values()))

    def test_light_spend_even_split(self):
        out = tighten_budget({"trip_id": "t1", "budget": 3000000,
                              "spent": 200000, "left": 2800000,
                              "by_kind": {"food": 200000}, "alert": ""})
        self.assertFalse(out["tightened"])
        self.assertEqual(out["allowed_remaining"], 2800000)

    def test_t046_fields_present(self):
        out = tighten_budget(STATE)
        for k in ("trip_id", "allowed_total", "allowed_remaining",
                  "per_kind_cap", "tightened", "reason"):
            self.assertIn(k, out)


if __name__ == "__main__":
    unittest.main()
