"""Unit test for replan budget wiring (T036a). Remaining + by-kind.

Run from repo root: python BE/tests/unit/test_replan_budget.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import expenses as ex  # noqa: E402


class TestReplanBudget(unittest.TestCase):
    def setUp(self):
        ex.reset()
        ex.set_budget("t1", 3000000)
        ex.add("t1", "Mi Quang", 120000, "food")
        ex.add("t1", "Ve", 60000, "ticket")
        ex.add("t1", "Xe", 200000, "transport")

    def test_remaining_correct(self):
        r = ex.replan_budget("t1")
        self.assertEqual((r["budget"], r["spent"], r["left"]),
                         (3000000, 380000, 2620000))
        self.assertEqual(r["alert"], "")

    def test_replan_fields_for_t036b(self):
        r = ex.replan_budget("t1")
        self.assertEqual(r["trip_id"], "t1")
        self.assertEqual(r["by_kind"],
                         {"food": 120000, "ticket": 60000,
                          "transport": 200000, "other": 0})
        print(f"\n replan: left {r['left']} by_kind {r['by_kind']}")


if __name__ == "__main__":
    unittest.main()
