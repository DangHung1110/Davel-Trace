"""Unit tests for the shadow LLM ranker (Hướng 3 / Hướng 6).

All judge calls are mocked — no network, no model billing.

Run from repo root:
    python -m pytest BE/tests/unit/test_ranker.py -q
"""

import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import ranker  # noqa: E402

PLANS = [
    {"itinerary_id": "plan-a", "total_cost": 300000, "travel_min": 20,
     "total_min": 300, "preference": 4.2, "passed": True, "violations": [],
     "activities": [{"poi_id": "p1", "start": "08:00", "end": "09:00"},
                    {"poi_id": "p2", "start": "09:20", "end": "10:00"}]},
    {"itinerary_id": "plan-b", "total_cost": 100000, "travel_min": 15,
     "total_min": 280, "preference": 4.5, "passed": True, "violations": [],
     "activities": [{"poi_id": "p3", "start": "08:00", "end": "09:00"},
                    {"poi_id": "p4", "start": "09:15", "end": "10:00"}]},
    {"itinerary_id": "plan-c", "total_cost": 200000, "travel_min": 25,
     "total_min": 320, "preference": 4.0, "passed": True, "violations": [],
     "activities": [{"poi_id": "p5", "start": "08:00", "end": "09:00"},
                    {"poi_id": "p6", "start": "09:25", "end": "10:00"}]},
]

REFERENCE = [
    {"plan_id": "plan-a", "feasible": True, "cost": 300000, "violations": [],
     "pois": [{"poi_id": "p1", "type": "beach", "rating": 4.2},
              {"poi_id": "p2", "type": "restaurant", "rating": 4.0}]},
    {"plan_id": "plan-b", "feasible": True, "cost": 100000, "violations": [],
     "pois": [{"poi_id": "p3", "name": "InterContinental", "type": "cafe",
               "rating": 4.5},
              {"poi_id": "p4", "type": "museum", "rating": 4.4}]},
    {"plan_id": "plan-c", "feasible": True, "cost": 200000, "violations": [],
     "pois": [{"poi_id": "p5", "type": "park", "rating": 4.1},
              {"poi_id": "p6", "type": "market", "rating": 4.0}]},
]

QUERY = {"city": "da-nang", "days": 1, "budget": 2000000,
         "activities": ["biển", "ăn"]}


# --------------------------------------------------------------------------
# judge mocks (read the rendered prompt only — plans are anonymised)
# --------------------------------------------------------------------------
def _block(prompt: str, label: str) -> str:
    match = re.search(
        rf"\[Plan {label}\]\n(.*?)(?=\n\n\[Plan|\n\n\[Reference checks\])",
        prompt, re.S)
    return match.group(1) if match else ""


def _cost(block: str) -> float:
    match = re.search(r"cost=(\d+(?:\.\d+)?)", block)
    return float(match.group(1)) if match else float("inf")


def judge_cheaper(prompt: str) -> str:
    """Consistent by content: the cheaper plan wins in both orders."""
    a, b = _cost(_block(prompt, "A")), _cost(_block(prompt, "B"))
    if a == b:
        return "Both fine.\n[[C]]"
    return "Cheaper wins.\n[[A]]" if a < b else "Cheaper wins.\n[[B]]"


def judge_tie(prompt: str) -> str:
    return "No meaningful difference.\n[[C]]"


def judge_always_a(prompt: str) -> str:
    return "[[A]]"


def judge_spoiled(prompt: str) -> str:
    return "I refuse to pick a winner."


def judge_explained(prompt: str) -> str:
    """Verdict must be the LAST marker even if prose mentions others."""
    return "Maybe [[A]] on length, but facts say [[B]].\n[[C]]"


# --------------------------------------------------------------------------
class TestRankerProtocol(unittest.TestCase):
    def test_swapped_pairs_agree_on_cheaper_plan(self):
        result = ranker.rank(QUERY, PLANS, judge_cheaper,
                             REFERENCE, use_cache=False)
        self.assertEqual(set(result), {"order", "verdicts",
                                       "swap_consistency", "model_ver"})
        self.assertEqual(result["swap_consistency"], 1.0)
        self.assertEqual(len(result["verdicts"]), 3)
        self.assertTrue(all(v["consistent"] and v["reason"] == "ok"
                            for v in result["verdicts"]))
        # plan-b cheapest, then plan-c, then plan-a
        self.assertEqual(result["order"], [1, 2, 0])

    def test_position_hack_is_inconsistent_and_ties(self):
        """A judge that always says [[A]] must not control the order."""
        result = ranker.rank(QUERY, PLANS, judge_always_a,
                             REFERENCE, use_cache=False)
        self.assertEqual(result["swap_consistency"], 0.0)
        self.assertTrue(all(not v["consistent"] for v in result["verdicts"]))
        self.assertTrue(all(v["reason"] == "inconsistent"
                            for v in result["verdicts"]))
        # 0.5 per pair each -> no win signal; verifier breaks the tie.
        self.assertEqual(result["order"], [1, 2, 0])

    def test_spoiled_answer_retried_then_tie(self):
        result = ranker.rank(QUERY, PLANS, judge_spoiled,
                             REFERENCE, use_cache=False)
        self.assertEqual(result["swap_consistency"], 0.0)
        self.assertTrue(all(v["reason"] == "spoiled"
                            for v in result["verdicts"]))

    def test_last_verdict_marker_wins(self):
        result = ranker.rank(QUERY, PLANS, judge_explained,
                             REFERENCE, use_cache=False)
        # Consistent [[C]] in both orders = a real tie, not a win.
        self.assertEqual(result["swap_consistency"], 1.0)
        self.assertTrue(all(v["tie"] for v in result["verdicts"]))

    def test_prompt_is_blind_and_carries_rubric(self):
        captured = []

        def judge(prompt: str) -> str:
            captured.append(prompt)
            return "[[C]]"

        ranker.rank(QUERY, PLANS, judge, REFERENCE, use_cache=False)
        self.assertTrue(captured)
        prompt = captured[0]
        for name in ("plan-a", "plan-b", "plan-c", "Beach",
                     "InterContinental"):
            self.assertNotIn(name, prompt)
        self.assertIn("feasibility 40", prompt)
        self.assertIn("time/cost 25", prompt)
        self.assertIn("preference-fit 20", prompt)
        self.assertIn("robustness 15", prompt)
        self.assertIn("position, length", prompt)
        self.assertIn("[Reference checks]", prompt)
        self.assertIn("POI-1", prompt)

    def test_rank_requires_llm(self):
        with self.assertRaises(ValueError):
            ranker.rank(QUERY, PLANS, None, use_cache=False)


class TestTieBreak(unittest.TestCase):
    def test_verifier_breaks_all_tie_deterministically(self):
        plans = [
            {"itinerary_id": "x", "total_cost": 500, "activities": []},
            {"itinerary_id": "y", "total_cost": 100, "activities": []},
            {"itinerary_id": "z", "total_cost": 1, "activities": []},
        ]
        reference = [
            {"feasible": True, "cost": 500, "violations": []},
            {"feasible": True, "cost": 100, "violations": []},
            {"feasible": False, "cost": 1, "violations": ["budget"]},
        ]
        first = ranker.rank(QUERY, plans, judge_tie, reference,
                            use_cache=False)
        second = ranker.rank(QUERY, plans, judge_tie, reference,
                             use_cache=False)
        self.assertEqual(first["order"], [1, 0, 2])
        self.assertEqual(first["order"], second["order"])

    def test_fully_equal_plans_use_seeded_pick(self):
        plans = [{"itinerary_id": f"p{i}", "total_cost": 0,
                  "activities": []} for i in range(4)]
        first = ranker.rank(QUERY, plans, judge_tie, use_cache=False)
        second = ranker.rank(QUERY, plans, judge_tie, use_cache=False)
        self.assertEqual(first["order"], second["order"])
        self.assertEqual(sorted(first["order"]), [0, 1, 2, 3])
        different = ranker.rank(QUERY, plans, judge_tie, seed=1,
                                use_cache=False)
        self.assertEqual(sorted(different["order"]), [0, 1, 2, 3])

    def test_cache_key_changes_with_plan_set(self):
        a = ranker.cache_key(QUERY, PLANS, "m1")
        b = ranker.cache_key(QUERY, PLANS[:-1], "m1")
        c = ranker.cache_key(QUERY, PLANS, "m2")
        self.assertEqual(len({a, b, c}), 3)


class TestShadowLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ranker_")
        self.path = os.path.join(self.tmp, "nested", "ranker_shadow.jsonl")

    def _read(self):
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_shadow_line_schema(self):
        entry = ranker.record_shadow(QUERY, PLANS, judge_cheaper, REFERENCE,
                                     path=self.path, model_ver="mock-v1")
        self.assertIsNotNone(entry)
        lines = self._read()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(set(line), {
            "ts", "query_hash", "plan_ids", "blind_rank",
            "swap_consistency", "latency_ms", "model_ver", "rubric_ver"})
        self.assertEqual(line["query_hash"], ranker.query_hash(QUERY))
        self.assertEqual(len(line["query_hash"]), 64)
        self.assertEqual(line["plan_ids"], ["plan-a", "plan-b", "plan-c"])
        self.assertEqual(line["blind_rank"], [1, 2, 0])
        self.assertEqual(line["swap_consistency"], 1.0)
        self.assertIsInstance(line["latency_ms"], int)
        self.assertGreaterEqual(line["latency_ms"], 0)
        self.assertEqual(line["model_ver"], "mock-v1")
        self.assertEqual(line["rubric_ver"], ranker.RUBRIC_VER)

    def test_shadow_never_raises_and_can_skip(self):
        def broken(prompt):
            raise ConnectionError("judge down")

        entry = ranker.record_shadow(QUERY, PLANS, broken, REFERENCE,
                                     path=self.path, model_ver="mock-v1",
                                     use_cache=False)
        # Every call failed -> spoiled ties, still a valid shadow line.
        self.assertIsNotNone(entry)
        self.assertEqual(entry["swap_consistency"], 0.0)
        self.assertEqual(len(self._read()), 1)

        # A bad path is swallowed too: no exception escapes.
        bad = os.path.join(self.tmp, "ranker_shadow.jsonl")
        with mock.patch.object(ranker, "_append",
                               side_effect=OSError("disk full")):
            self.assertIsNone(ranker.record_shadow(
                QUERY, PLANS, judge_cheaper, REFERENCE, path=bad))

    def test_spawn_shadow_is_best_effort_thread(self):
        thread = ranker.spawn_shadow(QUERY, PLANS, judge_cheaper, REFERENCE,
                                     path=self.path, model_ver="mock-v1")
        self.assertIsNotNone(thread)
        thread.join(timeout=5)
        self.assertEqual(len(self._read()), 1)


# --------------------------------------------------------------------------
class TestRouterShadowOff(unittest.TestCase):
    """RANKER_SHADOW=0 must leave POST /v1/itinerary unchanged."""

    POIS = [
        {"poi_id": "beach", "name": "Beach", "type": "beach", "lat": 16.0,
         "lon": 108.2, "opening_hours": ["00:00-23:59"],
         "visit_min": {"p25": 60, "p50": 90, "p75": 120},
         "dur_source": "category_rule", "dur_confidence": "low",
         "price_level": 1, "fee": 0, "rating": 4.6, "tags": ["biển"],
         "intensity": 2, "ambience": "", "weather_sensitive": True,
         "pros": [], "cons": [], "source": "t", "fetched_at": "2026-09-28",
         "verified": True},
        {"poi_id": "noodle", "name": "Noodle", "type": "restaurant",
         "lat": 16.0, "lon": 108.2, "opening_hours": ["07:00-21:00"],
         "visit_min": {"p25": 30, "p50": 60, "p75": 90},
         "dur_source": "category_rule", "dur_confidence": "low",
         "price_level": 2, "fee": 50000, "rating": 4.5, "tags": ["ăn"],
         "intensity": 1, "ambience": "", "weather_sensitive": False,
         "pros": [], "cons": [], "source": "t", "fetched_at": "2026-09-28",
         "verified": True},
    ]
    CELLS = {"beach->noodle": {"minutes": 10, "km": 3.0},
             "noodle->beach": {"minutes": 10, "km": 3.0}}
    TRIP = {"trip_id": "t1", "user_id": "u1", "city": "da-nang",
            "start_time": "07:00", "end_time": "18:00", "days": 1,
            "travelers": 2, "budget": 3000000, "transport": ["motorbike"],
            "must_visit": [], "avoid": [], "activities": ["biển", "ăn"],
            "food_prefs": [], "order_prefs": []}

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from BE.app import main as main_mod
        from BE.app.config import Settings
        from BE.app.routers import itinerary as itinerary_mod
        from BE.tests import conftest

        cls.itinerary_mod = itinerary_mod
        cls.client = TestClient(main_mod.app, raise_server_exceptions=False)
        cls.tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="snap_ranker_"), cls.POIS, cls.CELLS)
        cls._real_settings = itinerary_mod.get_settings
        itinerary_mod.get_settings = lambda: Settings(
            snapshot_dir=cls.tmp, snapshot_name="test")

    @classmethod
    def tearDownClass(cls):
        cls.itinerary_mod.get_settings = cls._real_settings

    def _builder(self, **kwargs):
        return {"activities": [], "total_cost": 0, "total_km": 0,
                "total_min": 0, "constraint_status": {}}

    def _post(self):
        with mock.patch.object(self.itinerary_mod, "_get_plan_builder",
                               return_value=self._builder):
            return self.client.post("/v1/itinerary", json={"trip": self.TRIP})

    @staticmethod
    def _normalise(body: dict) -> dict:
        body = json.loads(json.dumps(body))
        for plan in body.get("plans", []):
            plan.pop("itinerary_id", None)
        return body

    def test_flag_default_off_matches_old_response(self):
        calls = []
        fake = lambda **kwargs: calls.append(kwargs)  # noqa: E731
        with mock.patch.object(self.itinerary_mod.ranker_svc,
                               "spawn_shadow", fake):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("RANKER_SHADOW", None)
                unset = self._post()
            with mock.patch.dict(os.environ, {"RANKER_SHADOW": "0"}):
                off = self._post()
        self.assertEqual(unset.status_code, 200, unset.text)
        self.assertEqual(off.status_code, 200, off.text)
        self.assertEqual(self._normalise(unset.json()),
                         self._normalise(off.json()))
        self.assertEqual(calls, [])

    def test_flag_on_calls_shadow_once(self):
        calls = []
        fake = lambda **kwargs: calls.append(kwargs)  # noqa: E731
        with mock.patch.object(self.itinerary_mod.ranker_svc,
                               "spawn_shadow", fake):
            with mock.patch.dict(os.environ, {"RANKER_SHADOW": "1"}):
                response = self._post()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(calls), 1)
        self.assertIn("query", calls[0])
        self.assertEqual(len(calls[0]["plans"]), 3)
        self.assertEqual(len(calls[0]["reference"]), 3)


if __name__ == "__main__":
    unittest.main()
