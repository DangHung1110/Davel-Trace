"""Unit test for rolling replan (T046). Rain/clarify/no-solution.

Run from repo root: python BE/tests/unit/test_replan.py -v
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import scorer  # noqa: E402
from BE.app.services import state as store  # noqa: E402
from BE.app.services.common import to_min  # noqa: E402
from BE.app.services.matrix import MatrixService  # noqa: E402
from BE.app.services.optimizer import travel_from_matrix  # noqa: E402
from BE.app.services.replan import replan  # noqa: E402
from BE.app.services.validator import validate  # noqa: E402

H = 60
POIS = [
    {"poi_id": "hill", "verified": True, "visit_min": 120, "fee": 0, "intensity": 3,
     "weather_sensitive": True, "opening_hours": ["05:00-18:00"]},
    {"poi_id": "beach", "verified": True, "visit_min": 120, "fee": 0, "intensity": 2,
     "weather_sensitive": True, "opening_hours": ["00:00-23:59"]},
    {"poi_id": "museum", "verified": True, "visit_min": 90, "fee": 60000, "intensity": 1,
     "weather_sensitive": False, "opening_hours": ["07:30-17:00"]},
    {"poi_id": "noodle", "verified": True, "visit_min": 60, "fee": 50000, "intensity": 1,
     "weather_sensitive": False, "opening_hours": ["07:00-21:00"]},
]
IDS = [p["poi_id"] for p in POIS]
TRAVEL = {(a, b): 10 for a in ["depot"] + IDS for b in IDS if a != b}
TRIP = {"trip_id": "t1", "budget": 3000000, "avoid": [],
        "start_time": "07:00", "end_time": "18:00"}

# T046 deadline fixture: a long, weather-safe, verified POI. With the base
# fixture (hill+beach 120min completed) the remaining museum+noodle only reach
# 14:50, so a 15:00 return_time would never bind; this POI makes the horizon
# difference observable (a 18:00 horizon overshoots 15:00, a 15:00 horizon
# does not). `delay` drops nothing, so it stays in play.
DEADLINE_POI = {"poi_id": "lakeside", "verified": True, "visit_min": 150,
                "fee": 0, "intensity": 2, "weather_sensitive": False,
                "opening_hours": ["06:00-19:00"]}

REPO = os.path.join(os.path.dirname(__file__), "..", "..", "..")
SNAPSHOT_DIR = os.path.join(REPO, "BE", "data", "snapshots", "danang-v1")
MATRIX_JSON = os.path.join(SNAPSHOT_DIR, "matrix.json")
POIS_JSON = os.path.join(SNAPSHOT_DIR, "pois.json")
DEPOT = "ChIJ03jTTgAXQjERpVQunmJHv2c"  # Sontra Sea Hotel (matrix snapshot depot)


def fresh_state():
    s = store.new_state("t1", [{"poi_id": "hill", "start": "07:30", "end": "09:30"},
                               {"poi_id": "beach", "start": "10:00", "end": "12:00"},
                               {"poi_id": "noodle", "start": "12:30", "end": "13:30"}],
                        "07:00", "hotel")
    return store.complete(store.complete(s, "hill", "09:30"), "beach", "12:00")


class TestReplan(unittest.TestCase):
    def test_rain_replans_remaining_keeps_completed(self):
        s = fresh_state()
        out = replan(s, {"type": "rain", "at": "13:00"}, POIS, TRAVEL, TRIP)
        self.assertEqual(out["mode"], "plan")
        self.assertEqual(out["preserved_completed"], ["hill", "beach"])
        self.assertEqual(out["version"], s["version"] + 1)
        drops = [c["poi_id"] for c in out["changes"] if c["action"] == "drop"]
        self.assertNotIn("hill", drops + [a["poi_id"] for a in out["itinerary"]["activities"]]
                         if out["itinerary"]["activities"] else drops)
        print(f"\n rain: mode {out['mode']} v{out['version']} changes {out['changes']}")

    def test_replan_twice_no_duplicates(self):
        s = fresh_state()
        event = {"type": "rain", "at": "13:00"}
        first = replan(s, event, POIS, TRAVEL, TRIP)
        self.assertEqual(first["mode"], "plan")
        s2 = store.load("t1")
        second = replan(s2, event, POIS, TRAVEL, TRIP)
        self.assertEqual(second["mode"], "plan")
        s3 = store.load("t1")
        ids = [a["poi_id"] for a in s3["remaining"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual((s["version"], first["version"], second["version"]),
                         (1, 2, 3))

    def test_hard_conflict_clarifies(self):
        s = fresh_state()
        out = replan(s, {"type": "add_req", "delta": {"must_keep": ["hill"]}},
                     POIS, TRAVEL, dict(TRIP, avoid=["hill"]))
        self.assertEqual(out["mode"], "clarify")
        self.assertIn("hill", out["question"])
        self.assertEqual(out["version"], s["version"])

    def test_infeasible_no_solution(self):
        s = store.new_state("t9", [{"poi_id": "a", "start": "07:00", "end": "08:00"}])
        pois = [{"poi_id": "a", "visit_min": 300, "fee": 0, "intensity": 1,
                 "weather_sensitive": False, "opening_hours": ["07:00-08:00"]},
                {"poi_id": "b", "visit_min": 300, "fee": 0, "intensity": 1,
                 "weather_sensitive": False, "opening_hours": ["09:00-10:00"]}]
        travel = {("a", "b"): 120, ("b", "a"): 120}
        out = replan(s, {"type": "delay", "delta": {"must_keep_all": True}},
                     pois, travel,
                     {"trip_id": "t9", "budget": 100, "avoid": [],
                      "start_time": "07:00", "end_time": "08:30"})
        self.assertEqual(out["mode"], "no_solution")
        self.assertIn("preserved_completed", out)

    def test_unverified_poi_fails_FAR_in_replan(self):
        trip = dict(TRIP, trip_id="unverified")
        state = store.new_state("unverified", [{"poi_id": "draft"}],
                                "07:00", "depot")
        draft = {"poi_id": "draft", "verified": False, "visit_min": 60,
                 "fee": 0, "intensity": 1, "weather_sensitive": False,
                 "opening_hours": ["07:00-18:00"]}
        out = replan(state, {"type": "delay"}, [draft],
                     {("depot", "draft"): 5}, trip)
        self.assertEqual(out["mode"], "no_solution")
        self.assertIn("FAR", out["reason"])

    def test_wires_q_ij_into_optimizer(self):
        s = fresh_state()
        with mock.patch.object(scorer, "edge_scores",
                               wraps=scorer.edge_scores) as m:
            out = replan(s, {"type": "rain", "at": "13:00"}, POIS, TRAVEL, TRIP)
        self.assertTrue(m.called)
        self.assertEqual(out["mode"], "plan")

    def test_return_time_is_hard_deadline(self):
        """T046: return_time clamps the horizon to min(end_time, return_time).

        Pre-fix the optimizer ran to end_time (18:00), packed the remaining
        pool past 15:00 and the canonical ETB gate failed -> no_solution;
        post-fix the 15:00 horizon keeps every activity at/before 15:00 and
        the plan stands (mode "plan").
        """
        trip = dict(TRIP, return_time="15:00")
        pois = POIS + [DEADLINE_POI]
        ids = IDS + [DEADLINE_POI["poi_id"]]
        travel = {(a, b): 10 for a in ["depot"] + ids for b in ids if a != b}
        s = store.new_state("rt", [
            {"poi_id": "hill", "start": "07:30", "end": "09:30"},
            {"poi_id": "beach", "start": "10:00", "end": "12:00"},
            {"poi_id": "museum", "start": "12:10", "end": "13:40"},
            {"poi_id": "noodle", "start": "13:50", "end": "14:50"},
            {"poi_id": "lakeside", "start": "15:00", "end": "17:30"},
        ], "07:00", "hotel")
        s = store.complete(store.complete(s, "hill", "09:30"), "beach", "12:00")

        out = replan(s, {"type": "delay", "at": "12:00"}, pois, travel, trip)
        self.assertEqual(out["mode"], "plan")
        acts = out["itinerary"]["activities"]
        self.assertTrue(acts)
        for a in acts:
            self.assertLessEqual(to_min(a["end"]), to_min("15:00"))

        # canonical validator (with return_time) passes on completed + new
        by_id = {p["poi_id"]: {"verified": p["verified"], "fee": p["fee"],
                               "opening_hours": p["opening_hours"]} for p in pois}
        matrix = {f"{a}->{b}": {"minutes": 0 if a == b else 10}
                  for a in ids for b in ids}
        full = ([{"poi_id": a["poi_id"], "start": a["start"], "end": a["end"]}
                 for a in s["completed"]] + acts)
        self.assertTrue(validate({"activities": full}, trip, by_id,
                                 matrix)["passed"])
        print(f"\n return_time: mode {out['mode']} ends "
              f"{[(a['poi_id'], a['end']) for a in acts]} <= 15:00")

    def test_tightened_remaining_budget_rejects_over_budget(self):
        """T036b: replan validates against actual remaining, not total.

        POI fee 600k > 500k left: with the lane-C snapshot the canonical
        BCS gate refuses (no_solution); without it the legacy total budget
        (3M) still admits the same POI (mode plan). Proves the new input,
        not the old total, triggers refusal, and inputs are not mutated.
        """
        poi = {"poi_id": "expensive", "verified": True, "visit_min": 60,
               "fee": 600000, "intensity": 1, "weather_sensitive": False,
               "opening_hours": ["07:00-22:00"]}
        travel = {("depot", "expensive"): 10}
        trip = {"trip_id": "tight-budget", "budget": 3000000, "avoid": [],
                "start_time": "07:00", "end_time": "18:00"}
        budget_state = {"trip_id": "tight-budget", "budget": 3000000,
                        "spent": 2500000, "left": 500000,
                        "by_kind": {"food": 2500000, "ticket": 0,
                                    "transport": 0, "other": 0},
                        "alert": "80%"}

        def state(tid):
            return store.new_state(tid, [{"poi_id": "expensive",
                                          "start": "07:00", "end": "08:00"}],
                                   "07:00", "depot")

        out = replan(state("tight-budget"), {"type": "delay"}, [poi], travel,
                     trip, budget_state=budget_state)
        self.assertEqual(out["mode"], "no_solution")
        self.assertIn("BCS", out["reason"])
        self.assertEqual(trip["budget"], 3000000)
        self.assertEqual(budget_state["left"], 500000)

        legacy = replan(state("legacy-budget"), {"type": "delay"}, [poi],
                        travel, dict(trip, trip_id="legacy-budget"))
        self.assertEqual(legacy["mode"], "plan")

    @unittest.skipUnless(os.path.exists(MATRIX_JSON)
                         and os.path.exists(POIS_JSON),
                         "real matrix/pois snapshot absent")
    def test_real_matrix_replan_twice_no_duplicates(self):
        """T046/B1/B3 on the real danang-v1 matrix: two replans, v1->2->3.

        Candidates are the snapshot POIs that are `verified` (only these pass
        the canonical FAR gate; unverified candidates force no_solution). With
        just 5 verified POIs the full set is used (~6-8 slice not reachable);
        size chosen so the remaining pool is deterministically feasible.
        """
        svc = MatrixService(SNAPSHOT_DIR)
        with open(POIS_JSON, encoding="utf-8") as fh:
            raw = json.load(fh)["pois"]
        by = {p["poi_id"]: p for p in raw}

        def mk(pid):
            p, vm = by[pid], (by[pid].get("visit_min") or {})
            return {"poi_id": pid, "verified": True,
                    "visit_min": int(vm.get("p50") or 60),
                    "fee": int(p.get("fee") or 0),
                    "intensity": p.get("intensity", 2),
                    "weather_sensitive": bool(p.get("weather_sensitive")),
                    "rating": p.get("rating", 0),
                    "opening_hours": p.get("opening_hours") or []}

        cand = [i for i in svc.ids if i in by and by[i].get("verified")]
        self.assertGreaterEqual(len(cand), 4)
        pois = [mk(i) for i in cand]
        travel = travel_from_matrix(svc, [DEPOT] + cand)
        trip = {"trip_id": "real", "budget": 5000000, "avoid": [],
                "start_time": "07:00", "end_time": "18:00"}
        state_acts = [{"poi_id": cand[0], "start": "07:30", "end": "09:30"},
                      {"poi_id": cand[1], "start": "10:00", "end": "12:00"}] + \
                     [{"poi_id": i, "start": "13:00", "end": "14:00"}
                      for i in cand[2:]]
        s = store.new_state("real", state_acts, "07:00", "hotel")
        s = store.complete(store.complete(s, cand[0], "09:30"),
                           cand[1], "12:00")
        self.assertEqual(s["now"], "12:00")
        event = {"type": "rain", "at": "12:00"}

        first = replan(s, event, pois, travel, trip)
        self.assertEqual(first["mode"], "plan")
        second = replan(store.load("real"), event, pois, travel, trip)
        self.assertEqual(second["mode"], "plan")

        s3 = store.load("real")
        self.assertEqual((s["version"], first["version"], second["version"]),
                         (1, 2, 3))
        self.assertEqual([a["poi_id"] for a in s3["completed"]],
                         [cand[0], cand[1]])
        remaining = [a["poi_id"] for a in s3["remaining"]]
        self.assertEqual(len(remaining), len(set(remaining)))  # B1: no dupes
        acts = first["itinerary"]["activities"]
        self.assertTrue(set(a["poi_id"] for a in acts) <= set(cand))
        ordered = sorted(acts, key=lambda a: to_min(a["start"]))
        for x, y in zip(ordered, ordered[1:]):  # B3: gap >= real minutes
            need = svc.minutes(x["poi_id"], y["poi_id"])[0]
            self.assertGreaterEqual(to_min(y["start"]) - to_min(x["end"]), need)
        print(f"\n real: v{s['version']}->{first['version']}->{second['version']}"
              f" remaining {len(remaining)} unique, acts "
              f"{[(a['poi_id'][:8], a['start'], a['end']) for a in ordered]}")


if __name__ == "__main__":
    unittest.main()
