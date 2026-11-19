"""v2.3 curation: which POIs stay in danang-v2 and why the others go (BE/ml/data/curate_v2.py).

User rule of 19/11/2026: prices may be approximate; a POI without enough
information on Google Maps may be dropped. Google values decide, they are
never copied into the record.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

import curate_v2 as C  # noqa: E402
from migrate_v2 import fit_archetype, prov  # noqa: E402

from BE.tests.data.fixtures_v22 import rec  # noqa: E402


def stop(pid="ChIJx", category="restaurant", kind="safe_window", **kw):
    return rec(pid=pid, category=category, kind=kind, role=C.R.ROLE_OF[category],
               open_=("11:00-13:30",), **kw)


def run(recs, quarantine=None, gcheck=None, notes=None, conflict=()):
    kept, dropped, _ = C.curate(recs, quarantine or {}, gcheck or {}, notes or {}, set(conflict), prov)
    return [r["poi_id"] for r in kept], {d["poi_id"]: d["rule"] for d in dropped}


class TestGoogleEvidence(unittest.TestCase):
    def test_enough_reviews_and_hours_stays(self):
        kept, dropped = run([stop()], quarantine={"ChIJx": {"review_count": 250,
                                                            "opening_hours": ["10:00-22:00"]}})
        self.assertEqual(kept, ["ChIJx"])
        self.assertEqual(dropped, {})

    def test_few_reviews_goes_unless_signature(self):
        q = {"ChIJx": {"review_count": 12, "opening_hours": ["10:00-22:00"]}}
        self.assertEqual(run([stop()], quarantine=q)[1], {"ChIJx": "few_reviews"})
        sig = stop()
        sig["popularity"]["signature"] = True
        self.assertEqual(run([sig], quarantine=q)[0], ["ChIJx"])

    def test_business_without_hours_on_google_goes(self):
        q = {"ChIJx": {"review_count": 900}}
        notes = {"ChIJx": "Còn trên Google (4,5★, 900 đánh giá). Google không có giờ; giữ trống."}
        self.assertEqual(run([stop()], quarantine=q, notes=notes)[1], {"ChIJx": "no_hours"})

    def test_24h_or_partial_hours_on_google_count_as_hours(self):
        q = {"ChIJx": {"review_count": 300}}
        for note in ("Google ghi mở 24/24 (thường là giá trị mặc định): không điền",
                     "Google: 4,3★, 3.213 đánh giá, đóng cửa 02:00. Giờ mở chưa đầy đủ."):
            self.assertEqual(run([stop()], quarantine=q, notes={"ChIJx": note})[0], ["ChIJx"], note)

    def test_public_place_needs_no_opening_hours(self):
        beach = stop(category="beach", tier="free")
        self.assertEqual(run([beach], quarantine={"ChIJx": {"review_count": 4000}})[0], ["ChIJx"])

    def test_closed_on_google_goes_even_if_signature(self):
        r = stop(pid="osm:node/1")
        r["popularity"]["signature"] = True
        g = {"osm:node/1": {"found": True, "review_count": 600, "hours_listed": False,
                            "closed": "temporarily"}}
        self.assertEqual(run([r], gcheck=g)[1], {"osm:node/1": "closed"})

    def test_not_found_drops_a_shop_but_not_a_ticketed_heritage_site(self):
        shop = stop(pid="osm:node/1")
        house = stop(pid="osm:node/2", category="museum_indoor", tier="included",
                     requires_ticket_of="osm:node/9")
        g = {"osm:node/1": {"found": False}, "osm:node/2": {"found": False}}
        kept, dropped = run([shop, house], gcheck=g)
        self.assertEqual(kept, ["osm:node/2"])
        self.assertEqual(dropped, {"osm:node/1": "not_listed"})

    def test_unchecked_osm_business_needs_sourced_hours(self):
        osm = stop(pid="osm:node/1")
        self.assertEqual(run([osm])[1], {"osm:node/1": "no_hours"})
        fixed = stop(pid="osm:node/2", kind="fixed")
        self.assertEqual(run([fixed])[0], ["osm:node/2"])


class TestOtherRules(unittest.TestCase):
    def test_excluded_lodging_review_and_user_decision(self):
        ex = stop(pid="ChIJa", status="excluded")
        hotel = rec(pid="ChIJb", category="lodging", role="base", tier=None, kind="unknown", open_=())
        review = stop(pid="osm:node/1623183649", status="review")
        user = stop(pid="ChIJc")
        user["provenance"]["status"]["source"] = "user_decision"
        q = {"ChIJc": {"review_count": 3}}
        kept, dropped = run([ex, hotel, review, user], quarantine=q)
        self.assertEqual(kept, ["ChIJc"])                     # the user's "active" wins
        self.assertEqual(dropped, {"ChIJa": "excluded", "ChIJb": "lodging",
                                   "osm:node/1623183649": "review"})

    def test_hours_conflict_drops_a_non_signature_stop(self):
        q = {"ChIJx": {"review_count": 300, "opening_hours": ["10:00-12:30, 17:00-19:30"]}}
        self.assertEqual(run([stop()], quarantine=q, conflict={"ChIJx"})[1],
                         {"ChIJx": "hours_conflict"})

    def test_duplicate_keeps_the_better_known_record(self):
        a = stop(pid="osm:node/1")
        b = stop(pid="ChIJb")
        b["name"] = "Bảo tàng X."                              # same place, 0 m apart
        q = {"ChIJb": {"review_count": 500, "opening_hours": ["08:00-17:00"]}}
        g = {"osm:node/1": {"found": True, "review_count": 40, "hours_listed": True, "closed": None}}
        kept, dropped = run([a, b], quarantine=q, gcheck=g)
        self.assertEqual(kept, ["ChIJb"])
        self.assertEqual(dropped, {"osm:node/1": "duplicate"})

    def test_display_name_is_cleaned_and_raw_kept(self):
        r = stop(pid="ChIJu9GUjOgZQjERpfx8z-GIMEw")
        r["name"] = r["name_raw"] = "켓 바 1 Kết Bar"
        q = {r["poi_id"]: {"review_count": 80, "opening_hours": ["18:00-02:00"]}}
        kept, _ = run([r], quarantine=q)
        self.assertEqual(kept, [r["poi_id"]])
        self.assertEqual(r["name"], "Kết Bar")
        self.assertEqual(r["name_raw"], "켓 바 1 Kết Bar")
        self.assertIsNone(C.name_problem(r["name"]))
        self.assertEqual(C.clean_display_name("Spa A | 스파 | Spa"), "Spa A")


class TestHourGroupFit(unittest.TestCase):
    def test_breakfast_only_shop_moves_to_the_breakfast_group(self):
        hours = {"open": ["11:00-13:00"], "kind": "safe_window"}
        groups = {"an_sang": ["06:30-09:30"], "com_trua": ["11:00-13:00"],
                  "nha_hang": ["11:00-13:30", "17:30-20:30"], "an_toi": ["17:30-21:30"]}

        def build(a):
            return {"open": groups[a], "kind": "safe_window"}
        self.assertEqual(fit_archetype({}, "restaurant", "com_trua", hours, ["06:00-10:00"], build),
                         ("an_sang", False))
        # mostly inside Google's hours already: no change
        self.assertEqual(fit_archetype({}, "restaurant", "com_trua", hours, ["10:00-21:00"], build),
                         ("com_trua", False))
        # nothing in the family fits a 2 a.m.-5 a.m. shop: flagged as a conflict
        self.assertEqual(fit_archetype({}, "restaurant", "com_trua", hours, ["02:00-05:00"], build),
                         ("com_trua", True))


if __name__ == "__main__":
    unittest.main()
