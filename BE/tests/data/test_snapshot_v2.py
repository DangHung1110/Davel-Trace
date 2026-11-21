"""Data rules for snapshot `danang-v2` in format v2.1 (docs/travelagent/DATA_SPEC_v2_1.md §5).

Two layers:

- Structural rules 1-12 (always on): must hold for every build.
- Data-freeze gates G1-G5 (run with `P0_GATE=1`): completeness targets of
  DATA_FIX_PLAN.md §4. Expected to fail until the matching work package is
  done; skipped in the normal suite so a red gate never hides a regression.

Rule 12 (clean names) is enforced as a gate until WP5 (name table reviewed
by the user) lands; it then moves to the always-on layer.

Run from the repo root:  python -m pytest BE/tests/data -q
                          P0_GATE=1 python -m pytest BE/tests/data -q -k gate
"""

import csv
import json
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

import v2_rules as R  # noqa: E402
from migrate_v2 import V21_KEYS, PROVENANCE_KEYS  # noqa: E402
from BE.app.services import retrieval  # noqa: E402
from BE.app.services.snapshot import load_snapshot  # noqa: E402
from BE.common import (PRICE_TIERS, effective_fee, fee_upper, load_json,  # noqa: E402
                       matrix_path, poi_view, view_pois)

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
EXPORTS = os.path.join(ROOT, "BE", "data", "exports", "danang-v2")
GOLD_V2 = os.path.join(ROOT, "BE", "eval", "gold", "gold_v2.json")
VERIFIED_BY = {"human", "open_data", "user", "agent_web", "inferred"}
GOOGLE_KEYS = {"rating", "price_level", "type", "ambience", "pros", "cons"}
HOURS_KINDS = {"fixed", "safe_window", "by_booking", "unknown"}
STATUSES = {"active", "review", "excluded"}
SPAN = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
GATE = os.environ.get("P0_GATE") == "1"


def _rows(name):
    with open(os.path.join(EXPORTS, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _stop(p):
    """A POI that can be a stop of a day plan (active, not a trip base)."""
    return p["status"] == "active" and p["role"] != "base"


@unittest.skipUnless(os.path.exists(os.path.join(SNAP, "pois.json")),
                     "danang-v2 not built (python BE/ml/data/migrate_v2.py)")
class TestSnapshotV21(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_json(os.path.join(SNAP, "pois.json"))
        cls.pois = cls.raw["pois"]
        cls.data = load_snapshot(SNAP)          # v1 validator on the runtime view
        cls.quarantine = load_json(os.path.join(SNAP, "quarantine_google.json"))["items"]

    # 1. coordinates inside the bounding box, every POI has a known zone
    def test_01_coords_in_bbox_and_zone(self):
        b = R.BBOX
        for p in self.pois:
            self.assertTrue(b["lat_min"] <= p["lat"] <= b["lat_max"], p["name"])
            self.assertTrue(b["lon_min"] <= p["lon"] <= b["lon_max"], p["name"])
            self.assertIn(p["zone"], R.ZONES, p["name"])

    # 2. poi_id unique
    def test_02_unique_ids(self):
        ids = [p["poi_id"] for p in self.pois]
        self.assertEqual(len(ids), len(set(ids)))

    # 3. every stop has hours.open, or kind=unknown with a reason
    def test_03_hours_open_or_unknown_with_reason(self):
        for p in self.pois:
            h = p["hours"]
            self.assertIn(h["kind"], HOURS_KINDS, p["name"])
            for span in h["open"]:
                self.assertRegex(span, SPAN, p["name"])
            self.assertEqual(bool(h["open"]), h["kind"] != "unknown", p["name"])
            if _stop(p) and h["kind"] == "unknown":
                self.assertTrue(p["provenance"]["hours"].get("note"), p["name"])

    # 4. one price field: tier in the vocabulary or null; included <=> parent ticket
    def test_04_price_tier(self):
        for p in self.pois:
            self.assertEqual(set(p["price"]), {"tier", "note"}, p["name"])
            tier = p["price"]["tier"]
            self.assertTrue(tier is None or tier in PRICE_TIERS, (p["name"], tier))
            included = tier == "included"
            self.assertEqual(included, bool(p["requires_ticket_of"]) and p["role"] == "attraction",
                             p["name"])

    # 5. provenance: 8 groups, confidence in [0,1], known vocabulary, human has URL
    def test_05_provenance_well_formed(self):
        for p in self.pois:
            self.assertEqual(set(p["provenance"]), set(PROVENANCE_KEYS), p["name"])
            for field, pv in p["provenance"].items():
                self.assertIn(pv["verified_by"], VERIFIED_BY, (p["name"], field))
                self.assertGreaterEqual(pv["confidence"], 0.0)
                self.assertLessEqual(pv["confidence"], 1.0)
                if pv["verified_by"] == "human":
                    self.assertTrue(pv.get("evidence_url"), (p["name"], field))

    # 6. pois.json and exports carry no Google key or google_demo value
    def test_06_no_google_in_pois_or_exports(self):
        for p in self.pois:
            self.assertFalse(GOOGLE_KEYS & set(p), p["name"])
            self.assertNotIn("google_demo", json.dumps(p["provenance"]), p["name"])
        feats = _rows("poi_features.csv")
        self.assertEqual(len(feats), len(self.pois))
        self.assertFalse(GOOGLE_KEYS & set(feats[0].keys()))

    # 7. dropped fields (no source coverage) stay dropped: description, overture id
    def test_07_dropped_fields_absent(self):
        for p in self.pois:
            self.assertNotIn("description", p, p["name"])
            self.assertNotIn("overture", p["ext_ids"], p["name"])

    # 8. role=base and status=excluded never become candidates
    def test_08_base_and_excluded_not_candidates(self):
        trip = {"budget": 5_000_000, "start_time": "07:00", "end_time": "22:00",
                "must_visit": [], "avoid": [], "activities": []}
        res = retrieval.retrieve(trip, self.data["pois"])
        by_id = {p["poi_id"]: p for p in self.pois}
        for c in res["candidates"]:
            p = by_id[c["poi_id"]]
            self.assertNotEqual(p["role"], "base", p["name"])
            self.assertNotEqual(p["status"], "excluded", p["name"])

    # 9. count matches metadata
    def test_09_count_matches_metadata(self):
        self.assertEqual(self.raw["count"], len(self.pois))
        self.assertEqual(sum(self.raw["count_by_status"].values()), len(self.pois))
        self.assertEqual(self.raw["data_version"], "v2.1")

    # 10. vocabularies of category / role / status / tags
    def test_10_vocabularies(self):
        for p in self.pois:
            self.assertIn(p["category"], R.ALL_CATEGORIES, p["name"])
            self.assertEqual(p["role"], R.ROLE_OF[p["category"]], p["name"])
            self.assertIn(p["status"], STATUSES)
            if p["status"] != "active":
                self.assertTrue(p["status_reason"], p["name"])
            t = p["tags"]
            self.assertIn(t.get("indoor"), (True, False, None), p["name"])
            self.assertIsInstance(t.get("weather_sensitive"), bool, p["name"])
            self.assertNotIn("time", t)          # renamed -> good_times
            self.assertNotIn("budget", t)        # renamed -> time_budget
            self.assertFalse({"price_band", "ticket", "band_source"} & set(t), p["name"])

    # 11. ONLY the top-level keys of DATA_SPEC_v2_1 §2 (whitelist)
    def test_11_whitelisted_keys_only(self):
        for p in self.pois:
            self.assertEqual(list(p), list(V21_KEYS), p["poi_id"])
            self.assertEqual(p["data_version"], "v2.1")

    # ---- adapter (BE.common.poi_view) ------------------------------------

    def test_view_exposes_legacy_fields_and_passes_v1_through(self):
        v1 = {"poi_id": "x", "name": "n", "verified": True}
        self.assertIs(poi_view(v1), v1)
        for p in self.data["pois"]:
            for k in ("opening_hours", "visit_min", "smart_tags", "type", "cat",
                      "verified", "intensity", "weather_sensitive", "price_level"):
                self.assertIn(k, p, (p["poi_id"], k))

    def test_view_clean_policy_never_reads_google(self):
        clean = view_pois(self.pois, SNAP, policy="cach_ly")
        for p in clean:
            prior = p["popularity"]["prize_prior"]
            want = None if prior is None else round(3.0 + 2.0 * prior, 2)
            self.assertEqual(p["rating"], want, p["name"])     # WP6: clean prior, not Google
            self.assertEqual(p["ambience"], "")
        by_id = {p["poi_id"]: p for p in clean}
        for p in self.pois:
            want = [", ".join(p["hours"]["open"])] if p["hours"]["open"] else []
            self.assertEqual(by_id[p["poi_id"]]["opening_hours"], want, p["name"])

    def test_view_verified_is_eligibility_rule(self):
        for p, v in zip(self.pois, view_pois(self.pois, SNAP, policy="cach_ly")):
            self.assertEqual(v["verified"], _stop(p) and p["hours"]["kind"] != "unknown",
                             p["name"])

    def test_fee_reads_price_tier(self):
        for p in self.pois:
            tier = p["price"]["tier"]
            fee, up = effective_fee(p), fee_upper(p)
            if tier is None:
                self.assertIsNone(fee, p["name"])
            else:
                self.assertLessEqual(fee, up, p["name"])
            if tier in ("free", "included"):
                self.assertEqual(fee, 0, p["name"])

    def test_prize_prior_is_clean_and_covers_every_stop(self):
        """WP6: every stop has prize_prior in [0,1]; signature POIs rank high."""
        for p in self.pois:
            prior = p["popularity"]["prize_prior"]
            if p["role"] == "base":
                self.assertIsNone(prior, p["name"])
                continue
            self.assertIsNotNone(prior, p["name"])
            self.assertTrue(0.0 <= prior <= 1.0, p["name"])
            if p["popularity"]["signature"]:
                self.assertGreaterEqual(prior, 0.9, p["name"])
            self.assertNotIn("rating", p["provenance"]["popularity"]["note"] or "")

    # ---- data-freeze gates (P0_GATE=1) -------------------------------------

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_12_clean_names(self):
        bad = [p["name"] for p in self.pois
               if "|" in p["name"] or CJK.search(p["name"]) or len(p["name"]) > 60]
        self.assertEqual(bad, [], f"{len(bad)} names need cleaning (WP5)")

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_G1_every_stop_has_matrix_row(self):
        ids = set(load_json(matrix_path(SNAP)).get("ids", []))
        missing = [p["name"] for p in self.pois if _stop(p) and p["poi_id"] not in ids]
        self.assertEqual(missing, [], f"{len(missing)} stops lack a matrix row (WP7)")

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_G2_each_zone_has_basic_roles(self):
        need = {"attraction", "meal", "rest"}
        gaps = {}
        for z in R.ZONES:
            have = {p["role"] for p in self.pois if p["zone"] == z and p["status"] == "active"}
            if need - have:
                gaps[z] = sorted(need - have)
        self.assertEqual(gaps, {})

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_G3_signature_hours_fixed_and_price_sourced(self):
        bad = []
        for p in self.pois:
            if not p["popularity"]["signature"] or p["status"] == "excluded":
                continue
            pv = p["provenance"]["price"]
            price_ok = p["price"]["tier"] in ("free", "included") or (
                p["price"]["tier"] is not None and pv["verified_by"] != "inferred")
            if p["hours"]["kind"] != "fixed" or not price_ok:
                bad.append(p["name"])
        self.assertEqual(bad, [], f"{len(bad)} signature POIs lack fixed hours / sourced price (WP8)")

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_G4_no_review_left(self):
        left = [p["name"] for p in self.pois if p["status"] == "review"]
        self.assertEqual(left, [], f"{len(left)} POIs still in review (WP10)")

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_G5_gold_v2_not_worse_than_v1(self):
        self.assertTrue(os.path.exists(GOLD_V2), "gold v2 not built yet (WP11)")
        g = load_json(GOLD_V2)
        self.assertGreaterEqual(g["v2"]["gate_pass_rate"], g["v1"]["gate_pass_rate"])

    # 13. one tag schema for every POI; vocabularies match DATA_SPEC
    def test_13_one_tag_schema(self):
        keys = {tuple(sorted(p["tags"])) for p in self.pois}
        self.assertEqual(len(keys), 1, keys)
        for p in self.pois:
            t = p["tags"]
            self.assertNotIn("rain_protection", t)
            self.assertIn(t["space"], ("indoor", "outdoor", "both"), p["name"])
            self.assertIs(t["indoor"], t["space"] == "indoor", p["name"])
            self.assertIn(t["rain_cover"], ("open", "mixed", "enclosed"), p["name"])
            self.assertTrue(set(t["time_budget"]) <= {"quick-stop-30", "half-day", "full-day", "must-go"})
            self.assertTrue(set(t["good_times"]) <= {"sunrise", "morning", "sunset", "night"})
            self.assertTrue(set(t["party"]) <= {"family", "couple", "solo", "group"})

    # 14. no active POI with unknown hours (lodging = 24h rule)
    def test_14_no_unknown_hours_active(self):
        bad = [p["name"] for p in self.pois if p["status"] == "active" and p["hours"]["kind"] == "unknown"]
        self.assertEqual(bad, [])

    # 15. every active POI, lodging included, owns a matrix row
    def test_15_every_active_poi_in_matrix(self):
        with open(os.path.join(SNAP, "matrix.json"), encoding="utf-8") as f:
            ids = set(json.load(f)["ids"])
        self.assertEqual([p["poi_id"] for p in self.pois if p["status"] == "active" and p["poi_id"] not in ids], [])

    # 16. training export = pois.json (same status / category / hours / tags per POI)
    def test_16_export_matches_snapshot(self):
        by_id = {p["poi_id"]: p for p in self.pois}
        bad = []
        for r in _rows("poi_features.csv"):
            p = by_id[r["poi_id"]]
            for col, val in (("status", p["status"]), ("category", p["category"]),
                             ("hours_kind", p["hours"]["kind"]), ("rain_cover", p["tags"]["rain_cover"]),
                             ("time_profile", p["time_profile"])):
                if r[col] != str(val):
                    bad.append((p["name"], col, r[col], val))
        self.assertEqual(bad, [])

    # 17. display names: not ALL CAPS, no stray punctuation
    def test_17_display_names(self):
        bad = []
        for p in (x for x in self.pois if x["status"] == "active"):
            n = p["name"]
            letters = [c for c in n if c.isalpha()]
            if len(letters) > 6 and sum(c.isupper() for c in letters) > 0.7 * len(letters):
                bad.append(n)
            if re.search(r"\s[.,]\s|[.,]\s*$|^\W", n):
                bad.append(n)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
