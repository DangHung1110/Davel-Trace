"""The greedy seed under objective v1 (`optimizer._greedy_hint(objective=...)`).

The seed is the single-worker search's first incumbent; on the days the search cannot
prove optimal it decides how good the plan gets inside the budget. Written for the
legacy objective, the walk valued a stop by its score per minute plus a first-of-
category bonus and never charged a drive: on savings days (0.045U a riding minute) its
seed was below zero in 61 of 74 audit solves, and on one of them the search found
nothing better within 8 units (E02-wheelchair, 25/11). Under v1 it charges a stop
what the objective charges it there (T3, T4, T5 once a table is ready, A2, T8, T9).
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from BE.app.services import objective  # noqa: E402
from BE.app.services.optimizer import StubPOI, StubTrip, _greedy_hint  # noqa: E402

H = 60


def _spec(**w):
    return objective.Spec(w={**objective.weights("v1"), **w}, k0=8, pace=2, food_tour=False,
                          strict=frozenset(), breakfast=False)


def _poi(pid, group, open_h, close_h, visit=60, score=1.0, restaurant=False, zone="city"):
    return StubPOI(pid, visit_min=visit, open_min=open_h * H, close_min=close_h * H, score=score,
                   restaurant=restaurant, category="restaurant" if restaurant else group,
                   group="" if restaurant else group, zone=zone)


def _seed(pois, travel, trip, **kw):
    return [pois[i - 1].poi_id for i, _start in _greedy_hint(pois, travel, trip, set(), **kw)]


class TestSeedV1(unittest.TestCase):
    def test_distant_dinner_pays_for_the_lunch_pair(self):
        pois = [_poi("lunch", "", 11, 12, visit=30, restaurant=True),
                _poi("dinner", "", 18, 19, visit=30, restaurant=True)]
        travel = {("lunch", "dinner"): 5, ("dinner", "lunch"): 5}
        seeded = _seed(pois, travel, StubTrip(11 * H, 20 * H, None),
                       objective=_spec(meal_crowd=10, meal_scale=0))
        self.assertEqual(seeded, ["lunch"])

    def test_a_drive_worth_more_than_the_stop_is_not_seeded(self):
        """At the savings rate a 60-minute leg costs 2.7U: more than a stop worth 1U."""
        pois = [_poi("a", "history", 7, 20), _poi("b", "nature", 7, 20),
                _poi("c", "religious", 7, 20), _poi("far", "beach", 7, 20, zone="far")]
        travel = {(x.poi_id, y.poi_id): (60 if "far" in (x.poi_id, y.poi_id) else 5)
                  for x in pois for y in pois if x is not y}
        trip = StubTrip(8 * H, 20 * H, None)
        self.assertIn("far", _seed(pois, travel, trip))   # legacy: time is the only cost
        seeded = _seed(pois, travel, trip, objective=_spec(tau=0.045))
        self.assertNotIn("far", seeded)
        self.assertEqual(set(seeded), {"a", "b", "c"})

    def test_no_hours_of_waiting_for_a_meal_bonus(self):
        """A dawn stop far from town, then lunch: the sights of the morning come first.
        Counted after a long wait, the lunch bonus made the walk sit at 11:00 and leave
        the morning empty (W23-sunrise, M05-ba-na: seeds 22-43% below the legacy walk)."""
        pois = [_poi("dawn", "viewpoint", 5, 6, visit=30),
                _poi("museum", "history", 7, 17), _poi("temple", "religious", 7, 17),
                _poi("noodles", "", 11, 14, restaurant=True)]
        travel = {(x.poi_id, y.poi_id): (50 if "dawn" in (x.poi_id, y.poi_id) else 5)
                  for x in pois for y in pois if x is not y}
        seeded = _seed(pois, travel, StubTrip(5 * H, 20 * H, None), lunch_required=True,
                       objective=_spec())
        self.assertEqual(seeded[0], "dawn")
        self.assertLess(seeded.index("museum"), seeded.index("noodles"))
        self.assertLess(seeded.index("temple"), seeded.index("noodles"))


if __name__ == "__main__":
    unittest.main()
