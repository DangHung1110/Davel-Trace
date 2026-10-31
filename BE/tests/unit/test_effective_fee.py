"""effective_fee: what one person spends at a POI, and the budget that reads it.

Run from repo root: python -m pytest BE/tests/unit/test_effective_fee.py -q
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.gate import check_bcs  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, optimize  # noqa: E402
from BE.app.services.rank import score_poi  # noqa: E402
from BE.common import (  # noqa: E402
    effective_fee, fee_is_estimate, party_size, plan_cost, total_fee)

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshots" / "danang-v1"


def poi(cat="restaurant", band="medium", **extra):
    return {"poi_id": "p", "cat": cat, "fee": 0,
            "smart_tags": {"price_band": band, "ticket": False}, **extra}


class TestEffectiveFee(unittest.TestCase):
    def test_a_ticket_wins_over_the_band(self):
        self.assertEqual(effective_fee(poi("museum", "cheap", ticket_vnd=60000, fee=60000)), 60000)

    def test_band_gives_the_middle_of_the_band(self):
        self.assertEqual(effective_fee(poi("cafe", "cheap")), 50000)
        self.assertEqual(effective_fee(poi("restaurant", "medium")), 300000)
        self.assertEqual(effective_fee(poi("attraction", "expensive")), 700000)

    def test_open_access_is_free(self):
        self.assertEqual(effective_fee(poi("beach", "cheap")), 0)
        self.assertEqual(effective_fee(poi("landmark", "cheap")), 0)

    def test_a_cheap_museum_or_a_ticketed_temple_is_not_free(self):
        self.assertEqual(effective_fee(poi("museum", "cheap")), 50000)
        ticketed = poi("landmark", "cheap")
        ticketed["smart_tags"]["ticket"] = True
        self.assertEqual(effective_fee(ticketed), 50000)

    def test_no_band_is_unknown_not_free(self):
        self.assertIsNone(effective_fee({"cat": "restaurant", "fee": 0, "smart_tags": {}}))

    def test_a_poi_without_smart_tags_keeps_its_fee(self):
        self.assertEqual(effective_fee({"fee": 120000}), 120000)
        self.assertEqual(effective_fee({"fee": 0}), 0)
        self.assertEqual(effective_fee({}), 0)

    def test_estimate_flag(self):
        self.assertTrue(fee_is_estimate(poi()))
        self.assertFalse(fee_is_estimate(poi("beach", "cheap")))
        self.assertFalse(fee_is_estimate(poi("museum", "cheap", ticket_vnd=60000)))


class TestPlanCost(unittest.TestCase):
    pois = {"a": poi(), "b": poi("beach", "cheap"), "c": poi("cafe", "cheap")}
    acts = [{"poi_id": "a"}, {"poi_id": "b"}, {"poi_id": "c"}]

    def test_prices_are_per_person(self):
        self.assertEqual(total_fee(self.acts, self.pois), 350000)
        self.assertEqual(total_fee(self.acts, self.pois, 2), 700000)
        self.assertEqual(party_size({"travelers": 4}), 4)
        self.assertEqual(party_size({}), 1)

    def test_explicit_total_cost_wins(self):
        self.assertEqual(plan_cost({"total_cost": 5, "activities": self.acts}, self.pois, 2), 5)

    def test_gate_counts_the_party(self):
        itinerary = {"activities": self.acts}
        self.assertEqual(check_bcs(itinerary, {"budget": 400000}, self.pois, {})["score"], 1.0)
        self.assertEqual(check_bcs(itinerary, {"budget": 400000, "travelers": 2}, self.pois, {})["score"], 0.0)


class TestSolverBudget(unittest.TestCase):
    def solve(self, max_fee):
        stubs = [StubPOI("free", 60, 8 * 60, 20 * 60, 1.0, fee=0),
                 StubPOI("dear", 60, 8 * 60, 20 * 60, 5.0, fee=700000)]
        travel = {("free", "dear"): 10, ("dear", "free"): 10}
        out = optimize(stubs, travel, StubTrip(8 * 60, 20 * 60, None), workers=1, max_fee=max_fee)
        return {a["poi_id"] for a in out["itinerary"]["activities"]}

    def test_fee_ceiling_is_hard(self):
        self.assertEqual(self.solve(None), {"free", "dear"})
        self.assertEqual(self.solve(700000), {"free", "dear"})
        self.assertEqual(self.solve(699999), {"free"})


class TestRankReason(unittest.TestCase):
    def test_only_a_free_place_is_called_free(self):
        self.assertIn("mien phi", score_poi(poi("beach", "cheap"))["reasons"])
        self.assertNotIn("mien phi", score_poi(poi("restaurant", "medium"))["reasons"])
        unknown = score_poi({"poi_id": "p", "fee": 0, "smart_tags": {}})["reasons"]
        self.assertNotIn("mien phi", unknown)
        self.assertIn("gia chua ro", unknown)


class TestRealSnapshot(unittest.TestCase):
    def test_every_verified_poi_has_a_price(self):
        pois = json.loads((SNAPSHOT / "pois.json").read_text(encoding="utf-8"))["pois"]
        self.assertEqual([p["name"] for p in pois if p.get("verified") and effective_fee(p) is None], [])


if __name__ == "__main__":
    unittest.main()
