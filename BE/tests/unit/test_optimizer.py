"""Unit test for CP-SAT optimizer (T017). Fixture POIs/matrix (no lane data).

Covers: feasible schedule respects windows/gaps, timeout still returns
best-found, infeasible (require_all, contradictory windows) has reason.

Run from repo root: python BE/tests/unit/test_optimizer.py -v
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402

H = 60
POIS = [
    StubPOI("musu", visit_min=90, open_min=7 * H + 30, close_min=17 * H, score=3.0),
    StubPOI("beach", visit_min=120, open_min=6 * H, close_min=19 * H, score=5.0),
    StubPOI("noodle", visit_min=60, open_min=7 * H, close_min=21 * H, score=2.0),
    StubPOI("hill", visit_min=150, open_min=5 * H, close_min=18 * H, score=4.0),
    StubPOI("market", visit_min=60, open_min=6 * H, close_min=22 * H, score=1.0),
    StubPOI("bridge", visit_min=30, open_min=0, close_min=24 * H, score=1.0),
]
IDS = [p.poi_id for p in POIS]
TRAVEL = {(a, b): 10 for a in ["depot"] + IDS for b in IDS if a != b}
TRIP = StubTrip(start_min=7 * H, end_min=18 * H, origin_id="depot")


def to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


class TestOptimizer(unittest.TestCase):
    def test_feasible_respects_windows(self):
        out = optimize(POIS, TRAVEL, TRIP)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        acts = out["itinerary"]["activities"]
        self.assertGreater(len(acts), 0)
        by_id = {p.poi_id: p for p in POIS}
        prev_end = TRIP.start_min
        for k, a in enumerate(acts):
            p = by_id[a["poi_id"]]
            s, e = to_min(a["start"]), to_min(a["end"])
            self.assertGreaterEqual(s, p.open_min)
            self.assertLessEqual(e, min(p.close_min, TRIP.end_min))
            self.assertEqual(e - s, p.visit_min)
            if k:
                gap = s - prev_end
                need = TRAVEL[(acts[k - 1]["poi_id"], a["poi_id"])]
                self.assertGreaterEqual(gap, need)
            prev_end = e
        print(f"\n {out['status']}: {len(acts)} acts score "
              f"{out['itinerary']['total_score']} in {out['elapsed_s']}s")

    def test_timeout_returns_best_found(self):
        t0 = time.monotonic()
        out = optimize(POIS, TRAVEL, TRIP, timeout_s=5.0)
        dt = time.monotonic() - t0
        self.assertLess(dt, 8.0)
        self.assertIsNotNone(out["itinerary"])

    def test_infeasible_has_reason(self):
        bad = [StubPOI("x", visit_min=300, open_min=7 * H, close_min=8 * H),
               StubPOI("y", visit_min=300, open_min=9 * H, close_min=10 * H)]
        t = {("depot", pid): 120 for pid in ("x", "y")}
        t.update({(a, b): 120 for a in ("x", "y")
                  for b in ("x", "y") if a != b})
        out = optimize(bad, t, StubTrip(7 * H, 12 * H), require_all=True)
        self.assertEqual(out["status"], "infeasible")
        self.assertTrue(out["reason"])
        self.assertIsNone(out["itinerary"])

    def test_missing_travel_pair_is_infeasible_not_zero(self):
        poi = StubPOI("x", visit_min=60, open_min=7 * H, close_min=12 * H)
        out = optimize([poi], {("x", "depot"): 0},
                       StubTrip(7 * H, 12 * H), require_all=True)
        self.assertEqual(out["status"], "infeasible")
        self.assertIsNone(out["itinerary"])

    def test_origin_leg_uses_matrix(self):
        poi = StubPOI("x", visit_min=60, open_min=7 * H, close_min=12 * H)
        out = optimize([poi], {("depot", "x"): 45},
                       StubTrip(7 * H, 12 * H), require_all=True)
        self.assertIn(out["status"], ("optimal", "feasible-timeout"))
        self.assertGreaterEqual(to_min(out["itinerary"]["activities"][0]["start"]),
                                7 * H + 45)


if __name__ == "__main__":
    unittest.main()
