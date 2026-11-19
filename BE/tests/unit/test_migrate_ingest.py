"""v2.2 build pieces: price range -> tier, user decisions, human verify,
clean reasons and cross-field reconciliation (BE/ml/data/migrate_v2.py)."""

import copy
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from migrate_v2 import (apply_decision, apply_human_verify, build_tags, clean_reason,  # noqa: E402
                        prize_prior, reconcile, tier_of_range, time_budget_of)

from BE.tests.data.fixtures_v22 import rec  # noqa: E402


class TestPriceTier(unittest.TestCase):
    def test_tier_follows_the_range(self):
        self.assertEqual(tier_of_range(0, 0), "free")
        self.assertEqual(tier_of_range(20_000, 60_000), "cheap")
        self.assertEqual(tier_of_range(60_000, 60_000), "cheap")
        self.assertEqual(tier_of_range(200_000, 600_000), "medium")    # midpoint 400k
        self.assertEqual(tier_of_range(900_000, 900_000), "expensive")
        self.assertEqual(tier_of_range(400_000, None), "medium")
        self.assertIsNone(tier_of_range(None, None))


class TestDecisions(unittest.TestCase):
    def test_rename_keeps_raw_and_marks_user(self):
        r = rec()
        apply_decision(r, {"name": "Clover Spa", "_file": "decisions_names_x.json"})
        self.assertEqual(r["name"], "Clover Spa")
        self.assertEqual(r["name_raw"], "Bảo tàng X")
        self.assertEqual(r["provenance"]["name"]["verified_by"], "user")

    def test_status_decision_records_who_decided(self):
        r = rec(status="review")
        apply_decision(r, {"status": "active", "_file": "decisions_x.json"})
        self.assertEqual((r["status"], r["status_reason"]), ("active", None))
        apply_decision(r, {"status": "excluded", "status_reason": "tiệm hoa", "_file": "d.json"})
        self.assertEqual((r["status"], r["status_reason"]), ("excluded", "tiệm hoa"))
        self.assertEqual(r["provenance"]["status"]["source"], "user_decision")

    def test_old_town_ticket_sets_and_clears_the_range(self):
        r = rec(tier="cheap")
        apply_decision(r, {"requires_ticket_of": "osm:parent", "_file": "d.json"})
        self.assertEqual(r["price"], {**r["price"], "tier": "included", "min_vnd": 0, "max_vnd": 0})
        apply_decision(r, {"requires_ticket_of": None, "_file": "d.json"})
        self.assertEqual((r["price"]["tier"], r["price"]["min_vnd"], r["price"]["max_vnd"]),
                         (None, None, None))


class TestHumanVerify(unittest.TestCase):
    def test_human_with_url_sets_fixed_hours_and_tier_range(self):
        r = rec(kind="safe_window", tier=None)
        apply_human_verify(r, {"hours": "07:00-17:30", "price_tier": "cheap",
                               "evidence_url": "https://example.org/ve",
                               "checked_at": "2026-11-19", "_file": "human_verify_v2_x.json"})
        self.assertEqual(r["hours"], {**r["hours"], "open": ["07:00-17:30"], "kind": "fixed"})
        self.assertEqual((r["price"]["tier"], r["price"]["min_vnd"], r["price"]["max_vnd"]),
                         ("cheap", 0, 100_000))
        self.assertEqual(r["provenance"]["hours"]["verified_by"], "human")
        self.assertEqual(r["provenance"]["price"]["evidence_url"], "https://example.org/ve")

    def test_without_url_is_user_and_vnd_sets_an_exact_range(self):
        r = rec(tier=None)
        apply_human_verify(r, {"ticket_vnd": 150_000, "_file": "human_verify_v2_x.json"})
        self.assertEqual((r["price"]["tier"], r["price"]["min_vnd"], r["price"]["max_vnd"]),
                         ("medium", 150_000, 150_000))
        self.assertEqual(r["provenance"]["price"]["verified_by"], "user")

    def test_bad_hours_and_inconsistent_included_are_ignored(self):
        r = rec()
        before = copy.deepcopy(r)
        apply_human_verify(r, {"hours": "sáng thứ 2", "price_tier": "included",
                               "_file": "human_verify_v2_x.json"})
        self.assertEqual(r, before)    # no parent ticket -> 'included' is invalid


class TestCleanReason(unittest.TestCase):
    def test_google_numbers_never_reach_the_reason(self):
        note = "Google xếp 'Quán bar tiếp viên nữ' (5,0★, 626 đánh giá): quán có tiếp viên."
        self.assertEqual(clean_reason(note), "quán có tiếp viên — không hợp lịch trình du lịch")
        note = "Google chỉ có 1 đánh giá (dưới 5): chưa đủ bằng chứng là điểm đáng gợi ý."
        self.assertEqual(clean_reason(note), "quá ít bằng chứng là điểm đáng gợi ý")

    def test_duplicate_keeps_the_target_name(self):
        note = ("Trùng 'Bãi biển Non Nước' (cùng bãi trên OSM). Giữ bản 'Bãi biển Non Nước' "
                "(Google: loại Bãi biển, 232 đánh giá).")
        self.assertEqual(clean_reason(note), "trùng hoặc nằm trong 'Bãi biển Non Nước'")
        note = "Trùng với bản 'Viet Nam's Delights' kia (cách 322 m)."
        self.assertEqual(clean_reason(note), "trùng hoặc nằm trong 'Viet Nam's Delights'")

    def test_unknown_note_has_a_neutral_reason(self):
        self.assertEqual(clean_reason("???"), "loại khi duyệt v1")


class TestReconcile(unittest.TestCase):
    def test_good_times_follow_sourced_hours_only(self):
        r = rec(kind="fixed", open_=("17:00-22:00",))
        r["tags"]["good_times"] = ["morning", "night"]
        reconcile(r)
        self.assertEqual(r["tags"]["good_times"], ["night"])
        self.assertIn("bỏ good_times morning", r["provenance"]["tags"]["note"])
        s = rec(kind="safe_window", open_=("17:30-21:30",))
        s["tags"]["good_times"] = ["morning", "night"]
        reconcile(s)                    # a safe window is not the real opening time
        self.assertEqual(s["tags"]["good_times"], ["morning", "night"])


class TestTimeBudget(unittest.TestCase):
    def test_follows_dwell_not_the_old_v1_tag(self):
        p = {"smart_tags": {"budget": ["full-day"], "space": "outdoor"}}   # v1 said "full day"
        tags, _ = build_tags(p, "viewpoint", "viewpoint", {"p25": 15, "p50": 30, "p75": 50}, {}, False)
        self.assertEqual(tags["time_budget"], "quick")
        self.assertEqual(time_budget_of(45), "quick")
        self.assertEqual(time_budget_of(75), "half_day")
        self.assertEqual(time_budget_of(240), "half_day")
        self.assertEqual(time_budget_of(420), "full_day")


class TestPrizePrior(unittest.TestCase):
    def test_signature_wins_and_local_lowers(self):
        self.assertEqual(prize_prior("religious", True, None, None, None, None)[0], 0.9)
        self.assertEqual(prize_prior("restaurant", False, "tourist", None, None, None)[0], 0.45)
        self.assertEqual(prize_prior("restaurant", False, "local", None, None, None)[0], 0.35)
        self.assertEqual(prize_prior("restaurant", False, None, "Q1", None, None)[0], 0.55)


if __name__ == "__main__":
    unittest.main()
