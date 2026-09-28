"""CP-SAT optimizer basic, OPTW (T017, lane B). Depot/flow/Tmax/windows.

STUB-NOTE: TripRequest/POI schemas (T007 trip/poi) are not in the lane-B
worktree yet — minimal STUB dataclasses below stand in (same field
names); phase-PR swaps them for the real schemas without touching the
model code. Travel comes from dict-of-dict minutes (T010 matrix).

Model (OR-Tools CP-SAT, 5s timeout):
- circuit over depot + POIs; self-arc[i][i] == "skip i".
- t[i] visit start; open[i] <= t[i] <= close[i]-dur[i] iff visited.
- arc[i][j] => t[j] >= t[i]+dur[i]+travel[i][j]; depot t[0]=trip start.
- Tmax: all t[i] <= trip end. Objective: max total score of visited.
Returns {"status": optimal|feasible-timeout|infeasible, "itinerary" |
"reason", ...}. Best-found is returned even on timeout (never empty-
handed when a feasible prefix exists).
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

TIMEOUT_S = 5.0


@dataclass
class StubPOI:  # STUB (T007 poi.py) — same names, swapped at phase-PR
    poi_id: str
    visit_min: int = 60
    open_min: int = 7 * 60
    close_min: int = 18 * 60
    score: float = 1.0


@dataclass
class StubTrip:  # STUB (T007 trip.py) — same names, swapped at phase-PR
    start_min: int = 7 * 60
    end_min: int = 18 * 60
    origin_id: str = "depot"


def _hh(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def optimize(pois: list[StubPOI], travel: dict[tuple[str, str], int],
             trip: StubTrip, require_all: bool = False,
             timeout_s: float = TIMEOUT_S) -> dict:
    from ortools.sat.python import cp_model

    ids = [p.poi_id for p in pois]
    n = len(ids)
    node = {pid: i + 1 for i, pid in enumerate(ids)}  # 0 = depot
    dur = {0: 0, **{node[p.poi_id]: p.visit_min for p in pois}}
    opn = {0: trip.start_min, **{node[p.poi_id]: p.open_min for p in pois}}
    cls = {0: trip.end_min, **{node[p.poi_id]: p.close_min for p in pois}}
    sco = {i: (0.0 if i == 0 else pois[i - 1].score) for i in range(n + 1)}
    tmax = trip.end_min

    m = cp_model.CpModel()
    arc = {}
    for i in range(n + 1):
        for j in range(n + 1):
            tag = f"self_{i}" if i == j else f"arc_{i}_{j}"
            arc[(i, j)] = m.NewBoolVar(tag)
    # circuit: exactly one in/out per node (self-loop == skip)
    m.AddCircuit([(i, j, arc[(i, j)]) for i in range(n + 1) for j in range(n + 1)])
    t = {i: m.NewIntVar(trip.start_min, tmax, f"t_{i}") for i in range(n + 1)}
    m.Add(t[0] == trip.start_min)
    visit = {}
    for i in range(1, n + 1):
        visit[i] = m.NewBoolVar(f"visit_{i}")
        m.Add(arc[(i, i)] == 0).OnlyEnforceIf(visit[i])
        m.Add(arc[(i, i)] == 1).OnlyEnforceIf(visit[i].Not())
        if require_all:
            m.Add(visit[i] == 1)
        m.Add(opn[i] <= t[i]).OnlyEnforceIf(visit[i])
        m.Add(t[i] <= cls[i] - dur[i]).OnlyEnforceIf(visit[i])
        m.Add(t[i] <= tmax).OnlyEnforceIf(visit[i])
    for i in range(n + 1):
        for j in range(1, n + 1):  # skip j == 0: return leg must not pin t[0]
            if i == j:
                continue
            a, b = (trip.origin_id if i == 0 else ids[i - 1],
                    trip.origin_id if j == 0 else ids[j - 1])
            w = travel.get((a, b), travel.get((b, a), 0))
            m.Add(t[j] >= t[i] + dur[i] + w).OnlyEnforceIf(arc[(i, j)])
    m.Maximize(sum(int(sco[i] * 1000) * visit[i] for i in range(1, n + 1)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_s
    t0 = time.monotonic()
    status = solver.Solve(m)
    elapsed = time.monotonic() - t0
    name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "infeasible", "reason": f"solver {name}",
                "elapsed_s": round(elapsed, 3), "itinerary": None}
    order, node_now = [], 0
    while True:
        nxt = next(j for j in range(n + 1) if solver.Value(arc[(node_now, j)]))
        if nxt == 0:
            break
        order.append(nxt)
        node_now = nxt
    acts = [{"poi_id": ids[i - 1], "start": _hh(int(solver.Value(t[i]))),
             "end": _hh(int(solver.Value(t[i])) + dur[i])} for i in order]
    return {"status": "optimal" if status == cp_model.OPTIMAL else "feasible-timeout",
            "elapsed_s": round(elapsed, 3),
            "itinerary": {"activities": acts,
                          "total_score": round(sum(sco[i] for i in order), 3),
                          "total_min": (int(solver.Value(t[order[-1]]))
                                        + dur[order[-1]] - trip.start_min) if order else 0},
            "objective": solver.ObjectiveValue()}
