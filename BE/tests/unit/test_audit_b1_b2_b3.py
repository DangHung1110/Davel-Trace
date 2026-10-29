"""Full-audit B1/B2/B3 regressions: type match, fail-closed pool, word boundary.

B1: retrieval compared the Vietnamese `type` label with English category keys,
    so a real activity ("tắm biển") matched nothing and the price-uncertainty
    label (which required type == "restaurant") never fired. Both now use the
    canonical English category from `soft_rules.poi_category`.
B2: `profiles.build_plan` fell back to `list(pois_by_id)` (the WHOLE snapshot,
    unverified rows included) whenever the ranked pool was empty. The fallback
    is now verified-only and re-applies the hard profile filter + trip avoid;
    an empty pool returns an honest empty plan naming the constraint.
B3: substring matching ("ăn" in "văn hóa", "cầu" in "yêu cầu") is replaced by
    the word-boundary matcher used by profile_filter.

Run from repo root: python -m pytest BE/tests/unit/test_audit_b1_b2_b3.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import soft_rules, templates  # noqa: E402
from BE.app.services.profiles import build_plan  # noqa: E402
from BE.app.services.repair import _named_target  # noqa: E402
from BE.app.services.retrieval import retrieve, uncertainty, wanted_types  # noqa: E402

# Snapshot shape: `cat` = canonical English category, `type` = free Vietnamese
# label. This is exactly the gap B1 was about.
POIS = [
    {"poi_id": "beach", "cat": "beach", "type": "Bãi biển", "fee": 0,
     "verified": True, "rating": 4.5, "tags": ["tắm biển"],
     "opening_hours": ["00:00-23:59"]},
    {"poi_id": "rest", "cat": "restaurant", "type": "Nhà hàng", "fee": 50000,
     "verified": True, "rating": 4.3, "tags": ["ăn trưa"],
     "opening_hours": ["07:00-21:00"]},
    {"poi_id": "museum", "cat": "museum", "type": "Bảo tàng", "fee": 60000,
     "verified": True, "rating": 4.4, "tags": ["văn hóa"],
     "opening_hours": ["07:30-17:00"]},
    {"poi_id": "bridge", "cat": "landmark", "type": "Cầu", "fee": 0,
     "verified": True, "rating": 4.6, "tags": ["check-in"],
     "opening_hours": ["00:00-23:59"]},
]

TRIP = {"budget": 3000000, "start_time": "08:00", "end_time": "18:00",
        "must_visit": [], "avoid": []}


def _poi(pid, cat, *, verified=True, tags=None, fee=0, rating=4.5):
    return {"poi_id": pid, "name": f"{cat} {pid}", "cat": cat, "type": cat,
            "opening_hours": ["06:00-23:00"], "visit_min": 45, "fee": fee,
            "rating": rating, "tags": tags or [cat], "intensity": 1,
            "verified": verified}


def _cells(by_id):
    return {f"{a}->{b}": {"minutes": 10, "km": 1.0}
            for a in by_id for b in by_id if a != b}


class TestB1TypeMatch(unittest.TestCase):
    def test_tam_bien_returns_beach_pois(self):
        out = retrieve(dict(TRIP, activities=["tắm biển"]), POIS)
        self.assertEqual([c["poi_id"] for c in out["candidates"]], ["beach"])
        self.assertIn("khong khop loai", str(out["excluded"]))

    def test_van_hoa_does_not_add_restaurant(self):
        types = wanted_types(["văn hóa"])
        self.assertIn("museum", types)
        self.assertNotIn("restaurant", types)  # "ăn" must not hit "văn hóa"
        out = retrieve(dict(TRIP, activities=["văn hóa"]), POIS)
        self.assertEqual([c["poi_id"] for c in out["candidates"]], ["museum"])

    def test_quiet_request_does_not_add_landmark(self):
        types = wanted_types(["yêu cầu yên tĩnh"])
        self.assertEqual(types, set())  # "cầu" must not hit "yêu cầu"
        out = retrieve(dict(TRIP, activities=["yêu cầu yên tĩnh", "văn hóa"]),
                       POIS)
        self.assertEqual([c["poi_id"] for c in out["candidates"]], ["museum"])

    def test_price_uncertainty_label_fires_for_restaurant_without_fee(self):
        poi = _poi("r-unknown", "restaurant", fee=0)
        poi["type"] = "Nhà hàng"  # Vietnamese label, canonical cat in `cat`
        self.assertIn("gia chua xac minh", uncertainty(poi))
        self.assertNotIn("gia chua xac minh",
                         uncertainty(_poi("b-free", "beach", fee=0)))


class TestB3WordBoundary(unittest.TestCase):
    def test_template_hint_is_whole_word(self):
        self.assertEqual(templates.select_template({"party_type": "skid row"}),
                         templates.DEFAULT_TEMPLATE)
        # Free-text plurals keep working.
        self.assertEqual(templates.select_template({"party_type": "friends"}),
                         "friends-fast")

    def test_cafe_need_is_whole_word(self):
        self.assertFalse(soft_rules.cafe_need({"food_prefs": ["cafeteria"]}))
        self.assertTrue(soft_rules.cafe_need({"food_prefs": ["cà phê sữa"]}))
        self.assertTrue(soft_rules.cafe_need({"food_prefs": ["coffee"]}))

    def test_repair_named_target_is_whole_word(self):
        pois = {"p1": {"name": "Sen Spa", "cat": "spa", "type": "Spa mát xa"}}
        acts = [{"poi_id": "p1", "start": "09:00", "end": "10:00"}]
        issue = {"issue": "khong gian sparkling sach se",
                 "suggestion": ""}
        self.assertIsNone(_named_target(issue, acts, pois, {"p1": 1.0}))


class TestB2FailClosedPool(unittest.TestCase):
    def test_empty_ranked_pool_falls_back_verified_only(self):
        pois = [_poi("r1", "restaurant"), _poi("c1", "cafe"),
                _poi("b1", "beach"), _poi("m1", "market"),
                _poi("draft", "beach", verified=False),
                _poi("b2", "beach")]
        by_id = {p["poi_id"]: p for p in pois}
        cells = _cells(by_id)
        trip = {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
                "end_time": "18:00", "must_visit": [], "avoid": ["b2"]}

        plan = build_plan("balanced", trip, [], by_id, cells, template="")

        pool_ids = [p["poi_id"] for p in plan["_context"]["pois"]]
        # No all-POI fallback: unverified/avoided rows are out of the pool.
        self.assertEqual(sorted(pool_ids), ["b1", "c1", "m1", "r1"])
        self.assertTrue(all(by_id[pid]["verified"] for pid in pool_ids))
        self.assertNotIn("b2", pool_ids)
        self.assertNotIn("draft", pool_ids)
        # Whatever was planned comes from that same verified pool.
        self.assertTrue(plan["activities"])
        for act in plan["activities"]:
            self.assertIn(act["poi_id"], pool_ids)

    def test_fallback_rechecks_must_avoid(self):
        pois = [_poi("b1", "beach"), _poi("bar1", "bar"),
                _poi("spa1", "spa"),
                _poi("draft", "beach", verified=False)]
        by_id = {p["poi_id"]: p for p in pois}
        cells = _cells(by_id)
        trip = {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
                "end_time": "18:00", "must_visit": [], "avoid": [],
                "profile": {"must_avoid": ["nightlife", "spa"]}}

        plan = build_plan("balanced", trip, [], by_id, cells, template="")

        pool_ids = [p["poi_id"] for p in plan["_context"]["pois"]]
        # The re-applied hard filter drops the profile's must_avoid rows.
        self.assertEqual(pool_ids, ["b1"])
        self.assertNotIn("bar1", pool_ids)
        self.assertNotIn("spa1", pool_ids)

    def test_empty_verified_pool_returns_honest_empty_plan(self):
        pois = [_poi("draft", "beach", verified=False), _poi("b2", "beach")]
        by_id = {p["poi_id"]: p for p in pois}
        cells = _cells(by_id)
        trip = {"trip_id": "t", "budget": 3000000, "start_time": "08:00",
                "end_time": "18:00", "must_visit": [], "avoid": ["b2"]}

        plan = build_plan("balanced", trip, [], by_id, cells, template="")

        self.assertEqual(plan["activities"], [])
        self.assertEqual(plan["_context"]["pois"], [])
        self.assertEqual(plan["infeasible_by"]["rule"], "NO_VERIFIED_POOL")
        self.assertTrue(any("fail-closed" in w for w in plan["warnings"]),
                        plan["warnings"])


if __name__ == "__main__":
    unittest.main()
