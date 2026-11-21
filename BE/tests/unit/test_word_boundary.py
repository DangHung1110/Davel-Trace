"""Whole-word matching regressions (audit B3): no substring hits.

Covers templates._has (party/activity hints), soft_rules.cafe_need,
repair._mentions, profile_filter.has_word and profile_filter.cuisine_terms.

Run from repo root: python BE/tests/unit/test_word_boundary.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import profile_filter, repair, soft_rules, templates  # noqa: E402


class TestTemplateHints(unittest.TestCase):
    def test_party_values_still_map(self):
        cases = {"family_with_kids": "family-slow", "friends": "friends-fast",
                 "couple": "couple-calm", "gia đình": "family-slow",
                 "nhóm bạn": "friends-fast", "children": "family-slow"}
        for party, want in cases.items():
            self.assertEqual(templates.select_template({"party_type": party}), want,
                             party)

    def test_no_substring_activity_hint(self):
        solo = {"party_type": "solo"}
        self.assertEqual(templates.select_template(
            dict(solo, activities=["ăn barbecue"])), "couple-calm")
        self.assertEqual(templates.select_template(
            dict(solo, activities=["public beach"])), "couple-calm")
        self.assertEqual(templates.select_template(
            dict(solo, activities=["đi bar"])), "friends-fast")


class TestCafeNeed(unittest.TestCase):
    def test_whole_word(self):
        self.assertTrue(soft_rules.cafe_need({"food_prefs": ["cà phê"]}))
        self.assertTrue(soft_rules.cafe_need({"activities": ["uống coffee"]}))
        self.assertFalse(soft_rules.cafe_need({"food_prefs": ["cafeteria"]}))


class TestRepairMentions(unittest.TestCase):
    def test_whole_word(self):
        self.assertTrue(repair._mentions("bỏ quán bar này", "bar"))
        self.assertFalse(repair._mentions("đổi quán barbecue", "bar"))
        self.assertFalse(repair._mentions("văn hóa", "an"))
        self.assertFalse(repair._mentions("bất kỳ", ""))


class TestProfileFilterHelpers(unittest.TestCase):
    def test_has_word_on_folded_text(self):
        self.assertTrue(profile_filter.has_word("thich ca phe sang", ["cà phê"]))
        self.assertFalse(profile_filter.has_word("caphesua", ["ca phe"]))

    def test_cuisine_terms(self):
        self.assertEqual(profile_filter.cuisine_terms("ăn hải sản"), ["hải sản"])
        self.assertEqual(profile_filter.cuisine_terms("đồ chay thuần"), ["chay"])
        self.assertEqual(profile_filter.cuisine_terms("tắm biển"), [])


if __name__ == "__main__":
    unittest.main()
