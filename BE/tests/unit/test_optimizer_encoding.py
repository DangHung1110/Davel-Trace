"""How the optimizer encodes time-window tests and the A2 restaurant pairs.

Both encodings were rewritten for the search LP (the 9 s request of
BE/tools/bench_latency.py, 25/11) and must keep the exact meaning of the old ones:
- `_window_hits` decides a hit from the node's opening windows when every window
  starts its visits wholly inside or wholly outside the asked range, and reifies on
  t[i] otherwise: checked here against the definition on every start minute;
- A2 charges every pair of visited restaurants, whatever their hours (what the
  per-pair term always charged): R restaurants cost R(R-1)/2 pairs.

Run from repo root: python -m pytest BE/tests/unit/test_optimizer_encoding.py
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from ortools.sat.python import cp_model  # noqa: E402

from BE.app.services import optimizer as opt  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402

H = 60


class _Collect(cp_model.CpSolverSolutionCallback):
    def __init__(self, t, visit, hit):
        super().__init__()
        self.t, self.visit, self.hit, self.rows = t, visit, hit, []

    def on_solution_callback(self):
        self.rows.append((self.Value(self.t), self.Value(self.visit), self.Value(self.hit)))


def _node(windows, dur, first, last_end):
    """A one-node model with the optimizer's window constraints (optimize, visit loop)."""
    m = cp_model.CpModel()
    t = m.NewIntVar(first, last_end, "t")
    visit = m.NewBoolVar("visit")
    if len(windows) == 1:
        (lo, hi), = windows
        m.Add(lo <= t).OnlyEnforceIf(visit)
        m.Add(t <= hi - dur).OnlyEnforceIf(visit)
        picks = [visit]
    else:
        picks = []
        for k, (lo, hi) in enumerate(windows):
            pick = m.NewBoolVar(f"win_{k}")
            m.Add(lo <= t).OnlyEnforceIf(pick)
            m.Add(t <= hi - dur).OnlyEnforceIf(pick)
            picks.append(pick)
        m.Add(sum(picks) == visit)
    m.Add(t + dur <= last_end).OnlyEnforceIf(visit)
    return m, t, visit, picks


class TestWindowHitsExact(unittest.TestCase):
    """hit == visit AND lo <= t + offset < hi, on every start the model allows."""

    DAY = (0, 300)
    CASES = [  # (windows, visit length, asked range, probe offset)
        (((30, 110), (150, 260)), 20, (30, 110), 0),    # lunch window: wholly inside
        (((30, 110), (150, 260)), 20, (150, 260), 0),   # dinner window: wholly inside
        (((30, 110), (150, 260)), 20, (60, 170), 0),    # straddles both windows
        (((30, 110), (150, 260)), 20, (0, 30), 0),      # before both
        (((30, 110), (150, 260)), 20, (90, 91), 0),     # the last start of a window
        (((30, 110), (150, 260)), 20, (91, 150), 0),    # between the windows
        (((40, 200),), 30, (40, 171), 0),               # one window, its last start included
        (((40, 200),), 30, (40, 170), 0),               # ... and excluded: straddles
        (((40, 200),), 30, (100, 300), 0),              # one window, straddles
        (((40, 200),), 30, (0, 400), 0),                # the whole day
        (((40, 60), (100, 120)), 30, (0, 300), 0),      # a window too short for the visit
        (((30, 110), (150, 260)), 20, (35, 116), 5),    # a probe 5 minutes into the visit
        (((30, 110), (150, 260)), 20, (35, 115), 5),    # ... one minute short: straddles
    ]

    def _rows(self, windows, dur, lo, hi, offset):
        first, last_end = self.DAY
        m, t, visit, picks = _node(windows, dur, first, last_end)
        spans = opt._start_spans(windows, dur, first, last_end, picks)
        hit = opt._window_hits(m, {0: t}, {0: visit}, 0, lo, hi, "q", spans, offset=offset)
        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        solver.parameters.num_search_workers = 1
        rows = _Collect(t, visit, hit)
        self.assertEqual(solver.Solve(m, rows), cp_model.OPTIMAL)
        return rows.rows

    def test_hit_matches_its_definition_on_every_start(self):
        for windows, dur, (lo, hi), offset in self.CASES:
            with self.subTest(windows=windows, dur=dur, asked=(lo, hi), offset=offset):
                rows = self._rows(windows, dur, lo, hi, offset)
                seen = set()
                for start, visited, hit in rows:
                    want = int(bool(visited) and lo <= start + offset < hi)
                    self.assertEqual(hit, want, (start, visited))
                    seen.add((start, visited))
                # one row per (start, visited): the hit is fixed by them, never free
                self.assertEqual(len(rows), len(seen))
                # every start a window allows is there (nothing cut off)
                allowed = {s for a, b in windows for s in range(a, b - dur + 1)
                           if s + dur <= self.DAY[1]}
                self.assertEqual({s for s, v in seen if v}, allowed)

    def test_a_meal_window_is_the_window_pick_itself(self):
        """No time disjunction for a restaurant open at lunch and at dinner: the hit is
        the literal that chose the window, which the search LP sees."""
        first, last_end = self.DAY
        windows = ((30, 110), (150, 260))
        m, _t, visit, picks = _node(windows, 20, first, last_end)
        spans = opt._start_spans(windows, 20, first, last_end, picks)
        before = len(m.Proto().constraints)
        self.assertIs(opt._window_hits(m, {0: _t}, {0: visit}, 0, 30, 110, "q", spans), picks[0])
        self.assertIs(opt._window_hits(m, {0: _t}, {0: visit}, 0, 150, 260, "q", spans), picks[1])
        self.assertEqual(len(m.Proto().constraints), before)


class TestA2EveryPair(unittest.TestCase):
    """A2 = one penalty per pair of visited restaurants, whatever their hours."""

    @staticmethod
    def _objective(n_restaurants: int, weight: float) -> float:
        # Breakfast, lunch and dinner places, hours apart: never two in one meal slot.
        spans = [(7 * H, 9 * H), (11 * H, 13 * H), (18 * H, 20 * H)][:n_restaurants]
        pois = [StubPOI(f"r{k}", 45, lo, hi, 5.0, restaurant=True, category="restaurant")
                for k, (lo, hi) in enumerate(spans)]
        travel = {(a.poi_id, b.poi_id): 10 for a in pois for b in pois if a is not b}
        with mock.patch.object(opt, "A2_PAIR_WEIGHT", weight):
            out = optimize(pois, travel, StubTrip(7 * H, 21 * H, ""), workers=1,
                           must_visit=[p.poi_id for p in pois])
        assert out["status"] == "optimal", out
        return out["objective"]

    def test_pairs_are_counted_whatever_the_hours(self):
        pair = 5.0 * 1000  # unit (top score) * A2_PAIR_WEIGHT * 1000
        for count, pairs in ((1, 0), (2, 1), (3, 3)):
            with self.subTest(restaurants=count):
                charged = self._objective(count, 0.0) - self._objective(count, 1.0)
                self.assertEqual(charged, pairs * pair)


if __name__ == "__main__":
    unittest.main()
