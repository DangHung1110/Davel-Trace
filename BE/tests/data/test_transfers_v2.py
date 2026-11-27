"""Rule 18 (DATA_SPEC_v2_1 §5): `danang-v2/transfers.json` matches the snapshot.

Places a motorbike cannot reach are reached through a boat, a cable car or a
walk from a road end (`BE/app/services/transfers.py`). The file names places by
poi_id, so a rebuilt snapshot can drift from it; these checks make the drift loud:

- every gateway resolves (nothing skipped at load), its places exist with the same
  name and coordinates as `pois.json` (walks inside Bà Nà are measured on them);
- every active POI of cluster `ba_na` is behind the cable car (a new summit
  restaurant must not be driven to on the service road);
- boats and cable cars cite a web source, walks say how they were measured;
- on the loaded matrix no leg of Cù Lao Chàm beats the straight line any more
  (26.5% did: OSRM had snapped the island onto the mainland), and no summit leg
  is the old shared-snap minute.

Run from the repo root:  python -m pytest BE/tests/data/test_transfers_v2.py -q
"""

import json
import math
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)

from BE.app.services import transfers  # noqa: E402
from BE.app.services.matrix import load_matrix_doc  # noqa: E402

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
SPEC = os.path.join(SNAP, transfers.TRANSFERS_FILE)
# BE/tools/coord_check_osm.py (matrix_short_share): pairs this far apart, road km
# under this share of the straight line, cannot be a road.
MATRIX_MIN_KM, MATRIX_SHORT = 2.0, 0.85


def _km(a: dict, b: dict) -> float:
    return transfers._straight_km((a["lat"], a["lon"]), (b["lat"], b["lon"]))


@unittest.skipUnless(os.path.exists(SPEC), "danang-v2 has no transfers.json")
class TestTransfersV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = transfers.read(SPEC)
        with open(os.path.join(SNAP, "pois.json"), encoding="utf-8") as f:
            cls.pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
        cls.doc = load_matrix_doc(os.path.join(SNAP, "matrix.json"))
        cls.cells = cls.doc["cells"]
        cls.gates = {g["id"]: g for g in cls.spec["gateways"]}

    def test_every_gateway_resolves(self):
        summary = self.doc["transfers"]
        self.assertEqual(summary["skipped"], [])
        self.assertEqual(sorted(g["id"] for g in summary["gateways"]), sorted(self.gates))

    def test_places_match_the_snapshot(self):
        for gate in self.spec["gateways"]:
            for place in gate["places"]:
                poi = self.pois.get(place["poi_id"])
                self.assertIsNotNone(poi, place)
                self.assertEqual(place["name"], poi["name"])
                self.assertLess(_km(place, poi) * 1000, 1.0, place["name"])

    def test_road_ends_are_real_rows(self):
        for gate in self.spec["gateways"]:
            end = gate["road_end"]
            for pid in [end.get("poi_id")] + [v["poi_id"] for v in end.get("via") or []]:
                if pid:
                    self.assertEqual(self.pois[pid]["status"], "active", (gate["id"], pid))
                    self.assertIsNotNone(self.cells.get(f"{pid}->{pid}"), (gate["id"], pid))

    def test_every_active_summit_poi_is_behind_the_cable_car(self):
        behind = {p["poi_id"] for p in self.gates["ba_na_cable_car"]["places"]}
        summit = {pid for pid, p in self.pois.items()
                  if p.get("cluster_id") == "ba_na" and p["status"] == "active"}
        self.assertEqual(sorted(summit - behind), [])

    def test_sources_and_bases(self):
        for gate in self.spec["gateways"]:
            self.assertTrue(gate.get("basis"), gate["id"])
            self.assertGreaterEqual(int(gate["ride_min"]), 1, gate["id"])
            if gate["mode"] in ("boat", "cable_car"):
                web = [s for s in gate["sources"] if "openstreetmap.org" not in s["url"]]
                self.assertTrue(web, f"{gate['id']}: ride minutes need a web source")
            else:   # a walk: minutes follow its measured km at the file's walking speed
                walk = self.spec["walk"]
                self.assertEqual(int(gate["ride_min"]),
                                 round(float(gate["km"]) / walk["kmh"] * 60), gate["id"])

    def test_island_legs_no_longer_beat_the_straight_line(self):
        island = self.pois["manual:cu-lao-cham"]
        short = total = 0
        for pid in self.doc["ids"]:
            other = self.pois.get(pid)
            if other is None or _km(island, other) < MATRIX_MIN_KM:
                continue
            for key in (f"{pid}->manual:cu-lao-cham", f"manual:cu-lao-cham->{pid}"):
                total += 1
                short += self.cells[key]["km"] < MATRIX_SHORT * _km(island, other)
        self.assertGreater(total, 1000)
        self.assertEqual(short, 0)
        hoi_an = next(p for p in self.pois.values() if p["name"] == "Phố cổ Hội An")
        leg = self.cells[f"{hoi_an['poi_id']}->manual:cu-lao-cham"]
        self.assertEqual(leg["mode"], "motorbike+boat")
        self.assertGreaterEqual(leg["minutes"], 30 + 10)    # boat + a road to the pier

    def test_summit_legs_are_walked_not_one_shared_minute(self):
        places = [p for p in self.gates["ba_na_cable_car"]["places"] if p["status"] == "active"]
        for a in places:
            for b in places:
                if a is b:
                    continue
                leg = self.cells[f"{a['poi_id']}->{b['poi_id']}"]
                self.assertEqual(leg["mode"], "walk")
                walk = self.spec["walk"]
                floor = _km(a, b) * walk["detour"] / walk["kmh"] * 60
                self.assertGreaterEqual(leg["minutes"], math.floor(floor), (a["name"], b["name"]))
        base = self.gates["ba_na_cable_car"]["road_end"]["poi_id"]
        gate = self.gates["ba_na_cable_car"]
        for place in places:
            up = self.cells[f"{base}->{place['poi_id']}"]
            self.assertEqual((up["minutes"], up["mode"]),
                             (gate["ride_min"] + gate["board_min"], "cable_car"), place["name"])


if __name__ == "__main__":
    unittest.main()
