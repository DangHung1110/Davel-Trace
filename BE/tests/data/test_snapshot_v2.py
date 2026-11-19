"""Data rules for snapshot `danang-v2`, format v2.3 (docs/travelagent/DATA_SPEC.md §8).

Rules 1-10 are the ten checks of the architecture doc (§17.3); 11-15 keep the
format unified (whitelisted keys, one vocabulary per field, consistent
ranges); 16-18 are the data-freeze gates of v2.2 (G3-G6), always on since the
19/11/2026 curation decides every open item by rule (`curate_v2.py`).
G7 (a ticket price with a URL) was dropped: the user accepts approximate prices.

Run from the repo root:  python -m pytest BE/tests/data -q
"""

import csv
import difflib
import json
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

import v2_rules as R  # noqa: E402
import migrate_v2 as M  # noqa: E402
import curate_v2 as C  # noqa: E402

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
EXPORTS = os.path.join(ROOT, "BE", "data", "exports", "danang-v2")
GOOGLE_KEYS = set(M.GOOGLE_FIELDS) | {"price_note", "price_range", "opening_hours",
                                       "hours_by_day", "visit_min", "tags_v1",
                                       "price_band_v1", "review_note_v1", "gmaps_check"}
STATUSES = {"active"}                 # every other candidate is in dropped.json
HOURS_KINDS = {"fixed", "safe_window", "unknown"}
DAYS = {"Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"}
SPAN = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
PROV_KEYS = {"source", "verified_by", "confidence", "evidence_url", "verified_at", "note"}
GOOGLE_TEXT = re.compile(r"★|\d+\s*đánh giá|rating", re.I)


def _load(name):
    with open(os.path.join(SNAP, name), encoding="utf-8") as f:
        return json.load(f)


def _stop(p):
    """A POI that may become a stop of a day plan (since v2.3: every record)."""
    return p["status"] == "active" and p["role"] != "base"


@unittest.skipUnless(os.path.exists(os.path.join(SNAP, "pois.json")),
                     "danang-v2 not built (python BE/ml/data/migrate_v2.py)")
class TestSnapshotV23(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = _load("pois.json")
        cls.pois = cls.raw["pois"]
        cls.by_id = {p["poi_id"]: p for p in cls.pois}
        cls.quarantine = _load("quarantine_google.json")["items"]
        cls.dropped = _load("dropped.json")

    # 1. coordinates inside the bounding box, zone = zone_of(lat, lon)
    def test_01_coords_in_bbox_and_zone(self):
        b = R.BBOX
        for p in self.pois:
            self.assertTrue(b["lat_min"] <= p["lat"] <= b["lat_max"], p["name"])
            self.assertTrue(b["lon_min"] <= p["lon"] <= b["lon_max"], p["name"])
            self.assertEqual(p["zone"], R.zone_of(p["lat"], p["lon"]), p["name"])

    # 2. no duplicates: unique id; no two stops share an OSM element or sit
    #    < 50 m apart with names >= 85 % alike (architecture §17.3 rule 2)
    def test_02_no_duplicates(self):
        ids = [p["poi_id"] for p in self.pois]
        self.assertEqual(len(ids), len(set(ids)))
        stops = [p for p in self.pois if _stop(p)]
        osm = [p["ext_ids"]["osm"] for p in stops if p["ext_ids"]["osm"]]
        dup_osm = {o for o in osm if osm.count(o) > 1}
        self.assertFalse(dup_osm, f"stops sharing an OSM element: {sorted(dup_osm)[:5]}")
        close = []
        for i, a in enumerate(stops):
            for b in stops[i + 1:]:
                if abs(a["lat"] - b["lat"]) > 0.0005 or abs(a["lon"] - b["lon"]) > 0.0005:
                    continue
                if R.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) >= 50:
                    continue
                if difflib.SequenceMatcher(None, R.fold(a["name"]), R.fold(b["name"])).ratio() >= 0.85:
                    close.append((a["name"], b["name"]))
        self.assertFalse(close, close[:5])

    # 3. hours: every stop has hours.open, or kind=unknown with a reason
    def test_03_hours(self):
        for p in self.pois:
            h, pv = p["hours"], p["provenance"]["hours"]
            self.assertIn(h["kind"], HOURS_KINDS, p["name"])
            self.assertEqual(h["kind"] == "unknown", not h["open"], p["name"])
            for w in h["open"] + (h["access_window"] or []):
                self.assertRegex(w, SPAN, p["name"])
                self.assertIsNotNone(R.parse_span(w), w)
            self.assertTrue(set(h["closed_days"]) <= DAYS, p["name"])
            self.assertIn(h["archetype"], R.ARCHETYPES, p["name"])
            if h["kind"] == "fixed":
                self.assertIn(pv["verified_by"], M.FIXED_HOURS_BY, p["name"])
            if h["kind"] == "safe_window":
                self.assertEqual(pv["verified_by"], "inferred", p["name"])
            if _stop(p) and h["kind"] == "unknown":
                self.assertTrue(pv["note"], f"{p['name']}: unknown hours need a reason")

    # 4. price: one tier from the vocabulary, consistent with the VND range;
    #    included <=> parent ticket; paid attraction without a figure stays null
    def test_04_price(self):
        for p in self.pois:
            pr = p["price"]
            self.assertIn(pr["tier"], R.PRICE_TIERS + (None,), p["name"])
            self.assertEqual(pr["tier"] == "included",
                             bool(p["requires_ticket_of"]) and p["role"] == "attraction", p["name"])
            if pr["tier"] is None:
                self.assertEqual((pr["min_vnd"], pr["max_vnd"]), (None, None), p["name"])
                continue
            self.assertIsInstance(pr["min_vnd"], int, p["name"])
            self.assertIsInstance(pr["max_vnd"], int, p["name"])
            self.assertLessEqual(pr["min_vnd"], pr["max_vnd"], p["name"])
            if pr["tier"] in ("free", "included"):
                self.assertEqual((pr["min_vnd"], pr["max_vnd"]), (0, 0), p["name"])
            else:
                self.assertEqual(pr["tier"], M.tier_of_range(pr["min_vnd"], pr["max_vnd"]), p["name"])
            if p["category"] == "lodging":
                self.fail(f"{p['name']}: lodging has no per-visit price")

    # 5. provenance: 9 groups x 6 keys, confidence in [0,1], human has proof
    def test_05_provenance_well_formed(self):
        for p in self.pois:
            self.assertEqual(tuple(p["provenance"]), M.PROVENANCE_KEYS, p["name"])
            for group, v in p["provenance"].items():
                self.assertEqual(set(v), PROV_KEYS, (p["name"], group))
                self.assertIn(v["verified_by"], M.VERIFIED_BY, (p["name"], group))
                self.assertTrue(0.0 <= v["confidence"] <= 1.0, (p["name"], group))
                if v["verified_by"] == "human":
                    self.assertTrue(v["evidence_url"] and v["verified_at"], (p["name"], group))

    # 6. no Google value in pois.json or the exports
    def test_06_no_google_in_pois_or_exports(self):
        text = json.dumps(self.raw, ensure_ascii=False)
        for p in self.pois:
            self.assertFalse(GOOGLE_KEYS & set(p), p["name"])
            for field in ("status_reason",):
                self.assertFalse(GOOGLE_TEXT.search(p[field] or ""), (p["name"], p[field]))
            self.assertNotIn("google_maps", {p["provenance"][g]["source"]
                                             for g in ("hours", "price", "dwell", "tags")}, p["name"])
        self.assertNotIn("★", text)
        for name in ("poi_features.csv", "poi_classifier_weak.csv"):
            with open(os.path.join(EXPORTS, name), encoding="utf-8") as f:
                header = set(next(csv.reader(f)))
            self.assertFalse(GOOGLE_KEYS & header, name)
        for pid, q in self.quarantine.items():
            self.assertIn(pid, self.by_id)
            self.assertTrue(set(q) <= GOOGLE_KEYS, (pid, set(q) - GOOGLE_KEYS))

    # 7. a description always says where it came from and under which license
    def test_07_description_has_source_and_license(self):
        for p in self.pois:
            d = p["description"]
            self.assertEqual(set(d), {"text", "source", "license"})
            if d["text"]:
                self.assertTrue(d["source"] and d["license"], p["name"])

    # 8. pois.json holds only plannable stops (no lodging, nothing excluded or
    #    in review); every other candidate is in dropped.json with one reason
    def test_08_only_stops_and_every_drop_has_a_reason(self):
        for p in self.pois:
            self.assertTrue(_stop(p), p["name"])
            self.assertIsNone(p["status_reason"], p["name"])
            self.assertNotEqual(p["category"], "lodging", p["name"])
        items = self.dropped["items"]
        ids = [d["poi_id"] for d in items]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(set(ids) & set(self.by_id))
        for d in items:
            self.assertIn(d["rule"], C.RULES, d)
            self.assertTrue(d["reason"], d)
            self.assertFalse(GOOGLE_TEXT.search(d["reason"]), d)
        self.assertEqual(self.dropped["count"], len(items))

    # 9. metadata counts match the records
    def test_09_counts_match_metadata(self):
        self.assertEqual(self.raw["count"], len(self.pois))
        self.assertEqual(self.raw["data_version"], M.DATA_VERSION)
        self.assertEqual(self.raw["count_dropped"], self.dropped["count"])
        self.assertEqual(self.raw["count_candidates"], len(self.pois) + self.dropped["count"])
        by_rule = {}
        for d in self.dropped["items"]:
            by_rule[d["rule"]] = by_rule.get(d["rule"], 0) + 1
        self.assertEqual(self.raw["count_dropped_by_rule"], by_rule)
        for key, field in (("count_by_status", "status"), ("count_by_category", "category"),
                           ("count_by_zone", "zone")):
            got = {}
            for p in self.pois:
                got[p[field]] = got.get(p[field], 0) + 1
            self.assertEqual(self.raw[key], dict(sorted(got.items())), key)

    # 10. every zone has an attraction, a meal, a rest stop and an indoor
    #     option for a rainy day (§17.3 rule 10; G2 of the old plan)
    def test_10_each_zone_has_basic_roles(self):
        for z in R.ZONES:
            stops = [p for p in self.pois if p["zone"] == z and _stop(p)]
            roles = {p["role"] for p in stops}
            self.assertTrue({"attraction", "meal", "rest"} <= roles, (z, roles))
            self.assertTrue(any(p["tags"]["indoor"] for p in stops), (z, "no indoor stop"))

    # 11. whitelisted keys only, at every level of the record
    def test_11_whitelisted_keys(self):
        for p in self.pois:
            self.assertEqual(tuple(p), M.V22_KEYS, p["name"])
            self.assertEqual(tuple(p["hours"]), M.HOURS_KEYS, p["name"])
            self.assertEqual(tuple(p["price"]), M.PRICE_KEYS, p["name"])
            self.assertEqual(tuple(p["tags"]), M.TAG_KEYS, p["name"])
            self.assertEqual(tuple(p["popularity"]), M.POPULARITY_KEYS, p["name"])
            self.assertEqual(tuple(p["ext_ids"]), M.EXT_KEYS, p["name"])
            self.assertEqual(set(p["dwell"]), {"p25", "p50", "p75"}, p["name"])

    # 12. one vocabulary per field
    def test_12_vocabularies(self):
        profiles = set(R.TIME_PROFILE.values())
        for p in self.pois:
            t = p["tags"]
            self.assertIn(p["category"], R.ALL_CATEGORIES, p["name"])
            self.assertEqual(p["role"], R.ROLE_OF[p["category"]], p["name"])
            self.assertIn(p["status"], STATUSES, p["name"])
            self.assertIn(p["time_profile"], profiles, p["name"])
            self.assertIn(p["cluster_id"], {None, *M.CLUSTERS, "hoi_an_old_town"}, p["name"])
            self.assertIn(p["alt_group"], {None, "bay_mau", "ba_na_entry"}, p["name"])
            self.assertIn(t["indoor"], (True, False, None), p["name"])
            self.assertIn(t["effort"], (1, 2, 3), p["name"])
            self.assertTrue(set(t["party"]) <= set(M.PARTIES), p["name"])
            self.assertTrue(set(t["good_times"]) <= set(M.GOOD_TIMES), p["name"])
            self.assertIn(t["time_budget"], M.TIME_BUDGETS, p["name"])
            self.assertIn(t["rain_cover"], M.RAIN_COVERS + (None,), p["name"])
            for k in ("sun_exposure", "outdoor_exposure"):
                self.assertTrue(t[k] is None or 0.0 <= t[k] <= 1.0, (p["name"], k))
            for k in ("kid_friendly", "on_request", "weather_sensitive"):
                self.assertIsInstance(t[k], bool, (p["name"], k))
            self.assertEqual(t["kid_friendly"], "family" in t["party"] and p["category"] != "nightlife",
                             p["name"])
            self.assertIn(p["popularity"]["audience"], M.AUDIENCES + (None,), p["name"])
            self.assertIsInstance(p["popularity"]["signature"], bool, p["name"])

    # 13. ranges and references are coherent
    def test_13_dwell_ticket_parents_and_ids(self):
        for p in self.pois:
            d = p["dwell"]
            self.assertTrue(0 < d["p25"] <= d["p50"] <= d["p75"], p["name"])
            parent = p["requires_ticket_of"]
            if parent:
                self.assertIn(parent, self.by_id, p["name"])
                self.assertEqual(self.by_id[parent]["role"], "attraction", p["name"])
            e = p["ext_ids"]
            if e["osm"]:
                self.assertRegex(e["osm"], r"^(node|way|relation)/\d+$", p["name"])
            if e["wikidata"]:
                self.assertRegex(e["wikidata"], r"^Q\d+$", p["name"])
            self.assertEqual(e["google_place_id"],
                             p["poi_id"] if p["poi_id"].startswith("ChIJ") else None, p["name"])
            pp = p["popularity"]["prize_prior"]
            self.assertTrue(pp is None or 0.0 <= pp <= 1.0, p["name"])

    # 14. a good-time tag never contradicts sourced opening hours
    def test_14_good_times_inside_fixed_hours(self):
        for p in self.pois:
            if p["hours"]["kind"] != "fixed":
                continue
            spans = [s for w in p["hours"]["open"] for s in R.parse_element(w)]
            for g in p["tags"]["good_times"]:
                self.assertTrue(R.intersect(spans, M.GOOD_TIME_SPANS[g]), (p["name"], g))

    # 15. the travel matrix covers every POI (G1 of the old plan, now always on)
    def test_15_matrix_covers_every_poi(self):
        m = _load("matrix.json")
        self.assertEqual(m["format"], "dense-v1")
        self.assertEqual(m["mode"], "motorbike")
        self.assertEqual(set(m["ids"]), set(self.by_id))
        n = len(m["ids"])
        self.assertEqual(m["n"], n)
        self.assertEqual(len(m["minutes"]), n)
        self.assertEqual(len(m["km"]), n)
        idx = {pid: i for i, pid in enumerate(m["ids"])}
        stops = [idx[p["poi_id"]] for p in self.pois if _stop(p) or p["role"] == "base"]
        for i in stops:
            self.assertEqual(m["minutes"][i][i], 0)
            for j in stops:
                self.assertIsNotNone(m["minutes"][i][j], (m["ids"][i], m["ids"][j]))
        self.assertEqual(m["coverage"]["missing"], 0)
        self.assertTrue(set(m["coverage"]["estimated_ids"]) <= set(m["ids"]))

    # 16. (G3) signature POIs are plannable: hours (fixed or a safe window) and a price
    def test_16_signature_pois_are_plannable(self):
        bad = [p["name"] for p in self.pois if p["popularity"]["signature"]
               and (p["hours"]["kind"] == "unknown" or p["price"]["tier"] is None)]
        self.assertFalse(bad, bad)
        self.assertGreaterEqual(sum(p["popularity"]["signature"] for p in self.pois), 30)

    # 17. (G5) clean display names
    def test_17_clean_names(self):
        bad = [p["name"] for p in self.pois if M.name_problem(p["name"])]
        self.assertFalse(bad, bad)

    # 18. (G6) every stop has hours and a price (approximate is fine, user 19/11/2026)
    def test_18_every_stop_has_hours_and_price(self):
        bad = [p["name"] for p in self.pois
               if p["hours"]["kind"] == "unknown" or p["price"]["tier"] is None]
        self.assertFalse(bad, f"{len(bad)}: {bad[:20]}")

    # 19. time_budget is the size of the visit: it always agrees with dwell.p50
    def test_19_time_budget_follows_dwell(self):
        bad = [(p["name"], p["tags"]["time_budget"], p["dwell"]["p50"]) for p in self.pois
               if p["tags"]["time_budget"] != M.time_budget_of(p["dwell"]["p50"])]
        self.assertFalse(bad, f"{len(bad)}: {bad[:10]}")


if __name__ == "__main__":
    unittest.main()
