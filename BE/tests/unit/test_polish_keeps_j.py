"""`profiles._polished` keeps the solver's times when re-timing would lower J (step 2b).

The re-timing (`route_order.best_order`: least driving and dead time) looks only at
the clock. On the audit + gold requests it lowered J on about half the days, moving
stops out of the hours the solver chose for them, some into the rain
(reports/objective_v1/features_step2.md). The pilot's judge sees the shown day, so a
re-timing that J rates lower is dropped and the solver's own day is shown.

Run: python -m pytest BE/tests/unit/test_polish_keeps_j.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import profiles, route_order  # noqa: E402
from BE.app.services.optimizer import STOP_OVERHEAD_MIN, StubPOI  # noqa: E402

H = 60
MUSEUM = StubPOI("museum", visit_min=60, open_min=8 * H, close_min=17 * H, category="museum")
LUNCH = StubPOI("lunch", visit_min=40, open_min=10 * H + 30, close_min=15 * H, restaurant=True,
                category="restaurant")
TRIP = {"start_time": "08:00", "end_time": "20:00"}
TRAVEL = {("museum", "lunch"): 5, ("lunch", "museum"): 5}
# The solver's day: the museum at opening, then a long wait for lunch.
ACTS = [{"poi_id": "museum", "start": "08:00", "end": "09:00"},
        {"poi_id": "lunch", "start": "11:30", "end": "12:10"}]
KEEP_ORDER = [("museum", "lunch")]


def _starts(day):
    return [act["start"] for act in day]


class TestPolishKeepsJ(unittest.TestCase):
    def test_the_re_timing_would_move_this_day(self):
        rows = route_order.best_order(ACTS, {"museum": MUSEUM, "lunch": LUNCH}, TRAVEL,
                                      8 * H, 20 * H, STOP_OVERHEAD_MIN, precedence=KEEP_ORDER)
        self.assertIsNotNone(rows)
        self.assertNotEqual(_starts(rows), _starts(ACTS))

    def test_a_re_timing_that_lowers_j_is_dropped(self):
        def j_of(day):  # J rates the solver's hours best, as CP-SAT chose them
            return 0.0 if _starts(day) == _starts(ACTS) else -0.5

        out = profiles._polished([dict(a) for a in ACTS], [MUSEUM, LUNCH], TRAVEL, TRIP, {},
                                 KEEP_ORDER, {}, {}, None, j_of=j_of)
        self.assertEqual(out, ACTS)


if __name__ == "__main__":
    unittest.main()
