"""How far off are the legs of a day that starts at a GPS fix (services/gps_origin.py)?

The estimate is the code the planner runs (`gps_origin.locate` + `matrix.with_starts`),
measured two ways:

1. Leave-one-out on the snapshot matrix (no server needed): every place with a row
   plays the fix in turn; it cannot be its own anchor, so its legs are estimated from
   the others and compared with its real row. Also a fix 5-50 m from each hotel,
   against that hotel's row (what "GPS at the hotel" gives).
2. With `--osrm URL --roads FILE`: random points on the roads, against a running
   osrm-routed on the same motorbike graph (BE/tools/osrm/build_osrm.sh, serve with
   `--max-table-size 1100`). FILE is a GeoJSON sequence of OSM road lines, e.g.
     osmium tags-filter danang.osm.pbf w/highway=primary,secondary,tertiary,residential,\
       unclassified,living_street,trunk -o roads.osm.pbf
     osmium export roads.osm.pbf -f geojsonseq --geometry-types=linestring -o roads.geojsonseq
   Points are drawn per band of distance to the nearest place with a row, plus a plain
   random draw from the city core.

Error = estimated - true minutes per leg (true rounded like build_poi_matrix: half up,
at least 1). "short>3" is the share of legs the estimate makes more than 3 minutes
shorter than they are: a traveller who would arrive later than the plan says.

Usage (repo root):
  python BE/tools/gps_origin_error.py [--snapshot DIR] [--json out.json]
  python BE/tools/gps_origin_error.py --osrm http://127.0.0.1:5001 --roads roads.geojsonseq
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from BE.app.services import gps_origin, matrix  # noqa: E402
from BE.app.services.retrieval import load_pois_json  # noqa: E402

DEFAULT_SNAPSHOT = REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v2"
GAP_BANDS = [(0.0, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 5.0)]
CITY_CORE = (15.95, 16.13, 108.13, 108.30)  # lat min, lat max, lon min, lon max


def stats(errors: list[float]) -> dict:
    if not errors:
        return {"legs": 0}
    abs_sorted = sorted(abs(e) for e in errors)
    return {"legs": len(errors),
            "mae": round(sum(abs_sorted) / len(errors), 2),
            "p90": abs_sorted[min(len(errors) - 1, int(0.9 * len(errors)))],
            "bias": round(sum(errors) / len(errors), 2),
            "short_over_3": round(sum(1 for e in errors if e < -3) / len(errors), 4)}


def line(name: str, s: dict) -> str:
    if not s.get("legs"):
        return f"  {name:28s} no legs"
    return (f"  {name:28s} legs {s['legs']:7d}  mean {s['mae']:5.2f}  p90 {s['p90']:4.0f}  "
            f"bias {s['bias']:+5.2f}  short>3 {s['short_over_3'] * 100:4.1f}%")


def estimate(lat: float, lon: float, by_id, cells, targets: list[str]):
    """{target: minutes} from a fix, or (None, why) when the fix is not used."""
    start, why = gps_origin.locate(lat, lon, by_id, cells)
    if start is None:
        return None, why
    view = matrix.with_starts(cells, {start.start_id: start.row()})
    out = {}
    for b in targets:
        cell = view.get(f"{start.start_id}->{b}")
        if cell is not None:
            out[b] = cell["minutes"]
    return out, start


def leave_one_out(by_id: dict, cells, rows: list[str]) -> dict:
    places = [pid for pid in rows if by_id.get(pid, {}).get("lat") is not None]
    all_err, by_gap, refused = [], {band: [] for band in GAP_BANDS + [(5.0, 1e9)]}, 0
    for p in places:
        others = {k: v for k, v in by_id.items() if k != p}
        est, start = estimate(by_id[p]["lat"], by_id[p]["lon"], others, cells,
                              [b for b in places if b != p])
        if est is None:
            refused += 1
            continue
        gap = start.nearest.km
        for b, minutes in est.items():
            true = cells.get(f"{p}->{b}")
            if true is None:
                continue
            e = minutes - int(true["minutes"])
            all_err.append(e)
            for lo, hi in by_gap:
                if lo <= gap < hi:
                    by_gap[(lo, hi)].append(e)
    return {"places": len(places), "not_used": refused, "all": stats(all_err),
            "by_gap_km": {f"{lo}-{hi}": stats(v) for (lo, hi), v in by_gap.items()}}


def at_the_hotel(by_id: dict, cells, rows: list[str], seed: int = 3) -> dict:
    rng = random.Random(seed)
    places = [pid for pid in rows if by_id.get(pid, {}).get("lat") is not None]
    hotels = [pid for pid in places if by_id[pid].get("category") == "lodging"
              or by_id[pid].get("cat") == "lodging" or by_id[pid].get("type") == "lodging"]
    errors, same_anchor, tried = [], 0, 0
    for metres in (5, 15, 30, 50):
        for h in hotels:
            angle = rng.uniform(0, 2 * math.pi)
            lat = by_id[h]["lat"] + metres / 111_195.0 * math.cos(angle)
            lon = by_id[h]["lon"] + (metres * math.sin(angle)
                                     / (111_195.0 * math.cos(math.radians(by_id[h]["lat"]))))
            est, start = estimate(lat, lon, by_id, cells, [b for b in places if b != h])
            tried += 1
            if est is None:
                continue
            same_anchor += start.nearest.poi_id == h
            for b, minutes in est.items():
                true = cells.get(f"{h}->{b}")
                if true is not None:
                    errors.append(minutes - int(true["minutes"]))
    return {"hotels": len(hotels), "fixes": tried, "anchor_is_the_hotel": same_anchor,
            "all": stats(errors)}


def road_points(path: str, step_km: float = 0.1) -> list[tuple[float, float]]:
    pts = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip().lstrip("\x1e")
            if not raw:
                continue
            coords = json.loads(raw)["geometry"]["coordinates"]
            carry = 0.0
            for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
                seg = gps_origin.straight_km(y1, x1, y2, x2)
                t = step_km - carry
                while seg > 0 and t <= seg:
                    r = t / seg
                    pts.append((y1 + (y2 - y1) * r, x1 + (x2 - x1) * r))
                    t += step_km
                carry = (carry + seg) % step_km
    return pts


def osrm_row(base: str, lat: float, lon: float, places: list[tuple[float, float]]) -> list:
    coords = ";".join(f"{x:.6f},{y:.6f}" for y, x in [(lat, lon)] + places)
    url = f"{base.rstrip('/')}/table/v1/driving/{coords}?sources=0&annotations=duration"
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 - local osrm-routed
        body = json.loads(r.read())
    if body.get("code") != "Ok":
        raise RuntimeError(f"OSRM: {body.get('code')}")
    return [None if s is None else max(1, int(s / 60.0 + 0.5)) for s in body["durations"][0][1:]]


def random_roads(by_id: dict, cells, rows: list[str], osrm: str, roads: str,
                 per_band: int, core_points: int, seed: int = 11) -> dict:
    rng = random.Random(seed)
    places = [pid for pid in rows if by_id.get(pid, {}).get("lat") is not None]
    coords = [(by_id[p]["lat"], by_id[p]["lon"]) for p in places]
    import numpy as np  # only this mode: ~70k road points x ~1000 places

    lo_lon, lo_lat, hi_lon, hi_lat = 107.86, 15.73, 108.54, 16.29
    pts = [p for p in road_points(roads) if lo_lat <= p[0] <= hi_lat and lo_lon <= p[1] <= hi_lon]
    rad = np.radians(np.array(coords))
    gap = []
    for s in range(0, len(pts), 4000):
        p = np.radians(np.array(pts[s:s + 4000]))
        h = (np.sin((rad[None, :, 0] - p[:, None, 0]) / 2) ** 2
             + np.cos(p[:, None, 0]) * np.cos(rad[None, :, 0])
             * np.sin((rad[None, :, 1] - p[:, None, 1]) / 2) ** 2)
        gap += list((2 * gps_origin.EARTH_KM * np.arcsin(np.sqrt(np.clip(h, 0, 1)))).min(axis=1))
    draws = {}
    for lo, hi in GAP_BANDS:
        pool = [i for i, g in enumerate(gap) if lo <= g < hi]
        draws[f"gap {lo}-{hi} km"] = rng.sample(pool, min(per_band, len(pool)))
    core = [i for i, (y, x) in enumerate(pts)
            if CITY_CORE[0] <= y <= CITY_CORE[1] and CITY_CORE[2] <= x <= CITY_CORE[3]]
    draws["city core, plain random"] = rng.sample(core, min(core_points, len(core)))
    out = {}
    for name, picked in draws.items():
        errors, refused = [], 0
        for i in picked:
            lat, lon = pts[i]
            est, _start = estimate(lat, lon, by_id, cells, places)
            if est is None:
                refused += 1
                continue
            for b, true in zip(places, osrm_row(osrm, lat, lon, coords)):
                if true is not None and b in est:
                    errors.append(est[b] - true)
        out[name] = {"points": len(picked), "not_used": refused, **stats(errors)}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--osrm", default=None, help="a running osrm-routed (random road points)")
    ap.add_argument("--roads", default=None, help="GeoJSON sequence of OSM road lines")
    ap.add_argument("--per-band", type=int, default=60)
    ap.add_argument("--core-points", type=int, default=150)
    ap.add_argument("--json", default=None, help="write the numbers here")
    args = ap.parse_args(argv)
    by_id = {p["poi_id"]: p for p in load_pois_json(str(Path(args.snapshot) / "pois.json"))}
    cells = matrix.load_cells(args.snapshot)
    rows = list(getattr(cells, "row_ids", None) or {k.split("->", 1)[0] for k in cells})
    result = {"snapshot": args.snapshot, "anchors": gps_origin.ANCHORS,
              "at_place_km": gps_origin.AT_PLACE_KM,
              "leave_one_out": leave_one_out(by_id, cells, rows),
              "at_the_hotel": at_the_hotel(by_id, cells, rows)}
    loo = result["leave_one_out"]
    print(f"leave-one-out: {loo['places']} places, {loo['not_used']} too far to use")
    print(line("all legs", loo["all"]))
    for band, s in loo["by_gap_km"].items():
        print(line(f"nearest place {band} km", s))
    hotel = result["at_the_hotel"]
    print(f"a fix 5-50 m from a hotel: {hotel['fixes']} fixes, anchor = that hotel "
          f"{hotel['anchor_is_the_hotel']}")
    print(line("all legs", hotel["all"]))
    if args.osrm and args.roads:
        result["random_roads"] = random_roads(by_id, cells, rows, args.osrm, args.roads,
                                              args.per_band, args.core_points)
        print("random road points vs OSRM:")
        for name, s in result["random_roads"].items():
            print(line(f"{name} ({s['points']} pts)", s))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
