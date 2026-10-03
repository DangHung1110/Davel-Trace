"""Unit test for tier-1 metrics (T049). Stdlib unittest, seed danang-v1.

Good plan passes the gate with full soft scores; each tampered plan
fails with its NAMED violation and gets no soft scores (contracts/api.md).

Run from repo root: python BE/tests/unit/test_metrics.py -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.eval.metrics import GATE_CHECKS, evaluate, vroh  # noqa: E402

SNAPSHOT_DIR = os.path.join("data", "snapshots", "danang-v1")


def _mm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _hh(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def chain(ids: list[str], pois: dict, matrix: dict, start: str = "07:30",
          gap_pad: int = 5, evidence: bool = True) -> list[dict]:
    """Chain activities with p50 durations + matrix gaps (feasible base)."""
    acts, cur = [], _mm(start)
    prev = None
    for pid in ids:
        if prev is not None:
            cur += matrix[f"{prev}->{pid}"]["minutes"] + gap_pad
        dur = pois[pid]["visit_min"]["p50"]
        act = {"poi_id": pid, "start": _hh(cur), "end": _hh(cur + dur)}
        if evidence:
            act["explanation"] = {"evidence": [f"seed:{pid}"]}
        acts.append(act)
        prev, cur = pid, cur + dur
    return acts


class TestMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SNAPSHOT_DIR, "pois.json"), encoding="utf-8") as f:
            cls.pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
        with open(os.path.join(SNAPSHOT_DIR, "matrix.json"), encoding="utf-8") as f:
            cls.matrix = json.load(f)["cells"]
        cls.trip = {"budget": 3000000, "start_time": "07:00", "end_time": "18:00",
                    "must_visit": ["son-tra"], "avoid": [],
                    "order_prefs": [["son-tra", "cham-museum"]]}
        cls.good = {"activities": chain(
            ["son-tra", "mi-quang-ba-mua", "cham-museum"], cls.pois, cls.matrix)}

    def test_good_plan_passes_gate_with_soft(self):
        rep = evaluate(self.good, self.trip, self.pois, self.matrix)
        self.assertEqual(rep["gate"], {"passed": True, "violations": []})
        self.assertEqual(set(rep["soft"]), {"STR", "DTU", "SSR", "CSM", "EDI", "AQE"})
        self.assertEqual(rep["soft"]["STR"], 1.0)
        self.assertEqual(rep["soft"]["SSR"], 1.0)
        self.assertEqual(rep["soft"]["EDI"], 1.0)
        self.assertEqual(rep["soft"]["AQE"], round((4.7 + 4.5 + 4.4) / 3 / 5, 3))
        print(f"\n good soft: {rep['soft']}")

    def test_closed_poi_fails_vroh(self):
        bad = {"activities": [{"poi_id": "cham-museum",
                               "start": "18:00", "end": "19:30"}]}
        trip = dict(self.trip, start_time="07:00", end_time="20:00", must_visit=[])
        rep = evaluate(bad, trip, self.pois, self.matrix)
        self.assertFalse(rep["gate"]["passed"])
        self.assertIn("VROH", rep["gate"]["violations"])
        self.assertEqual(rep["soft"], {})

    def test_over_budget_fails_bcs(self):
        trip = dict(self.trip, budget=50000)
        rep = evaluate(self.good, trip, self.pois, self.matrix)
        self.assertFalse(rep["gate"]["passed"])
        self.assertIn("BCS", rep["gate"]["violations"])
        self.assertEqual(rep["soft"], {})

    def test_overlap_fails_tcs(self):
        bad = {"activities": [
            {"poi_id": "son-tra", "start": "07:30", "end": "11:24"},
            {"poi_id": "my-khe", "start": "10:00", "end": "12:00"}]}
        trip = dict(self.trip, must_visit=[])
        rep = evaluate(bad, trip, self.pois, self.matrix)
        self.assertIn("TCS", rep["gate"]["violations"])
        self.assertEqual(rep["soft"], {})

    def test_unknown_poi_fails_far(self):
        bad = {"activities": [{"poi_id": "ghost-poi",
                               "start": "08:00", "end": "09:00"}]}
        trip = dict(self.trip, must_visit=[])
        rep = evaluate(bad, trip, self.pois, self.matrix)
        self.assertIn("FAR", rep["gate"]["violations"])
        self.assertEqual(rep["soft"], {})

    def test_avoid_violation_fails_hcs(self):
        bad = {"activities": [{"poi_id": "my-khe",
                               "start": "08:00", "end": "10:00"}]}
        trip = dict(self.trip, must_visit=[], avoid=["my-khe"],
                    order_prefs=[])
        rep = evaluate(bad, trip, self.pois, self.matrix)
        self.assertIn("HCS", rep["gate"]["violations"])
        self.assertEqual(rep["soft"], {})

    def test_all_metric_fns_callable(self):
        self.assertEqual(len(GATE_CHECKS), 5)
        for _, fn, _ in GATE_CHECKS:
            fn(self.good, self.trip, self.pois, self.matrix)

    def test_multi_interval_hours_parse(self):
        def score(activities, hours):
            return vroh(
                {"activities": activities}, {},
                {"poi": {"opening_hours": hours}}, {},
            )

        multi_interval = ["10:30-14:00, 16:30-22:30"]
        self.assertAlmostEqual(score([
            {"poi_id": "poi", "start": "11:00", "end": "12:00"},
            {"poi_id": "poi", "start": "17:00", "end": "18:00"},
            {"poi_id": "poi", "start": "15:00", "end": "16:00"},
        ], multi_interval), 1 / 3)

        overnight_and_daytime = ["22:00-02:00, 08:00-12:00"]
        self.assertEqual(score([
            {"poi_id": "poi", "start": "23:00", "end": "01:00"},
            {"poi_id": "poi", "start": "09:00", "end": "10:00"},
        ], overnight_and_daytime), 0.0)

        # A single-time fragment is not an interval and is treated as closed.
        self.assertEqual(score([
            {"poi_id": "poi", "start": "12:03", "end": "12:04"},
        ], ["12:03"]), 1.0)

        # An empty hours list continues to mean that no hours constraint exists.
        self.assertEqual(score([
            {"poi_id": "poi", "start": "12:03", "end": "12:04"},
        ], []), 0.0)


if __name__ == "__main__":
    unittest.main()
