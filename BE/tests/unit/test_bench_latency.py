"""Latency summary of BE/tools/bench_latency.py."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.tools.bench_latency import summarize  # noqa: E402


class TestSummarize(unittest.TestCase):
    def test_nearest_rank_p95(self):
        report = summarize([float(s) for s in range(1, 21)])
        self.assertEqual(report, {"requests": 20, "median_s": 10.5, "p95_s": 19.0, "max_s": 20.0})

    def test_one_request(self):
        self.assertEqual(summarize([2.0])["p95_s"], 2.0)


if __name__ == "__main__":
    unittest.main()
