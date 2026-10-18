"""Unit test for expense store (T035). Thresholds + validation.

Run from repo root: python BE/tests/unit/test_expenses.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import expenses as ex  # noqa: E402


class TestExpenses(unittest.TestCase):
    def setUp(self):
        ex.reset()

    def test_three_expenses_sum(self):
        ex.set_budget("t1", 3000000)
        ex.add("t1", "Mi Quang", 120000, "food")
        ex.add("t1", "Ve Bao Tang", 60000, "ticket")
        ex.add("t1", "Xe", 200000, "transport")
        s = ex.summary("t1")
        self.assertEqual((s["budget"], s["spent"], s["left"]),
                         (3000000, 380000, 2620000))
        self.assertEqual(s["alert"], "")

    def test_alert_80_and_100(self):
        ex.set_budget("t1", 1000)
        ex.add("t1", "a", 800, "food")
        self.assertEqual(ex.summary("t1")["alert"], "80%")
        ex.add("t1", "b", 200, "other")
        self.assertEqual(ex.summary("t1")["alert"], "100%")

    def test_bad_kind_and_amount(self):
        with self.assertRaises(ValueError):
            ex.add("t1", "x", 100, "shopping")
        with self.assertRaises(ValueError):
            ex.add("t1", "x", -5, "food")

    def test_default_budget(self):
        ex.add("t1", "x", 100, "food")
        self.assertEqual(ex.summary("t1")["budget"], 3000000)


if __name__ == "__main__":
    unittest.main()
