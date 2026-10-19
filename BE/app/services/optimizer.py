"""CP-SAT optimizer basic, OPTW (T017, lane B). Depot/flow/Tmax/windows.

STUB-NOTE: TripRequest/POI schemas (T007 trip/poi) are not in the lane-B
worktree yet — minimal STUB dataclasses below stand in (same field
names); phase-PR swaps them for the real schemas without touching the
model code. Travel comes from dict-of-dict minutes (T010 matrix).

Model (OR-Tools CP-SAT, 5s timeout):
- circuit over depot + POIs; self-arc[i][i] == "skip i".
- t[i] visit start; open[i] <= t[i] <= close[i]-dur[i] iff visited.
- arc[i][j] => t[j] >= t[i]+dur[i]+travel[i][j]; depot t[0]=trip start.
- Tmax: every visit finishes by trip end. Objective: max total score of visited.
Returns {"status": optimal|feasible-timeout|infeasible, "itinerary" |
"reason", ...}. Best-found is returned even on timeout (never empty-
handed when a feasible prefix exists).

T061a depot decision: `StubTrip.origin_id` is the depot (hotel). A falsy
origin (`""`/`None`) selects the OPEN-TOUR variant ("drop depot legs"):
the origin leg is not modelled, so the first activity may start at
trip.start_min. Chosen over "add a depot node to the matrix" because the
committed seed matrix has no depot cell and adding one needs a live OSRM
call (offline demo) — haversine is banned for feasibility (R4/B3). Every
INTER-POI transition still comes from the matrix; only the untracked
origin leg is dropped.

T030: optional q_ij edge bonuses + W_A+s_A<=W_B precedence (PATM).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from BE.app.services.common import hh, parse_hours, to_min

TIMEOUT_S = 5.0

# T061a: must-go landmarks (snapshot `must_go`) get a small score nudge so
# they surface first. It is a SOFT signal only — the hard must_visit
# constraint stays in retrieval/validator (validator HCS), never here.
MUST_GO_BONUS = 0.5


# ponytail: STUB dataclasses are a deliberate ceiling — T007 poi/trip
# schemas are not in this worktree; phase-PR swaps them in, model code
# untouched. Same field names, shared from here (imported by profiles/replan).
@dataclass
class StubPOI:
    poi_id: str
    visit_min: int = 60
    open_min: int = 7 * 60
    close_min: int = 18 * 60
    score: float = 1.0


@dataclass
class StubTrip:
    start_min: int = 7 * 60
    end_min: int = 18 * 60
    origin_id: str = "depot"


def poi_visit_min(poi: dict) -> int:
    """T061a adapter: schedule with p50 when the POI carries a VisitMin dict.

    The real snapshot stores `visit_min: {p25,p50,p75}` (R8: schedule p50,
    gate p75 buffer, UI the range). Legacy fixtures pass a flat int; both
    are accepted so old tests and live snapshots share one seam.
    """
    vm = poi.get("visit_min", 60)
    if isinstance(vm, dict):
        return int(vm.get("p50") or vm.get("p25") or 60)
    return int(vm or 60)


def poi_window(poi: dict, trip: dict | None = None,
               deadline: int | None = None) -> tuple[int, int]:
    """T061a adapter: opening window in minutes, trip window when unset.

    Opening hours stay authoritative; when a POI has none the trip window
    `[start_time, deadline]` is used. `deadline` (ETB: min(end, return))
    wins over end_time when supplied so a horizon never silently stretches.
    """
    win = parse_hours(poi.get("opening_hours"))
    if win is not None:
        return win
    start = to_min((trip or {}).get("start_time", "07:00"))
    if deadline is not None:
        end = deadline
    else:
        end = to_min((trip or {}).get("end_time", "18:00"))
    return start, end


def poi_to_stub(poi: dict, trip: dict | None = None, score: float = 1.0,
                deadline: int | None = None) -> StubPOI:
    """T061a adapter: POI dict (snapshot or fixture) -> optimizer input."""
    open_min, close_min = poi_window(poi, trip, deadline)
    bonus = MUST_GO_BONUS if poi.get("must_go") else 0.0
    return StubPOI(poi["poi_id"], poi_visit_min(poi), open_min, close_min,
                   float(score) + bonus)


def stubs_from_pois(pois: list[dict], trip: dict | None = None,
                    score_fn=None, deadline: int | None = None) -> list[StubPOI]:
    """T061a adapter: adapt a POI list with one score function (or rating)."""
    def _score(p: dict) -> float:
        if score_fn is not None:
            return float(score_fn(p))
        return float(p.get("rating") or 1.0)

    return [poi_to_stub(p, trip, _score(p), deadline) for p in pois]


def travel_from_matrix(matrix, ids=None):
    """T017 wiring: build optimize()'s travel dict from the cached matrix.

    `matrix` is MatrixService-compatible (needs .ids and .minutes_or_none).
    Pairs missing from the artifact stay ABSENT (arc forbidden in the model —
    B3: infeasible stays infeasible, never 0/haversine/estimate). POI-metadata
    adaptation (visit_min/opening-hours) stays in T061a, not here.
    """
    ids = list(matrix.ids) if ids is None else list(ids)
    travel = {}
    for a in ids:
        for b in ids:
            if a == b:
                continue
            m, _src = matrix.minutes_or_none(a, b)
            if m is not None:
                travel[(a, b)] = m
    return travel


def optimize(pois: list[StubPOI], travel: dict[tuple[str, str], int],
             trip: StubTrip, require_all: bool = False,
             timeout_s: float = TIMEOUT_S,
             edge_scores: dict[tuple[str, str], float] | None = None,
             precedence: list[tuple[str, str]] | None = None,
             workers: int = 0,
             must_visit: list[str] | None = None) -> dict:
    """T030: q_ij edge bonuses + W_A+s_A<=W_B precedence (both optional).

    edge_scores[(a, b)]: bonus added when transition a->b is used.
    precedence[(A, B)]: when BOTH visited, t[B] >= t[A]+dur[A].
    workers: 0 = solver default (wall-clock search, may vary run to run);
    1 = single deterministic worker, used by the T053 eval harness so a
    baseline comparison is reproducible.

    must_visit (T053 bug 2): HARD constraint — every listed POI MUST be in
    the itinerary (visit[i] == 1), unlike the SOFT MUST_GO_BONUS nudge in
    poi_to_stub. A must_visit POI outside the candidate set, or one the
    horizon cannot fit, makes the model infeasible -> honest no_solution
    rather than a silently must-less plan that fails gate HCS.
    """
    from ortools.sat.python import cp_model

    ids = [p.poi_id for p in pois]
    n = len(ids)
    must_set = set(must_visit or [])
    missing = sorted(must_set - set(ids))
    if missing:
        return {"status": "infeasible",
                "reason": f"must_visit ngoai candidate: {missing}",
                "elapsed_s": 0.0, "itinerary": None}

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
        if ids[i - 1] in must_set:
            # T053 bug 2: must_visit is HARD (gate HCS), not the soft bonus.
            m.Add(visit[i] == 1)
        m.Add(opn[i] <= t[i]).OnlyEnforceIf(visit[i])
        m.Add(t[i] <= cls[i] - dur[i]).OnlyEnforceIf(visit[i])
        m.Add(t[i] + dur[i] <= tmax).OnlyEnforceIf(visit[i])
    for i in range(n + 1):
        for j in range(1, n + 1):  # skip j == 0: return leg must not pin t[0]
            if i == j:
                continue
            if i == 0 and not trip.origin_id:
                # T061a "drop depot legs": open tour — the origin/hotel leg
                # is not modelled (seed has no depot node; adding one needs
                # an OSRM call and haversine is banned for feasibility).
                # The FIRST activity is therefore free to start at
                # trip.start_min; inter-POI arcs stay matrix-verified (B3).
                m.Add(t[j] >= t[i] + dur[i]).OnlyEnforceIf(arc[(i, j)])
                continue
            a, b = (trip.origin_id if i == 0 else ids[i - 1],
                    trip.origin_id if j == 0 else ids[j - 1])
            w = travel.get((a, b))
            if w is None:
                m.Add(arc[(i, j)] == 0)
            else:
                m.Add(t[j] >= t[i] + dur[i] + w).OnlyEnforceIf(arc[(i, j)])
    for prec in precedence or []:
        ia, ib = node.get(prec[0]), node.get(prec[1])
        if ia is not None and ib is not None:
            m.Add(t[ib] >= t[ia] + dur[ia]).OnlyEnforceIf(
                [visit[ia], visit[ib]])
    obj = sum(int(sco[i] * 1000) * visit[i] for i in range(1, n + 1))
    for (a, b), q in (edge_scores or {}).items():
        ia, ib = node.get(a), node.get(b)
        if ia is not None and ib is not None and ia != ib:
            obj += int(float(q) * 100) * arc[(ia, ib)]
    m.Maximize(obj)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_s
    if workers:
        solver.parameters.num_search_workers = workers
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
    acts = [{"poi_id": ids[i - 1], "start": hh(int(solver.Value(t[i]))),
             "end": hh(int(solver.Value(t[i])) + dur[i])} for i in order]
    return {"status": "optimal" if status == cp_model.OPTIMAL else "feasible-timeout",
            "elapsed_s": round(elapsed, 3),
            "itinerary": {"activities": acts,
                          "total_score": round(sum(sco[i] for i in order), 3),
                          "total_min": (int(solver.Value(t[order[-1]]))
                                        + dur[order[-1]] - trip.start_min) if order else 0},
            "objective": solver.ObjectiveValue()}
