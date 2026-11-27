"""What reaching a stop costs besides its own price (`access_fees`, specs/025).

A summit stop of Bà Nà is priced `included`: the Sun World ticket pays for it and for
the cable car. Cù Lao Chàm needs the Cửa Đại cano. A plan pays each stop's own price,
a parent's ticket once for the trip unless the parent is itself a stop, and a
transfer fare once each day it is used. The solver (max_fee), the gate (BCS) and the
plan's total_cost must charge the same money.

Run from the repo root: python -m pytest BE/tests/unit/test_access_fees.py -q
"""

from __future__ import annotations

import itertools
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from BE.app.services import multiday, response, retrieval, transfers  # noqa: E402
from BE.app.services import state as store  # noqa: E402
from BE.app.services.gate import check_bcs  # noqa: E402
from BE.app.services.optimizer import (  # noqa: E402
    StubPOI, StubTrip, _greedy_hint, optimize, poi_to_stub, stubs_fee)
from BE.app.services.profiles import _gate_view  # noqa: E402
from BE.app.services.rank import score_poi  # noqa: E402
from BE.app.services.replan import replan  # noqa: E402
from BE.common import (  # noqa: E402
    PAID_ACCESS, fee_breakdown, paid_after, plan_cost, total_fee, view_pois, visit_fee)

SUN, BRIDGE, PARK, NOODLE = "sun", "bridge", "park", "noodle"
ISLAND, TOWN, HALL, CAFE = "island", "town", "hall", "cafe"


def rec(pid, name, tier, category="paid_attraction", role="attraction", requires=None,
        by="agent_web", osm=None, open_=("08:00-18:00",)):
    """A danang-v2 (v2.1) record, as pois.json stores it."""
    return {
        "poi_id": pid, "name": name, "category": category, "role": role, "status": "active",
        "zone": "ba_na_tay", "cluster_id": None, "alt_group": None, "requires_ticket_of": requires,
        "hours": {"open": list(open_), "kind": "fixed", "closed_days": [], "access_window": None,
                  "archetype": "co_ve"},
        "price": {"tier": tier, "note": None},
        "dwell": {"p25": 30, "p50": 60, "p75": 90},
        "tags": {"effort": 1, "weather_sensitive": False},
        "popularity": {"prize_prior": 0.8},
        "ext_ids": {"osm": osm},
        "provenance": {"price": {"source": "web", "verified_by": by}},
        "data_version": "v2.1",
    }


RECORDS = [
    rec(SUN, "Sun World Bà Nà Hills", "expensive"),
    rec(BRIDGE, "Cầu Vàng", "included", category="viewpoint", requires=SUN, by="inferred"),
    rec(PARK, "Fantasy Park", "included", requires=SUN, by="inferred"),
    rec(NOODLE, "Kungfu Noodle", "medium", category="restaurant", role="meal", requires=SUN),
    rec(ISLAND, "Cù Lao Chàm", "cheap"),
    rec(TOWN, "Phố cổ Hội An", "medium", osm="node/42"),
    rec(HALL, "Hội quán Phúc Kiến", "included", category="religious", requires="osm:node/42",
        by="inferred"),
    rec(CAFE, "Cafe", "cheap", category="cafe", role="meal"),
]
TRANSFERS = {
    "format": transfers.FORMAT,
    "gateways": [
        {"id": "cable", "name": "Cáp treo", "mode": "cable_car",
         "places": [{"poi_id": BRIDGE}, {"poi_id": PARK}, {"poi_id": NOODLE}],
         "fare": {"ticket_of": SUN}},
        {"id": "boat", "name": "Cano Cửa Đại - Cù Lao Chàm", "mode": "boat",
         "places": [{"poi_id": ISLAND}],
         "fare": {"vnd": 260000, "per": "visit", "verified_by": "agent_web"}},
        {"id": "trail", "name": "Đường mòn", "mode": "walk", "places": [{"poi_id": CAFE}]},
    ],
}


def views(records=RECORDS, spec=TRANSFERS) -> dict:
    """{poi_id: view} as the app loads them, with `transfers.json` next to pois.json."""
    with tempfile.TemporaryDirectory() as snap:
        with open(os.path.join(snap, transfers.TRANSFERS_FILE), "w", encoding="utf-8") as f:
            json.dump(spec, f)
        return {p["poi_id"]: p for p in view_pois([dict(r) for r in records], snap)}


POIS = views()


def acts(*ids, day=None):
    return [{"poi_id": pid, **({"day": day} if day else {})} for pid in ids]


class TestAttach(unittest.TestCase):
    def test_a_summit_stop_carries_the_sun_world_ticket(self):
        self.assertEqual(POIS[BRIDGE]["access_fees"], [
            {"key": SUN, "vnd": 850000, "name": "Sun World Bà Nà Hills", "kind": "ticket",
             "per": "trip", "estimate": False}])
        # a meal up there pays its own price and the ticket
        self.assertEqual([c["key"] for c in POIS[NOODLE]["access_fees"]], [SUN])

    def test_the_parent_and_a_plain_stop_carry_nothing(self):
        self.assertNotIn("access_fees", POIS[SUN])
        self.assertNotIn("access_fees", POIS[TOWN])

    def test_an_osm_ref_finds_its_parent(self):
        self.assertEqual([(c["key"], c["vnd"]) for c in POIS[HALL]["access_fees"]], [(TOWN, 250000)])

    def test_the_island_pays_the_cano_each_visit(self):
        self.assertEqual(POIS[ISLAND]["access_fees"], [
            {"key": "fare:boat", "vnd": 260000, "name": "Cano Cửa Đại - Cù Lao Chàm",
             "kind": "transfer", "per": "visit", "estimate": False}])

    def test_a_cable_car_inside_a_ticket_and_a_walk_add_no_fare(self):
        self.assertEqual(len(POIS[BRIDGE]["access_fees"]), 1)
        self.assertNotIn("access_fees", POIS[CAFE])

    def test_an_unsourced_fare_is_an_estimate(self):
        spec = json.loads(json.dumps(TRANSFERS))
        spec["gateways"][1]["fare"]["verified_by"] = "inferred"
        self.assertTrue(views(spec=spec)[ISLAND]["access_fees"][0]["estimate"])

    def test_a_free_parent_or_a_bad_fare_charges_nothing(self):
        records = [rec(SUN, "Sun World", "free")] + RECORDS[1:]
        spec = json.loads(json.dumps(TRANSFERS))
        spec["gateways"][1]["fare"] = {"vnd": "a lot"}
        out = views(records, spec)
        self.assertNotIn("access_fees", out[BRIDGE])
        self.assertNotIn("access_fees", out[ISLAND])
        self.assertEqual(transfers.fares({"gateways": [None, {"id": "x", "fare": {"vnd": -5}}]}), {})

    def test_no_transfers_file_still_charges_tickets(self):
        out = {p["poi_id"]: p for p in view_pois([dict(r) for r in RECORDS])}
        self.assertEqual([c["key"] for c in out[BRIDGE]["access_fees"]], [SUN])
        self.assertNotIn("access_fees", out[ISLAND])


class TestFeeBreakdown(unittest.TestCase):
    def test_two_summit_stops_buy_one_ticket(self):
        cost, charges = fee_breakdown(acts(BRIDGE, PARK), POIS)
        self.assertEqual(cost, 850000)
        self.assertEqual([(c["key"], c["for"]) for c in charges], [(SUN, [BRIDGE, PARK])])

    def test_the_sun_world_stop_is_the_ticket(self):
        self.assertEqual(fee_breakdown(acts(SUN, BRIDGE, PARK), POIS), (850000, []))

    def test_a_summit_meal_pays_its_meal_and_the_ticket(self):
        self.assertEqual(fee_breakdown(acts(NOODLE), POIS)[0], 250000 + 850000)

    def test_a_ticket_is_once_a_trip_the_cano_once_a_day(self):
        trip = acts(BRIDGE, ISLAND, day=1) + acts(PARK, ISLAND, day=2)
        cost, charges = fee_breakdown(trip, POIS)
        self.assertEqual(cost, 2 * 50000 + 850000 + 2 * 260000)
        self.assertEqual(sorted((c["key"], c.get("day")) for c in charges),
                         [("fare:boat", 1), ("fare:boat", 2), (SUN, None)])

    def test_what_is_paid_costs_nothing(self):
        self.assertEqual(fee_breakdown(acts(BRIDGE, PARK), POIS, paid={SUN}), (0, []))

    def test_the_party_pays_per_person(self):
        self.assertEqual(total_fee(acts(BRIDGE, PARK), POIS, 4), 3400000)
        self.assertEqual(plan_cost({"activities": acts(BRIDGE, PARK)}, POIS, 4, paid={SUN}), 0)
        self.assertEqual(plan_cost({"activities": acts(BRIDGE), "total_cost": 7}, POIS, 4), 7)

    def test_visit_fee_is_a_stop_on_its_own(self):
        self.assertEqual(visit_fee(POIS[BRIDGE]), 850000)
        self.assertEqual(visit_fee(POIS[BRIDGE], {SUN}), 0)
        self.assertEqual(visit_fee(POIS[ISLAND]), 50000 + 260000)
        self.assertIsNone(visit_fee({"cat": "restaurant", "fee": 0, "smart_tags": {}}))

    def test_what_a_stop_buys_for_later(self):
        self.assertEqual(paid_after(acts(BRIDGE), POIS), {SUN, BRIDGE})
        self.assertEqual(paid_after(acts(ISLAND), POIS), {ISLAND})
        self.assertEqual(paid_after(acts(ISLAND), POIS, same_day=True), {ISLAND, "fare:boat"})


class TestOneFormula(unittest.TestCase):
    """Solver, gate and total_cost price one plan alike."""

    family = {"travelers": 4, "budget": 3400000}

    def test_the_gate_view_keeps_the_charges(self):
        gate = {pid: _gate_view(p) for pid, p in POIS.items()}
        self.assertEqual(gate[BRIDGE]["access_fees"], POIS[BRIDGE]["access_fees"])
        self.assertEqual(plan_cost({"activities": acts(BRIDGE, PARK)}, gate, 4), 3400000)

    def test_bcs_charges_the_ticket(self):
        gate = {pid: _gate_view(p) for pid, p in POIS.items()}
        plan = {"activities": acts(BRIDGE, PARK)}
        self.assertTrue(check_bcs(plan, self.family, gate, {})["passed"])
        self.assertFalse(check_bcs(plan, {**self.family, "budget": 3000000}, gate, {})["passed"])
        paid = {**self.family, "budget": 0, PAID_ACCESS: [SUN]}
        self.assertTrue(check_bcs(plan, paid, gate, {})["passed"])

    def test_plan_totals_says_what_the_ticket_costs(self):
        stops = [{**a, "start": "09:00", "end": "10:00"} for a in acts(BRIDGE, PARK)]
        totals = response.plan_totals(stops, self.family, POIS, {})
        self.assertEqual(totals["total_cost"], 3400000)
        self.assertEqual(totals["access_fees"], [
            {"key": SUN, "kind": "ticket", "per": "trip", "name": "Sun World Bà Nà Hills",
             "vnd_per_person": 850000, "travelers": 4, "vnd": 3400000, "for": [BRIDGE, PARK],
             "estimate": False}])
        self.assertFalse(totals["cost_estimated"])
        plain = response.plan_totals([{**stops[0], "poi_id": SUN}], self.family, POIS, {})
        self.assertNotIn("access_fees", plain)

    def test_a_guessed_ticket_makes_the_cost_an_estimate(self):
        records = [rec(SUN, "Sun World", "expensive", by="inferred")] + RECORDS[1:]
        pois = views(records)
        stops = [{"poi_id": BRIDGE, "start": "09:00", "end": "10:00"}]
        self.assertTrue(response.plan_totals(stops, {}, pois, {})["cost_estimated"])

    def test_stubs_carry_what_the_trip_has_not_paid(self):
        self.assertEqual(poi_to_stub(POIS[BRIDGE]).access, ((SUN, 850000),))
        self.assertEqual(poi_to_stub(POIS[BRIDGE], {PAID_ACCESS: [SUN]}).access, ())
        self.assertEqual(poi_to_stub(POIS[SUN]).access, ())

    def test_the_solver_sum_is_the_plan_sum(self):
        stubs = {pid: poi_to_stub(p) for pid, p in POIS.items()}
        for size in range(1, 4):
            for ids in itertools.combinations(sorted(POIS), size):
                self.assertEqual(stubs_fee([stubs[pid] for pid in ids]),
                                 fee_breakdown(acts(*ids), POIS)[0], ids)


def stub(pid, score, fee=0, access=(), visit=60):
    return StubPOI(pid, visit, 8 * 60, 20 * 60, score, fee=fee, access=tuple(access))


class TestSolverBudget(unittest.TestCase):
    ticket = ((SUN, 850000),)

    def solve(self, stubs, max_fee, must=None):
        ids = [s.poi_id for s in stubs]
        travel = {(a, b): 10 for a in ids for b in ids if a != b}
        out = optimize(stubs, travel, StubTrip(8 * 60, 20 * 60, None), workers=1,
                       max_fee=max_fee, must_visit=must)
        itinerary = out.get("itinerary")
        return None if itinerary is None else {a["poi_id"] for a in itinerary["activities"]}

    def test_a_summit_stop_alone_needs_the_ticket(self):
        stubs = [stub(BRIDGE, 5.0, access=self.ticket), stub(CAFE, 1.0, fee=50000)]
        self.assertEqual(self.solve(stubs, 849999), {CAFE})
        self.assertEqual(self.solve(stubs, 900000), {BRIDGE, CAFE})

    def test_two_summit_stops_share_the_ticket(self):
        stubs = [stub(BRIDGE, 5.0, access=self.ticket), stub(PARK, 5.0, access=self.ticket),
                 stub(CAFE, 1.0, fee=50000)]
        self.assertEqual(self.solve(stubs, 850000), {BRIDGE, PARK})

    def test_the_sun_world_stop_covers_its_summit(self):
        stubs = [stub(SUN, 1.0, fee=850000), stub(BRIDGE, 5.0, access=self.ticket),
                 stub(PARK, 5.0, access=self.ticket)]
        self.assertEqual(self.solve(stubs, 850000, must=[SUN]), {SUN, BRIDGE, PARK})

    def test_a_named_summit_stop_over_budget_has_no_plan(self):
        stubs = [stub(BRIDGE, 5.0, access=self.ticket), stub(CAFE, 1.0, fee=50000)]
        self.assertIsNone(self.solve(stubs, 500000, must=[BRIDGE]))

    def test_the_island_pays_its_cano(self):
        stubs = [stub(ISLAND, 5.0, fee=50000, access=(("fare:boat", 260000),)), stub(CAFE, 1.0, fee=50000)]
        self.assertEqual(self.solve(stubs, 309999), {CAFE})
        self.assertEqual(self.solve(stubs, 360000), {ISLAND, CAFE})

    def test_the_seed_keeps_the_ticket_money_for_a_named_stop(self):
        # A dear dinner worth more per minute must not take the money the named
        # summit stop needs for its ticket.
        stubs = [stub("dinner", 9.0, fee=800000, visit=30), stub(BRIDGE, 1.0, access=self.ticket)]
        travel = {(a, b): 10 for a in ("dinner", BRIDGE) for b in ("dinner", BRIDGE) if a != b}
        hint = _greedy_hint(stubs, travel, StubTrip(8 * 60, 20 * 60, None), {BRIDGE}, max_fee=900000)
        seated = [stubs[i - 1] for i, _start in hint]
        self.assertEqual([s.poi_id for s in seated], [BRIDGE])
        self.assertLessEqual(stubs_fee(seated), 900000)


class TestDays(unittest.TestCase):
    def day_plan(self, ids, cost, fees=()):
        return {"activities": [{"poi_id": pid, "start": "09:00", "end": "10:00"} for pid in ids],
                "total_cost": cost, "passed": True, "access_fees": list(fees),
                "activity_match": [], "segments": [], "constraint_status": {}}

    def test_a_ticket_bought_on_day_one_is_not_bought_again(self):
        seen = []
        ticket = {"key": SUN, "per": "trip", "vnd": 850000}
        cano = {"key": "fare:boat", "per": "visit", "vnd": 260000}

        def solve(day_trip, used, diagnose):
            seen.append(set(day_trip.get(PAID_ACCESS) or ()))
            return (self.day_plan([BRIDGE, ISLAND], 1160000, [ticket, cano]) if len(seen) == 1
                    else self.day_plan([PARK], 0))

        multiday._solve_days(solve, {"days": 2, "budget": 3000000}, 2, False)
        self.assertEqual(seen, [set(), {SUN, BRIDGE, ISLAND}])

    def test_the_trip_lists_every_days_charges(self):
        plans = [self.day_plan([BRIDGE], 850000, [{"key": SUN, "per": "trip", "vnd": 850000}]),
                 self.day_plan([ISLAND], 310000, [{"key": "fare:boat", "per": "visit", "vnd": 260000}])]
        merged = multiday.merge_days(plans, {"days": 2}, 2,
                                     lambda it, trip: {"passed": True, "failed": [], "soft_failed": [],
                                                       "checks": {}})
        self.assertEqual([(f["key"], f["day"]) for f in merged["access_fees"]],
                         [(SUN, 1), ("fare:boat", 2)])
        self.assertEqual(merged["total_cost"], 1160000)

    def test_a_replanned_day_knows_the_other_days_tickets(self):
        others = acts(BRIDGE, day=1)
        scope = multiday.day_scope({"budget": 2000000, "travelers": 2}, others, acts(PARK, day=2), POIS)
        self.assertEqual(scope["budget"], 2000000 - 2 * 850000)
        self.assertIn(SUN, scope[PAID_ACCESS])


class TestReplanAndFilters(unittest.TestCase):
    def test_a_summit_stop_done_bought_the_ticket_for_the_next_one(self):
        pois = list(POIS.values())
        ids = [p["poi_id"] for p in pois]
        travel = {(a, b): 10 for a in ["depot"] + ids for b in ids if a != b}
        state = store.new_state("t1", [{"poi_id": BRIDGE, "start": "09:00", "end": "10:00"},
                                       {"poi_id": PARK, "start": "10:30", "end": "11:30"}],
                                "08:00", "depot")
        state = store.complete(state, BRIDGE, "10:00")
        trip = {"trip_id": "t1", "budget": 900000, "avoid": [], "start_time": "08:00",
                "end_time": "18:00"}
        out = replan(state, {"type": "delay"}, pois, travel, trip)
        self.assertEqual(out["mode"], "plan", out.get("reason"))
        self.assertIn(PARK, [a["poi_id"] for a in out["itinerary"]["activities"]])

    def test_retrieval_drops_a_summit_stop_the_budget_cannot_reach(self):
        trip = {"budget": 500000, "travelers": 1, "start_time": "08:00", "end_time": "18:00"}
        out = retrieval.retrieve(trip, [POIS[BRIDGE], POIS[CAFE]], {})
        self.assertEqual([c["poi_id"] for c in out["candidates"]], [CAFE])
        self.assertIn({"poi_id": BRIDGE, "reason": "vuot ngan sach"}, out["excluded"])

    def test_a_summit_stop_is_not_called_free(self):
        self.assertNotIn("mien phi", score_poi(POIS[BRIDGE])["reasons"])


if __name__ == "__main__":
    unittest.main()
