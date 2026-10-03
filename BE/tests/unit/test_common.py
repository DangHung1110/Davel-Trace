"""Unit tests for BE/app/services/common.py opening-hours parsing.

Covers multi-interval comma strings (e.g. "10:30-14:00, 16:30-22:30")
and stray single-time fragments, which used to raise ValueError.

Run from repo root: python BE/tests/unit/test_common.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.common import in_range, parse_hours, to_min  # noqa: E402


class TestCommonHours(unittest.TestCase):
    def test_multi_interval_hours_parse(self):
        spec = "10:30-14:00, 16:30-22:30"

        # inside the first interval
        self.assertTrue(in_range(to_min("10:30"), to_min("14:00"), spec))
        self.assertTrue(in_range(to_min("11:00"), to_min("12:00"), spec))

        # inside the second interval
        self.assertTrue(in_range(to_min("17:00"), to_min("18:00"), spec))

        # outside both intervals (the midday gap)
        self.assertFalse(in_range(to_min("15:00"), to_min("16:00"), spec))

        # overnight wrap mixed with a daytime comma interval
        night = "09:00-11:00, 22:00-02:00"
        self.assertTrue(in_range(to_min("23:00"), to_min("23:30"), night))
        self.assertTrue(in_range(to_min("01:00"), to_min("01:30"), night))
        self.assertFalse(in_range(to_min("12:00"), to_min("13:00"), night))

        # stray single-time fragments must not crash
        self.assertFalse(in_range(to_min("11:00"), to_min("12:00"), "12:03"))
        # ...and are ignored while a valid interval in the same string wins
        self.assertTrue(
            in_range(to_min("11:00"), to_min("12:00"), "10:30-14:00, 12:03"))

        # parse_hours: first span wins across comma intervals
        self.assertEqual(parse_hours([spec]), (to_min("10:30"), to_min("14:00")))
        self.assertEqual(parse_hours(["12:03", spec]),
                         (to_min("10:30"), to_min("14:00")))
        self.assertIsNone(parse_hours(["12:03"]))

        # empty / unset is unchanged
        self.assertIsNone(parse_hours([]))
        self.assertIsNone(parse_hours(None))
        self.assertFalse(in_range(to_min("11:00"), to_min("12:00"), ""))


if __name__ == "__main__":
    unittest.main()
