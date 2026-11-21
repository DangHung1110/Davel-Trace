"""danang-v2.1 adapter + eligibility (DATA_FIX_PLAN WP1/WP2/WP4).

Pure unit tests on hand-built records: no snapshot file needed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import retrieval  # noqa: E402
from BE.common import (TIER_MIDPOINT, effective_fee, fee_upper, poi_view,  # noqa: E402
                       tier_of_vnd)


def rec(pid="osm:node/1", tier="medium", kind="fixed", open_=("08:00-17:00",),
        status="active", role="attraction", category="museum_indoor", **extra):
    p = {
        "poi_id": pid, "name": "Bảo tàng X", "name_raw": "Bảo tàng X", "name_en": None,
        "lat": 16.06, "lon": 108.22, "category": category, "role": role,
        "status": status, "status_reason": None if status == "active" else "x",
        "zone": "trung_tam", "cluster_id": None, "alt_group": None, "requires_ticket_of": None,
        "hours": {"open": list(open_), "kind": kind, "closed_days": [], "access_window": None,
                  "archetype": "bao_tang"},
        "price": {"tier": tier, "note": None},
        "dwell": {"p25": 30, "p50": 60, "p75": 90},
        "tags": {"indoor": True, "effort": 1, "kid_friendly": True, "weather_sensitive": False,
                 "good_times": ["morning"], "time_budget": ["quick"], "space": "indoor"},
        "time_profile": "indoor_flat",
        "popularity": {"signature": False, "prize_prior": None, "wikidata": None,
                       "wikidata_sitelinks": None, "wikipedia_views_90d": None},
        "ext_ids": {"osm": None, "google_place_id": None},
        "provenance": {k: {"source": "x", "verified_by": "inferred", "confidence": 0.5,
                           "evidence_url": None, "verified_at": None, "note": None}
                       for k in ("name", "location", "category", "hours", "price", "dwell",
                                 "tags", "popularity")},
        "data_version": "v2.1", "valid_from": "2026-11-18", "valid_to": None,
    }
    p.update(extra)
    return p


TRIP = {"budget": 2_000_000, "start_time": "07:00", "end_time": "21:00",
        "must_visit": [], "avoid": [], "activities": []}


class TestTiers(unittest.TestCase):
    def test_vnd_to_tier_table(self):
        self.assertEqual(tier_of_vnd(0), "free")
        self.assertEqual(tier_of_vnd(60_000), "cheap")
        self.assertEqual(tier_of_vnd(100_000), "medium")
        self.assertEqual(tier_of_vnd(500_000), "medium")
        self.assertEqual(tier_of_vnd(850_000), "expensive")
        self.assertIsNone(tier_of_vnd(None))

    def test_fee_midpoint_and_upper(self):
        self.assertEqual(effective_fee(rec(tier="medium")), TIER_MIDPOINT["medium"])
        self.assertEqual(fee_upper(rec(tier="medium")), 500_000)
        self.assertEqual(effective_fee(rec(tier="included")), 0)
        self.assertIsNone(effective_fee(rec(tier=None)))   # unknown, never free


class TestPoiView(unittest.TestCase):
    def test_legacy_fields(self):
        v = poi_view(rec(), policy="cach_ly")
        self.assertEqual(v["opening_hours"], ["08:00-17:00"])
        self.assertEqual(v["visit_min"], {"p25": 30, "p50": 60, "p75": 90})
        self.assertEqual(v["cat"], "museum")
        self.assertEqual(v["smart_tags"]["price_band"], "medium")
        self.assertEqual(v["smart_tags"]["time"], ["morning"])      # renamed back
        self.assertEqual(v["smart_tags"]["budget"], ["quick"])
        self.assertEqual(v["intensity"], 1)
        self.assertIsNone(v["rating"])
        self.assertTrue(v["verified"])

    def test_multi_window_hours_are_one_legacy_element(self):
        v = poi_view(rec(open_=("11:00-14:00", "17:00-22:00")), policy="cach_ly")
        self.assertEqual(v["opening_hours"], ["11:00-14:00, 17:00-22:00"])

    def test_google_only_in_demo_policy(self):
        q = {"osm:node/1": {"rating": 4.6, "type": "Bảo tàng nghệ thuật",
                            "hours_open": ["07:00-18:00"]}}
        demo = poi_view(rec(kind="safe_window"), "demo_phi_thuong_mai", q)
        clean = poi_view(rec(kind="safe_window"), "cach_ly", q)
        self.assertEqual(demo["rating"], 4.6)
        self.assertEqual(demo["opening_hours"], ["07:00-18:00"])
        self.assertIsNone(clean["rating"])
        self.assertEqual(clean["opening_hours"], ["08:00-17:00"])
        # sourced (fixed) hours always win over Google
        fixed = poi_view(rec(kind="fixed"), "demo_phi_thuong_mai", q)
        self.assertEqual(fixed["opening_hours"], ["08:00-17:00"])

    def test_v1_record_passes_through(self):
        v1 = {"poi_id": "a", "verified": False}
        self.assertIs(poi_view(v1), v1)


class TestEligibilityWP4(unittest.TestCase):
    def view(self, *recs):
        return [poi_view(r, "cach_ly") for r in recs]

    def test_no_legacy_verified_flag_needed(self):
        res = retrieval.retrieve(TRIP, self.view(rec()))
        self.assertEqual([c["poi_id"] for c in res["candidates"]], ["osm:node/1"])

    def test_unknown_hours_review_and_base_are_not_candidates(self):
        pois = self.view(rec("a", kind="unknown", open_=()), rec("b", status="review"),
                         rec("c", role="base", category="lodging"))
        res = retrieval.retrieve(TRIP, pois)
        self.assertEqual(res["candidates"], [])

    def test_missing_matrix_row_is_excluded_with_reason(self):
        pois = self.view(rec("a"), rec("b"))
        cells = {"a->a": {"minutes": 0}}
        res = retrieval.retrieve(TRIP, pois, cells)
        self.assertEqual([c["poi_id"] for c in res["candidates"]], ["a"])
        self.assertIn({"poi_id": "b", "reason": "chua co ma tran di chuyen"}, res["excluded"])

    def test_safe_window_hours_are_labelled(self):
        poi = rec(kind="safe_window")
        poi["popularity"]["signature"] = True   # a known sight stays in the main tier
        res = retrieval.retrieve(TRIP, self.view(poi))
        self.assertIn("nen kiem tra gio", res["candidates"][0]["uncertainty"])

    def test_unknown_sight_without_sourced_hours_is_local_tier(self):
        res = retrieval.retrieve(TRIP, self.view(rec(kind="safe_window")))
        self.assertEqual(res["candidates"], [])
        self.assertEqual(res["excluded"][0]["reason"], "chi xep khi duoc yeu cau")


if __name__ == "__main__":
    unittest.main()
