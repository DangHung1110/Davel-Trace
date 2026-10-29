"""Append verified snapshot POIs to the committed OSRM matrix (T010b follow-up).

Why: `build_poi_matrix.py` selects the top-N POIs by rating, which is almost
all restaurants/cafes. The optimizer can only use POIs that are BOTH verified
and matrix-connected, so a category-balanced plan (F1: food + sightseeing) is
impossible when every routable POI is a food stop. This tool APPENDS rows/
columns for verified POIs the matrix does not cover yet, keeping every
existing cell byte-for-byte intact.

Same fetch path as the builder: local `osrm-routed` `/table` (MLD, motorbike/
car profile), no haversine, unroutable pairs stay OMITTED (B3 infeasible —
never a silent 0).

Usage (repo root, OSRM up on 127.0.0.1:5000):
    python BE/tools/expand_poi_matrix.py --dry-run       # selection only
    python BE/tools/expand_poi_matrix.py                 # merge into matrix.json
    python BE/tools/expand_poi_matrix.py --verified-only # default: only verified

Guards:
- a timestamped backup of matrix.json is written OUTSIDE the repo before the
  write (override with --backup);
- existing cells are never rewritten (merge only adds missing pairs);
- the artifact stays homogeneous (`source: "osrm"`, no per-cell source) only
  when every cell came from this OSRM; otherwise each cell keeps its source.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import date, datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services.osrm_client import OsrmClient  # noqa: E402

DEFAULT_URL = "http://127.0.0.1:5000"
DEFAULT_SNAPSHOT = os.path.join("BE", "data", "snapshots", "danang-v1")
ROW_SEP = "->"
# osrm-routed is started with --max-table-size 300 (see build_poi_matrix.py);
# the whole point set travels in one request, so n must stay under it.
MAX_TABLE_SIZE = 300


def _has_coords(poi: dict) -> bool:
    return (isinstance(poi.get("lat"), (int, float))
            and isinstance(poi.get("lon"), (int, float)))


def select_expansion(pois: list[dict], existing_ids: list[str],
                     verified_only: bool = True) -> list[dict]:
    """Verified, coordinate-bearing POIs the matrix does not cover yet.

    Sorted by poi_id so repeated runs produce an identical append order.
    Unverified candidates are excluded unless `verified_only=False`; the
    optimizer would never pick them anyway (FR-013).
    """
    seen = set(existing_ids)
    picked = []
    for poi in pois:
        pid = poi.get("poi_id")
        if not pid or pid in seen:
            continue
        if verified_only and poi.get("verified") is not True:
            continue
        if not _has_coords(poi):
            continue
        picked.append(poi)
    picked.sort(key=lambda p: p["poi_id"])
    return picked


def category_counts(pois: list[dict]) -> dict[str, int]:
    """Count POIs per canonical category (`cat`, legacy `type` fallback)."""
    counts: dict[str, int] = {}
    for poi in pois:
        cat = str(poi.get("cat") or poi.get("type") or "?").strip().lower()
        counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items()))


def merge(existing: dict, new_pois: list[dict], cells: dict,
          *, osrm_url: str, elapsed_s: float, requests: int = 0,
          failed_requests: int = 0, failed_shards: list | None = None,
          last_error: str | None = None) -> tuple[dict, dict]:
    """Append new POIs + their cells to `existing`; never rewrite old cells.

    `cells` = {(a_id, b_id): {"km", "minutes", "source"?}} from the OSRM
    table for the FULL point set (old + new). Only pairs touching a new POI
    are written. Returns `(doc, report)`; `report` lists missing pairs.
    """
    old_ids = list(existing["ids"])
    new_ids = [p["poi_id"] for p in new_pois]
    overlap = set(old_ids) & set(new_ids)
    if overlap:
        raise ValueError(f"POIs already in matrix: {sorted(overlap)[:5]}")
    ids = old_ids + new_ids
    new_set = set(new_ids)

    merged = dict(existing["cells"])  # old cells stay untouched
    missing = []
    added = 0
    for a in ids:
        for b in ids:
            if a not in new_set and b not in new_set:
                continue  # old->old pair: keep the committed value
            cell = cells.get((a, b))
            if cell is None:
                missing.append(f"{a}{ROW_SEP}{b}")
                continue
            merged[f"{a}{ROW_SEP}{b}"] = {"km": cell["km"],
                                          "minutes": cell["minutes"]}
            added += 1

    # Per-cell source only when the artifact is no longer homogeneous.
    mixed = any(c.get("source") not in (None, "osrm")
                for c in existing["cells"].values())
    if mixed:
        for key, cell in list(merged.items()):
            if "source" in cell:
                continue
            src = (existing["cells"].get(key) or {}).get("source", "osrm")
            merged[key] = {**cell, "source": src}

    n = len(ids)
    total = n * n
    haversine = sum(1 for c in merged.values()
                    if c.get("source") == "haversine_seed")
    stats = dict(existing.get("stats") or {})
    stats["requests"] = int(stats.get("requests", 0)) + int(requests)
    stats["failed_requests"] = int(stats.get("failed_requests", 0)) + int(failed_requests)
    stats["failed_shards"] = list(stats.get("failed_shards") or []) + list(failed_shards or [])
    stats["last_error"] = last_error or stats.get("last_error")
    stats["elapsed_s"] = round(float(stats.get("elapsed_s", 0.0)) + elapsed_s, 3)

    doc = dict(existing)
    doc["ids"] = ids
    doc["n"] = n
    doc["coverage"] = {
        "pairs_total": total,
        "cells": len(merged),
        "osrm": len(merged) - haversine,
        "haversine_seed": haversine,
        "infeasible": total - len(merged),
    }
    doc["stats"] = stats
    doc["expanded_at"] = datetime.now().isoformat(timespec="seconds")
    doc["expansions"] = list(existing.get("expansions") or []) + [{
        "at": date.today().isoformat(),
        "osrm_base_url": osrm_url,
        "added_pois": new_ids,
        "by_category": category_counts(new_pois),
        "cells_added": added,
        "cells_missing": len(missing),
        "elapsed_s": round(elapsed_s, 3),
    }]
    doc["cells"] = merged
    return doc, {"added": added, "missing": missing, "n": n}


def _backup_path(matrix_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join(tempfile.gettempdir(), "matrix-backups")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{os.path.basename(matrix_path)}.{ts}.bak")


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--pois", default="", help="default: <snapshot-dir>/pois.json")
    ap.add_argument("--matrix", default="", help="default: <snapshot-dir>/matrix.json")
    ap.add_argument("--osrm-url", default=DEFAULT_URL)
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--backup", default="", help="default: OS temp dir, timestamped")
    ap.add_argument("--include-unverified", action="store_true",
                    help="also add unverified POIs (NOT recommended: FR-013)")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:  # Windows cp1252 console vs Vietnamese names
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    pois_path = args.pois or os.path.join(args.snapshot_dir, "pois.json")
    matrix_path = args.matrix or os.path.join(args.snapshot_dir, "matrix.json")
    with open(pois_path, encoding="utf-8") as f:
        pois = json.load(f)["pois"]
    with open(matrix_path, encoding="utf-8") as f:
        existing = json.load(f)

    new_pois = select_expansion(pois, existing["ids"],
                                verified_only=not args.include_unverified)
    n_total = len(existing["ids"]) + len(new_pois)
    print(f"matrix n={existing['n']} -> {n_total} "
          f"(+{len(new_pois)} POIs); by category {category_counts(new_pois)}")
    if not new_pois:
        print("nothing to add; matrix already covers every verified POI")
        return 0
    if args.dry_run:
        for p in new_pois:
            print(f"  {p['poi_id']}  {p.get('cat')}  rating={p.get('rating')}  "
                  f"{p.get('name')}")
        return 0
    if n_total > MAX_TABLE_SIZE:
        print(f"ERROR: {n_total} points > max-table-size {MAX_TABLE_SIZE}; "
              f"raise osrm-routed --max-table-size or split the build",
              file=sys.stderr)
        return 2

    points = [(p["poi_id"], float(p["lat"]), float(p["lon"]))
              for p in existing_pois_by_id(pois, existing["ids"]) + new_pois]
    client = OsrmClient(args.osrm_url, chunk=args.chunk, timeout_s=args.timeout)
    t0 = time.monotonic()
    cells, stats = client.table(points)
    elapsed = time.monotonic() - t0
    if not cells:
        print(f"ERROR: OSRM returned 0 cells at {args.osrm_url} — is osrm-routed "
              f"up? (stats={stats})", file=sys.stderr)
        return 2

    doc, report = merge(existing, new_pois, cells, osrm_url=args.osrm_url,
                        elapsed_s=elapsed, requests=stats["requests"],
                        failed_requests=stats["failed_requests"],
                        failed_shards=stats.get("failed_shards"),
                        last_error=stats.get("last_error"))
    backup = args.backup or _backup_path(matrix_path)
    os.makedirs(os.path.dirname(os.path.abspath(backup)), exist_ok=True)
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(matrix_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")

    cov = doc["coverage"]
    print(f"backup: {backup}")
    print(f"wrote {matrix_path}: n={doc['n']} cells={cov['cells']}/{cov['pairs_total']} "
          f"osrm={cov['osrm']} infeasible={cov['infeasible']} "
          f"added={report['added']} elapsed={elapsed:.2f}s")
    if report["missing"]:
        print(f"WARNING: {len(report['missing'])} new pair(s) unroutable (B3: "
              f"left absent, never 0): {report['missing'][:5]}")
        return 1
    return 0


def existing_pois_by_id(pois: list[dict], ids: list[str]) -> list[dict]:
    """Matrix ids in matrix order (raises if a committed id lost its POI)."""
    by_id = {p["poi_id"]: p for p in pois}
    out = []
    for pid in ids:
        poi = by_id.get(pid)
        if poi is None or not _has_coords(poi):
            raise ValueError(f"matrix id {pid} has no POI/coords in pois.json")
        out.append(poi)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
