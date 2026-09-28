"""Unit test for event classifier S2 (T044). Stdlib unittest.

Gates: overall acc >= 0.85, min per-class F1 >= 0.70 on template +
rule-based-variant data (10 classes). Trains in-process (CPU seconds).

Run from repo root: python BE/tests/unit/test_event_clf.py -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.event_clf.paraphrase import build_dataset, variants  # noqa: E402
from BE.ml.event_clf.templates import EVENT_TYPES, TEMPLATES  # noqa: E402
from BE.ml.event_clf.train import LABELS, predict, train_eval  # noqa: E402
import random  # noqa: E402

N_PER_CLASS, SEED = 40, 7


class TestEventClf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_dataset(N_PER_CLASS, SEED)
        cls.tmp = tempfile.mkdtemp(prefix="evt_")
        cls.rep = train_eval([t for t, _ in cls.data], [l for _, l in cls.data],
                             SEED, cls.tmp)

    def test_10_types_covered_balanced(self):
        self.assertEqual(len(EVENT_TYPES), 10)
        self.assertEqual(set(TEMPLATES), set(EVENT_TYPES))
        counts = {}
        for _, l in self.data:
            counts[l] = counts.get(l, 0) + 1
        self.assertTrue(all(v == N_PER_CLASS for v in counts.values()), counts)

    def test_variants_keep_meaning_diversify(self):
        rng = random.Random(SEED)
        seen = set()
        for tpl in TEMPLATES["rain"][:2]:
            for v in variants(tpl, rng, k=3):
                seen.add(v)
        self.assertGreater(len(seen), 4)  # real surface diversity

    def test_accuracy_gate(self):
        print(f"\n acc {self.rep['acc']} macro-F1 {self.rep['macro_f1']} "
              f"min-F1 {self.rep['min_f1']}")
        self.assertGreaterEqual(self.rep["acc"], 0.85)
        self.assertGreaterEqual(self.rep["min_f1"], 0.70)

    def test_reload_predict_roundtrip(self):
        for text, label in (("trời mưa to quá, tìm chỗ trong nhà đi", "rain"),
                            ("tôi mệt quá, giảm cường độ đi", "tired"),
                            ("kẹt xe cứng ở cầu, tới nơi trễ chắc", "traffic")):
            self.assertEqual(predict(text, self.tmp), label, text)

    def test_labels_match_spec_types(self):
        self.assertEqual(LABELS, list(EVENT_TYPES))


if __name__ == "__main__":
    unittest.main()
