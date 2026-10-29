"""D2 step 3 (N3): candidate cap before the O(n^2) scorer / CP-SAT model.

The 742-POI fallback pool made `scorer.edge_scores` ~550k pairs and the CP-SAT
model ~552k arcs per profile per request. `profiles.cap_candidates` keeps the
top-K by cheap rank score, balanced across categories (so rare museum/park
rows survive a restaurant-heavy pool) and pinning `must_visit`.

Run from repo root: python -m pytest BE/tests/unit/test_candidate_cap.py -q
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import profiles  # noqa: E402
from BE.app.services.common import plan_cost, total_fee  # noqa: E402
from BE.app.services.gate import check_bcs  # noqa: E402
from BE.app.services.profiles import (  # noqa: E402
    CANDIDATE_CAP_DEFAULT,
    build_plan,
    cap_candidates,
    candidate_cap_limit,
)
from BE.app.services.validator import validate  # noqa: E402

CATS = ("restaurant", "cafe", "museum", "park", "beach", "market", "bar",
        "spa", "landmark", "viewpoint", "nature")


def _poi(pid: str, cat: str, rating: float = 4.0) -> dict:
    return {"poi_id": pid, "name": pid, "cat": cat, "type": cat,
            "opening_hours": ["06:00-23:00"], "visit_min": 30, "fee": 0,
            "rating": rating, "tags": [cat], "intensity": 1,
            "verified": True}


def _pool(n_food: int = 180) -> list[dict]:
    pois = [_poi(f"r{i}", "restaurant") for i in range(n_food)]
    pois += [_poi(f"{cat}0", cat) for cat in CATS if cat != "restaurant"]
    return pois


def _ranked(pois: list[dict]) -> list[dict]:
    """Cheap rank stage output; earlier rows score higher."""
    n = max(1, len(pois))
    return [{"poi_id": p["poi_id"], "score": 1.0 - i / (n + 1),
             "reasons": ["test"]} for i, p in enumerate(pois)]


def _trip(**extra) -> dict:
    return {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
            "end_time": "18:00", "must_visit": [], "avoid": [], **extra}


class TestCandidateCap(unittest.TestCase):
    def test_cap_respects_k_and_keeps_every_category(self):
        pois = _pool(180)
        selected, stats = cap_candidates(pois, _ranked(pois), 20)
        self.assertEqual(len(selected), 20)
        self.assertEqual(stats["cap"], 20)
        self.assertTrue(stats["capped"])
        self.assertEqual(stats["capped_from_n"], len(pois))
        self.assertEqual(stats["after"], 20)
        # Diversity survives: every category keeps its best row ...
        kept = {p["cat"] for p in selected}
        self.assertEqual(kept, set(CATS))
        # ... and one category cannot eat the whole cap.
        self.assertLess(
            sum(1 for p in selected if p["cat"] == "restaurant"), 20)

    def test_must_visit_is_pinned_through_the_cap(self):
        pois = _pool(180)
        ranked = _ranked(pois)
        lowest = ranked[-1]["poi_id"]  # would be capped away by rank alone
        selected, stats = cap_candidates(pois, ranked, 10,
                                         must_visit=[lowest])
        self.assertIn(lowest, [p["poi_id"] for p in selected])
        self.assertEqual(stats["pinned_must_visit"], 1)

    def test_scorer_sees_at_most_k_candidates(self):
        pois = _pool(180)
        by_id = {p["poi_id"]: p for p in pois}
        seen = {}

        def fake_edges(ids, by_id_arg, user=None, ctx=None):
            seen["n"] = len(ids)
            return {}

        def fake_optimize(*args, **kwargs):
            return {"itinerary": None, "reason": "test-stop"}

        with mock.patch.object(profiles.scorer, "edge_scores",
                               side_effect=fake_edges), \
                mock.patch.object(profiles, "optimize",
                                  side_effect=fake_optimize):
            plan = build_plan("balanced", _trip(), _ranked(pois), by_id, {},
                              template="")

        self.assertLessEqual(seen["n"], CANDIDATE_CAP_DEFAULT)
        self.assertTrue(plan["candidate_pool"]["capped"])
        self.assertEqual(plan["candidate_pool"]["before"], len(pois))
        self.assertEqual(plan["candidate_pool"]["capped_from_n"], len(pois))
        self.assertTrue(any("CANDIDATE_CAP" in w
                            for w in plan.get("warnings", [])))

    def test_env_override_changes_k(self):
        pois = _pool(180)
        with mock.patch.dict(os.environ, {"CANDIDATE_CAP": "7"}):
            self.assertEqual(candidate_cap_limit(), 7)
            selected, stats = cap_candidates(pois, _ranked(pois), None)
        self.assertEqual(len(selected), 7)
        self.assertEqual(stats["cap"], 7)

    def test_invalid_env_falls_back_to_default(self):
        with mock.patch.dict(os.environ, {"CANDIDATE_CAP": "not-a-number"}):
            self.assertEqual(candidate_cap_limit(), CANDIDATE_CAP_DEFAULT)

    def test_param_override_through_build_plan(self):
        pois = _pool(50)
        by_id = {p["poi_id"]: p for p in pois}
        with mock.patch.object(profiles.scorer, "edge_scores",
                               return_value={}), \
                mock.patch.object(profiles, "optimize",
                                  return_value={"itinerary": None,
                                                "reason": "test-stop"}):
            plan = build_plan("balanced", _trip(), _ranked(pois), by_id, {},
                              template="", candidate_cap=5)
        self.assertEqual(plan["candidate_pool"]["cap"], 5)
        self.assertLessEqual(plan["candidate_pool"]["after"], 5)
        self.assertEqual(len(plan["_context"]["pois"]), 5)

    def test_pool_below_k_is_untouched(self):
        pois = _pool(0)  # 10 non-food rows, default cap 80
        by_id = {p["poi_id"]: p for p in pois}
        seen = {}

        def fake_edges(ids, by_id_arg, user=None, ctx=None):
            seen["ids"] = list(ids)
            return {}

        with mock.patch.object(profiles.scorer, "edge_scores",
                               side_effect=fake_edges), \
                mock.patch.object(profiles, "optimize",
                                  return_value={"itinerary": None,
                                                "reason": "test-stop"}):
            plan = build_plan("balanced", _trip(), _ranked(pois), by_id, {},
                              template="")

        self.assertFalse(plan["candidate_pool"]["capped"])
        self.assertEqual(plan["candidate_pool"]["after"], len(pois))
        self.assertEqual(len(seen["ids"]), len(pois))
        self.assertEqual(seen["ids"], [p["poi_id"] for p in pois])
        self.assertFalse(any("CANDIDATE_CAP" in w
                             for w in plan.get("warnings", [])))


class TestGateProjectionMoney(unittest.TestCase):
    """The gate slice must carry B5 money, or internal BCS reads cost 0."""

    def _money_pois(self) -> list[dict]:
        base = {"verified": True, "opening_hours": ["06:00-23:00"],
                "cat": "museum", "type": "museum", "visit_min": 30}
        return [
            {**base, "poi_id": "ticket", "ticket_vnd": 60000},
            {**base, "poi_id": "band",
             "smart_tags": {"price_band": "medium"}},
            {**base, "poi_id": "legacy", "fee": 50000},
            {**base, "poi_id": "unknown"},
        ]

    def test_internal_cost_equals_effective_fee_sum(self):
        pois = self._money_pois()
        acts = [{"poi_id": p["poi_id"], "start": f"{8 + i:02d}:00",
                 "end": f"{8 + i:02d}:30"} for i, p in enumerate(pois)]
        gate = {p["poi_id"]: profiles._gate_poi(p) for p in pois}
        by_id = {p["poi_id"]: p for p in pois}
        itinerary = {"activities": acts}
        # 60k ticket + 300k medium band + 50k legacy + unknown (0 counted).
        self.assertEqual(total_fee(acts, by_id), 410000)
        self.assertEqual(plan_cost(itinerary, gate), 410000)
        # The old projection priced everything at 0.
        self.assertNotEqual(plan_cost(itinerary, gate), 0)

    def test_bcs_verdict_matches_evaluate_path(self):
        pois = self._money_pois()
        acts = [{"poi_id": p["poi_id"], "start": f"{8 + i:02d}:00",
                 "end": f"{8 + i:02d}:30"} for i, p in enumerate(pois)]
        gate = {p["poi_id"]: profiles._gate_poi(p) for p in pois}
        by_id = {p["poi_id"]: p for p in pois}
        itinerary = {"activities": acts}
        # Evaluate path prices the same POI set from the full rows.
        evaluate_cost = total_fee(acts, by_id)
        tight = _trip(budget=evaluate_cost - 1)
        exact = _trip(budget=evaluate_cost)
        for projection in (gate, by_id):
            self.assertFalse(check_bcs(itinerary, tight, projection,
                                       {})["passed"])
            self.assertTrue(check_bcs(itinerary, exact, projection,
                                      {})["passed"])
        rep = validate(itinerary, tight, gate, {})
        self.assertIn("BCS", rep["violations"])
        self.assertFalse(rep["checks"]["BCS"])


if __name__ == "__main__":
    unittest.main()
