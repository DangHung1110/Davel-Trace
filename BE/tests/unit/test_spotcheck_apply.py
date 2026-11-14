"""Unit tests for the verified-flag applier (full-audit B6 + C2).

Tiny in-memory fixtures only — never the real 742-POI snapshot. Covers:
  - all auto-checks green -> verified=true + verified_by/verified_at stamp
  - ambiguous rows (missing hours, perfect rating, duplicates) -> human queue,
    never flipped
  - deterministic criteria violations -> `fail`, never flipped
  - coarse type / fine cat refinements pass, contradictions queue
  - --dry-run (default) writes nothing at all
  - re-running --apply-flag is idempotent (byte-identical pois.json)

Run: $env:PYTHONPATH='BE'; python -m pytest BE/tests/unit/test_spotcheck_apply.py -q
     python -m unittest BE.tests.unit.test_spotcheck_apply -v
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.data import spotcheck_v2 as sv  # noqa: E402


def poi(pid: str, name: str, cat: str, typ: str, **overrides) -> dict:
    """Minimal snapshot row; every default passes the auto criteria."""
    base = {
        "poi_id": pid,
        "name": name,
        "cat": cat,
        "type": typ,
        "lat": 16.0544,
        "lon": 108.2200,
        "opening_hours": ["09:00-22:00"],
        "rating": 4.5,
        "source": "serpapi/google-maps",
        "verified": False,
        "visit_min": {"p25": 50, "p50": 72, "p75": 101},
        "smart_tags": {"ticket": False},
    }
    base.update(overrides)
    return base


def write_snapshot(directory: str, pois: list[dict]) -> str:
    path = os.path.join(directory, "pois.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"snapshot": "fixture", "count": len(pois), "pois": pois},
                  f, ensure_ascii=False, indent=2)
    return path


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_main(argv: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = sv.main(argv)
    assert rc == 0, f"main() returned {rc}"
    return buf.getvalue()


class JudgeTests(unittest.TestCase):
    def plan_for(self, *pois: dict) -> dict[str, dict]:
        plan, _ = sv.build_plan(list(pois))
        return {v["poi_id"]: v for v in plan}

    def test_clean_row_auto_passes(self):
        verdicts = self.plan_for(poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng"))
        self.assertEqual(verdicts["a"]["decision"], sv.AUTO_PASS)
        self.assertEqual(verdicts["a"]["hard"], [])
        self.assertEqual(verdicts["a"]["queue"], [])

    def test_missing_hours_is_queued_not_failed(self):
        verdicts = self.plan_for(
            poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng", opening_hours=[]))
        self.assertEqual(verdicts["a"]["decision"], sv.QUEUE)
        self.assertIn("hours_missing", verdicts["a"]["queue"])
        self.assertEqual(verdicts["a"]["hard"], [])

    def test_zero_length_hours_is_a_hard_fail(self):
        verdicts = self.plan_for(
            poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng",
                opening_hours=["10:00-10:00"]))
        self.assertEqual(verdicts["a"]["decision"], sv.FAIL)
        self.assertIn("hours_zero_length", verdicts["a"]["hard"])

    def test_overnight_hours_are_plausible(self):
        verdicts = self.plan_for(
            poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng",
                opening_hours=["07:30-02:00"]))
        self.assertEqual(verdicts["a"]["decision"], sv.AUTO_PASS)

    def test_coords_outside_bbox_fails(self):
        verdicts = self.plan_for(
            poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng",
                lat=16.90, lon=108.20))
        self.assertEqual(verdicts["a"]["decision"], sv.FAIL)
        self.assertIn("coords_outside_bbox", verdicts["a"]["hard"])

    def test_missing_source_fails(self):
        verdicts = self.plan_for(
            poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng", source=""))
        self.assertEqual(verdicts["a"]["decision"], sv.FAIL)
        self.assertIn("source_missing", verdicts["a"]["hard"])

    def test_perfect_rating_and_ticket_claim_queue(self):
        verdicts = self.plan_for(
            poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng", rating=5.0),
            poi("b", "Bảo Tàng Nhỏ Xinh", "museum", "Bảo tàng",
                smart_tags={"ticket": True}))
        self.assertEqual(verdicts["a"]["decision"], sv.QUEUE)
        self.assertIn("rating_perfect", verdicts["a"]["queue"])
        self.assertEqual(verdicts["b"]["decision"], sv.QUEUE)
        self.assertIn("ticket_unverified", verdicts["b"]["queue"])

    def test_duplicate_names_queue_both_sides(self):
        verdicts = self.plan_for(
            poi("a", "Mây Coffee", "cafe", "Quán cà phê"),
            poi("b", "Mây Coffee", "cafe", "Quán cà phê"))
        for pid in ("a", "b"):
            self.assertEqual(verdicts[pid]["decision"], sv.QUEUE)
            self.assertIn("duplicate_name", verdicts[pid]["queue"])
        self.assertEqual(verdicts["a"]["siblings"], ["b"])

    def test_coarse_type_refinement_is_consistent(self):
        # Raw Google type is a coarse "attraction"; curated cat is `museum`.
        verdicts = self.plan_for(
            poi("a", "Bảo Tàng Chăm", "museum", "Điểm thu hút khách du lịch"))
        self.assertEqual(verdicts["a"]["decision"], sv.AUTO_PASS)

    def test_contradictory_type_vs_cat_queues(self):
        # Tea shop typed as a shop (market) but curated as cafe: either field
        # may be wrong -> human decides, no flip.
        verdicts = self.plan_for(
            poi("a", "Trà Quán Góc Nhà", "cafe", "Cửa hàng trà truyền thống"))
        self.assertEqual(verdicts["a"]["decision"], sv.QUEUE)
        self.assertIn("type_cat_mismatch", verdicts["a"]["queue"])

    def test_unmapped_type_queues(self):
        verdicts = self.plan_for(
            poi("a", "Nhà Văn Hoá", "attraction", "Hiệp hội/Tổ chức"))
        self.assertEqual(verdicts["a"]["decision"], sv.QUEUE)
        self.assertIn("type_unmapped", verdicts["a"]["queue"])

    def test_already_verified_rows_are_out_of_scope(self):
        verdicts = self.plan_for(
            poi("a", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng", verified=True))
        self.assertEqual(verdicts["a"]["decision"], sv.ALREADY)


class ApplierTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.path = write_snapshot(self.dir, [
            poi("auto", "Quán Ăn Biển Xanh", "restaurant", "Nhà hàng"),
            poi("nohours", "Bảo Tàng Không Giờ", "museum", "Bảo tàng",
                opening_hours=[]),
            poi("bad", "Quán Ngoài Bờ Biển", "restaurant", "Nhà hàng",
                lat=17.00),
            poi("done", "Quán Đã Duyệt", "restaurant", "Nhà hàng", verified=True),
        ])

    def test_apply_flips_only_auto_pass(self):
        before = load_snapshot(self.path)
        plan, _ = sv.build_plan(before["pois"])
        flipped = sv.apply_plan(before["pois"], plan, today="2026-10-29")
        self.assertEqual(flipped, 1)
        rows = {p["poi_id"]: p for p in before["pois"]}
        self.assertTrue(rows["auto"]["verified"])
        self.assertEqual(rows["auto"]["verified_by"], sv.AUTO_VERIFIED_BY)
        self.assertEqual(rows["auto"]["verified_at"], "2026-10-29")
        for pid in ("nohours", "bad"):
            self.assertFalse(rows[pid]["verified"])
            self.assertNotIn("verified_by", rows[pid])

    def test_cli_dry_run_is_the_default_and_writes_nothing(self):
        before = read_bytes(self.path)
        out = run_main(["--snapshot", self.dir])
        self.assertIn("DRY-RUN (no files written)", out)
        self.assertIn("auto_pass=1", out)
        self.assertEqual(read_bytes(self.path), before)
        self.assertEqual(os.listdir(self.dir), ["pois.json"])

    def test_cli_apply_writes_queue_and_is_idempotent(self):
        run_main(["--snapshot", self.dir, "--apply-flag"])
        after_first = read_bytes(self.path)
        rows = {p["poi_id"]: p for p in load_snapshot(self.path)["pois"]}
        self.assertTrue(rows["auto"]["verified"])
        self.assertFalse(rows["nohours"]["verified"])
        self.assertFalse(rows["bad"]["verified"])

        queue = read_jsonl(os.path.join(self.dir, sv.QUEUE_FILENAME))
        by_id = {q["poi_id"]: q for q in queue}
        self.assertEqual(set(by_id), {"nohours", "bad"})
        self.assertEqual(by_id["nohours"]["decision"], sv.QUEUE)
        self.assertEqual(by_id["bad"]["decision"], sv.FAIL)

        # Second apply: nothing left to flip, files stay byte-identical.
        out = run_main(["--snapshot", self.dir, "--apply-flag"])
        self.assertIn("auto_pass=0", out)
        self.assertIn("flipped=0", out)
        self.assertEqual(read_bytes(self.path), after_first)
        self.assertEqual(
            read_jsonl(os.path.join(self.dir, sv.QUEUE_FILENAME)), queue)

    def test_explicit_dry_run_flag_matches_default(self):
        before = read_bytes(self.path)
        out = run_main(["--snapshot", self.dir, "--dry-run"])
        self.assertIn("DRY-RUN", out)
        self.assertEqual(read_bytes(self.path), before)

    def test_missing_coords_fails_without_crashing_report(self):
        write_snapshot(self.dir, [
            poi("nocoords", "Quán Không Toạ Độ", "restaurant", "Nhà hàng",
                lat=None, lon=None)])
        out = run_main(["--snapshot", self.dir])
        self.assertIn("auto_pass=0", out)
        self.assertIn("fail=1", out)
        self.assertIn("coords_missing=1", out)

    def test_verified_by_override_is_stamped(self):
        run_main(["--snapshot", self.dir, "--apply-flag",
                  "--verified-by", "auto-verify-v1-batch2"])
        rows = {p["poi_id"]: p for p in load_snapshot(self.path)["pois"]}
        self.assertEqual(rows["auto"]["verified_by"], "auto-verify-v1-batch2")

    def test_queue_out_override(self):
        target = os.path.join(self.dir, "queue", "human.jsonl")
        os.makedirs(os.path.dirname(target))
        run_main(["--snapshot", self.dir, "--apply-flag", "--queue-out", target])
        self.assertTrue(os.path.exists(target))
        self.assertEqual(len(read_jsonl(target)), 2)


if __name__ == "__main__":
    unittest.main()
