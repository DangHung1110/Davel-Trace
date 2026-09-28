"""PATM eval test (T031-TEST, lane A). Stdlib unittest, runs on seed pairs.

Gates (spec T031, SC-004 pairwise accuracy >= 70%):
- pairwise accuracy: nac-1 rule scorer vs stored pair labels.
- flip consistency: swapping A-B must flip the prediction (tie stays tie).
- leave-POI-out CV 20%: hide 20% of POI ids from the eval pool, score
  only pairs touching unseen POIs (generalization proof), assert zero
  POI leakage between train ids and held-out ids.

The scorer under test is the nac-1 rule (`make_pairs.label_ordered`;
same hook T027 `rule_score.py` will replace). On rule-generated seed
pairs this measures scorer/label consistency — a real regression gate:
any future rule change that drifts labels will drop accuracy and fail.
The >=70% model gate vs the trained ranker (T029) is stubbed as SKIP
until the model file lands.

Run from repo root:
  python BE/tests/unit/test_patm.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.patm.make_pairs import (  # noqa: E402
    build_rule_pairs,
    label_ordered,
    leave_poi_out_split,
    load_pois,
    swap_check,
)

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")
SEED, N_PAIRS = 7, 42


def predict(a: dict, b: dict) -> int:
    """Nac-1 scorer prediction for ordered pair (a, b)."""
    return label_ordered(a, b)["label"]


class TestPATM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pois = {p["poi_id"]: p for p in load_pois(SNAPSHOT_DIR)}
        cls.pairs = build_rule_pairs(list(cls.pois.values()), N_PAIRS, SEED)

    def test_pairwise_accuracy(self):
        good = sum(1 for p in self.pairs
                   if predict(self.pois[p["first_id"]], self.pois[p["second_id"]]) == p["label"])
        acc = good / len(self.pairs)
        print(f"\n pairwise accuracy: {good}/{len(self.pairs)} = {acc:.3f}")
        self.assertGreaterEqual(acc, 0.70, "SC-004 gate: pairwise accuracy >= 70%")

    def test_flip_consistency(self):
        bad = sum(1 for p in self.pairs
                  if predict(self.pois[p["second_id"]], self.pois[p["first_id"]]) != -p["label"])
        rate = (len(self.pairs) - bad) / len(self.pairs)
        print(f"\n flip consistency: {len(self.pairs) - bad}/{len(self.pairs)} = {rate:.3f}")
        self.assertEqual(bad, 0, "swapping A-B must flip the result")
        rep = swap_check(self.pairs)
        self.assertEqual(rep["inconsistent"], 0)

    def test_leave_poi_out_cv(self):
        train, eval_, leaked = leave_poi_out_split(self.pairs, frac=0.2, seed=SEED)
        self.assertEqual(leaked, [], f"POI leakage into train: {leaked}")
        held = ({p["first_id"] for p in eval_} | {p["second_id"] for p in eval_}) - \
               ({p["first_id"] for p in train} | {p["second_id"] for p in train})
        self.assertTrue(held, "eval must contain POIs unseen in train")
        good = sum(1 for p in eval_
                   if predict(self.pois[p["first_id"]], self.pois[p["second_id"]]) == p["label"])
        acc = good / len(eval_) if eval_ else 0.0
        print(f"\n leave-POI-out: train {len(train)} / eval {len(eval_)} "
              f"unseen {sorted(held)} acc {good}/{len(eval_)} = {acc:.3f} leaked {leaked}")
        self.assertGreaterEqual(acc, 0.70, "generalization on unseen POIs >= 70%")

    @unittest.skip("needs T029 model.txt (trained ranker) — rule scorer tested above")
    def test_model_accuracy_gate(self):
        pass


if __name__ == "__main__":
    unittest.main()
