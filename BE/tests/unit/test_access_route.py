"""Sơn Trà road window bounds hours set after the build (decisions / human verify)."""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))

from migrate_v2 import clip_to_access, load_access_route  # noqa: E402


def _rec(open_, access):
    return {"hours": {"open": open_, "access_window": access}}


class TestAccessRoute(unittest.TestCase):
    def test_clip_24h_to_window(self):
        r = _rec(["00:00-23:59"], ["07:30-17:30"])
        clip_to_access(r)
        self.assertEqual(r["hours"]["open"], ["07:30-17:30"])

    def test_clip_late_close(self):
        r = _rec(["07:30-19:00"], ["07:30-17:30"])
        clip_to_access(r)
        self.assertEqual(r["hours"]["open"], ["07:30-17:30"])

    def test_no_window_untouched(self):
        r = _rec(["05:00-22:00"], None)
        clip_to_access(r)
        self.assertEqual(r["hours"]["open"], ["05:00-22:00"])

    def test_load_later_file_wins_and_ignores_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            for fn, cls in (("access_route_a.json", "off_route"), ("access_route_b.json", "on_route")):
                with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
                    json.dump({"items": [{"poi_id": "p1", "class": cls},
                                         {"poi_id": "p2", "class": "unknown"}]}, f)
            self.assertEqual(load_access_route(d), {"p1": "on_route"})


if __name__ == "__main__":
    unittest.main()
