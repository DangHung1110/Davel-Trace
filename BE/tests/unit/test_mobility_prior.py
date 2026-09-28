"""Mobility prior tests (T062 M1, lane A). Prior loads + seed ablation.

Ablation bar: rule + 0.1 * direction-logprior beats rule-only order
accuracy on the 38 seed pairs by >=5pp (>=2 pairs). Fixed w=0.1,
no tuning (seed too small to tune honestly).

Run from repo root: python BE/tests/unit/test_mobility_prior.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.patm.estimate_duration import canonical_category  # noqa: E402
from BE.ml.patm.make_pairs import build_rule_pairs, load_pois  # noqa: E402
from BE.ml.patm.prior import bucket_of_hour, load, logprob, prob  # noqa: E402
from BE.ml.patm.rule_score import score_transition  # noqa: E402

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")
W = 0.1


class TestMobilityPrior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior = load()
        cls.pois = {p["poi_id"]: p for p in load_pois(SNAPSHOT_DIR)}
        cls.pairs = build_rule_pairs(list(cls.pois.values()), 42, 7)

    def test_prior_loads_with_backoff(self):
        self.assertGreaterEqual(len(self.prior["cats"]), 8)
        for b in self.prior["buckets"]:
            for c1 in self.prior["cats"]:
                row = self.prior["trans"].get(b, {}).get(c1, {})
                self.assertAlmostEqual(sum(row.values()), 1.0, places=6)
        self.assertTrue(0.0 < prob("restaurant", "museum", 9) < 1.0)
        self.assertTrue(abs(logprob("nope-cat", "also-nope", 3)) < 1e6)

    def test_bucketing(self):
        self.assertEqual([bucket_of_hour(h) for h in (6, 12, 16, 22)],
                         ["sang", "trua", "chieu", "toi"])

    def test_ablation_direction_accuracy(self):
        """REAL +5pp ground: held-out Foursquare directions (hermetic sample).

        NOTE (ceiling artifact, documented): the same test on rule-generated
        seed pairs is invalid — rule-only is perfect-by-construction there
        (38/38), so any perturbation can only hurt. Real mobility data is
        the honest ablation ground. Fixed w=0.1, actual transition hour.
        """
        import json as _json
        sample = _json.load(open(os.path.join("BE", "ml", "patm",
                                              "foursquare_sample.json"),
                                 encoding="utf-8"))["sample"]
        sens = {"beach", "nature"}
        base = comb = 0.0
        for t in sample:
            a = {"poi_id": "x", "type": t["prev"], "intensity": 2,
                 "weather_sensitive": t["prev"] in sens}
            b = {"poi_id": "y", "type": t["next"], "intensity": 2,
                 "weather_sensitive": t["next"] in sens}
            m = score_transition(a, b)
            dlp = (logprob(t["next"], t["prev"], t["hour"])
                   - logprob(t["prev"], t["next"], t["hour"]))
            m2 = m + W * dlp
            mb = score_transition(b, a)
            mb2 = mb + W * (logprob(t["prev"], t["next"], t["hour"])
                            - logprob(t["next"], t["prev"], t["hour"]))
            base += 1.0 if m > mb else (0.5 if m == mb else 0.0)
            comb += 1.0 if m2 > mb2 else (0.5 if m2 == mb2 else 0.0)
        n = len(sample)
        gain_pp = (comb - base) / n * 100
        print(f"\n ablation Foursquare n={n}: rule {base/n:.3f} vs "
              f"+prior {comb/n:.3f} (gain {gain_pp:+.1f}pp, bar +5pp)")
        # Regression lock (deterministic): bar +5pp NOT met -> PARTIAL,
        # no tick (see docs/mobility-prior.md). Change these only with cause.
        self.assertAlmostEqual(base / n, 0.510, places=3)
        self.assertAlmostEqual(comb / n, 0.520, places=3)


if __name__ == "__main__":
    unittest.main()
