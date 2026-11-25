"""Plan pairs for two human raters (BE/eval/human/make_plan_pairs.py)."""

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from BE.eval.human import make_plan_pairs as mpp  # noqa: E402

HUMAN = ROOT / "BE" / "eval" / "human"


def plan(ids, passed=True, day=None, start=8 * 60, dwell=60, leg=10, cost=100_000, travel=None):
    """A planner-shaped plan: stops back to back with a `leg`-minute drive between."""
    acts, segs, t = [], [], start
    for i, pid in enumerate(ids):
        if i:
            segs.append({"from_id": ids[i - 1], "to_id": pid, "minutes": leg, "day": day})
            t += leg
        acts.append({"poi_id": pid, "start": f"{t // 60:02d}:{t % 60:02d}",
                     "end": f"{(t + dwell) // 60:02d}:{(t + dwell) % 60:02d}", "day": day})
        t += dwell
    return {"passed": passed, "activities": acts, "segments": segs, "total_cost": cost,
            "travel_min": travel if travel is not None else leg * max(0, len(ids) - 1), "warnings": []}


def pois(*ids):
    return {pid: {"poi_id": pid, "name": f"Điểm {pid}", "type": "Công viên", "fee": 0} for pid in ids}


def row(request_id, plans, source="audit", trip=None):
    return {"request_id": request_id, "source": source, "status": 200,
            "trip": trip or {"budget": 3_000_000, "travelers": 2, "start_time": "08:00", "end_time": "20:00"},
            "plans": plans}


class TestDifference(unittest.TestCase):
    def test_edit_distance(self):
        self.assertEqual(mpp.edit_distance([], []), 0)
        self.assertEqual(mpp.edit_distance(list("abcde"), list("abcde")), 0)
        self.assertEqual(mpp.edit_distance(list("abcde"), list("abXde")), 1)    # one stop swapped
        self.assertEqual(mpp.edit_distance(list("abcde"), list("abcdeX")), 1)   # one stop added
        self.assertEqual(mpp.edit_distance(list("abcde"), list("bacde")), 2)    # two stops reordered
        self.assertEqual(mpp.edit_distance(list("abc"), list("xyz")), 3)

    def test_difference_counts_days(self):
        one = plan(["a", "b", "c", "d"], day=1)
        moved = {**one, "activities": [{**a, "day": 2 if a["poi_id"] == "d" else 1} for a in one["activities"]]}
        diff = mpp.difference(one, moved)
        self.assertEqual(diff["edits"], 1)          # the same place on another day is another stop
        self.assertEqual(diff["jaccard"], 1.0)
        self.assertEqual(diff["shared"], 4)

    def test_near_identical(self):
        five = plan(list("abcde"))
        self.assertTrue(mpp.near_identical(mpp.difference(five, five)))
        self.assertTrue(mpp.near_identical(mpp.difference(five, plan(list("abXde")))))
        self.assertFalse(mpp.near_identical(mpp.difference(five, plan(list("aXYde")))))
        twelve = plan([f"s{i}" for i in range(12)])
        two_off = plan([f"s{i}" for i in range(10)] + ["x", "y"])
        self.assertTrue(mpp.near_identical(mpp.difference(twelve, two_off)))   # 2 of 12 < 0.2


class TestCandidates(unittest.TestCase):
    def test_drops_unshown_and_near_identical_plans(self):
        rows = [row("r1", {
            "experience": plan(list("xyzw")),
            "balanced": plan(list("abcd")),
            "savings": plan(list("abcd")),           # the same plan as balanced
        }), row("r2", {
            "savings": plan(list("abcd")),
            "balanced": plan(list("efgh"), passed=False),
            "experience": plan(["a"]),                # one stop: the app would not show it
        })]
        keep, dropped = mpp.candidate_pairs(rows)
        self.assertEqual([(c["request_id"], c["first"], c["second"]) for c in keep],
                         [("r1", "savings", "experience"), ("r1", "balanced", "experience")])
        reasons = {(d["request_id"], d["first"], d["second"]): d["reason"] for d in dropped}
        self.assertEqual(reasons[("r1", "savings", "balanced")], "near-identical")
        self.assertTrue(all(reasons[k].startswith("plan not shown") for k in reasons if k[0] == "r2"))
        self.assertEqual(len(dropped), 4)

    def test_other_variant_names_sort_after_the_profiles(self):
        rows = [row("r1", {"w2": plan(list("abcd")), "experience": plan(list("efgh")), "w1": plan(list("ijkl"))})]
        keep, _ = mpp.candidate_pairs(rows)
        self.assertEqual([(c["first"], c["second"]) for c in keep],
                         [("experience", "w1"), ("experience", "w2"), ("w1", "w2")])


class TestSelection(unittest.TestCase):
    def setUp(self):
        letters = "abcdefghijklmnop"
        self.rows = [row(f"r{i:02d}", {"savings": plan(list(letters[0:4])), "balanced": plan(list(letters[4:8])),
                                      "experience": plan(list(letters[8:12]))}) for i in range(10)]
        self.candidates, _ = mpp.candidate_pairs(self.rows)

    def test_round_robin_spreads_and_balances(self):
        picked = mpp.select_pairs(self.candidates, n=15, per_request=2, seed=7)
        self.assertEqual(len(picked), 15)
        self.assertEqual(len({c["request_id"] for c in picked[:10]}), 10)   # round 1: every request once
        self.assertLessEqual(max(Counter(c["request_id"] for c in picked).values()), 2)
        combos = Counter(c["combo"] for c in picked)
        self.assertLessEqual(max(combos.values()) - min(combos.values()), 1)
        for a, b in zip(picked, picked[1:]):
            self.assertNotEqual(a["request_id"], b["request_id"])

    def test_seeded(self):
        ids = lambda seed: [(c["request_id"], c["combo"]) for c in mpp.select_pairs(self.candidates, 15, 2, seed)]  # noqa: E731
        self.assertEqual(ids(7), ids(7))
        self.assertNotEqual(ids(7), ids(8))

    def test_per_request_caps_the_total(self):
        self.assertEqual(len(mpp.select_pairs(self.candidates, n=100, per_request=2)), 20)
        self.assertEqual(len(mpp.select_pairs(self.candidates, n=100, per_request=3)), 30)

    def test_sides_are_balanced_per_combo(self):
        picked = mpp.select_pairs(self.candidates, n=30, per_request=3, seed=7)
        flips = mpp.assign_sides(picked, seed=7)
        for combo in {c["combo"] for c in picked}:
            sides = [f for c, f in zip(picked, flips) if c["combo"] == combo]
            self.assertIn(sum(sides), (len(sides) // 2, (len(sides) + 1) // 2))


class TestViews(unittest.TestCase):
    def test_plan_view_legs_idle_prices(self):
        by_id = pois("a", "b", "c")
        by_id["b"] = {"poi_id": "b", "name": "Quán Mì", "data_version": "v2.1", "category": "restaurant",
                      "price": {"tier": "cheap"}, "provenance": {"price": {"verified_by": "inferred"}},
                      "dishes": ["mì Quảng"]}
        p = plan(["a", "b", "c"], leg=10)
        p["activities"][2]["start"] = "10:40"      # b ends 10:10, 10 min drive, 20 min left over
        p["activities"][2]["end"] = "11:40"
        view = mpp.plan_view(p, by_id)
        a, b, c = view["stops"]
        self.assertIsNone(a["leg_min"])
        self.assertEqual((b["leg_min"], b["idle_min"]), (10, 0))
        self.assertEqual((c["leg_min"], c["idle_min"]), (10, 20))
        self.assertEqual((b["fee"], b["fee_estimated"]), (50_000, True))
        self.assertEqual(b["kind"], "Nhà hàng · mì Quảng")
        self.assertEqual((a["fee"], a["fee_estimated"], a["kind"]), (0, False, "Công viên"))
        self.assertEqual((view["start"], view["end"], view["total_cost"]), ("08:00", "11:40", 100_000))
        self.assertIn("query=Qu%C3%A1n%20M%C3%AC", b["maps"])

    def test_a_new_day_has_no_leg(self):
        p = plan(["a", "b"], day=1)
        p2 = plan(["c", "d"], day=2)
        p["activities"] += p2["activities"]
        p["segments"] += p2["segments"]
        stops = mpp.plan_view(p, pois("a", "b", "c", "d"))["stops"]
        self.assertEqual([s["leg_min"] for s in stops], [None, 10, None, 10])
        self.assertEqual([s["day"] for s in stops], [1, 1, 2, 2])

    def test_hidden_warnings(self):
        p = plan(["a", "b"])
        p["warnings"] = ["khong lay duoc du bao thoi tiet, dung nhiet do gia dinh 30.0C",
                         "chi phi la uoc tinh theo muc gia, chua phai gia that",
                         "ngay 2: chi phi la uoc tinh theo muc gia", "khong dua vao lich 'X': khong co trong du lieu"]
        self.assertEqual(mpp.plan_view(p, pois("a", "b"))["notes"], ["khong dua vao lich 'X': khong co trong du lieu"])

    def test_request_view(self):
        by_id = pois("m1", "m2", "v1")
        trip = {"budget": 600_000, "travelers": 2, "start_time": "08:00", "end_time": "20:00", "days": 1,
                "date": "2026-11-16", "activities": ["chùa"], "must_visit": ["m1", "Ngũ Hành Sơn"], "avoid": ["v1"],
                "order_prefs": [["m1", "m2"]],
                "profile": {"party_type": "couple", "pace": 2, "fitness": 2, "allergy": ["seafood"],
                            "accessibility": ["wheelchair"], "must_avoid": ["nightlife"]}}
        view = mpp.request_view(trip, by_id)
        self.assertEqual(view["party"], "Cặp đôi")
        self.assertEqual(view["date"], "Thứ 2, 16/11/2026")
        self.assertEqual(view["must_visit"], ["Điểm m1", "Ngũ Hành Sơn"])
        self.assertEqual(view["avoid"], ["Điểm v1"])
        self.assertEqual(view["order"], ["Điểm m1 trước Điểm m2"])
        self.assertEqual(view["notes"], ["Nhịp đi vừa", "Thể lực trung bình", "Dị ứng hải sản",
                                         "Có người đi xe lăn", "Không muốn: chơi đêm, quán bar"])
        self.assertEqual(mpp.request_view({"budget": 1}, by_id)["party"], "Chưa rõ nhóm khách")

    def test_gold_trip_fits_the_party(self):
        by_id = pois("m1", "v1")
        query = {"trip": {"budget": 1_000_000, "travelers": 1, "start_time": "07:00", "end_time": "12:00",
                          "must_visit": ["m1", "gone"], "avoid": ["v1", "gone2"], "order_prefs": [["m1", "gone"]],
                          "activities": ["tắm biển"]},
                 "profile": {"party_type": "couple", "pace": 2, "fitness": 2, "food_prefs": []}}
        trip = mpp.gold_trip(query, by_id)
        self.assertEqual(trip["travelers"], 2)                 # a couple is two people
        self.assertEqual((trip["must_visit"], trip["avoid"], trip["order_prefs"]), (["m1"], ["v1"], []))
        self.assertEqual(trip["profile"], {"party_type": "couple", "pace": 2, "fitness": 2})
        self.assertEqual(query["trip"]["travelers"], 1)       # the gold query itself is untouched


class TestDataset(unittest.TestCase):
    def setUp(self):
        letters = "abcdefghijkl"
        self.by_id = pois(*letters)
        self.rows = [row(f"r{i}", {"savings": plan(list(letters[0:4])), "balanced": plan(list(letters[4:8])),
                                   "experience": plan(list(letters[8:12]))}) for i in range(6)]

    def test_raters_never_see_which_profile(self):
        pairs_doc, key_doc = mpp.build_dataset(self.rows, self.by_id, n=12, built_at="2026-11-25")
        blob = json.dumps(pairs_doc, ensure_ascii=False)
        for word in ("savings", "balanced", "experience", "Tiết kiệm", "Cân bằng", "Trải nghiệm", "r0/"):
            self.assertNotIn(word, blob)
        self.assertEqual(pairs_doc["dataset"], key_doc["dataset"])
        self.assertEqual(len(pairs_doc["pairs"]), 12)
        rows = {r["request_id"]: r for r in self.rows}
        for shown in pairs_doc["pairs"]:
            k = key_doc["pairs"][shown["pair_id"]]
            self.assertEqual({k["A"], k["B"]}, {k["first"], k["second"]})
            for side in ("A", "B"):
                variant = k["variants"][k[side]]
                expected = mpp.plan_view(rows[k["request_id"]]["plans"][variant], self.by_id)
                self.assertEqual(shown[side], expected)
        self.assertEqual(key_doc["stats"]["first_shown_as_a"], 6)
        self.assertEqual(set(key_doc["requests"]), {f"r{i}" for i in range(6)})

    def test_dataset_id_follows_the_content(self):
        one, _ = mpp.build_dataset(self.rows, self.by_id, n=6, built_at="2026-11-25")
        again, _ = mpp.build_dataset(self.rows, self.by_id, n=6, built_at="2026-12-01")
        other, _ = mpp.build_dataset(self.rows, self.by_id, n=6, seed=8, built_at="2026-11-25")
        self.assertEqual(one["dataset"], again["dataset"])     # the build date is not content
        self.assertNotEqual(one["dataset"], other["dataset"])

    def test_cache_is_reused_only_for_its_snapshot(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp, "plans.json")
            self.assertEqual(mpp.cached_rows(cache, "danang-v2"), {})
            mpp.write_json(cache, {"snapshot": "danang-v2", "rows": [
                {**self.rows[0], "status": 200}, {**self.rows[1], "status": 500}]})
            self.assertEqual(list(mpp.cached_rows(cache, "danang-v2")), ["r0"])   # a failed request is planned again
            self.assertEqual(mpp.cached_rows(cache, "danang-v1"), {})

    def test_embed(self):
        page = '<p>x</p><script type="application/json" id="pairs-data">{"pairs":[]}</script><script>go()</script>'
        doc = {"dataset": "d", "pairs": [{"name": "Bar </script><b>"}]}
        out = mpp.embed(page, doc)
        self.assertEqual(mpp.embed(out, doc), out)
        self.assertTrue(out.endswith("<script>go()</script>"))
        inner = out[out.index(mpp.DATA_OPEN) + len(mpp.DATA_OPEN):out.index("</script>", out.index(mpp.DATA_OPEN))]
        self.assertNotIn("<", inner)
        self.assertEqual(json.loads(inner), doc)


class TestCommittedSample(unittest.TestCase):
    """The pairs file, the key and the page in the repo belong to one dataset."""

    def test_files_agree(self):
        pairs_path, key_path, page_path = (HUMAN / "plan_pairs_v1.json", HUMAN / "plan_pairs_v1_key.json",
                                           HUMAN / "plan_pairs.html")
        if not pairs_path.exists():
            self.skipTest("no committed sample")
        pairs_doc = json.loads(pairs_path.read_text(encoding="utf-8"))
        key_doc = json.loads(key_path.read_text(encoding="utf-8"))
        page = page_path.read_text(encoding="utf-8")
        start = page.index(mpp.DATA_OPEN) + len(mpp.DATA_OPEN)
        embedded = json.loads(page[start:page.index("</script>", start)])
        self.assertEqual(embedded, pairs_doc)
        self.assertEqual(pairs_doc["dataset"], key_doc["dataset"])
        self.assertEqual(pairs_doc["dataset"], mpp.dataset_id(pairs_doc["pairs"]))
        self.assertTrue(100 <= len(pairs_doc["pairs"]) <= 200)
        self.assertEqual([p["pair_id"] for p in pairs_doc["pairs"]], sorted(key_doc["pairs"]))
        for k in key_doc["pairs"].values():
            self.assertEqual({k["A"], k["B"]}, {k["first"], k["second"]})
            self.assertIn(k["request_id"], key_doc["requests"])
        blob = json.dumps(pairs_doc, ensure_ascii=False)
        for word in ("savings", "balanced", "experience", "Tiết kiệm", "Cân bằng", "Trải nghiệm"):
            self.assertNotIn(word, blob)


if __name__ == "__main__":
    unittest.main()
