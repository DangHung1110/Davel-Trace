"""Places a motorbike cannot reach: a boat, a cable car or a walk from a road end.

OSRM snaps every pin onto the nearest motorbike road, and for a few places that
road is the wrong one. Cù Lao Chàm (an island) lands on the mainland, so the
matrix reads Hội An -> island 20 min by motorbike; every summit stop of Bà Nà
lands on the closed service road, 35 min from the cable-car base and 1 min from
each other. `<snapshot>/transfers.json` says how each such place is reached, with
its sources: from a road end (a matrix row) by a fixed transfer (ride + board
minutes, both ways). `apply_dense` rewrites the rows and columns of those places
once, when the matrix is loaded (`matrix.load_matrix_doc`), so the solver, the
gate, the plan segments and the audit all read the same minutes:

    a -> X  = road(a -> road end of X) + transfer(X)
    X -> b  = transfer(X) + road(road end of X -> b)
    X -> Y  = transfer(X) + road(end of X -> end of Y) + transfer(Y)    two gateways
    X -> Y  = a walk on the straight line x detour      one gateway, `inside: walk`

A road end is a matrix row: a POI standing there (`poi_id`), the place's own row
(`own_row`: a beach down a trail, where OSRM already stopped at the road), or the
best of a few rows plus a short ride (`via`: the Cửa Đại pier has no POI).
A stale file never breaks loading: a gateway whose ids are not in the matrix is
skipped and named in the summary (the data test keeps the committed one clean).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass

TRANSFERS_FILE = "transfers.json"
FORMAT = "transfers-v1"
MODES = ("boat", "cable_car", "walk")


@dataclass(frozen=True)
class Gate:
    """One gateway, resolved to matrix row indices."""
    id: str
    name: str
    mode: str
    minutes: int                  # one way: ride + board
    km: float
    ends: tuple                   # ((row, minutes, km), ...): the road end options
    places: tuple                 # rows of the places behind it
    coords: dict                  # row -> (lat, lon), for walks inside
    inside: str | None            # "walk": legs between two of its places are walked

    def info(self) -> dict:
        """What a cell says about this gateway's part of a leg."""
        return {"gateway": self.id, "name": self.name, "mode": self.mode,
                "minutes": self.minutes, "km": self.km, "inside": self.inside}


def read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    if spec.get("format") != FORMAT:
        raise ValueError(f"unknown transfers format {spec.get('format')!r} in {path}")
    return spec


def resolve(spec: dict, index: dict) -> tuple[list[Gate], list[str]]:
    """(usable gateways, why each other one was skipped)."""
    gates, skipped, taken = [], [], set()
    for g in spec.get("gateways") or []:
        gid = g.get("id") or "?"
        places = [p["poi_id"] for p in g.get("places") or []]
        end = g.get("road_end") or {}
        if end.get("own_row"):
            if len(places) != 1:
                skipped.append(f"{gid}: own_row needs exactly one place")
                continue
            end_ids = [(places[0], 0, 0.0)]
        elif end.get("poi_id"):
            end_ids = [(end["poi_id"], 0, 0.0)]
        else:
            end_ids = [(v["poi_id"], int(v["minutes"]), float(v["km"])) for v in end.get("via") or []]
        missing = [pid for pid in places + [e[0] for e in end_ids] if pid not in index]
        if g.get("mode") not in MODES:
            skipped.append(f"{gid}: unknown mode {g.get('mode')!r}")
        elif not places or not end_ids:
            skipped.append(f"{gid}: no place or no road end")
        elif missing:
            skipped.append(f"{gid}: not in the matrix: {', '.join(missing)}")
        elif taken & set(places):
            skipped.append(f"{gid}: a place is already behind another gateway")
        else:
            taken |= set(places)
            gates.append(Gate(
                id=gid, name=g.get("name") or gid, mode=g["mode"],
                minutes=int(g["ride_min"]) + int(g.get("board_min") or 0),
                km=round(float(g.get("km") or 0.0), 2),
                ends=tuple((index[pid], m, k) for pid, m, k in end_ids),
                places=tuple(index[pid] for pid in places),
                coords={index[p["poi_id"]]: (float(p["lat"]), float(p["lon"]))
                        for p in g["places"] if p.get("lat") is not None and p.get("lon") is not None},
                inside=g.get("inside")))
    # A road end must be a real road point, not a place behind some gateway.
    behind = {row for gate in gates for row in gate.places}
    usable = []
    for gate in gates:
        own = gate.ends == ((gate.places[0], 0, 0.0),) and len(gate.places) == 1
        if not own and any(row in behind for row, _m, _k in gate.ends):
            skipped.append(f"{gate.id}: its road end is behind a gateway")
        else:
            usable.append(gate)
    return usable, skipped


def _best(options):
    """The fastest (minutes, km) of the options; None when none is routable."""
    best = None
    for minutes, km in options:
        if best is None or minutes < best[0] or (minutes == best[0] and km < best[1]):
            best = (minutes, km)
    return best


def _straight_km(a: tuple, b: tuple) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def walk_leg(a: tuple, b: tuple, walk: dict) -> tuple[int, float]:
    """(minutes, km) on foot between two points: the straight line x detour."""
    km = _straight_km(a, b) * float(walk.get("detour", 1.3))
    return max(1, math.ceil(km / float(walk.get("kmh", 4.0)) * 60)), round(km, 2)


def apply_dense(ids: list[str], minutes: list[list], km: list[list],
                spec: dict) -> tuple[dict[int, dict], dict]:
    """Rewrite, in place, the rows and columns of every place behind a gateway.

    Returns ({row: gateway info} for `matrix.DenseCells`, a summary for the
    matrix document). The diagonal and unroutable (None) road legs stay as they are.
    """
    index = {pid: i for i, pid in enumerate(ids)}
    gates, skipped = resolve(spec, index)
    walk = spec.get("walk") or {}
    behind = {row: gate for gate in gates for row in gate.places}
    n = len(ids)
    # Road legs from / to each road end, read before any row changes.
    out, inn = {}, {}
    for gate in gates:
        out[gate.id] = [_best((m0 + minutes[e][j], k0 + km[e][j]) for e, m0, k0 in gate.ends
                              if minutes[e][j] is not None) for j in range(n)]
        inn[gate.id] = [_best((minutes[i][e] + m0, km[i][e] + k0) for e, m0, k0 in gate.ends
                              if minutes[i][e] is not None) for i in range(n)]
    between = {(g.id, h.id): _best((out[g.id][e][0] + m0, out[g.id][e][1] + k0)
                                   for e, m0, k0 in h.ends if out[g.id][e] is not None)
               for g in gates for h in gates if g is not h}

    def put(i: int, j: int, value) -> int:
        new = (None, None) if value is None else (int(value[0]), round(value[1], 2))
        if (minutes[i][j], km[i][j]) == new:
            return 0
        minutes[i][j], km[i][j] = new
        return 1

    changed = 0
    for x, gate in behind.items():
        for j in range(n):
            if j == x:
                continue
            other = behind.get(j)
            if other is gate:
                # Inside a car-free area the motorbike cell is a service road (or
                # one shared snap point, 1 min): the walk is the only estimate.
                if gate.inside == "walk" and x in gate.coords and j in gate.coords:
                    changed += put(x, j, walk_leg(gate.coords[x], gate.coords[j], walk))
                continue
            if other is not None:       # its column is written by its own row pass
                road = between[(gate.id, other.id)]
                changed += put(x, j, road and (gate.minutes + road[0] + other.minutes,
                                               gate.km + road[1] + other.km))
                continue
            road = out[gate.id][j]
            changed += put(x, j, road and (gate.minutes + road[0], gate.km + road[1]))
            road = inn[gate.id][j]
            changed += put(j, x, road and (road[0] + gate.minutes, road[1] + gate.km))
    via = {row: gate.info() for row, gate in behind.items()}
    summary = {"file": TRANSFERS_FILE, "cells_changed": changed, "skipped": skipped,
               "gateways": [{"id": g.id, "mode": g.mode, "minutes": g.minutes,
                             "places": len(g.places)} for g in gates]}
    return via, summary


def describe(a: dict | None, b: dict | None, minutes: int) -> dict:
    """`mode` (+ `transfers`) of a leg that leaves gateway info `a` or enters `b`.

    "motorbike+boat", "cable_car" (from the road end itself), "walk" (inside one
    gateway); the road part is named only when it takes a minute or more.
    """
    if a and b and a["gateway"] == b["gateway"]:
        return {"mode": "walk"} if a.get("inside") == "walk" else {}
    legs = [t for t in (a, b) if t]
    road = minutes - sum(t["minutes"] for t in legs)
    modes = ([a["mode"]] if a else []) + (["motorbike"] if road > 0 else []) + ([b["mode"]] if b else [])
    return {"mode": "+".join(modes),
            "transfers": [{k: t[k] for k in ("gateway", "name", "mode", "minutes", "km")}
                          for t in legs]}


def side_file(matrix_path: str) -> str:
    """The transfers file that goes with a matrix file."""
    return os.path.join(os.path.dirname(matrix_path), TRANSFERS_FILE)
