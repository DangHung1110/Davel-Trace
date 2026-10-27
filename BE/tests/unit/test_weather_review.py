"""Unit tests for the T063 weather-label standalone HTML review generator.

Run from repo root: python -m unittest BE.tests.unit.test_weather_review -v
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.ml.weather_label.render_review import (  # noqa: E402
    LS_KEY,
    render_html,
)


def _sample_rows() -> list[dict]:
    return [
        {
            "poi_id": "p1",
            "name": "Bãi biển Mỹ Khê",
            "type": "Bãi biển",
            "lat": 16.07,
            "lon": 108.24,
            "old_space": "outdoor",
            "suggested_space": "outdoor",
            "space_source": "tag",
            "space_confidence": 0.9,
            "space_evidence": ["tag tourism=beach"],
            "old_rain_protection": False,
            "rain_protection": False,
            "rain_protection_confidence": 0.9,
            "rain_protection_evidence": ["không có mái che"],
            "space_conflict": False,
        },
        {
            "poi_id": "p2",
            "name": "Bảo tàng Chăm",
            "type": "Bảo tàng",
            "lat": 16.05,
            "lon": 108.22,
            "old_space": "unknown",
            "suggested_space": "indoor",
            "space_source": "tag",
            "space_confidence": 0.9,
            "space_evidence": ["tag tourism=museum"],
            "old_rain_protection": False,
            "rain_protection": True,
            "rain_protection_confidence": 0.8,
            "rain_protection_evidence": ["có mái che"],
            "space_conflict": True,
        },
        {
            "poi_id": "p3",
            "name": "Cà phê cóc",
            "type": "Quán cà phê",
            "old_space": "indoor",
            "suggested_space": "both",
            "space_source": "heuristic",
            "space_confidence": 0.6,
            "space_evidence": ["name contains cafe", "outdoor seating"],
            "rain_protection": "partial",
            "rain_protection_evidence": ["một phần mái che"],
            "space_conflict": False,
        },
    ]


def _extract_rows(html_doc: str) -> list[dict]:
    """Extract the embedded JSON row payload from the raw script text."""
    m = re.search(
        r'<script type="application/json" id="rows-data">(.*?)</script>',
        html_doc,
        re.S,
    )
    assert m is not None, "rows-data script block not found"
    # Script text content is raw, not HTML-unescaped by the browser.
    return json.loads(m.group(1))


def _poi_ids(html_doc: str) -> list[str]:
    return re.findall(r"data-poi-id='([^']+)'", html_doc)


class TestWeatherReview(unittest.TestCase):
    def test_card_count_and_unique_ids(self):
        rows = _sample_rows()
        doc = render_html(rows)
        ids = _poi_ids(doc)
        self.assertEqual(len(ids), len(rows))
        self.assertEqual(len(set(ids)), len(rows))
        for row in rows:
            self.assertIn(str(row["poi_id"]), ids)

    def test_controls_per_card(self):
        rows = _sample_rows()
        doc = render_html(rows)
        for poi_id in [str(r["poi_id"]) for r in rows]:
            self.assertIn(f"data-poi='{poi_id}'", doc)
            # Three mutually-exclusive choices.
            for value in ("indoor", "outdoor", "both"):
                self.assertIn(
                    f"value='{value}'",
                    doc,
                )
            self.assertIn(f"<button class='confirm' data-poi='{poi_id}'>Xác nhận</button>", doc)

    def test_filters_present(self):
        doc = render_html(_sample_rows())
        expected = ["all", "todo", "old-indoor", "old-outdoor", "old-both", "old-unknown"]
        for f in expected:
            self.assertIn(f'data-f="{f}"', doc)

    def test_progress_shown(self):
        rows = _sample_rows()
        doc = render_html(rows)
        self.assertIn(f"id=\"prog\">Đã xác nhận 0/{len(rows)}</b>", doc)

    def test_local_storage_key_stable_and_restore_logic(self):
        doc = render_html(_sample_rows())
        self.assertIn(LS_KEY, doc)
        self.assertIn("localStorage.getItem(LS_KEY)", doc)
        self.assertIn("localStorage.setItem(LS_KEY", doc)
        # Restoring a saved choice should check the right checkbox and mark confirmed.
        self.assertIn("saved[poiId]", doc)
        self.assertIn(".choice[value=\"' + CSS.escape(String(val)) + '\"]')", doc)
        self.assertIn("markConfirmed(poiId)", doc)
        # Key must not drift between renders.
        doc2 = render_html(_sample_rows()[:1])
        self.assertEqual(doc2.count(LS_KEY), doc.count(LS_KEY))

    def test_export_logic(self):
        doc = render_html(_sample_rows())
        self.assertIn('id="exp"', doc)
        self.assertIn("JSON.stringify(saved", doc)
        self.assertIn("new Blob([JSON.stringify(saved", doc)
        self.assertIn("download", doc)

    def test_blind_mode_hides_model_output_and_uses_private_storage(self):
        rows = _sample_rows()
        doc = render_html(rows, blind=True)
        self.assertIn("(blind)", doc)
        self.assertNotIn("<h4>Nhãn cũ</h4>", doc)
        self.assertNotIn("<h4>Đề xuất mới</h4>", doc)
        self.assertNotIn("space_evidence", doc)
        self.assertIn(f"{LS_KEY}_blind", doc)
        self.assertIn("weather_review_blind_decisions.json", doc)
        exported_rows = _extract_rows(doc)
        allowed = {"poi_id", "name", "type", "lat", "lon"}
        self.assertTrue(all(set(row) <= allowed for row in exported_rows))
        self.assertNotIn("old_space", doc)
        self.assertNotIn("suggested_space", doc)

    def test_html_escaping(self):
        rows = [
            {
                "poi_id": "x1",
                "name": "<script>alert('xss')</script>",
                "type": "Test",
                "old_space": "indoor",
                "suggested_space": "outdoor",
                "space_source": "test",
                "space_confidence": 0.5,
                "space_evidence": ["<b>bad</b>"],
                "rain_protection": True,
                "space_conflict": True,
            }
        ]
        doc = render_html(rows)
        # The literal payload must not appear in the HTML source.
        self.assertNotIn("<script>alert('xss')</script>", doc)
        self.assertNotIn("<b>bad</b>", doc)
        # The raw script block must be JSON-safe text, not HTML-escaped.
        self.assertIn("\\u003cscript\\u003e", doc)
        self.assertIn("\\u003cb\\u003e", doc)
        # Round-trip through the raw script text still yields the original data.
        self.assertEqual(_extract_rows(doc), rows)

    def test_script_tag_injection_roundtrip(self):
        payload = "</script><img src=x onerror=alert(1)>"
        rows = [
            {
                "poi_id": "x1",
                "name": payload,
                "type": "Test",
                "old_space": "indoor",
                "suggested_space": "outdoor",
                "space_source": "test",
                "space_confidence": 0.5,
                "space_evidence": [payload],
                "rain_protection": False,
                "space_conflict": True,
            }
        ]
        doc = render_html(rows)
        # The payload must not appear literally in the generated HTML.
        self.assertNotIn(payload, doc)
        # The script block's raw text must not contain an unescaped </script>.
        m = re.search(
            r'<script type="application/json" id="rows-data">(.*?)</script>',
            doc,
            re.S,
        )
        self.assertIsNotNone(m)
        self.assertNotIn("</script>", m.group(1))
        # JSON.parse on the raw text can reconstruct the original payload.
        self.assertEqual(_extract_rows(doc), rows)

    def test_map_link_when_coordinates_exist(self):
        with_coords = render_html(_sample_rows()[:2])
        self.assertIn("Xem bản đồ", with_coords)
        self.assertIn("openstreetmap.org", with_coords)

    def test_no_map_link_without_coordinates(self):
        rows = [{"poi_id": "p0", "name": "No coords", "type": "X",
                 "old_space": "indoor", "suggested_space": "indoor",
                 "space_source": "x", "space_confidence": 0.5,
                 "space_evidence": [], "rain_protection": False,
                 "space_conflict": False}]
        doc = render_html(rows)
        self.assertNotIn("Xem bản đồ", doc)

    def test_embedded_json_matches_input(self):
        rows = _sample_rows()
        doc = render_html(rows)
        extracted = _extract_rows(doc)
        self.assertEqual(extracted, rows)

    def test_render_empty_rows(self):
        doc = render_html([])
        self.assertIn("Đã xác nhận 0/0", doc)
        self.assertEqual(_poi_ids(doc), [])


if __name__ == "__main__":
    unittest.main()
