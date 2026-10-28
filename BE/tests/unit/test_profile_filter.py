"""Unit tests for the hard profile pre-filter (allergy / must_avoid / accessibility).

Fixture POIs only; no snapshot needed. Covers Vietnamese + English allergen
terms, diacritic safety ("cá" must not hit "cà phê"), concept-level
must_avoid, mobility rules, and crash safety on missing fields.

Run: python -m pytest BE/tests/unit/test_profile_filter.py -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services.profile_filter import (  # noqa: E402
    drop_reason,
    hard_filter,
    matches,
    taste_match,
    warning,
)

SEAFOOD = {"poi_id": "sea", "name": "Hải sản My Hanh", "cat": "restaurant",
           "type": "Nhà hàng hải sản", "tags": ["Nhà hàng hải sản"]}
CAFE = {"poi_id": "cafe", "name": "Cà phê Muối", "cat": "cafe",
        "type": "Quán cà phê", "tags": ["Quán cà phê"]}
PEANUT = {"poi_id": "nut", "name": "Bánh", "cat": "restaurant",
          "type": "Nhà hàng", "tags": ["đậu phộng", "món Việt"]}
BAR = {"poi_id": "bar", "name": "Night Bar", "cat": "bar",
       "type": "Quán bar", "tags": ["Quán bar", "karaoke"]}
CAFE_BAR = {"poi_id": "cafebar", "name": "Lữ Cafe", "cat": "cafe",
            "type": "Quán cà phê", "tags": ["Quán cà phê", "Quán bar"]}
TREK = {"poi_id": "trek", "name": "Núi Sơn Trà", "cat": "nature",
        "type": "Đỉnh núi", "tags": ["leo núi"], "intensity": 3}
HIGH_TASTE = {"poi_id": "high", "name": "Quán ăn", "cat": "restaurant",
              "type": "Nhà hàng", "tags": ["Nhà hàng"], "intensity": 3}
BEACH = {"poi_id": "beach", "name": "Bãi biển", "cat": "beach",
         "type": "Bãi biển", "tags": ["Bãi biển"], "intensity": 2}
MARKET = {"poi_id": "market", "name": "Chợ đêm", "cat": "market",
          "type": "Chợ đêm", "tags": ["Chợ đêm"], "intensity": 1}
CAFE_HILL = {"poi_id": "cafehill", "name": "Cafe", "cat": "cafe",
             "type": "Quán cà phê", "tags": ["Quán cà phê"],
             "intensity": 1}
FISH = {"poi_id": "fish", "name": "Quán cá", "cat": "restaurant",
        "type": "Nhà hàng", "tags": ["cá nướng"]}
POIS = [SEAFOOD, CAFE, PEANUT, BAR, CAFE_BAR, TREK, HIGH_TASTE, BEACH,
        MARKET, CAFE_HILL]


def ids(pois):
    return [p["poi_id"] for p in pois]


class TestAllergy(unittest.TestCase):
    def test_english_allergen_hits_vietnamese_tags(self):
        kept, drops = hard_filter(POIS, {"allergy": ["seafood"]})
        self.assertNotIn("sea", ids(kept))
        self.assertIn("cafe", ids(kept))
        drop = next(d for d in drops if d["poi_id"] == "sea")
        self.assertEqual(drop["rule"], "allergy")
        self.assertIn("hải sản", drop["detail"])

    def test_diacritics_keep_ca_and_ca_phe_apart(self):
        """'cá' (fish) must not match 'cà phê' after folding."""
        self.assertIsNotNone(matches(FISH, "cá"))
        self.assertIsNone(matches(CAFE, "cá"))
        kept, _drops = hard_filter([FISH, CAFE], {"allergy": ["cá"]})
        self.assertEqual(ids(kept), ["cafe"])

    def test_vietnamese_allergen(self):
        kept, _drops = hard_filter(POIS, {"allergy": ["đậu phộng"]})
        self.assertNotIn("nut", ids(kept))

    def test_taste_match_ratio(self):
        ratio, hits = taste_match(SEAFOOD, ["hải sản", "chay"])
        self.assertAlmostEqual(ratio, 0.5)
        self.assertEqual(hits, ["hải sản"])
        self.assertEqual(taste_match(CAFE, []), (0.0, []))

    def test_shop_tag_does_not_match_crab_allergen(self):
        """'cửa hàng' (shop) folds to 'cua hang'; it must not read as 'cua'."""
        souvenir = {"poi_id": "souvenir", "name": "Coffee & Souvenir",
                    "cat": "cafe", "type": "Quán cà phê",
                    "tags": ["Quán cà phê", "Cửa hàng lưu niệm"]}
        kept, drops = hard_filter([souvenir], {"allergy": ["seafood"]})
        self.assertEqual(ids(kept), ["souvenir"])
        self.assertEqual(drops, [])

    def test_taste_reads_the_name_too(self):
        """A vegan kitchen tagged only 'Nhà hàng' still carries 'chay' in name."""
        vegan = {"poi_id": "vegan", "name": "Nhà hàng chay Shanti Vegan",
                 "cat": "restaurant", "type": "Nhà hàng", "tags": ["Nhà hàng"]}
        ratio, hits = taste_match(vegan, ["chay"])
        self.assertEqual((ratio, hits), (1.0, ["chay"]))
        ratio, hits = taste_match(vegan, ["vegan"])
        self.assertEqual(ratio, 1.0)
        # allergy matching stays tag-only: the name is not a safety signal
        kept, _drops = hard_filter([vegan], {"allergy": ["vegan"]})
        self.assertEqual(ids(kept), ["vegan"])


class TestMustAvoid(unittest.TestCase):
    def test_nightlife_concept(self):
        kept, drops = hard_filter(POIS, {"must_avoid": ["nightlife"]})
        self.assertNotIn("bar", ids(kept))
        self.assertNotIn("cafebar", ids(kept))  # cafe that is also a bar
        self.assertIn("cafe", ids(kept))
        self.assertEqual({d["rule"] for d in drops}, {"must_avoid"})

    def test_trek_drops_high_effort_outdoor_without_tag(self):
        kept, drops = hard_filter(POIS, {"must_avoid": ["trek"]})
        self.assertNotIn("trek", ids(kept))
        # intensity 3 without a trek tag is still an adventure stop
        self.assertNotIn("high", ids(kept))
        self.assertIn("cafe", ids(kept))
        self.assertEqual(len(drops), 2)

    def test_unknown_term_is_a_plain_substring_rule(self):
        kept, _drops = hard_filter(POIS, {"must_avoid": ["karaoke"]})
        self.assertNotIn("bar", ids(kept))


class TestAccessibility(unittest.TestCase):
    def test_wheelchair_drops_beach_and_nature(self):
        kept, drops = hard_filter(POIS, {"accessibility": ["wheelchair"]})
        self.assertNotIn("beach", ids(kept))
        self.assertNotIn("trek", ids(kept))
        self.assertIn("cafehill", ids(kept))
        self.assertIn("market", ids(kept))
        self.assertEqual({d["rule"] for d in drops}, {"accessibility"})

    def test_low_walking_keeps_intensity_two(self):
        kept, _drops = hard_filter(POIS, {"accessibility": ["low_walking"]})
        self.assertIn("beach", ids(kept))       # intensity 2 allowed
        self.assertNotIn("trek", ids(kept))     # nature + intensity 3
        self.assertNotIn("high", ids(kept))     # intensity 3 restaurant

    def test_unknown_accessibility_value_is_ignored(self):
        kept, drops = hard_filter(POIS, {"accessibility": ["teleport"]})
        self.assertEqual(ids(kept), ids(POIS))
        self.assertEqual(drops, [])


class TestShape(unittest.TestCase):
    def test_drop_carries_warning_fields(self):
        drop = drop_reason(SEAFOOD, {"allergy": ["seafood"]})
        self.assertEqual(drop["rule"], "allergy")
        _kept, drops = hard_filter([SEAFOOD], {"allergy": ["seafood"]})
        line = warning(drops[0])
        self.assertIn("da loai", line)
        self.assertIn("di ung", line)
        self.assertIn("Hải sản My Hanh", line)

    def test_first_rule_wins(self):
        both = dict(SEAFOOD, intensity=3, cat="nature")
        drop = drop_reason(both, {"allergy": ["seafood"],
                                  "accessibility": ["wheelchair"]})
        self.assertEqual(drop["rule"], "allergy")

    def test_empty_profile_is_a_noop(self):
        kept, drops = hard_filter(POIS, {})
        self.assertEqual(ids(kept), ids(POIS))
        self.assertEqual(drops, [])


if __name__ == "__main__":
    unittest.main()
