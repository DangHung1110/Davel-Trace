"""Approach-B gold generator (T051-BUILDER, lane A). filter -> TSP -> chain.

- FILTER: `retrieval.retrieve`, the planner's own filter, so the gold and the
  app choose from the same candidates. A must_visit it does not keep marks the
  query infeasible (no gold).
- ORDER: must_visit first, in every order until one fits; then an OR-Tools TSP
  tour on matrix minutes using PATH_CHEAPEST_ARC over the candidates nearest the
  last must_visit (or, with none, nearest dragon-bridge or a candidate picked
  from the query id). The return leg is not emitted (open activity path).
  This is a heuristic: it is NOT guaranteed to be shorter/optimal than
  any ad-hoc order — it is only the distance-only baseline future
  hybrids try to beat on preference (SC-009).
- CHAIN: matrix minutes + p50 durations from start_time, walking the order; an
  optional candidate whose hours/window/price never fit, or that would break a
  day rule of the gate (one per category, no two of a kind in a row), is skipped
  in tour order (it is not a rating-tail drop). A must_visit that cannot be
  placed makes the query infeasible.
- FAIL CLOSED: an empty candidate list, or any required ordered
  candidate-to-candidate matrix cell that is missing (never treated as a
  0-minute edge), yields infeasible instead of a bogus gold.

Evidence: every activity carries ["gold:approach-b"], which is synthetic
generator provenance ("this gold was produced by this generator"), NOT
independent EDI evidence. Gold validity = passes the T049 gate (checked
by build.py + unit test).
"""

from __future__ import annotations

import itertools
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services import retrieval  # noqa: E402
from BE.app.services.gate import (  # noqa: E402
    check_a1, check_cafe_cap, check_category_cap, check_no_adjacent_food, check_no_consecutive)
from BE.common import (  # noqa: E402
    effective_fee, hhmm as _hh, party_size, poi_open_windows, to_min as _to_min)

DEFAULT_ORIGIN = "dragon-bridge"
# A day holds 6-8 stops, and the day rules below skip some of the nearest stops.
GOLD_POOL = 40
# Gate rules a stop can break the moment it joins the plan.
STEP_CHECKS = (check_a1, check_cafe_cap, check_category_cap, check_no_consecutive,
               check_no_adjacent_food)


def _edge_minutes(matrix: dict, a: str, b: str) -> int | None:
    """Matrix travel minutes for a->b, or None when the cell is missing."""
    cell = matrix.get(f"{a}->{b}")
    if not cell:
        return None
    m = cell.get("minutes")
    return None if m is None else int(m)


def filter_pois(trip: dict, pois: dict) -> tuple[list[str], str]:
    """Return (candidate ids, infeasible_reason or '')."""
    cands = [c["poi_id"] for c in retrieval.retrieve(trip, list(pois.values()))["candidates"]]
    for m in trip.get("must_visit", []):
        if m not in cands:
            return [], f"must_visit {m} unvisitable"
    return cands, ""


def tsp_order(ids: list[str], matrix: dict, origin: str) -> list[str]:
    """OR-Tools TSP tour rotated to start at origin (open path)."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    idx = {pid: i for i, pid in enumerate(ids)}
    cost = [[int((matrix.get(f"{a}->{b}", {}) or {}).get("minutes", 10 ** 6))
             for b in ids] for a in ids]
    mgr = pywrapcp.RoutingIndexManager(len(ids), 1, idx[origin])
    routing = pywrapcp.RoutingModel(mgr)
    routing.SetArcCostEvaluatorOfAllVehicles(
        routing.RegisterTransitCallback(lambda f, t: cost[mgr.IndexToNode(f)][mgr.IndexToNode(t)]))
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.time_limit.FromSeconds(5)
    sol = routing.SolveWithParameters(search)
    if sol is None:
        return list(ids)  # degenerate fallback (still validated by gate)
    tour, node = [], routing.Start(0)
    while not routing.IsEnd(node):
        tour.append(ids[mgr.IndexToNode(node)])
        node = sol.Value(routing.NextVar(node))
    return tour


def nearest_pool(cands: list[str], must: list[str], origin: str, matrix: dict,
                 k: int = GOLD_POOL) -> list[str]:
    """Origin + must_visit + the `k` candidates nearest the origin. A missing cell
    sorts last and stays in, so the fail-closed check below still sees it."""
    fixed = [origin, *[m for m in must if m != origin and m in cands]]

    def minutes(pid: str) -> int:
        leg = _edge_minutes(matrix, origin, pid)
        return 10 ** 6 if leg is None else leg

    rest = sorted((c for c in cands if c not in fixed), key=lambda c: (minutes(c), c))
    return fixed + rest[:k]


def _place(arrival: int, dur: int, poi: dict, ws: int, we: int) -> int | None:
    """Earliest feasible start >= arrival inside the planner's opening windows
    (no hours: the group's safe window) and the trip window. No group has none."""
    windows = poi_open_windows(poi)
    best = None
    for o, c in ((0, 24 * 60),) if windows is None else windows:
        s = max(arrival, ws, o)
        if s + dur <= min(c, we):
            best = s if best is None else min(best, s)
    return best


def chain_order(order: list[str], trip: dict, pois: dict, matrix: dict,
                evidence: str = "gold:approach-b") -> tuple[list[dict] | None, str]:
    """Hours-aware placement of `order` -> (activities, "") or (None, reason).

    Shared by the Approach-B gold generator (T051) and the T053 LLM-only
    baseline: both hand an ORDER to the same chaining/placement seam, so a
    baseline planner is compared on its ORDERING, not on a different
    scheduler. An optional POI whose hours/window never fit is skipped in
    order; a must_visit that cannot be placed makes the query infeasible.
    A missing matrix cell fails closed (never a 0-minute edge).
    """
    ws, we = _to_min(trip["start_time"]), _to_min(trip["end_time"])
    must = set(trip.get("must_visit", []))
    budget, party, spent = int(trip.get("budget", 0)), party_size(trip), 0
    acts, cur, prev = [], ws, None
    for pid in order:
        gap = 0 if prev is None else _edge_minutes(matrix, prev, pid)
        if gap is None:
            return None, f"missing matrix pair {prev}->{pid}"
        arrival = cur + gap
        dur = int(pois[pid]["visit_min"]["p50"])
        start = _place(arrival, dur, pois[pid], ws, we)
        if start is None:
            if pid in must:
                return None, f"must_visit {pid} exceeds hours/window"
            continue
        fee = (effective_fee(pois[pid]) or 0) * party
        if spent + fee > budget:
            if pid in must:
                return None, f"must_visit {pid} exceeds budget"
            continue
        stop = {"poi_id": pid, "start": _hh(start), "end": _hh(start + dur),
                "explanation": {"evidence": [evidence]}}
        plan = {"activities": [*acts, stop]}
        if not all(check(plan, trip, pois, matrix)["passed"] for check in STEP_CHECKS):
            if pid in must:
                return None, f"must_visit {pid} breaks a day rule"
            continue
        acts.append(stop)
        prev, cur, spent = pid, start + dur, spent + fee
    if not acts:
        return None, "empty"
    if any(m not in [a["poi_id"] for a in acts] for m in must):
        return None, "must_visit dropped"
    return acts, ""


def make_gold(query: dict, pois: dict, matrix: dict) -> dict:
    """Return {"query_id", "itinerary" | None, "infeasible": reason or ''}."""
    trip = query["trip"]
    cands, bad = filter_pois(trip, pois)
    if bad:
        return {"query_id": query["query_id"], "itinerary": None, "infeasible": bad}
    if not cands:
        return {"query_id": query["query_id"], "itinerary": None,
                "infeasible": "no candidates"}
    must = trip.get("must_visit", [])
    spread = sum(map(ord, str(query["query_id"]))) % len(cands)
    start = DEFAULT_ORIGIN if DEFAULT_ORIGIN in cands else cands[spread]
    bad = ""
    # Approach-B is preference-blind by design (baseline); order_prefs are scored by SSR.
    for first in itertools.permutations(m for m in must if m in cands):
        origin = first[-1] if first else start
        tour = nearest_pool(cands, list(first), origin, matrix)
        # FAIL CLOSED: every ordered cell of the tour must exist, so a missing OSRM
        # pair can never be silently treated as a 0-minute edge.
        for a in tour:
            for b in tour:
                if _edge_minutes(matrix, a, b) is None:
                    return {"query_id": query["query_id"], "itinerary": None,
                            "infeasible": f"missing matrix pair {a}->{b}"}
        walk = tsp_order([p for p in tour if p not in first[:-1]], matrix, origin)
        acts, bad = chain_order([*first[:-1], *walk], trip, pois, matrix)
        if acts is not None:
            return {"query_id": query["query_id"],
                    "itinerary": {"activities": acts}, "infeasible": ""}
    return {"query_id": query["query_id"], "itinerary": None, "infeasible": bad}
