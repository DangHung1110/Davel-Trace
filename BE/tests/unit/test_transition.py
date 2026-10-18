"""Unit test for transition scorer + precedence wiring (T030, closes US3).

- score form (float) + rule-path speed (<5ms mean over 200 calls).
- env-aware source: lane-A T026+T062 extractor + v4 model -> "model";
  a clean checkout (no BE/ml/patm) -> "rule" with the 16f stub.
- model path works (micro LightGBM trained to TEMP in-test).
- real v4 model scores a finite q_ij when present.
- precedence respected: hiking->beach order wins when both feasible;
  flipped precedence flips the order.

Run from repo root: python BE/tests/unit/test_transition.py -v
"""

import math
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import scorer  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402


def _lane_a_ok() -> bool:
    try:
        from BE.ml.patm.features import extract  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - clean checkout has no BE/ml/patm
        return False


LANE_A_OK = _lane_a_ok()

H = 60
HILL = {"poi_id": "hill", "type": "nature", "intensity": 3, "rating": 4.7,
        "price_level": 1, "visit_min": {"p50": 120}, "weather_sensitive": True,
        "tags": ["leo núi"]}
BEACH = {"poi_id": "beach", "type": "beach", "intensity": 2, "rating": 4.6,
         "price_level": 1, "visit_min": {"p50": 120}, "weather_sensitive": True,
         "tags": ["biển"]}
NOODLE = {"poi_id": "noodle", "type": "restaurant", "intensity": 1,
          "price_level": 2, "visit_min": {"p50": 60}, "rating": 4.5,
          "weather_sensitive": False, "tags": ["ăn"]}
BY_ID = {"hill": HILL, "beach": BEACH, "noodle": NOODLE}

POIS = [StubPOI("hill", 120, 5 * H, 12 * H, 1.0),
        StubPOI("beach", 120, 6 * H, 19 * H, 1.0),
        StubPOI("noodle", 60, 7 * H, 21 * H, 1.0)]
TRAVEL = {(a, b): 10 for a in ["depot", "hill", "beach", "noodle"]
          for b in ("hill", "beach", "noodle") if a != b}
TRIP = StubTrip(7 * H, 18 * H)


def order_of(out: dict) -> list[str]:
    return [a["poi_id"] for a in out["itinerary"]["activities"]]


class TestTransition(unittest.TestCase):
    def test_score_form_and_source(self):
        s = scorer.score_transition(HILL, BEACH)
        self.assertIsInstance(s, float)
        expected = "model" if LANE_A_OK and os.path.exists(scorer.MODEL_PATH) else "rule"
        self.assertEqual(scorer.describe()["backend"], expected)
        self.assertEqual(scorer.describe()["n_features"], 17 if LANE_A_OK else 16)

    def test_rule_path_fast(self):
        saved = (scorer._bst, scorer._backend, scorer._note)
        scorer._bst, scorer._backend, scorer._note = None, "rule", ""
        try:
            t0 = time.monotonic()
            for _ in range(200):
                scorer.score_transition(HILL, BEACH,
                                        model_path=os.path.join("no", "such", "model.txt"))
            mean_ms = (time.monotonic() - t0) / 200 * 1000
        finally:
            scorer._bst, scorer._backend, scorer._note = saved
        print(f"\n rule mean {mean_ms:.3f}ms/call")
        self.assertLess(mean_ms, 5.0)

    def test_model_path(self):
        import lightgbm as lgb
        import numpy as np
        width = scorer._lane_a_extract()[1]
        tmp = os.path.join(tempfile.mkdtemp(prefix="sc_"), "model.txt")
        X = np.array([[scorer._features(HILL, BEACH, None, None)],
                      [scorer._features(BEACH, HILL, None, None)]] * 10,
                     dtype=float).reshape(20, width)
        dtr = lgb.Dataset(X, [1] * 10 + [0] * 10)
        lgb.train({"objective": "binary", "verbosity": -1, "num_leaves": 3},
                  dtr, num_boost_round=5).save_model(tmp)
        s = scorer.score_transition(HILL, BEACH, model_path=tmp)
        self.assertIsInstance(s, float)
        scorer._bst, scorer._backend, scorer._note = None, "rule", ""  # reset global

    @unittest.skipUnless(os.path.exists(scorer.MODEL_PATH) and LANE_A_OK,
                         "v4 model or lane-A extractor not present")
    def test_real_v4_model(self):
        scorer._bst, scorer._backend, scorer._note = None, "rule", ""
        try:
            self.assertEqual(scorer.describe()["backend"], "model")
            s = scorer.score_transition(HILL, BEACH)
            self.assertIsInstance(s, float)
            self.assertTrue(math.isfinite(s))
            q = scorer.edge_scores(["hill", "beach"], BY_ID)
            self.assertEqual(set(q), {("hill", "beach"), ("beach", "hill")})
            for v in q.values():
                self.assertTrue(math.isfinite(v))
        finally:
            scorer._bst, scorer._backend, scorer._note = None, "rule", ""

    def test_precedence_hill_before_beach(self):
        q = scorer.edge_scores(["hill", "beach", "noodle"], BY_ID)
        out = optimize(POIS, TRAVEL, TRIP, require_all=False,
                       edge_scores={**q, ("hill", "beach"): 5.0},
                       precedence=[("hill", "beach")])
        order = order_of(out)
        self.assertLess(order.index("hill"), order.index("beach"))
        print(f"\n precedence order: {order}")

    def test_flipped_precedence_flips(self):
        out = optimize(POIS, TRAVEL, TRIP,
                       edge_scores={("beach", "hill"): 5.0},
                       precedence=[("beach", "hill")])
        order = order_of(out)
        self.assertLess(order.index("beach"), order.index("hill"))


if __name__ == "__main__":
    unittest.main()
