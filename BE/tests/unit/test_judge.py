"""Unit test for LLM judge (T050). Mock clients only — no network, no billing.

Covers: swap-consistent accept, swap-inconsistent discard, bad-JSON
discard, transport-error path, cost-log correctness, batch kept counts.

Run from repo root: python BE/tests/unit/test_judge.py -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.eval.judge import CostLog, judge_batch, judge_pair  # noqa: E402

A = {"poi_id": "son-tra", "name": "Son Tra", "type": "nature",
     "rating": 4.7, "tags": ["rong"]}
B = {"poi_id": "my-khe", "name": "My Khe", "type": "beach",
     "rating": 4.6, "tags": ["bien"]}


def _resp(text: str, pt: int = 100, ct: int = 10) -> dict:
    return {"text": text, "prompt_tokens": pt, "completion_tokens": ct}


def client_sontra_wins(prompt: str) -> dict:
    first_line = [ln for ln in prompt.splitlines() if ln.startswith("A:")][0]
    return _resp('{"winner": "A"}' if "Son Tra" in first_line else '{"winner": "B"}')


def client_tie(prompt: str) -> dict:
    return _resp('{"winner": "tie"}')


def client_flipflop(prompt: str) -> dict:
    return _resp('{"winner": "A"}')  # same answer both orders -> inconsistent


def client_garbage(prompt: str) -> dict:
    return _resp('chac la A ngon hon!!')


def client_down(prompt: str) -> dict:
    raise ConnectionError("ollama not running")


class TestJudge(unittest.TestCase):
    def test_swap_consistent_accepted(self):
        r = judge_pair(A, B, client=client_sontra_wins)
        self.assertEqual(r, {"verdict": 1, "reason": "ok"})

    def test_swap_tie_accepted(self):
        r = judge_pair(A, B, client=client_tie)
        self.assertEqual(r, {"verdict": 0, "reason": "ok"})

    def test_swap_inconsistent_discarded(self):
        r = judge_pair(A, B, client=client_flipflop)
        self.assertIsNone(r["verdict"])
        self.assertEqual(r["reason"], "inconsistent")

    def test_bad_json_discarded(self):
        r = judge_pair(A, B, client=client_garbage)
        self.assertIsNone(r["verdict"])
        self.assertEqual(r["reason"], "bad_json")

    def test_transport_error_path(self):
        r = judge_pair(A, B, client=client_down)
        self.assertIsNone(r["verdict"])
        self.assertEqual(r["reason"], "transport")

    def test_cost_log_correct(self):
        path = os.path.join(tempfile.mkdtemp(prefix="judge_"), "cost.jsonl")
        cost = CostLog(path, model="qwen3:14b", price_per_1k_usd=0.0)
        judge_pair(A, B, client=client_sontra_wins, cost=cost)
        self.assertEqual(cost.totals, {"prompt_tokens": 200, "completion_tokens": 20})
        with open(path, encoding="utf-8") as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["model"], "qwen3:14b")
        self.assertEqual(entry["est_usd"], 0.0)
        self.assertEqual(entry["prompt_tokens"], 200)

    def test_batch_kept_counts(self):
        pairs = [{"pair_id": "p1", "first_id": "son-tra", "second_id": "my-khe"},
                 {"pair_id": "p2", "first_id": "my-khe", "second_id": "son-tra"}]
        pois = {"son-tra": A, "my-khe": B}
        out = judge_batch(pairs, pois, client=client_sontra_wins)
        self.assertEqual([o["judge_verdict"] for o in out], [1, -1])
        self.assertTrue(all(o["judge_reason"] == "ok" for o in out))
        out2 = judge_batch(pairs, pois, client=client_garbage)
        self.assertTrue(all(o["judge_verdict"] is None for o in out2))


if __name__ == "__main__":
    unittest.main()
