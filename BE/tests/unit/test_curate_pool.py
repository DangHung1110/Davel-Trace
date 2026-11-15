"""Unit test for offline LLM-assisted candidate curation (no network, no LLM).

Pins the safety contract: one prompt, strict JSON normalisation, unknown ids
rejected, skipped ids reported (never a silent keep), and the snapshot is not
mutated — the report is evidence only.

Run from repo root: python BE/tests/unit/test_curate_pool.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.data import curate_pool as cp  # noqa: E402

CANDIDATES = [
    {"poi_id": "r1", "name": "Hải sản My Hanh", "type": "Nhà hàng hải sản",
     "cat": "restaurant", "tags": ["Hải sản"], "rating": 4.7},
    {"poi_id": "r2", "name": "Nhà hàng chay Shanti", "type": "Nhà hàng",
     "cat": "restaurant", "tags": ["Chay"], "rating": 4.9},
    {"poi_id": "b1", "name": "Bãi biển Sơn Trà", "type": "Bãi biển",
     "cat": "beach", "tags": [], "rating": 4.8},
]
PROFILE = {"food_prefs": ["hải sản"], "activities": [], "must_avoid": []}


def fake_complete(prompt):
    assert "/no_think" in prompt
    assert "Hải sản My Hanh" in prompt
    assert '"drop"' in prompt  # double-quoted JSON example
    return {"decisions": [
        {"poi_id": "r1", "keep": True, "reason": "dung hai san"},
        # taste mismatch: vegan vs seafood-only profile -> drop
        {"poi_id": "r2", "keep": False, "reason": "chay, lech khu vau hai san"},
        {"poi_id": "ghost", "keep": True, "reason": "khong co trong pool"},
        # b1 intentionally skipped -> must be reported, not silently kept
    ]}


class TestCuration(unittest.TestCase):
    def test_normalises_decisions_and_reports_gaps(self):
        report = cp.curate(CANDIDATES, PROFILE, complete=fake_complete,
                           tag="seafood", snapshot="danang-v1")
        self.assertEqual(report["candidate_count"], 3)
        self.assertEqual(report["decisions"]["r1"],
                         {"keep": True, "drop": False, "reason": "dung hai san"})
        self.assertTrue(report["decisions"]["r2"]["drop"])
        self.assertNotIn("ghost", report["decisions"])
        self.assertEqual(report["unknown_ids"], ["ghost"])
        self.assertEqual(report["missing_ids"], ["b1"])
        self.assertEqual([d["poi_id"] for d in report["drops"]], ["r2"])
        self.assertEqual(report["dropped"], 1)
        self.assertEqual(report["kept"], 1)

    def test_report_is_evidence_only(self):
        report = cp.curate(CANDIDATES, PROFILE, complete=fake_complete)
        self.assertFalse(report["applied"])
        self.assertIn("auto-applied", report["note"])
        self.assertEqual(report["profile"]["food_prefs"], ["hải sản"])

    def test_tolerates_mapping_shape(self):
        def complete(_prompt):
            return {"decisions": {"r1": {"keep": True, "reason": "ok"}}}
        report = cp.curate(CANDIDATES, PROFILE, complete=complete)
        self.assertTrue(report["decisions"]["r1"]["keep"])
        self.assertEqual(sorted(report["missing_ids"]), ["b1", "r2"])

    def test_drop_flag_without_keep_is_read(self):
        def complete(_prompt):
            return {"decisions": [{"poi_id": "r2", "drop": True,
                                   "reason": "sai khau vi"}]}
        report = cp.curate(CANDIDATES, PROFILE, complete=complete)
        self.assertFalse(report["decisions"]["r2"]["keep"])
        self.assertTrue(report["decisions"]["r2"]["drop"])

    def test_drop_list_shape_marks_unflagged_as_keep(self):
        def complete(_prompt):
            return {"drop": [{"poi_id": "r2", "reason": "chay, lech hai san"}]}
        report = cp.curate(CANDIDATES, PROFILE, complete=complete)
        self.assertEqual(report["response_shape"], "drop_list")
        self.assertEqual(report["decisions"]["r2"],
                         {"keep": False, "drop": True,
                          "reason": "chay, lech hai san"})
        self.assertTrue(report["decisions"]["r1"]["keep"])
        self.assertTrue(report["decisions"]["b1"]["keep"])
        self.assertEqual(report["missing_ids"], [])
        self.assertEqual([d["poi_id"] for d in report["drops"]], ["r2"])

    def test_prompt_lists_profile_and_candidates(self):
        prompt = cp.build_prompt(CANDIDATES, PROFILE)
        self.assertIn("hải sản", prompt)
        for pid in ("r1", "r2", "b1"):
            self.assertIn(pid, prompt)
        self.assertTrue(prompt.rstrip().endswith("/no_think"))


if __name__ == "__main__":
    unittest.main()
