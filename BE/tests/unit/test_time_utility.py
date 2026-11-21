"""u(t) priors (BE/data/priors/time_profiles.json) + sun times."""

import datetime as dt
import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)

from BE.app.services.time_utility import PRIORS, load_profiles, sun_times, u_at, u_mean  # noqa: E402

JUNE, DEC = dt.date(2026, 6, 21), dt.date(2026, 12, 21)


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


class TestSun(unittest.TestCase):
    def test_danang_against_published_tables(self):
        # day length 2026-06-21 = 13h05, 2026-12-22 = 11h10 (weatherspark.com);
        # 2026-12-15 sunrise 06:06 / sunset 17:17 (alpenglowapp.com) — ±3 min
        j = sun_times(JUNE)
        self.assertLess(abs((j["sunset"] - j["sunrise"]) - (13 * 60 + 5)), 3)
        d22 = sun_times(dt.date(2026, 12, 22))
        self.assertLess(abs((d22["sunset"] - d22["sunrise"]) - (11 * 60 + 10)), 3)
        d15 = sun_times(dt.date(2026, 12, 15))
        self.assertLess(abs(d15["sunrise"] - hm("06:06")), 3)
        self.assertLess(abs(d15["sunset"] - hm("17:17")), 3)


class TestProfiles(unittest.TestCase):
    def test_every_snapshot_profile_has_a_curve(self):
        with open(os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2", "pois.json"), encoding="utf-8") as f:
            used = {p.get("time_profile") for p in json.load(f)["pois"]}
        self.assertFalse(used - set(load_profiles()), used - set(load_profiles()))

    def test_range_peak_and_24h(self):
        for name, prof in load_profiles().items():
            vals = [u_at(name, m, day) for day in (JUNE, DEC) for m in range(0, 1440, 10)]
            self.assertTrue(all(0.0 <= v <= 1.0 for v in vals), name)
            if name != "none":
                self.assertAlmostEqual(max(p["u"] for p in prof["points"]), 1.0, msg=name)

    def test_beach_follows_the_sun(self):
        # peak 30 min after sunrise moves with the season; noon is low
        for day in (JUNE, DEC):
            s = sun_times(day)
            self.assertAlmostEqual(u_at("sun_anchored_beach", s["sunrise"] + 30, day), 1.0, places=2)
            self.assertLess(u_at("sun_anchored_beach", s["solar_noon"] + 30, day), 0.4)

    def test_mean_over_stay(self):
        # a 3h beach stay from 10:00 into noon heat scores below a 1h stay at 06:00 (June)
        self.assertGreater(u_mean("sun_anchored_beach", hm("06:00"), 60, JUNE),
                           u_mean("sun_anchored_beach", hm("10:00"), 180, JUNE))
        self.assertAlmostEqual(u_mean("open_hours_flat", 600, 120, JUNE), 1.0)

    def test_unknown_profile_is_neutral(self):
        self.assertEqual(u_at("no_such_profile", 600, JUNE), 1.0)

    def test_priors_file_marks_design_status(self):
        with open(PRIORS, encoding="utf-8") as f:
            self.assertIn("design prior", json.load(f)["status"])


if __name__ == "__main__":
    unittest.main()
