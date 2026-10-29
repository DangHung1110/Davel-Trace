"""FULL-AUDIT B4 + B5 regression tests (money + explanation).

B5: one `effective_fee(poi)` = ticket_vnd -> price_band midpoint -> legacy
fee -> None ("giá chưa rõ"), wired into retrieval, `total_fee`/BCS, rank and
`response.total_cost`. `fee = 0` is UNKNOWN, never "miễn phí".
B4: POST /v1/itinerary carries `needs_verification` (poi_id/reasons/
must_visit) and `excluded` (one reason per POI) instead of discarding them.

Run from repo root: python -m pytest BE/tests/unit/test_audit_b4_b5.py -q
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.routers import itinerary as itinerary_mod  # noqa: E402
from BE.app.services.common import effective_fee, total_fee  # noqa: E402
from BE.app.services.gate import check_bcs  # noqa: E402
from BE.app.services.rank import score_poi  # noqa: E402
from BE.app.services.response import build_plan  # noqa: E402
from BE.app.services.retrieval import retrieve  # noqa: E402
from BE.common import BAND_MIDPOINT, plan_cost  # noqa: E402
from BE.tests import conftest  # noqa: E402


def _poi(pid, **extra):
    poi = {"poi_id": pid, "verified": True, "opening_hours": ["00:00-23:59"],
           "rating": 4.5, "intensity": 2, "tags": [], "fee": 0}
    poi.update(extra)
    return poi


class TestEffectiveFee(unittest.TestCase):
    """B5: ticket_vnd > price_band midpoint > legacy fee > unknown (None)."""

    def test_ticket_vnd_wins_over_band(self):
        self.assertEqual(effective_fee({"ticket_vnd": 60000,
                                        "smart_tags": {"price_band": "expensive"}}),
                         60000)

    def test_zero_ticket_is_really_free(self):
        self.assertEqual(effective_fee({"ticket_vnd": 0}), 0)

    def test_band_midpoints(self):
        for band, expected in (("cheap", 100_000), ("medium", 300_000),
                               ("expensive", 700_000)):
            with self.subTest(band=band):
                self.assertEqual(
                    effective_fee({"smart_tags": {"price_band": band}}), expected)
        self.assertEqual(BAND_MIDPOINT, {"cheap": 100_000, "medium": 300_000,
                                         "expensive": 700_000})

    def test_legacy_fee_kept_when_nonzero(self):
        self.assertEqual(effective_fee({"fee": 50000}), 50000)

    def test_unknown_price_is_none_not_zero(self):
        for poi in ({}, {"fee": 0}, {"smart_tags": {}},
                    {"smart_tags": {"price_band": None}}, None):
            with self.subTest(poi=poi):
                self.assertIsNone(effective_fee(poi))

    def test_total_and_plan_cost_use_effective_fees(self):
        pois = {"musu": {"ticket_vnd": 60000},
                "park": {"smart_tags": {"price_band": "cheap"}},
                "beach": {"fee": 0}}
        acts = [{"poi_id": "musu"}, {"poi_id": "park"}, {"poi_id": "beach"}]
        self.assertEqual(total_fee(acts, pois), 160_000)
        self.assertEqual(plan_cost({"activities": acts}, pois), 160_000)
        # Explicit total_cost still wins (one cost formula, both sides).
        self.assertEqual(plan_cost({"total_cost": 5, "activities": acts}, pois), 5)


class TestBcsBlocksRealCost(unittest.TestCase):
    """B5: BCS must reject a plan whose KNOWN ticket sum exceeds the budget."""

    def test_ticket_fees_over_budget_fail_bcs(self):
        pois = {"ticket": _poi("ticket", ticket_vnd=350000)}
        itinerary = {"activities": [
            {"poi_id": "ticket", "start": "09:00", "end": "11:00"}]}
        trip = {"budget": 300000}
        self.assertFalse(check_bcs(itinerary, trip, pois, {})["passed"])

        ok_trip = {"budget": 400000}
        self.assertTrue(check_bcs(itinerary, ok_trip, pois, {})["passed"])

    def test_band_midpoint_over_budget_fails_bcs(self):
        pois = {"resort": _poi("resort", smart_tags={"price_band": "expensive"})}
        itinerary = {"activities": [
            {"poi_id": "resort", "start": "09:00", "end": "11:00"}]}
        # 700k midpoint (expensive) vs 500k budget.
        self.assertFalse(check_bcs(itinerary, {"budget": 500000}, pois, {})["passed"])

    def test_unknown_price_does_not_fake_free_but_cannot_block(self):
        pois = {"mystery": _poi("mystery", fee=0)}
        itinerary = {"activities": [
            {"poi_id": "mystery", "start": "09:00", "end": "11:00"}]}
        self.assertTrue(check_bcs(itinerary, {"budget": 0}, pois, {})["passed"])
        self.assertEqual(total_fee(itinerary["activities"], pois), 0)


class TestRetrievalFeeFilter(unittest.TestCase):
    """B5: the retrieval budget filter reads the effective fee."""

    TRIP = {"budget": 500000, "start_time": "07:00", "end_time": "18:00",
            "must_visit": [], "avoid": [], "activities": []}

    def test_band_over_budget_excluded(self):
        pois = [_poi("expensive", smart_tags={"price_band": "expensive"}),
                _poi("cheap", smart_tags={"price_band": "cheap"}),]
        out = retrieve(self.TRIP, pois)
        ids = [c["poi_id"] for c in out["candidates"]]
        self.assertIn("cheap", ids)
        self.assertNotIn("expensive", ids)
        self.assertIn({"poi_id": "expensive", "reason": "vuot ngan sach"},
                      out["excluded"])

    def test_ticket_over_budget_excluded(self):
        out = retrieve(self.TRIP, [_poi("ticket", ticket_vnd=650000)])
        self.assertEqual(out["candidates"], [])
        self.assertIn("vuot ngan sach", str(out["excluded"]))

    def test_unknown_price_kept(self):
        out = retrieve(self.TRIP, [_poi("mystery")])
        self.assertEqual([c["poi_id"] for c in out["candidates"]], ["mystery"])


class TestRankPriceLabel(unittest.TestCase):
    """B5/FR-026: no false "mien phi" stamp on fee-less POIs."""

    CTX = {"hour": "12:00"}

    def test_fee_less_poi_is_uncertain_not_free(self):
        reasons = score_poi(_poi("mystery"), {}, self.CTX)["reasons"]
        self.assertNotIn("mien phi", reasons)
        self.assertIn("gia chua xac minh", reasons)

    def test_banded_poi_is_not_labelled_uncertain(self):
        reasons = score_poi(_poi("banded", smart_tags={"price_band": "cheap"}),
                            {}, self.CTX)["reasons"]
        self.assertNotIn("mien phi", reasons)
        self.assertNotIn("gia chua xac minh", reasons)

    def test_only_verified_free_ticket_says_mien_phi(self):
        reasons = score_poi(_poi("free", ticket_vnd=0), {}, self.CTX)["reasons"]
        self.assertIn("mien phi", reasons)

    def test_price_level_spending_fit_still_applies(self):
        cheap = _poi("cheap", price_level=1, smart_tags={"price_band": "cheap"})
        budget_user = score_poi(cheap, {"spending_level": 1}, self.CTX)["score"]
        luxury_user = score_poi(cheap, {"spending_level": 3}, self.CTX)["score"]
        self.assertGreater(budget_user, luxury_user)


class TestResponsePriceUncertainty(unittest.TestCase):
    """B5: response total_cost sums effective fees + labels unknown prices."""

    POIS = {
        "musu": {"verified": True, "ticket_vnd": 60000,
                 "opening_hours": ["07:30-17:00"], "rating": 4.5},
        "beach": {"verified": True, "fee": 0, "opening_hours": ["00:00-23:59"],
                  "rating": 4.6},
    }
    MATRIX = {"musu->beach": {"minutes": 10, "km": 3.5}}
    TRIP = {"trip_id": "t1", "budget": 3000000,
            "start_time": "07:00", "end_time": "18:00"}
    OPT = {"status": "optimal", "itinerary": {"activities": [
        {"poi_id": "musu", "start": "08:00", "end": "09:30"},
        {"poi_id": "beach", "start": "10:00", "end": "12:00"}]}}

    def test_total_cost_and_unknown_labels(self):
        from BE.app.services.validator import validate
        plan = build_plan(self.OPT,
                          validate(self.OPT["itinerary"], self.TRIP,
                                   self.POIS, self.MATRIX),
                          self.TRIP, self.POIS, self.MATRIX)
        self.assertEqual(plan["total_cost"], 60000)
        self.assertEqual(plan["price_uncertainty"],
                         [{"poi_id": "beach", "label": "gia chua xac minh"}])


class TestItineraryResponseExplanation(unittest.TestCase):
    """B4: needs_verification + excluded reasons reach the HTTP response."""

    POIS = [
        {"poi_id": "beach", "name": "Bien", "type": "beach", "cat": "beach",
         "opening_hours": ["00:00-23:59"], "fee": 0, "rating": 4.6,
         "intensity": 2, "tags": [], "verified": True},
        {"poi_id": "draft", "name": "Draft beach", "type": "beach",
         "cat": "beach", "opening_hours": ["00:00-23:59"], "fee": 0,
         "rating": 4.4, "intensity": 1, "tags": [], "verified": False},
        {"poi_id": "pricy", "name": "Pricy resort", "type": "Điểm thu hút",
         "cat": "attraction", "opening_hours": ["00:00-23:59"],
         "smart_tags": {"price_band": "expensive"}, "rating": 4.2,
         "intensity": 1, "tags": [], "verified": True},
    ]
    CELLS = {"beach->pricy": {"minutes": 10, "km": 3.0},
             "pricy->beach": {"minutes": 10, "km": 3.0}}
    TRIP = {"trip_id": "t1", "user_id": "u1", "city": "da-nang",
            "start_time": "07:00", "end_time": "18:00", "days": 1,
            "travelers": 2, "budget": 400000, "transport": ["motorbike"],
            "must_visit": ["draft"], "avoid": [],
            "activities": [], "food_prefs": [], "order_prefs": []}

    def test_response_carries_needs_verification_and_excluded(self):
        from fastapi.testclient import TestClient
        from BE.app import main as main_mod
        from BE.app.config import Settings

        tmp = conftest.write_snapshot(
            tempfile.mkdtemp(prefix="snap_b4_"), self.POIS, self.CELLS)

        def build_plan(**kwargs):
            return {"activities": [], "total_cost": 0, "total_km": 0,
                    "total_min": 0, "constraint_status": {}}

        old_settings = itinerary_mod.get_settings
        old_builder = itinerary_mod._get_plan_builder
        try:
            itinerary_mod.get_settings = lambda: Settings(
                snapshot_dir=tmp, snapshot_name="test")
            itinerary_mod._get_plan_builder = lambda: build_plan
            r = TestClient(main_mod.app, raise_server_exceptions=False).post(
                "/v1/itinerary", json={"trip": self.TRIP,
                                       "profiles": ["balanced"]})
        finally:
            itinerary_mod.get_settings = old_settings
            itinerary_mod._get_plan_builder = old_builder

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()

        nv = {e["poi_id"]: e for e in body["needs_verification"]}
        self.assertIn("draft", nv)
        self.assertTrue(nv["draft"]["must_visit"])
        self.assertEqual(nv["draft"]["name"], "Draft beach")
        self.assertTrue(nv["draft"]["reasons"])

        excluded = {e["poi_id"]: e for e in body["excluded"]}
        self.assertEqual(excluded["pricy"]["reason"], "vuot ngan sach")
        self.assertEqual(excluded["pricy"]["name"], "Pricy resort")

        # FR-031: an unverified must-visit is surfaced as a plan warning.
        warnings = " | ".join(body["plans"][0].get("warnings") or [])
        self.assertIn("Draft beach", warnings)
        self.assertIn("chua xac minh", warnings)


if __name__ == "__main__":
    unittest.main()
