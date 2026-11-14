"""Structural profile objectives + cross-option Jaccard guarantee.

USER DECISION pinned here:
- omitting `profiles` returns the three objectives (contract test also covers
  the endpoint default);
- savings is COST-FIRST (fee + travel), not a fee tie-break;
- experience is NOVELTY-FIRST (Vargas-style novelty + dominant category
  spread), so its composition differs from the rating-first plan;
- every returned multi-option response keeps pairwise POI-set Jaccard <= 0.6,
  replacing the loser from its own solution pool; a forced-similar pool
  degrades honestly (`satisfied` false, `exhausted` reported) instead of
  crashing or silently dropping an option.

Run: python -m pytest BE/tests/unit/test_profile_objectives.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import pool as pool_svc  # noqa: E402
from BE.app.services.profiles import (  # noqa: E402
    DIVERSITY_WEIGHT_BY_PROFILE,
    _score,
    build_plan,
    novelty_scores,
    plan_diversity,
)


def _poi(pid, cat, rating, fee=0, price_level=1, visit=45,
         hours=("06:00-23:59",)):
    return {"poi_id": pid, "name": pid, "cat": cat, "type": cat,
            "opening_hours": list(hours), "visit_min": visit,
            "fee": fee, "rating": rating, "price_level": price_level,
            "tags": [cat], "intensity": 1, "verified": True}


# Cost fixture: one expensive high-rated cluster, one cheap compact cluster.
COST_POIS = [
    _poi("exp", "restaurant", 4.9, 500_000, 3),
    _poi("cheap", "restaurant", 4.2, 0, 1),
    _poi("fancy", "attraction", 4.8, 300_000, 3),
    _poi("mkt", "market", 4.3),
    _poi("cafe", "cafe", 4.5, 0, 2),
    _poi("beach", "beach", 4.4),
    _poi("park", "park", 4.1),
]
NEAR = {"cheap", "mkt", "beach", "cafe", "park"}
COST_CELLS = {}
for _a in COST_POIS:
    for _b in COST_POIS:
        if _a["poi_id"] == _b["poi_id"]:
            continue
        # A ride the rating-first plan takes for a better dinner; 40 min each way
        # is not worth 0.7 stars to any profile now that travel counts.
        _m = 5 if (_a["poi_id"] in NEAR and _b["poi_id"] in NEAR) else 12
        COST_CELLS[f"{_a['poi_id']}->{_b['poi_id']}"] = {
            "minutes": _m, "km": _m / 10}
COST_BY_ID = {p["poi_id"]: p for p in COST_POIS}
COST_RANKED = [{"poi_id": p["poi_id"]} for p in COST_POIS]
COST_TRIP = {"trip_id": "t", "budget": 3_000_000, "start_time": "08:00",
             "end_time": "18:00", "must_visit": [], "avoid": [],
             "profile": {"party_type": "solo", "pace": 2}}


class TestStructuralObjectives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans = {
            profile: build_plan(profile, COST_TRIP, COST_RANKED, COST_BY_ID,
                                COST_CELLS, template="")
            for profile in ("savings", "balanced", "experience")
        }

    def test_savings_minimises_fee_and_travel(self):
        savings = self.plans["savings"]
        balanced = self.plans["balanced"]
        self.assertTrue(savings["passed"])
        self.assertEqual(savings["total_cost"], 0, savings["activities"])
        self.assertLess(savings["total_cost"], balanced["total_cost"])
        self.assertLessEqual(savings["travel_min"], balanced["travel_min"])
        # The expensive cluster is not merely re-ordered: it is absent.
        ids = {a["poi_id"] for a in savings["activities"]}
        self.assertNotIn("exp", ids)
        self.assertNotIn("fancy", ids)

    def test_experience_is_novelty_first(self):
        experience = self.plans["experience"]
        balanced = self.plans["balanced"]
        self.assertTrue(experience["passed"])
        div_exp = experience["diversity"]
        div_bal = balanced["diversity"]
        self.assertEqual(div_exp["objective"], "novelty_first")
        self.assertGreater(div_exp["novelty"], div_bal["novelty"])
        # Experience never spreads FEWER categories than rating-first, and it
        # reaches the pool's full spread in this fixture.
        self.assertGreaterEqual(div_exp["distinct_categories"],
                                div_bal["distinct_categories"])
        self.assertGreater(div_exp["distinct_categories"], 5)
        # Composition really changes (not a reorder): at least one stop that
        # the rating-first plan skipped, and it is a novel (high-novelty) one.
        set_exp = {a["poi_id"] for a in experience["activities"]}
        set_bal = {a["poi_id"] for a in balanced["activities"]}
        self.assertNotEqual(set_exp, set_bal)
        novel = novelty_scores(COST_POIS)
        exclusive = set_exp - set_bal
        self.assertTrue(exclusive, (set_exp, set_bal))
        best = max(exclusive, key=lambda pid: novel[pid])
        # The stop rating-first skipped is a genuinely novel one: its novelty
        # beats the rating-first plan's AVERAGE novelty.
        self.assertGreater(novel[best], div_bal["novelty"],
                           (best, novel[best], div_bal["novelty"]))

    def test_node_scores_encode_the_three_objectives(self):
        nov = novelty_scores(COST_POIS)
        cheap = COST_BY_ID["cheap"]
        exp = COST_BY_ID["exp"]
        # savings: a 500k fee is worth far more than 0.7 rating points.
        self.assertGreater(
            _score("savings", cheap, avg_leg=5, budget=COST_TRIP["budget"]),
            _score("savings", exp, avg_leg=40, budget=COST_TRIP["budget"]))
        # experience: a rare, low-popularity place beats a mainstream 4.9.
        self.assertGreater(
            _score("experience", cheap, novelty=nov,
                   budget=COST_TRIP["budget"]),
            _score("experience", exp, novelty=nov,
                   budget=COST_TRIP["budget"]))
        # balanced stays rating-first.
        self.assertGreater(_score("balanced", exp), _score("balanced", cheap))
        # Category spread is dominant for experience, neutral for the rest.
        self.assertGreater(DIVERSITY_WEIGHT_BY_PROFILE["experience"], 2.0)
        self.assertEqual(DIVERSITY_WEIGHT_BY_PROFILE["balanced"], 1.0)

    def test_plan_diversity_reports_categories_and_novelty(self):
        acts = [{"poi_id": "beach"}, {"poi_id": "cafe"}, {"poi_id": "beach"}]
        report = plan_diversity(acts, COST_POIS, "experience")
        self.assertEqual(report["distinct_categories"], 2)
        self.assertEqual(report["categories"], ["beach", "cafe"])
        self.assertGreater(report["novelty"], 0.0)
        self.assertEqual(report["objective"], "novelty_first")


def _plan(profile, ids, utility, candidates=None, objective=None):
    plan = {"profile": profile, "activities": [{"poi_id": p} for p in ids],
            "scores": {"utility": utility}}
    if objective is not None:
        plan["_objective"] = objective
    if candidates is not None:
        plan["_pool_plans"] = candidates
    return plan


class TestJaccardGuarantee(unittest.TestCase):
    def test_pairs_already_under_ceiling_are_untouched(self):
        plans = [_plan("a", ["1", "2", "3", "4"], 0.9),
                 _plan("b", ["3", "4", "5", "6"], 0.8),
                 _plan("c", ["7", "8", "9", "10"], 0.7)]
        out, report = pool_svc.enforce_pairwise(plans)
        self.assertTrue(report["satisfied"], report)
        self.assertEqual([p["profile"] for p in out], ["a", "b", "c"])
        self.assertEqual(report["replaced"], [])
        self.assertEqual(len(report["pairwise_distances"]), 3)
        self.assertLessEqual(report["max_pairwise_similarity"], 0.6)

    def test_conflicting_lower_quality_plan_is_replaced(self):
        # a/b share 4 of 5 POIs -> Jaccard 0.667 > 0.6. b is worse, and its
        # pool holds a genuinely different day.
        a = _plan("a", ["1", "2", "3", "4", "x"], 0.9)
        alt = _plan("b", ["6", "7", "8", "9", "y"], 0.85, objective=0.9)
        b = _plan("b", ["1", "2", "3", "4", "z"], 0.5,
                  candidates=[alt], objective=0.4)
        c = _plan("c", ["m", "n", "o", "p", "q"], 0.8)
        out, report = pool_svc.enforce_pairwise([a, b, c])
        self.assertTrue(report["satisfied"], report)
        self.assertEqual(out[1]["profile"], "b")
        self.assertNotIn("z", {act["poi_id"] for act in out[1]["activities"]})
        self.assertIn("y", {act["poi_id"] for act in out[1]["activities"]})
        self.assertEqual(len(report["replaced"]), 1)
        self.assertLessEqual(report["max_pairwise_similarity"], 0.6)

    def test_refill_callback_is_used_when_no_pool_is_attached(self):
        calls = []
        a = _plan("a", ["1", "2", "3", "4", "5"], 0.9)
        b = _plan("b", ["1", "2", "3", "4", "z"], 0.4)
        c = _plan("c", ["m", "n", "o", "p", "q"], 0.8)

        def refill(plan, others):
            calls.append((plan["profile"], [o["profile"] for o in others]))
            return [_plan("b", ["6", "7", "8", "9", "y"], 0.7)]

        out, report = pool_svc.enforce_pairwise([a, b, c], refill=refill)
        self.assertEqual(calls, [("b", ["a", "c"])])
        self.assertTrue(report["satisfied"], report)
        self.assertIn("y", {act["poi_id"] for act in out[1]["activities"]})

    def test_forced_similar_fallback_is_honest(self):
        # Every alternative still shares 4/5 POIs with `a`: the ceiling cannot
        # be met. The function must return the same number of plans, keep the
        # best-effort least-similar one and report exhaustion.
        a = _plan("a", ["1", "2", "3", "4", "x"], 0.9)
        alt = _plan("b", ["1", "2", "3", "4", "y"], 0.6, objective=0.8)
        b = _plan("b", ["1", "2", "3", "4", "z"], 0.4,
                  candidates=[alt], objective=0.4)
        out, report = pool_svc.enforce_pairwise([a, b])
        self.assertFalse(report["satisfied"])
        self.assertEqual(len(out), 2)
        self.assertTrue(report["exhausted"])
        self.assertLessEqual(report["max_pairwise_similarity"], 1.0)
        self.assertEqual(report["max_jaccard"], 0.6)


if __name__ == "__main__":
    unittest.main()
