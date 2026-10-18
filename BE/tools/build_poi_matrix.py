"""Build the OSRM travel-time matrix for the top-N snapshot POIs (T010b, lane B).

Pulls `https://download.geofabrik.de/asia/vietnam-latest.osm.pbf`, preprocesses
it with osrm-extract/partition/customize (MLD — see docker note below), then
queries the local osrm-routed `/table` service and writes `matrix.json` next to
the snapshot's `pois.json` (the location `MatrixService` loads from).

Usage (repo root; server up — never commit OSRM data, see .gitignore):
    python BE/tools/build_poi_matrix.py                      # top-150 by rating
    python BE/tools/build_poi_matrix.py --top 50 --out tmp/m.json
    python BE/tools/build_poi_matrix.py --dry-run            # selection only

Docker (data dir OUTSIDE the repo, e.g. TMP):
    docker run --rm -v <tmp>:/data osrm/osrm-backend \
        osrm-extract -p /opt/car.lua /data/vietnam-latest.osm.pbf
    docker run --rm -v <tmp>:/data osrm/osrm-backend osrm-partition /data/vietnam-latest.osrm
    docker run --rm -v <tmp>:/data osrm/osrm-backend osrm-customize /data/vietnam-latest.osrm
    docker run -d --name osrm-vn --restart unless-stopped -p 127.0.0.1:5000:5000 \
        -v <tmp>:/data osrm/osrm-backend \
        osrm-routed --algorithm mld --max-table-size 300 /data/vietnam-latest.osrm

B3 FAILURE POLICY: an OSRM failure / unroutable pair is OMITTED from `cells`
(infeasible — `MatrixService.minutes` raises `MatrixMissError`), NEVER a
silent 0. `--seed-fallback` fills such holes with the legacy haversine 30 km/h
seed (step 5 min) labelled per-cell `source: "haversine_seed"` + confidence
`low`; pass it only when a consumer cannot represent infeasible holes
(e.g. T008 `load_matrix` asserts exactly n*n cells).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services.osrm_client import OsrmClient, OsrmTableError  # noqa: E402

DEFAULT_URL = "http://127.0.0.1:5000"
SEED_KMH = 30.0  # legacy seed speed (data/snapshots/danang-v1/README.md)
SEED_MIN_MINUTES = 5  # legacy seed floor


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Legacy seed distance (haversine, R=6371 km) — fallback label only."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def seed_cell(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Haversine seed minute/km, labelled so it is never read as OSRM."""
    km = haversine_km(lat1, lon1, lat2, lon2)
    return {"km": round(km, 2),
            "minutes": max(SEED_MIN_MINUTES, int(km / SEED_KMH * 60 + 0.5)),
            "source": "haversine_seed",
            "confidence": "low"}


def select_top(pois: list[dict], top: int) -> list[dict]:
    """Top-N POIs by rating (desc), tie-break poi_id; coords required, ids unique."""
    usable = [p for p in pois
              if isinstance(p.get("lat"), (int, float))
              and isinstance(p.get("lon"), (int, float))]
    usable.sort(key=lambda p: (-(p.get("rating") or 0.0), p["poi_id"]))
    picked = usable[:top]
    ids = [p["poi_id"] for p in picked]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate poi_id in top-N selection")
    return picked


def build(picked: list[dict], *, client: OsrmClient, snapshot: str,
          seed_fallback: bool = False, osrm_url: str = DEFAULT_URL,
          pairs_total: int | None = None) -> dict:
    """Query OSRM for all pairs and assemble the matrix document (pure)."""
    points = [(p["poi_id"], float(p["lat"]), float(p["lon"])) for p in picked]
    cells, stats = client.table(points)
    total = pairs_total if pairs_total is not None else len(points) ** 2

    if seed_fallback:
        for (a_id, a_lat, a_lon) in points:
            for (b_id, b_lat, b_lon) in points:
                if (a_id, b_id) in cells:
                    continue
                if a_id == b_id:  # trivially 0, never the seed's 5-min floor
                    cells[(a_id, b_id)] = {"km": 0.0, "minutes": 0,
                                           "source": "derived_self",
                                           "confidence": "high"}
                else:
                    cells[(a_id, b_id)] = seed_cell(a_lat, a_lon, b_lat, b_lon)

    haversine_cells = sum(1 for c in cells.values()
                          if c.get("source") == "haversine_seed")
    osrm_cells = sum(1 for c in cells.values() if c.get("source") == "osrm")
    infeasible = max(0, total - len(cells))  # holes = unroutable, never 0 (B3)
    mixed = haversine_cells > 0
    cells_out = {}
    for (a_id, b_id), cell in cells.items():
        if mixed:
            cells_out[f"{a_id}->{b_id}"] = cell  # per-cell source, no ambiguity
        else:
            cells_out[f"{a_id}->{b_id}"] = {"km": cell["km"],
                                            "minutes": cell["minutes"]}

    doc = {
        "snapshot": snapshot,
        "ids": [pid for pid, _lat, _lon in points],
        "n": len(points),
        "top_by": "rating",
        "mode": "motorbike",
        "method": "osrm_table_mld",
        "generated_by": "BE/tools/build_poi_matrix.py",
        "source": "mixed" if mixed else "osrm",
        "confidence": "low" if mixed else "high",
        "osrm_base_url": osrm_url,
        "extract": "vietnam-latest.osm.pbf (Geofabrik), MLD car profile",
        "built_at": date.today().isoformat(),
        "coverage": {"pairs_total": total,
                     "cells": len(cells),
                     "osrm": osrm_cells,
                     "haversine_seed": haversine_cells,
                     "infeasible": infeasible},
        "stats": {"requests": stats["requests"],
                  "failed_requests": stats["failed_requests"],
                  "failed_shards": stats["failed_shards"],
                  "last_error": stats["last_error"],
                  "elapsed_s": stats["elapsed_s"]},
        "cells": cells_out,
    }
    return doc


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pois", default=os.path.join("BE", "data", "snapshots", "danang-v1", "pois.json"))
    ap.add_argument("--out", default="", help="default: <pois dir>/matrix.json")
    ap.add_argument("--snapshot", default="", help="default: <pois dir> basename")
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--osrm-url", default=DEFAULT_URL)
    ap.add_argument("--chunk", type=int, default=100,
                    help="sources per /table request (<= osrm-routed --max-table-size)")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--seed-fallback", action="store_true",
                    help="fill OSRM holes with labelled haversine seed (B3: last resort)")
    ap.add_argument("--min-coverage", type=float, default=0.99,
                    help="exit 1 if (osrm+seed)/pairs below this")
    ap.add_argument("--dry-run", action="store_true", help="print selection, no network")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:  # Windows cp1252 console vs Vietnamese POI names
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    pois_dir = os.path.dirname(os.path.abspath(args.pois))
    snapshot = args.snapshot or os.path.basename(pois_dir)
    out = args.out or os.path.join(pois_dir, "matrix.json")
    with open(args.pois, encoding="utf-8") as f:
        data = json.load(f)
    picked = select_top(data["pois"], args.top)
    print(f"selected top-{len(picked)}/{len(data['pois'])} POIs by rating "
          f"(snapshot {snapshot}) -> {out}")
    if args.dry_run:
        for p in picked:
            print(f"  {p['poi_id']}  rating={p.get('rating')}  {p['name'][:50]}")
        return 0

    client = OsrmClient(args.osrm_url, chunk=args.chunk, timeout_s=args.timeout)
    doc = build(picked, client=client, snapshot=snapshot, seed_fallback=args.seed_fallback,
                osrm_url=args.osrm_url)
    cov = doc["coverage"]
    total = cov["pairs_total"]
    if cov["osrm"] == 0:  # nothing came from OSRM: server down / wrong URL
        print(f"ERROR: OSRM returned 0 cells at {args.osrm_url} — is osrm-routed "
              f"up? (stats={doc['stats']})", file=sys.stderr)
        return 2
    if cov["infeasible"] or doc["stats"]["failed_requests"]:
        print(f"WARNING: {cov['infeasible']} pair(s) unroutable/failed -> infeasible "
              f"(never 0, B3); failed_requests={doc['stats']['failed_requests']} "
              f"failed_shards={doc['stats']['failed_shards']} "
              f"last_error={doc['stats']['last_error']}")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    print(f"wrote {out}: n={doc['n']} cells={len(doc['cells'])}/{total} "
          f"osrm={cov['osrm']} haversine_seed={cov['haversine_seed']} "
          f"infeasible={cov['infeasible']} -> source={doc['source']}")
    ratio = (total - cov["infeasible"]) / total if total else 0.0
    if ratio < args.min_coverage:
        print(f"ERROR: coverage {ratio:.4f} < --min-coverage {args.min_coverage}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
