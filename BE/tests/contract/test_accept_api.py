"""Contract test for POST /v1/accept (NOTE(test-local) "Chốt plan" log).

Pins the 200 shape, the 400 validation envelope, and the exact JSONL line
schema written to BE/data/accepted_days.jsonl. The log path is redirected to
a temp file via ACCEPTED_DAYS_PATH so the repo file is never touched.

Run: python -m pytest BE/tests/contract/test_accept_api.py -q
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi.testclient import TestClient  # noqa: E402

from BE.app import main as main_mod  # noqa: E402

client = TestClient(main_mod.app, raise_server_exceptions=False)

PLANS = [
    {"itinerary_id": "plan-a", "profile": "savings",
     "activities": [{"poi_id": "mi-quang", "start": "08:00", "end": "09:00"}]},
    {"itinerary_id": "plan-b", "profile": "balanced",
     "activities": [{"poi_id": "cham-museum", "start": "09:00", "end": "10:30"}]},
]

LINE_KEYS = {"ts", "query", "profile", "picked_plan", "picked_index",
             "all_plan_ids", "note"}


class TestAcceptApi(unittest.TestCase):
    def setUp(self):
        fd, self.log = tempfile.mkstemp(suffix=".jsonl", prefix="accept-test-")
        os.close(fd)
        os.unlink(self.log)  # let the router create it
        self._old = os.environ.get("ACCEPTED_DAYS_PATH")
        os.environ["ACCEPTED_DAYS_PATH"] = self.log

    def tearDown(self):
        if self._old is None:
            os.environ.pop("ACCEPTED_DAYS_PATH", None)
        else:
            os.environ["ACCEPTED_DAYS_PATH"] = self._old
        if os.path.exists(self.log):
            os.unlink(self.log)

    def _lines(self) -> list[dict]:
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_happy_path_appends_line_and_returns_count(self):
        r = client.post("/v1/accept", json={
            "query": "di Da Nang 1 ngay thich hai san",
            "profile": "balanced",
            "plans": PLANS,
            "picked_index": 1,
            "note": "chot cho demo",
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"ok": True, "n": 1})

        lines = self._lines()
        self.assertEqual(len(lines), 1)
        entry = lines[0]
        self.assertEqual(set(entry), LINE_KEYS)
        self.assertEqual(entry["query"], "di Da Nang 1 ngay thich hai san")
        self.assertEqual(entry["profile"], "balanced")
        self.assertEqual(entry["picked_index"], 1)
        self.assertEqual(entry["picked_plan"], PLANS[1])
        self.assertEqual(entry["all_plan_ids"], ["plan-a", "plan-b"])
        self.assertEqual(entry["note"], "chot cho demo")
        self.assertIsInstance(entry["ts"], str)
        self.assertTrue(entry["ts"])

        # Second accept appends, never rewrites.
        r2 = client.post("/v1/accept", json={"query": "q2", "profile": "savings",
                                             "plans": PLANS, "picked_index": 0})
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json()["n"], 2)
        self.assertEqual(len(self._lines()), 2)
        self.assertEqual(self._lines()[1]["picked_plan"], PLANS[0])
        self.assertEqual(self._lines()[1]["note"], "")

    def test_out_of_range_index_is_400(self):
        for bad in (-1, 2):
            r = client.post("/v1/accept", json={
                "query": "q", "profile": "balanced", "plans": PLANS,
                "picked_index": bad,
            })
            self.assertEqual(r.status_code, 400, r.text)
            self.assertEqual(r.json()["error"], "VALIDATION_ERROR")
        self.assertFalse(os.path.exists(self.log), "400 must not write a line")

    def test_empty_plans_is_400(self):
        r = client.post("/v1/accept", json={"query": "q", "plans": [],
                                            "picked_index": 0})
        self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(r.json()["error"], "VALIDATION_ERROR")
        self.assertFalse(os.path.exists(self.log))


if __name__ == "__main__":
    unittest.main()
