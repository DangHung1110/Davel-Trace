"""Unit tests for the T063 snapshot weather wiring.

Run from repo root:
    python -m unittest BE.tests.unit.test_weather_enrichment -v

Covers audit preservation (the 46 existing labels), old->new transitions,
legacy rain-proof removal, party/time preservation, dry-run immutability,
idempotent apply and the 200-row deterministic review helper.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, os.path.abspath(REPO_ROOT))

from BE.ml.data.enrich_snapshot import (  # noqa: E402
    REVIEW_LIMIT,
    build_weather_review_rows,
    enrich,
    main,
    parse_audit,
)
from BE.ml.data.enrich_tags import tag_poi  # noqa: E402

SNAPSHOT = os.path.join(REPO_ROOT, "BE", "data", "snapshots", "danang-v1")
POIS_PATH = os.path.join(SNAPSHOT, "pois.json")
SPOT_CHECK = os.path.join(SNAPSHOT, "SPOT_CHECK.md")

AUDIT_EXPECTED = {
    "I": ("indoor", False),
    "O": ("outdoor", True),
    "B": ("both", True),
}

REVIEW_KEYS = {
    "poi_id", "name", "type", "lat", "lon", "old_space", "suggested_space",
    "space_source", "space_confidence", "space_evidence",
    "old_rain_protection", "rain_protection", "rain_protection_confidence",
    "rain_protection_evidence", "space_conflict",
}


def make_poi(pid, name, typ="Nhà hàng", cat="restaurant",
             old_space="both", time=None, party=None, io_label=None):
    return {
        "poi_id": pid,
        "name": name,
        "type": typ,
        "cat": cat,
        "lat": 16.0,
        "lon": 108.0,
        "io_label": io_label,
        "intensity": 2,
        "visit_min": {"p50": 60},
        "fee": 0,
        "smart_tags": {
            "ticket": False,
            "price_band": None,
            "space": old_space,
            "party": list(party or ["family"]),
            "time": list(time if time is not None else ["morning", "rain-proof"]),
            "budget": ["half-day"],
        },
    }


def _write_temp_snapshot(directory: str, pois: list[dict]) -> None:
    with open(os.path.join(directory, "pois.json"), "w", encoding="utf-8") as f:
        json.dump({"pois": pois}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(directory, "SPOT_CHECK.md"), "w", encoding="utf-8") as f:
        f.write("# test audit\n")


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class TestAuditPreservation(unittest.TestCase):
    def test_46_snapshot_audit_labels_are_exact(self):
        if not os.path.exists(POIS_PATH):
            self.skipTest("snapshot absent")
        with open(POIS_PATH, encoding="utf-8") as f:
            pois = copy.deepcopy(json.load(f)["pois"])
        audit = parse_audit(SPOT_CHECK)
        report = enrich(pois, audit)

        audited = [p for p in pois if p.get("io_label") in AUDIT_EXPECTED]
        self.assertEqual(len(audited), 46)
        self.assertEqual(report["audit_labels"], 46)
        self.assertEqual(report["preserved_audit"], 46)

        for p in audited:
            space, weather = AUDIT_EXPECTED[p["io_label"]]
            self.assertEqual(p["smart_tags"]["space"], space, p["poi_id"])
            self.assertEqual(p["space_source"], "audit", p["poi_id"])
            self.assertEqual(p["space_confidence"], 1.0, p["poi_id"])
            self.assertEqual(p["weather_sensitive"], weather, p["poi_id"])
            self.assertEqual(p["ws_source"], "audit", p["poi_id"])
            self.assertIn(p["rain_protection"],
                          ("enclosed", "sheltered", "none", "unknown"))

    def test_audit_beats_canonical_and_curated(self):
        p = make_poi("audit-1", "Bãi biển Mỹ Khê", typ="Bãi biển",
                     cat="beach", old_space="indoor", io_label="O")
        enrich([p], {})
        self.assertEqual(p["smart_tags"]["space"], "outdoor")
        self.assertEqual(p["space_source"], "audit")
        self.assertTrue(p["weather_sensitive"])

        # Curated "cho dem" no longer forces outdoor over an audit/OSM label.
        tags, _ = tag_poi(make_poi("market-1", "Chợ đêm Helio",
                                   typ="Chợ đêm", cat="market",
                                   io_label="I"))
        self.assertEqual(tags["space"], "indoor")


class TestEnrichChanges(unittest.TestCase):
    def test_old_to_new_space_transitions(self):
        pois = [
            make_poi("p-beach", "Bãi biển Mỹ Khê", typ="Bãi biển",
                     cat="beach", old_space="both"),
            make_poi("p-cafe", "Quán cà phê", typ="Quán cà phê",
                     cat="cafe", old_space="both"),
            make_poi("p-audit", "Bảo tàng Chăm", typ="Bảo tàng",
                     cat="museum", old_space="indoor", io_label="O"),
        ]
        before = copy.deepcopy(pois)
        report = enrich(pois, {})

        self.assertEqual(pois[0]["smart_tags"]["space"], "outdoor")
        self.assertEqual(pois[1]["smart_tags"]["space"], "indoor")
        self.assertEqual(pois[2]["smart_tags"]["space"], "outdoor")
        self.assertEqual(report["space_transitions"]["both->outdoor"], 1)
        self.assertEqual(report["space_transitions"]["both->indoor"], 1)
        self.assertEqual(report["space_transitions"]["indoor->outdoor"], 1)
        self.assertEqual(set(report["changed_ids"]),
                         {"p-beach", "p-cafe", "p-audit"})
        for old, new in zip(before, pois):
            self.assertEqual(old["intensity"], new["intensity"])
            self.assertEqual(old["visit_min"], new["visit_min"])
            self.assertEqual(old["fee"], new["fee"])

    def test_rain_proof_removed_and_rain_protection_set(self):
        dry = make_poi("p-dry", "Quán ăn", cat="restaurant",
                       time=["morning", "rain-proof"])
        enclosed = make_poi("p-enclosed", "Quán ăn 2", cat="restaurant",
                            time=["night", "rain-proof"])
        enclosed["osm_evidence"] = {"osm": "node/1", "dist_m": 3}
        osm_by_poi = {"p-enclosed": [{"type": "node",
                                      "tags": {"indoor": "yes"}}]}

        report = enrich([dry, enclosed], {}, osm_by_poi=osm_by_poi)

        self.assertNotIn("rain-proof", dry["smart_tags"]["time"])
        self.assertNotIn("rain-proof", enclosed["smart_tags"]["time"])
        self.assertEqual(dry["smart_tags"]["time"], ["morning"])
        self.assertEqual(enclosed["smart_tags"]["time"], ["night"])
        self.assertEqual(dry["smart_tags"]["rain_protection"], "unknown")
        self.assertEqual(enclosed["smart_tags"]["rain_protection"], "enclosed")
        self.assertEqual(report["rain_distribution"]["unknown"], 1)
        self.assertEqual(report["rain_distribution"]["enclosed"], 1)
        self.assertEqual(report["rain_transitions"]["rain-proof->unknown"], 1)
        self.assertEqual(report["rain_changed_count"], 2)
        self.assertEqual(report["changed_poi_count"], 2)

    def test_party_and_time_of_day_rules_preserved(self):
        tags, _ = tag_poi(make_poi("p-party", "Quán cà phê",
                                   typ="Quán cà phê", cat="cafe"))
        self.assertEqual(tags["party"], ["couple", "solo"])
        self.assertEqual(tags["time"], ["morning"])
        self.assertNotIn("rain-proof", tags["time"])

        tags, _ = tag_poi(make_poi("p-rest", "Nhà hàng", cat="restaurant"))
        self.assertEqual(tags["party"], ["family", "couple", "group"])
        self.assertEqual(tags["time"], ["morning", "night"])

        tags, src = tag_poi(make_poi("p-bana", "Sun World Ba Na Hills",
                                     typ="attraction", cat="attraction"))
        self.assertTrue(tags["ticket"])
        self.assertEqual(tags["price_band"], "expensive")
        self.assertIn("must-go", tags["budget"])
        self.assertEqual(src, "rule_v1+curated")

    def test_tag_poi_uses_precomputed_classifier_result(self):
        p = make_poi("p-pre", "X", cat="restaurant")
        result = {"space": "outdoor", "rain_protection": "sheltered"}
        tags, _ = tag_poi(p, weather_result=result)
        self.assertEqual(tags["space"], "outdoor")
        self.assertEqual(tags["rain_protection"], "sheltered")


class TestCliAndDeterminism(unittest.TestCase):
    def test_check_is_dry_run(self):
        pois = [make_poi("p1", "Quán cà phê", cat="cafe")]
        with tempfile.TemporaryDirectory() as tmp:
            _write_temp_snapshot(tmp, pois)
            path = os.path.join(tmp, "pois.json")
            before = _read_bytes(path)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["--snapshot", tmp, "--check"])
            self.assertEqual(rc, 0)
            self.assertEqual(_read_bytes(path), before)
            self.assertFalse(os.path.exists(os.path.join(
                tmp, "RELABEL_REPORT.json")))
            self.assertFalse(os.path.exists(os.path.join(
                tmp, "weather_review_200.json")))

    def test_apply_is_idempotent(self):
        pois = [
            make_poi(f"p{i:03d}", f"POI {i}", cat="cafe" if i % 2 else "beach",
                     typ="Quán cà phê" if i % 2 else "Bãi biển",
                     old_space="both")
            for i in range(12)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            _write_temp_snapshot(tmp, pois)
            path = os.path.join(tmp, "pois.json")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--snapshot", tmp, "--apply"]), 0)
            first = _read_bytes(path)
            for name in ("RELABEL_REPORT.json", "RELABEL_REPORT.md",
                         "weather_review_200.json"):
                self.assertTrue(os.path.exists(os.path.join(tmp, name)), name)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--snapshot", tmp, "--apply"]), 0)
            second = _read_bytes(path)

            self.assertEqual(first, second)

    def test_cli_osm_json_applies_rain_evidence(self):
        pois = [make_poi("p-osm", "Quán ăn", cat="restaurant",
                         old_space="both")]
        osm_payload = {
            "by_poi": {
                "p-osm": [{"type": "node", "tags": {"indoor": "yes"}}],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            _write_temp_snapshot(tmp, pois)
            osm_path = os.path.join(tmp, "osm.json")
            with open(osm_path, "w", encoding="utf-8") as f:
                json.dump(osm_payload, f)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["--snapshot", tmp, "--osm-json", osm_path,
                           "--apply"])
            self.assertEqual(rc, 0)

            with open(os.path.join(tmp, "pois.json"), encoding="utf-8") as f:
                enriched = json.load(f)["pois"][0]
            self.assertEqual(enriched["smart_tags"]["rain_protection"],
                             "enclosed")
            self.assertEqual(enriched["rain_protection_source"], "osm")
            with open(os.path.join(tmp, "weather_review_200.json"),
                      encoding="utf-8") as f:
                rows = json.load(f)
            self.assertEqual(rows[0]["rain_protection"], "enclosed")

    def test_review_rows_exactly_200_and_deterministic(self):
        pois = []
        for i in range(260):
            if i < 80:
                p = make_poi(f"p{i:03d}", f"Bãi biển {i}", typ="Bãi biển",
                             cat="beach", old_space="both")
            elif i < 160:
                p = make_poi(f"p{i:03d}", f"Quán cà phê {i}", typ="Quán cà phê",
                             cat="cafe", old_space="both")
            elif i < 210:
                p = make_poi(f"p{i:03d}", f"Điểm tham quan {i}",
                             typ="Điểm tham quan", cat="attraction",
                             old_space="unknown")
            else:
                p = make_poi(f"p{i:03d}", f"Khách sạn {i}", typ="Khách sạn",
                             cat="lodging", old_space="indoor")
            pois.append(p)

        old_by_id = {
            p["poi_id"]: {
                "space": p["smart_tags"]["space"],
                "rain_protection": "rain-proof",
            }
            for p in pois
        }
        enriched = copy.deepcopy(pois)
        report = enrich(enriched, {})
        rows = build_weather_review_rows(enriched, old_by_id=old_by_id)
        self.assertEqual(len(rows), REVIEW_LIMIT)
        self.assertEqual(len(report["review_rows"]), REVIEW_LIMIT)
        self.assertEqual(rows, report["review_rows"])

        ids = [row["poi_id"] for row in rows]
        self.assertEqual(len(set(ids)), REVIEW_LIMIT)
        for row in rows:
            self.assertEqual(set(row), REVIEW_KEYS)

        # Top-ranked row is a changed label, and new-outdoor comes first.
        self.assertNotEqual(rows[0]["old_space"], rows[0]["suggested_space"])
        self.assertEqual(rows[0]["suggested_space"], "outdoor")
        # Deterministic across calls.
        self.assertEqual(rows,
                         build_weather_review_rows(enriched,
                                                   old_by_id=old_by_id))

    def test_review_rows_under_limit_returns_all(self):
        pois = [make_poi(f"p{i:03d}", f"POI {i}", cat="cafe") for i in range(7)]
        rows = build_weather_review_rows(pois, old_by_id={})
        self.assertEqual(len(rows), 7)


if __name__ == "__main__":
    unittest.main()
