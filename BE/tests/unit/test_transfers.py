"""Boat / cable-car / walk legs applied to the matrix at load (services/transfers.py).

A toy line of places, road minutes = distance on the line (km = minutes / 2):

    q2=1  isle=2  a=0  b=4  q1=6  base=10  beach=15  top1=top2=30 (both snapped
    onto one far service road, like the Bà Nà summit)

- top1, top2 sit behind `base` (cable car, 5 ride + 3 board), walked between;
- isle sits behind a pier with no row: via q1 (+2 min, 1 km) or q2 (+6 min, 3 km),
  boat 20 min;
- beach keeps its own row (OSRM stopped at the road), 7 min walk down.

Run from repo root: python -m pytest BE/tests/unit/test_transfers.py -q
"""

import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import matrix as matrix_mod  # noqa: E402
from BE.app.services import transfers  # noqa: E402
from BE.app.services.matrix import DENSE_FORMAT, DenseCells, load_matrix_doc  # noqa: E402
from BE.app.services.response import plan_totals  # noqa: E402

POS = {"a": 0, "b": 4, "base": 10, "top1": 30, "top2": 30, "isle": 2, "q1": 6, "q2": 1, "beach": 15}
IDS = list(POS)
# top1 / top2: 0.5 km apart (0.0045 deg of latitude); the walk is 0.65 km.
TOP1, TOP2 = (16.0, 108.0), (16.0045, 108.0)

SPEC = {
    "format": transfers.FORMAT,
    "walk": {"kmh": 4.0, "detour": 1.3},
    "gateways": [
        {"id": "cable", "name": "Cáp treo", "mode": "cable_car", "road_end": {"poi_id": "base"},
         "ride_min": 5, "board_min": 3, "km": 2.0, "inside": "walk",
         "places": [{"poi_id": "top1", "lat": TOP1[0], "lon": TOP1[1]},
                    {"poi_id": "top2", "lat": TOP2[0], "lon": TOP2[1]}]},
        {"id": "boat", "name": "Cano", "mode": "boat",
         "road_end": {"via": [{"poi_id": "q1", "minutes": 2, "km": 1.0},
                              {"poi_id": "q2", "minutes": 6, "km": 3.0}]},
         "ride_min": 20, "km": 9.0, "places": [{"poi_id": "isle"}]},
        {"id": "trail", "name": "Đường mòn", "mode": "walk", "road_end": {"own_row": True},
         "ride_min": 7, "board_min": 0, "km": 0.5, "places": [{"poi_id": "beach"}]},
    ],
}


def _rows():
    minutes = [[abs(POS[a] - POS[b]) for b in IDS] for a in IDS]
    km = [[m / 2 for m in row] for row in minutes]
    return minutes, km


def _applied(spec=SPEC, rows=None):
    minutes, km = rows or _rows()
    via, summary = transfers.apply_dense(IDS, minutes, km, spec)
    return DenseCells(IDS, minutes, km, via), summary


class TestApplyDense(unittest.TestCase):
    def setUp(self):
        self.cells, self.summary = _applied()

    def leg(self, a, b):
        return self.cells[f"{a}->{b}"]

    def test_cable_car_place_is_reached_from_its_base(self):
        self.assertEqual(self.leg("a", "top1")["minutes"], 10 + 8)      # road to base + cable
        self.assertEqual(self.leg("top1", "b")["minutes"], 8 + 6)
        self.assertEqual(self.leg("base", "top2")["minutes"], 8)        # from the base itself
        self.assertEqual(self.leg("top2", "base")["minutes"], 8)
        self.assertEqual(self.leg("a", "top1")["km"], 5.0 + 2.0)

    def test_two_places_of_one_gateway_are_walked(self):
        cell = self.leg("top1", "top2")
        self.assertEqual((cell["minutes"], cell["km"]), (10, 0.65))    # 0.65 km at 4 km/h
        self.assertEqual(cell["mode"], "walk")
        self.assertNotIn("transfers", cell)

    def test_island_pier_is_the_best_of_its_via_rows(self):
        # a: via q1 6+2=8, via q2 1+6=7 -> 7; b: via q1 2+2=4 -> 4
        self.assertEqual(self.leg("a", "isle")["minutes"], 7 + 20)
        self.assertEqual(self.leg("b", "isle")["minutes"], 4 + 20)
        self.assertEqual(self.leg("isle", "b")["minutes"], 20 + 4)
        self.assertEqual(self.leg("a", "isle")["km"], 0.5 + 3.0 + 9.0)  # km follows the fastest

    def test_two_gateways_chain_their_transfers(self):
        # pier -> base: via q1 2 + |6-10| = 6 (via q2: 6 + 9 = 15)
        self.assertEqual(self.leg("isle", "top1")["minutes"], 20 + 6 + 8)
        self.assertEqual(self.leg("top1", "isle")["minutes"], 8 + 6 + 20)
        self.assertEqual(self.leg("isle", "top1")["mode"], "boat+motorbike+cable_car")

    def test_own_row_walk_adds_the_trail_both_ways(self):
        self.assertEqual(self.leg("a", "beach")["minutes"], 15 + 7)
        self.assertEqual(self.leg("beach", "a")["minutes"], 7 + 15)
        self.assertEqual(self.leg("beach", "top1")["minutes"], 7 + 5 + 8)
        self.assertEqual(self.leg("a", "beach")["mode"], "motorbike+walk")

    def test_other_legs_diagonal_and_bulk_reads_are_unchanged(self):
        self.assertEqual(self.leg("a", "b"), {"km": 2.0, "minutes": 4})
        self.assertEqual(self.leg("top1", "top1"), {"km": 0, "minutes": 0})
        bulk = self.cells.travel_minutes(IDS)
        self.assertEqual(bulk[("a", "top1")], 18)
        self.assertEqual(bulk[("a", "b")], 4)
        self.assertEqual(matrix_mod.legs_from(self.cells, "a", ["isle"]), {("a", "isle"): 27})

    def test_cells_say_how_the_leg_is_made(self):
        cell = self.leg("a", "isle")
        self.assertEqual(cell["mode"], "motorbike+boat")
        self.assertEqual(cell["transfers"], [{"gateway": "boat", "name": "Cano", "mode": "boat",
                                              "minutes": 20, "km": 9.0}])
        self.assertEqual(self.leg("base", "top1")["mode"], "cable_car")   # no road part
        self.assertEqual(self.leg("top1", "a")["mode"], "cable_car+motorbike")

    def test_summary_counts_and_lists_gateways(self):
        self.assertEqual(self.summary["skipped"], [])
        self.assertEqual([g["id"] for g in self.summary["gateways"]], ["cable", "boat", "trail"])
        self.assertEqual(self.summary["gateways"][0]["minutes"], 8)
        self.assertGreater(self.summary["cells_changed"], 0)

    def test_unroutable_road_leg_stays_absent(self):
        minutes, km = _rows()
        i, j1, j2 = IDS.index("a"), IDS.index("q1"), IDS.index("q2")
        minutes[i][j1] = minutes[i][j2] = None
        cells, _ = _applied(rows=(minutes, km))
        self.assertIsNone(cells.get("a->isle"))
        self.assertEqual(cells["b->isle"]["minutes"], 24)

    def test_stale_or_bad_gateways_are_skipped_not_fatal(self):
        spec = copy.deepcopy(SPEC)
        spec["gateways"][0]["places"].append({"poi_id": "gone"})   # not in this matrix
        spec["gateways"][1]["mode"] = "rocket"
        cells, summary = _applied(spec)
        self.assertEqual(len(summary["skipped"]), 2, summary["skipped"])
        self.assertEqual([g["id"] for g in summary["gateways"]], ["trail"])
        self.assertEqual(cells["a->top1"], {"km": 15.0, "minutes": 30})   # raw matrix
        self.assertEqual(cells["a->beach"]["minutes"], 22)

    def test_a_malformed_entry_is_skipped_with_its_reason(self):
        spec = copy.deepcopy(SPEC)
        del spec["gateways"][0]["ride_min"]
        spec["gateways"][1]["road_end"]["via"][0]["minutes"] = "five"
        spec["gateways"].append("not a gateway")
        _cells, summary = _applied(spec)
        self.assertEqual([g["id"] for g in summary["gateways"]], ["trail"])
        self.assertEqual([why.split(":")[0] for why in summary["skipped"]], ["cable", "boat", "?"])

    def test_a_road_end_or_place_behind_another_gateway_is_refused(self):
        spec = copy.deepcopy(SPEC)
        spec["gateways"][2]["road_end"] = {"poi_id": "top1"}
        spec["gateways"][1]["places"].append({"poi_id": "top2"})
        _cells, summary = _applied(spec)
        self.assertEqual([g["id"] for g in summary["gateways"]], ["cable"])
        self.assertEqual(len(summary["skipped"]), 2, summary["skipped"])


class TestLoader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tr_")
        matrix_mod._DOC_CACHE.clear()
        minutes, km = _rows()
        self.matrix = os.path.join(self.dir, "matrix.json")
        with open(self.matrix, "w", encoding="utf-8") as f:
            json.dump({"format": DENSE_FORMAT, "ids": IDS, "n": len(IDS),
                       "minutes": minutes, "km": km}, f)

    def _write_spec(self, spec):
        path = os.path.join(self.dir, transfers.TRANSFERS_FILE)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        return path

    def test_no_file_reads_the_raw_matrix(self):
        doc = load_matrix_doc(self.matrix)
        self.assertNotIn("transfers", doc)
        self.assertEqual(doc["cells"]["a->top1"]["minutes"], 30)

    def test_file_next_to_the_matrix_is_applied_and_can_be_skipped(self):
        self._write_spec(SPEC)
        doc = load_matrix_doc(self.matrix)
        self.assertEqual(doc["cells"]["a->top1"]["minutes"], 18)
        self.assertEqual(doc["transfers"]["skipped"], [])
        raw = load_matrix_doc(self.matrix, transfers=False)
        self.assertEqual(raw["cells"]["a->top1"]["minutes"], 30)
        self.assertIs(load_matrix_doc(self.matrix), doc)           # cached per flag
        self.assertEqual(matrix_mod.load_cells(self.dir)["a->top1"]["minutes"], 18)

    def test_editing_the_file_reloads(self):
        path = self._write_spec(SPEC)
        self.assertEqual(load_matrix_doc(self.matrix)["cells"]["a->top1"]["minutes"], 18)
        spec = copy.deepcopy(SPEC)
        spec["gateways"][0]["ride_min"] = 15
        self._write_spec(spec)
        os.utime(path, ns=(1, 1))
        self.assertEqual(load_matrix_doc(self.matrix)["cells"]["a->top1"]["minutes"], 28)

    def test_unknown_format_and_legacy_matrix_are_loud(self):
        self._write_spec({"format": "transfers-v9"})
        with self.assertRaises(ValueError):
            load_matrix_doc(self.matrix)
        legacy_dir = tempfile.mkdtemp(prefix="trl_")
        legacy = os.path.join(legacy_dir, "matrix.json")
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump({"cells": {"a->b": {"km": 1.0, "minutes": 2}}}, f)
        with open(os.path.join(legacy_dir, transfers.TRANSFERS_FILE), "w", encoding="utf-8") as f:
            json.dump(SPEC, f)
        with self.assertRaises(ValueError):
            load_matrix_doc(legacy)


class TestPlanSegments(unittest.TestCase):
    def test_segments_carry_the_mode_and_transfers(self):
        cells, _ = _applied()
        acts = [{"poi_id": "a", "start": "08:00", "end": "09:00"},
                {"poi_id": "isle", "start": "09:30", "end": "15:00"},
                {"poi_id": "b", "start": "15:30", "end": "16:00"}]
        totals = plan_totals(acts, {"travelers": 1}, {}, cells)
        first, second = totals["segments"]
        self.assertEqual((first["mode"], first["minutes"]), ("motorbike+boat", 27))
        self.assertEqual(first["transfers"][0]["mode"], "boat")
        self.assertEqual((second["mode"], second["minutes"]), ("boat+motorbike", 24))
        self.assertEqual(totals["travel_min"], 51)

    def test_gps_segment_keeps_the_chosen_anchors_transfer(self):
        base, _ = _applied()
        acts = [{"poi_id": "top1", "start": "09:00", "end": "10:00"}]
        for access, mode in [(0, "cable_car"), (2, "motorbike+cable_car")]:
            cells = matrix_mod.with_starts(base, {"@gps": (("a", 1, 0.5), ("base", access, 0))})
            totals = plan_totals(acts, {"origin_id": "@gps"}, {}, cells)
            segment, = totals["segments"]
            self.assertEqual((segment["source"], segment["mode"]), ("gps_estimate", mode))
            self.assertEqual(segment["minutes"], 8 + access)
            self.assertEqual(segment["transfers"], base["base->top1"]["transfers"])
        self.assertEqual(matrix_mod.legs_to(base, ["top1"], "base"), {("top1", "base"): 8})

    def test_road_legs_keep_the_old_shape(self):
        cells, _ = _applied()
        acts = [{"poi_id": "a", "start": "08:00", "end": "09:00"},
                {"poi_id": "b", "start": "09:30", "end": "10:00"}]
        (segment,) = plan_totals(acts, {"travelers": 1}, {}, cells)["segments"]
        self.assertEqual(segment, {"from_id": "a", "to_id": "b", "mode": "motorbike",
                                   "km": 2.0, "minutes": 4, "source": "cache"})


if __name__ == "__main__":
    unittest.main()
