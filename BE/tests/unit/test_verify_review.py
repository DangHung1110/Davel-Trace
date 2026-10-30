"""Unit test: review pages, verdict ingest and precision scoring (Phase 4).

Covers build_verify_page (OS-independent hashes, lodging dropped, verified
POIs flagged for recheck first, queue reasons re-judged on today's data,
row_hash tracks the shown fields, blind stratified sample), ingest_verdicts
(schema and stale rejections, reviewer conflicts, dropped edits, applied
edits, LOẠI never auto-passed again, re-run is a no-op) and verify_precision
(Wilson interval, Cohen's kappa, strict precision gate).

Run from repo root: python BE/tests/unit/test_verify_review.py -v
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.data import ingest_verdicts as ing  # noqa: E402
from BE.ml.data import spotcheck_v2 as sv  # noqa: E402
from BE.ml.data.verify_precision import cohen_kappa, score, wilson  # noqa: E402
from BE.tools import build_verify_page as bvp  # noqa: E402

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshots" / "danang-v1"


def poi(pid, name, cat, typ, **overrides):
    base = {"poi_id": pid, "name": name, "cat": cat, "type": typ,
            "lat": 16.0544, "lon": 108.2200, "opening_hours": ["09:00-22:00"],
            "rating": 4.5, "source": "serpapi/google-maps", "verified": False,
            "visit_min": {"p25": 50, "p50": 72, "p75": 101},
            "dur_source": "category_rule", "smart_tags": {"ticket": False}, "tags": []}
    base.update(overrides)
    return base


FIXTURE = [
    poi("museum", "Bảo tàng Chăm", "museum", "Bảo tàng", verified=True,
        verified_by="auto-verify-v1", smart_tags={"ticket": True}, ticket_vnd=60000),
    poi("market", "Chợ Non Nước", "market", "Chợ", verified=True,
        verified_by="spotcheck-v1", opening_hours=[]),
    poi("cafe1", "Quán A", "cafe", "Quán cà phê", verified=True,
        verified_by="auto-verify-v1", lat=16.06),
    poi("cafe2", "Quán B", "cafe", "Quán cà phê", verified=True,
        verified_by="auto-verify-v1", lat=16.07),
    poi("pagoda", "Chùa Tam Thai", "landmark", "Chùa", opening_hours=[], lat=16.08),
    poi("hotel", "Khách sạn X", "lodging", "Khách sạn", opening_hours=[], lat=16.09),
]
QUEUE = [{"poi_id": "pagoda", "name": "Chùa Tam Thai", "cat": "landmark",
          "decision": "queue", "hard": [], "queue": ["duration_outlier"], "siblings": []},
         {"poi_id": "hotel", "name": "Khách sạn X", "cat": "lodging",
          "decision": "queue", "hard": [], "queue": ["hours_missing"], "siblings": []}]
XC = {"museum": {"fields": {"exists": "confirmed", "location": "confirmed",
                            "category": "conflict", "hours": "single"},
                 "match": {"osm": "n42", "name": "X", "dist_m": 3.0},
                 "evidence": {"osm_categories": ["market"]}}}


def write_snapshot(directory, pois=FIXTURE, queue=QUEUE, newline="\n"):
    d = Path(directory)
    (d / "pois.json").write_text(json.dumps({"snapshot": "fixture", "pois": pois},
                                            ensure_ascii=False, indent=2), encoding="utf-8")
    with open(d / "auto_verify_queue.jsonl", "w", encoding="utf-8", newline="") as f:
        for row in queue:
            f.write(json.dumps(row, ensure_ascii=False) + newline)
    (d / "osm_crosscheck.json").write_text(json.dumps({"pois": XC}), encoding="utf-8")
    return d


class TestReviewPage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.snap = write_snapshot(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_queue_hash_ignores_line_endings(self):
        _, lf = bvp.build_rows(self.snap)
        with tempfile.TemporaryDirectory() as other:
            _, crlf = bvp.build_rows(write_snapshot(other, newline="\r\n"))
        self.assertEqual(lf["queue_hash"], crlf["queue_hash"])
        self.assertEqual(lf["page_hash"], crlf["page_hash"])

    def test_rows(self):
        rows, meta = bvp.build_rows(self.snap)
        ids = [r["poi_id"] for r in rows]
        self.assertNotIn("hotel", ids)                  # lodging dropped
        self.assertEqual(meta["queue_excluded"], 1)
        self.assertEqual(ids[:2], ["museum", "market"])  # recheck before queue
        by_id = {r["poi_id"]: r for r in rows}
        self.assertEqual(by_id["museum"]["queue"], ["osm_category_conflict"])
        self.assertEqual(by_id["market"]["queue"], ["hours_missing"])
        self.assertEqual(by_id["market"]["safe_hours"], [])
        # re-judged today: the file's duration_outlier is gone
        self.assertNotIn("duration_outlier", by_id["pagoda"]["queue"])
        self.assertEqual(by_id["museum"]["osm"]["url"], "https://www.openstreetmap.org/node/42")

    def test_row_hash_tracks_shown_fields(self):
        a = copy.deepcopy(FIXTURE[0])
        b = dict(a, opening_hours=["08:00-17:00"])
        c = dict(a, pros=["x"])
        self.assertNotEqual(bvp.row_hash(a), bvp.row_hash(b))
        self.assertEqual(bvp.row_hash(a), bvp.row_hash(c))

    def test_drafts_ride_along_without_changing_the_page_hash(self):
        _, before = bvp.build_rows(self.snap)
        draft = {"poi_id": "museum", "suggest": "dung", "edits": {"cat": "museum"},
                 "note": "x", "by": "claude-google-maps", "checked_at": "2026-10-30"}
        (self.snap / "review_drafts.jsonl").write_text(json.dumps(draft) + "\n",
                                                       encoding="utf-8")
        rows, after = bvp.build_rows(self.snap)
        by_id = {r["poi_id"]: r for r in rows}
        self.assertEqual(by_id["museum"]["draft"]["suggest"], "dung")
        self.assertNotIn("draft", by_id["market"])
        self.assertEqual(after["drafts"], 1)
        self.assertEqual(before["page_hash"], after["page_hash"])

    def test_committed_drafts_fit_the_edit_fields(self):
        pois = {p["poi_id"] for p in json.loads(
            (SNAPSHOT / "pois.json").read_text(encoding="utf-8"))["pois"]}
        drafts = bvp.load_drafts(SNAPSHOT)
        self.assertTrue(drafts)
        for pid, draft in drafts.items():
            self.assertIn(pid, pois)
            self.assertIn(draft["suggest"], {"dung", "loai", "skip"})
            self.assertEqual(ing.edit_errors(draft["edits"]), [], pid)
            # the page has one hours field where "," separates sessions of a
            # day, so a draft can only prefill one window list for every day
            self.assertLessEqual(len(draft["edits"].get("opening_hours", [])), 1, pid)

    def test_render_is_safe(self):
        rows, meta = bvp.build_rows(self.snap)
        rows[0]["name"] = "</script><b>x"
        html = bvp.render(rows, meta)
        self.assertNotIn("</script><b>", html)
        self.assertIn('"mode":"review"', html)


class TestSample(unittest.TestCase):
    def test_allocate(self):
        plan = bvp.allocate({"restaurant": 99, "cafe": 74, "museum": 8, "viewpoint": 1}, 50)
        self.assertEqual(sum(plan.values()), 50)
        self.assertTrue(all(1 <= plan[k] for k in plan))
        self.assertEqual(plan["viewpoint"], 1)
        self.assertGreater(plan["restaurant"], plan["cafe"])
        self.assertEqual(sum(bvp.allocate({"a": 2, "b": 1}, 10).values()), 3)

    def test_sample_is_blind_and_seeded(self):
        with tempfile.TemporaryDirectory() as d:
            snap = write_snapshot(d)
            rows, meta = bvp.build_sample(snap, 3, seed=1)
            again, _ = bvp.build_sample(snap, 3, seed=1)
        self.assertEqual([r["poi_id"] for r in rows], [r["poi_id"] for r in again])
        self.assertEqual({r["poi_id"] for r in rows}, {"museum", "cafe1", "cafe2"})
        for key in ("osm", "hard", "queue", "verified_by", "verified", "source"):
            self.assertNotIn(key, rows[0])
        self.assertEqual(meta["population"], 3)

    def test_real_snapshot_builds(self):
        rows, meta = bvp.build_rows(SNAPSHOT)
        self.assertFalse([r for r in rows if r["cat"] in bvp.EXCLUDED_CATS])
        self.assertGreater(meta["recheck"], 0)
        self.assertTrue(all(r["row_hash"] for r in rows))


def line(pid, verdict="dung", reviewer="Lan", ts="2026-10-30T01:00:00Z", **kw):
    out = {"poi_id": pid, "verdict": verdict, "note": "", "reviewer": reviewer, "ts": ts,
           "page": "review"}
    out.update(kw)
    return out


class TestIngest(unittest.TestCase):
    def setUp(self):
        self.pois = {p["poi_id"]: copy.deepcopy(p) for p in FIXTURE}

    def plan(self, lines):
        return ing.plan_ingest([("f.jsonl", i, l, "") for i, l in enumerate(lines, 1)],
                               self.pois)

    def test_rejections(self):
        plan = self.plan([
            line("nope"),
            line("pagoda", verdict="maybe"),
            line("pagoda", reviewer=""),
            line("pagoda", page="sample"),
            line("pagoda", edits={"opening_hours": ["7h-17h"]}),
            # two weekday variants typed as two sessions of one day
            line("pagoda", edits={"opening_hours": ["07:00-17:30, 07:00-17:00"]}),
            line("pagoda", edits={"visit_p50": 2}),
            line("pagoda", row_hash="000000000000"),
        ])
        self.assertEqual(plan["apply"], {})
        self.assertEqual(len(plan["rejected"]), 8)
        self.assertIn("stale", plan["rejected"][-1]["reason"])

    def test_conflicts_and_dropped_edits(self):
        plan = self.plan([
            line("pagoda", reviewer="A"), line("pagoda", verdict="loai", reviewer="B"),
            line("cafe1", reviewer="A", edits={"visit_p50": 40}),
            line("cafe1", reviewer="B", edits={"visit_p50": 60, "cat": "bar"}),
        ])
        self.assertEqual([c["poi_id"] for c in plan["conflicts"]], ["pagoda"])
        self.assertEqual(plan["apply"]["cafe1"]["edits"], {"cat": "bar"})
        self.assertEqual(plan["dropped_edits"][0]["field"], "visit_p50")

    def test_apply_edits_and_rejection_sticks(self):
        h = bvp.row_hash(self.pois["pagoda"])
        plan = self.plan([
            line("pagoda", row_hash=h, draft_by="claude@2026-10-30",
                 edits={"opening_hours": ["07:00-17:30"], "visit_p50": 30}),
            line("museum", verdict="loai"),
        ])
        for pid, decision in plan["apply"].items():
            ing.apply_one(self.pois[pid], decision, "2026-10-30")
        pagoda, museum = self.pois["pagoda"], self.pois["museum"]
        self.assertEqual((pagoda["verified"], pagoda["verified_by"]),
                         (True, ing.VERIFIED_BY))
        self.assertEqual((pagoda["opening_hours"], pagoda["hours_source"]),
                         (["07:00-17:30"], "human"))
        self.assertEqual(pagoda["visit_min"], {"p25": 21, "p50": 30, "p75": 42})
        self.assertEqual(pagoda["dur_source"], "human")
        self.assertFalse(museum["verified"])
        self.assertNotIn("verified_by", museum)
        self.assertEqual(pagoda["review"]["by"][0]["draft_by"], "claude@2026-10-30")
        verdicts = {v["poi_id"]: v["decision"] for v in sv.build_plan(list(self.pois.values()))[0]}
        self.assertEqual(verdicts["museum"], sv.HUMAN_REJECTED)
        # the same lines again are a no-op
        again = self.plan([line("pagoda", row_hash=h), line("museum", verdict="loai")])
        self.assertEqual(again["apply"], {})
        self.assertEqual({r["reason"] for r in again["rejected"]}, {"already applied"})


class TestPrecision(unittest.TestCase):
    def test_wilson_and_kappa(self):
        lo, hi = wilson(34, 39)
        self.assertAlmostEqual(lo, 0.733, places=2)
        self.assertAlmostEqual(hi, 0.944, places=2)
        self.assertEqual(cohen_kappa([(True, True), (False, False)]), 1.0)
        self.assertAlmostEqual(cohen_kappa([(True, True), (True, False), (False, False),
                                            (False, True)]), 0.0)

    def test_strict_gate(self):
        def lines(verdicts):
            return {f"p{i}": {"poi_id": f"p{i}", "verdict": v, "page": "sample"}
                    for i, v in enumerate(verdicts)}
        a = lines(["dung"] * 50)
        b = lines(["dung"] * 49 + ["sai"])
        report = score({"A": a, "B": b})
        self.assertEqual(report["strict"]["correct"], 49)
        self.assertEqual(report["agreement"]["disagree"], ["p49"])
        # 49/50 = 98%, but the Wilson lower bound is 0.895 < 0.90: with 50 rows
        # a single error already fails the gate.
        self.assertFalse(report["strict"]["pass"])
        self.assertLess(report["strict"]["ci95"][0], 0.90)
        perfect = score({"A": lines(["dung"] * 50)})
        self.assertTrue(perfect["strict"]["pass"])


if __name__ == "__main__":
    unittest.main()
