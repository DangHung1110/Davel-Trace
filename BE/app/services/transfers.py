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

TIMETABLES. A cable car or a boat runs only between its first and last departure
(`service.go`: from the road end toward the places, `service.back`: from the places
back), the island boats only in some months (`service.months`). A walk has none.
The places behind such a gateway inherit three clock times (`place_service`, carried
by the POI view as `transfer`):

    arrive_from = go.first + ride      no visit before the first car or boat arrives
    arrive_by   = go.last + ride       the last one up / out arrives then
    leave_by    = back.last - board    a visit ends in time for the last one back

`arrive_from`..`leave_by` is also the place's `hours.access_window`, written into
`pois.json` by `BE/ml/data/migrate_v2.py` like the Sơn Trà road window. `arrive_by`
binds the leg, not the place: once on the summit a traveller may stay after the
last car up. `leg_bounds` / `leg_arrival` turn a leg's departure into its arrival
(waiting for the first boat back, or None after the last car up), the same formula
for the solver, the order search and gate B3.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

TRANSFERS_FILE = "transfers.json"
FORMAT = "transfers-v1"
MODES = ("boat", "cable_car", "walk")
# A timetable's two directions: `go` from the road end toward the places behind the
# gateway, `back` from them to the road end. Each is {"first", "last"} departure.
SERVICE_KEYS = ("go", "back")
DAY_MIN = 24 * 60


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
    runs: dict = field(default_factory=dict)   # {"go"|"back": "HH:MM-HH:MM"} departures

    def info(self) -> dict:
        """What a cell says about this gateway's part of a leg."""
        return {"gateway": self.id, "name": self.name, "mode": self.mode,
                "minutes": self.minutes, "km": self.km, "inside": self.inside, **self.runs}


@dataclass(frozen=True)
class Service:
    """A gateway's timetable in minutes, as one leg rides it (from a POI's `transfer`)."""
    gateway: str
    ride: int                     # minutes on the car or boat
    board: int                    # minutes from the road end (or the place) onto it
    go: tuple                     # (first, last) departure toward the places
    back: tuple                   # (first, last) departure back to the road end


def _clock(text) -> int:
    hours, minutes = str(text).strip().split(":")
    value = int(hours) * 60 + int(minutes)
    if not 0 <= value < DAY_MIN:
        raise ValueError(f"not a clock time: {text!r}")
    return value


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _window(text: str) -> tuple[int, int]:
    first, last = str(text).split("-")
    return _clock(first), _clock(last)


def timetable(g: dict) -> dict | None:
    """A gateway's `service` in minutes: {"go": (first, last), "back": (first, last),
    "months": (3, ..., 8) | None}. None: it runs whenever (a walk). ValueError says
    what is wrong with it."""
    service = g.get("service")
    if not service:
        return None
    gid = g.get("id") or "?"
    out: dict = {}
    for key in SERVICE_KEYS:
        window = service.get(key) or {}
        first, last = _clock(window.get("first")), _clock(window.get("last"))
        if last < first:
            raise ValueError(f"{gid}: service.{key} ends before it starts")
        out[key] = (first, last)
    months = service.get("months")
    if months is not None:
        months = tuple(sorted({int(m) for m in months}))
        if not months or not all(1 <= m <= 12 for m in months):
            raise ValueError(f"{gid}: service.months must list months 1-12")
    out["months"] = months
    return out


def place_service(spec: dict) -> dict[str, dict]:
    """{poi_id: what a place behind a gateway with a timetable inherits from it}.

    The POI view carries it as `transfer` (`BE.common.view_pois`), so the solver's
    stubs, the order search, gate B3, a replan and the audit read one record:
    gateway, mode, ride/board minutes, both departure windows, `arrive_from`,
    `arrive_by`, `leave_by` (module docstring) and the months it runs. A gateway
    whose timetable cannot be read gives none (the data test names it); its
    minutes still load.
    """
    out: dict[str, dict] = {}
    for g in spec.get("gateways") or []:
        try:
            times = timetable(g)
            if times is None:
                continue
            ride, board = int(g["ride_min"]), int(g.get("board_min") or 0)
            (go_first, go_last), (back_first, back_last) = times["go"], times["back"]
            if go_last + ride >= DAY_MIN or back_last - board < go_first + ride:
                raise ValueError("no visit fits between the first arrival and the last return")
            info = {"gateway": g["id"], "name": g.get("name") or g["id"], "mode": g["mode"],
                    "ride_min": ride, "board_min": board,
                    "go": f"{_hhmm(go_first)}-{_hhmm(go_last)}",
                    "back": f"{_hhmm(back_first)}-{_hhmm(back_last)}",
                    "arrive_from": _hhmm(go_first + ride), "arrive_by": _hhmm(go_last + ride),
                    "leave_by": _hhmm(back_last - board),
                    "months": list(times["months"]) if times["months"] else None}
            ids = [place["poi_id"] for place in g.get("places") or []]
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        for pid in ids:
            out.setdefault(pid, info)   # behind two gateways: `resolve` keeps the first
    return out


def season_label(months: list[int] | None) -> str:
    """'thang 3-8' for the months a boat runs (one span, else the list)."""
    months = sorted(months or [])
    if months and months == list(range(months[0], months[-1] + 1)):
        return f"thang {months[0]}-{months[-1]}"
    return "thang " + ", ".join(str(m) for m in months)


def service(info: dict | None) -> Service | None:
    """A POI's `transfer` (`place_service`) -> Service; None: no timetable binds it."""
    if not info:
        return None
    return Service(info["gateway"], int(info["ride_min"]), int(info["board_min"]),
                   _window(info["go"]), _window(info["back"]))


def crossing(src: Service | None, dst: Service | None) -> tuple[Service | None, Service | None]:
    """(left, entered): the timetables a leg from `src`'s place to `dst`'s rides.
    Two places behind one gateway are walked between: no car, no boat."""
    if src is not None and dst is not None and src.gateway == dst.gateway:
        return None, None
    return src, dst


def leg_bounds(minutes: int, left: Service | None,
               entered: Service | None) -> tuple[int | None, int | None, bool]:
    """(latest departure, earliest arrival, possible) of a leg of `minutes` door to door.

    It leaves the places behind `left` (board, then its car or boat back) and/or enters
    those behind `entered` (its car or boat is the leg's last part). Before the first
    departure one waits; after the last there is none:

        latest   = min(left.back.last - left.board,  entered.go.last - (minutes - entered.ride))
        earliest = max(left.back.first + minutes - left.board,  entered.go.first + entered.ride)

    `possible` is False when even the first boat back reaches the road end after the
    last car up. Both bounds are linear in the departure, so the solver states them as
    two constraints and `leg_arrival` as a max.
    """
    latest = earliest = None
    possible = True
    if left is not None:
        latest = left.back[1] - left.board
        earliest = left.back[0] + minutes - left.board
    if entered is not None:
        cut = entered.go[1] - (minutes - entered.ride)
        latest = cut if latest is None else min(latest, cut)
        first = entered.go[0] + entered.ride
        earliest = first if earliest is None else max(earliest, first)
        if left is not None:
            possible = left.back[0] + minutes - left.board - entered.ride <= entered.go[1]
    return latest, earliest, possible


def leg_arrival(depart: int, minutes: int, left: Service | None,
                entered: Service | None) -> int | None:
    """When a leg that leaves at `depart` arrives; None when a car or boat it needs has
    already made its last run. With no timetable it is `depart + minutes`."""
    latest, earliest, possible = leg_bounds(minutes, left, entered)
    if not possible or (latest is not None and depart > latest):
        return None
    return depart + minutes if earliest is None else max(depart + minutes, earliest)


def open_start(entered: Service) -> tuple[int, int]:
    """Start window of a place that opens an open tour (no base, no first leg): the
    day begins there, so it is where the traveller gets off a car or boat that runs."""
    return entered.go[0] + entered.ride, entered.go[1] + entered.ride


def read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    if spec.get("format") != FORMAT:
        raise ValueError(f"unknown transfers format {spec.get('format')!r} in {path}")
    return spec


def _gate(g: dict, index: dict) -> Gate:
    """One gateway of the file on this matrix; ValueError says why it cannot be used."""
    gid = g.get("id") or "?"
    places = [p["poi_id"] for p in g.get("places") or []]
    end = g.get("road_end") or {}
    if end.get("own_row"):
        if len(places) != 1:
            raise ValueError(f"{gid}: own_row needs exactly one place")
        end_ids = [(places[0], 0, 0.0)]
    elif end.get("poi_id"):
        end_ids = [(end["poi_id"], 0, 0.0)]
    else:
        end_ids = [(v["poi_id"], int(v["minutes"]), float(v["km"])) for v in end.get("via") or []]
    missing = [pid for pid in places + [e[0] for e in end_ids] if pid not in index]
    if g.get("mode") not in MODES:
        raise ValueError(f"{gid}: unknown mode {g.get('mode')!r}")
    if not places or not end_ids:
        raise ValueError(f"{gid}: no place or no road end")
    if missing:
        raise ValueError(f"{gid}: not in the matrix: {', '.join(missing)}")
    minutes = int(g["ride_min"]) + int(g.get("board_min") or 0)
    if minutes < 1:
        raise ValueError(f"{gid}: a transfer takes at least a minute")
    return Gate(id=gid, name=g.get("name") or gid, mode=g["mode"], minutes=minutes,
                km=round(float(g.get("km") or 0.0), 2),
                ends=tuple((index[pid], m, k) for pid, m, k in end_ids),
                places=tuple(index[pid] for pid in places),
                coords={index[p["poi_id"]]: (float(p["lat"]), float(p["lon"]))
                        for p in g["places"] if p.get("lat") is not None and p.get("lon") is not None},
                inside=g.get("inside"), runs=_runs(g))


def _runs(g: dict) -> dict:
    """{"go"|"back": "HH:MM-HH:MM"}: the departures a cell names; {} without a readable
    timetable (a walk, or a malformed one: its minutes still load)."""
    try:
        times = timetable(g)
    except (ValueError, KeyError, TypeError, AttributeError):
        return {}
    if not times:
        return {}
    return {key: f"{_hhmm(times[key][0])}-{_hhmm(times[key][1])}" for key in SERVICE_KEYS}


def resolve(spec: dict, index: dict) -> tuple[list[Gate], list[str]]:
    """(usable gateways, why each other one was skipped)."""
    gates, skipped, taken = [], [], set()
    for g in spec.get("gateways") or []:
        gid = (g.get("id") if isinstance(g, dict) else None) or "?"
        try:
            gate = _gate(g, index)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:   # stale or malformed
            why = str(exc) if isinstance(exc, ValueError) else f"bad entry ({exc!r})"
            skipped.append(why if why.startswith(f"{gid}:") else f"{gid}: {why}")
            continue
        if taken & set(gate.places):
            skipped.append(f"{gate.id}: a place is already behind another gateway")
            continue
        taken |= set(gate.places)
        gates.append(gate)
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
    gateway); the road part is named only when it takes a minute or more. A transfer
    with a timetable also says `runs`: its first and last departure in the direction
    this leg rides it ("16:30" is the last car up, "14:30" the last boat back).
    """
    if a and b and a["gateway"] == b["gateway"]:
        return {"mode": "walk"} if a.get("inside") == "walk" else {}
    legs = [(t, way) for t, way in ((a, "back"), (b, "go")) if t]
    road = minutes - sum(t["minutes"] for t, _way in legs)
    modes = ([a["mode"]] if a else []) + (["motorbike"] if road > 0 else []) + ([b["mode"]] if b else [])
    return {"mode": "+".join(modes),
            "transfers": [{**{k: t[k] for k in ("gateway", "name", "mode", "minutes", "km")},
                           **({"runs": t[way]} if t.get(way) else {})}
                          for t, way in legs]}


def side_file(matrix_path: str) -> str:
    """The transfers file that goes with a matrix file."""
    return os.path.join(os.path.dirname(matrix_path), TRANSFERS_FILE)
