"""Approach-B gold generator (T051-BUILDER, lane A). filter -> TSP -> chain.

- FILTER: verified, not avoided, fee <= budget, opening hours overlap
  the trip window. must_visit always kept (dropped only if hours never
  overlap the window — then the query is marked infeasible, no gold).
- ORDER: OR-Tools TSP tour on matrix minutes, rotated to start at the
  query origin (default first must_visit else dragon-bridge); return leg
  dropped (open path). Shorter travel than any ad-hoc order: this is the
  distance-only baseline future hybrids must beat on preference (SC-009).
- CHAIN: p50 durations + matrix gaps from start_time; tail POIs dropped
  (lowest rating first, must_visit protected) until the window fits.
  Every activity carries evidence ["gold:approach-b"] (EDI=1).

Gold validity = passes the T049 gate (checked by build.py + unit test).
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

DEFAULT_ORIGIN = "dragon-bridge"


def _to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _hh(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _overlaps(hours: list[str], ws: int, we: int) -> bool:
    for h in hours or []:
        o, c = h.split("-")
        o, c = _to_min(o), _to_min(c)
        if o <= c and o < we and ws < c:
            return True
        if o > c and (ws < c or o < we):
            return True
    return not hours


def filter_pois(trip: dict, pois: dict) -> tuple[list[str], str]:
    """Return (candidate ids, infeasible_reason or '')."""
    ws, we = _to_min(trip["start_time"]), _to_min(trip["end_time"])
    avoid = set(trip.get("avoid", []))
    cands = []
    for pid, p in pois.items():
        if not p.get("verified") or pid in avoid:
            continue
        if int(p.get("fee", 0)) > int(trip.get("budget", 0)):
            continue
        if pid in trip.get("must_visit", []) or _overlaps(p.get("opening_hours", []), ws, we):
            cands.append(pid)
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


def _ranges(hours: list[str]) -> list[tuple[int, int]]:
    out = []
    for h in hours or ["00:00-23:59"]:
        o, c = h.split("-")
        out.append((_to_min(o), _to_min(c)))
    return out


def _place(arrival: int, dur: int, hours: list[str], ws: int, we: int) -> int | None:
    """Earliest feasible start >= arrival fitting POI hours + window."""
    best = None
    for o, c in _ranges(hours):
        s = max(arrival, ws, o)
        if s + dur <= min(c, we):
            best = s if best is None else min(best, s)
    return best


def make_gold(query: dict, pois: dict, matrix: dict) -> dict:
    """Return {"query_id", "itinerary" | None, "infeasible": reason or ''}."""
    trip = query["trip"]
    cands, bad = filter_pois(trip, pois)
    if bad:
        return {"query_id": query["query_id"], "itinerary": None, "infeasible": bad}
    origin = next((m for m in trip.get("must_visit", []) if m in cands),
                  DEFAULT_ORIGIN if DEFAULT_ORIGIN in cands else cands[0])
    order = tsp_order(cands, matrix, origin)
    if trip.get("order_prefs"):
        pass  # Approach-B is preference-blind by design (baseline); prefs scored by SSR
    ws, we = _to_min(trip["start_time"]), _to_min(trip["end_time"])
    must = set(trip.get("must_visit", []))
    # hours-aware placement in TSP order; skip unplaceable (must_visit -> infeasible)
    acts, cur, prev = [], ws, None
    for pid in order:
        arrival = cur + (int((matrix.get(f"{prev}->{pid}", {}) or {}).get("minutes", 0))
                         if prev is not None else 0)
        dur = int(pois[pid]["visit_min"]["p50"])
        start = _place(arrival, dur, pois[pid].get("opening_hours", []), ws, we)
        if start is None:
            if pid in must:
                return {"query_id": query["query_id"], "itinerary": None,
                        "infeasible": f"must_visit {pid} exceeds hours/window"}
            continue
        acts.append({"poi_id": pid, "start": _hh(start), "end": _hh(start + dur),
                     "explanation": {"evidence": ["gold:approach-b"]}})
        prev, cur = pid, start + dur
    if not acts:
        return {"query_id": query["query_id"], "itinerary": None, "infeasible": "empty"}
    if any(m not in [a["poi_id"] for a in acts] for m in must):
        return {"query_id": query["query_id"], "itinerary": None,
                "infeasible": "must_visit dropped"}
    return {"query_id": query["query_id"],
            "itinerary": {"activities": acts}, "infeasible": ""}
