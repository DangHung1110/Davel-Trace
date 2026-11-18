"""Data rules for snapshot `danang-v2` (P0, TRAVELAGENT_CONTEXT.md section 7).

Two layers:

- Structural rules (always on): must hold for every build. They keep the
  snapshot honest (no Google value in exports, provenance well-formed,
  lodging never a candidate, ...).
- P0 gate rules (run with `P0_GATE=1`): data COMPLETENESS
  targets (ticket prices with evidence, every zone covers the basic roles).
  They are expected to fail until the verification queue is worked through;
  they are skipped in the normal suite so a red gate never hides a real
  regression.

Run from the repo root:  python -m pytest BE/tests/data -q
                          P0_GATE=1 python -m pytest BE/tests/data -q -k gate
"""

import csv
import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

import v2_rules as R  # noqa: E402
from BE.app.services import retrieval  # noqa: E402
from BE.app.services.snapshot import load_snapshot  # noqa: E402
from BE.common import load_matrix_cells  # noqa: E402

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
EXPORTS = os.path.join(ROOT, "BE", "data", "exports", "danang-v2")
VERIFIED_BY = {"human", "open_data", "user", "agent_web", "google_demo", "inferred"}
NEEDS_URL = {"human"}
GATE = os.environ.get("P0_GATE") == "1"


def _rows(name):
    with open(os.path.join(EXPORTS, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


@unittest.skipUnless(os.path.exists(os.path.join(SNAP, "pois.json")),
                     "danang-v2 not built (python BE/ml/data/migrate_v2.py)")
class TestSnapshotV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_snapshot(SNAP)          # also runs the v1 validator
        cls.pois = cls.data["pois"]
        with open(os.path.join(SNAP, "quarantine_google.json"), encoding="utf-8") as f:
            cls.quarantine = json.load(f)["items"]

    # 1. coordinates inside the bounding box, every POI has a known zone
    def test_01_coords_in_bbox_and_zone(self):
        b = R.BBOX
        for p in self.pois:
            self.assertTrue(b["lat_min"] <= p["lat"] <= b["lat_max"], p["name"])
            self.assertTrue(b["lon_min"] <= p["lon"] <= b["lon_max"], p["name"])
            self.assertIn(p["zone"], R.ZONES, p["name"])

    # 2. no duplicate ids (near-duplicates are only flagged in reports)
    def test_02_unique_ids(self):
        ids = [p["poi_id"] for p in self.pois]
        self.assertEqual(len(ids), len(set(ids)))

    # 3. every POI has hours or an hour archetype; every active candidate
    #    has usable opening_hours unless its archetype is "look it up"
    def test_03_hours_or_archetype(self):
        for p in self.pois:
            self.assertIn(p["hours"]["archetype"], R.ARCHETYPES, p["name"])
            if p["status"] == "active" and p["role"] != "base":
                if p["hours"]["archetype"] != "co_ve":
                    self.assertTrue(p["opening_hours"], p["name"])

    # 4. every POI has a price status; known prices carry a band
    def test_04_price_band_or_explicit_status(self):
        for p in self.pois:
            pr = p["price"]
            self.assertIn(pr["status"], {"known", "estimate", "band_only", "todo",
                                         "unknown", "not_applicable"}, p["name"])
            if pr["status"] in ("known", "estimate") and pr["basis"] != "included_in_parent":
                self.assertIn(pr["band"], R.BANDS, p["name"])
            if pr["band"]:
                self.assertIn(pr["band"], R.BANDS)

    # 5. provenance: confidence in [0,1], known vocabulary, evidence for human
    def test_05_provenance_well_formed(self):
        for p in self.pois:
            for field in ("name", "location", "category", "hours", "price", "dwell", "tags"):
                pv = p["provenance"][field]
                self.assertIn(pv["verified_by"], VERIFIED_BY, (p["name"], field))
                self.assertGreaterEqual(pv["confidence"], 0.0)
                self.assertLessEqual(pv["confidence"], 1.0)
                if pv["verified_by"] in NEEDS_URL:
                    self.assertTrue(pv.get("evidence_url"), (p["name"], field))
                if pv["verified_by"] == "agent_web" and pv["confidence"] >= 0.6:
                    self.assertTrue(pv.get("evidence_url") or pv.get("note"), (p["name"], field))

    # 6. exports never contain Google-derived values; snapshot keeps them
    #    only in quarantine (and in legacy fields when policy = demo)
    def test_06_no_google_in_exports(self):
        feats = _rows("poi_features.csv")
        self.assertEqual(len(feats), len(self.pois))
        banned = {"rating", "price_level", "type", "ambience", "pros", "cons"}
        self.assertFalse(banned & set(feats[0].keys()))
        by_id = {p["poi_id"]: p for p in self.pois}
        for r in feats:
            p = by_id[r["poi_id"]]
            if p["provenance"]["price"]["verified_by"] == "google_demo":
                self.assertEqual(r["price_band"], "", p["name"])
                self.assertEqual(r["price_min_vnd"], "", p["name"])
            if p["provenance"]["hours"]["verified_by"] == "google_demo":
                self.assertEqual(r["hours_verified_by"], "inferred", p["name"])
        for p in self.pois:
            self.assertNotIn("quarantine", p)
        if self.data["google_policy"] == "cach_ly":
            for p in self.pois:
                for field in ("hours", "price"):
                    self.assertNotEqual(p["provenance"][field]["verified_by"], "google_demo")

    # 7. a description is only present with its source and licence
    def test_07_description_has_source_and_license(self):
        for p in self.pois:
            d = p["description"]
            if d.get("text"):
                self.assertTrue(d.get("source") and d.get("license"), p["name"])

    # 8. role=base (lodging) and status=excluded never become candidates
    def test_08_base_and_excluded_not_candidates(self):
        trip = {"budget": 2_000_000, "start_time": "07:00", "end_time": "22:00",
                "must_visit": [], "avoid": [], "activities": []}
        res = retrieval.retrieve(trip, self.pois)
        by_id = {p["poi_id"]: p for p in self.pois}
        for c in res["candidates"]:
            p = by_id[c["poi_id"]]
            self.assertNotEqual(p["role"], "base", p["name"])
            self.assertNotEqual(p["status"], "excluded", p["name"])

    # 9. count matches metadata; ids identical to v1 so the v1 matrix applies
    def test_09_count_matches_metadata(self):
        self.assertEqual(self.data["count"], len(self.pois))
        self.assertEqual(sum(self.data["count_by_status"].values()), len(self.pois))
        cells = load_matrix_cells(SNAP)
        self.assertGreater(len(cells), 0)

    # 10 (structural part). vocabularies
    def test_10_vocabularies(self):
        for p in self.pois:
            self.assertIn(p["category"], R.ALL_CATEGORIES, p["name"])
            self.assertEqual(p["role"], R.ROLE_OF[p["category"]], p["name"])
            self.assertIn(p["status"], {"active", "review", "excluded"})
            if p["status"] != "active":
                self.assertTrue(p["status_reason"], p["name"])
            if p["requires_ticket_of"] and p["role"] == "attraction":
                self.assertEqual(p["price"]["basis"], "included_in_parent", p["name"])

    def test_legacy_fields_follow_confidence_floor(self):
        """A value only reaches the fields the app reads when confident enough."""
        for p in self.pois:
            band = (p.get("smart_tags") or {}).get("price_band")
            if band:
                by = p["smart_tags"].get("band_source")
                conf = p["provenance"]["price"]["confidence"]
                self.assertTrue(conf >= 0.5 if by == "google_demo" else conf >= 0.55, p["name"])
            if p.get("free_entry"):
                self.assertGreaterEqual(p["provenance"]["price"]["confidence"], 0.6)

    def test_inferred_hours_use_safe_windows(self):
        for p in self.pois:
            pv = p["provenance"]["hours"]
            if pv["source"].startswith("archetype:") and p["opening_hours"]:
                safe = [s for w in p["hours"]["safe_windows"] for s in R.parse_element(w)]
                got = R.parse_element(p["opening_hours"][0])
                self.assertTrue(R.contains(safe, got), p["name"])

    # ---- P0 gate: completeness targets --------------------------------

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_paid_attractions_have_ticket_with_evidence(self):
        missing = [p["name"] for p in self.pois
                   if p["category"] == "paid_attraction" and p["status"] != "excluded"
                   and p["price"]["basis"] != "included_in_parent"
                   and not (p["price"]["ticket_vnd"] is not None
                            and p["provenance"]["price"].get("evidence_url"))]
        self.assertEqual(missing, [], f"{len(missing)} paid attractions lack ticket+evidence")

    @unittest.skipUnless(GATE, "P0 gate (set P0_GATE=1)")
    def test_gate_each_zone_has_basic_roles(self):
        need = {"attraction", "meal", "rest"}
        gaps = {}
        for z in R.ZONES:
            have = {p["role"] for p in self.pois if p["zone"] == z and p["status"] == "active"}
            if need - have:
                gaps[z] = sorted(need - have)
        self.assertEqual(gaps, {})


if __name__ == "__main__":
    unittest.main()
