"""Grid-search motorbike.lua calibration knobs offline (Phase 3).

Reuses the VietMap answers of one `calibrate_matrix.py` run (no new VietMap
request): for every (SPEED_SCALE, CLASS_SPREAD) it builds a graph from the
same `danang.osm.pbf`, routes the answered pairs with exact OSRM `/route`
seconds and scores time MAPE on the FIT half (even indices, as
`calibrate_matrix.report` splits) and the HOLDOUT half, plus distance MAPE
(route choice) and the signed bias per km band.

Pick by FIT, report HOLDOUT: a holdout far above the fit is overfitting.

    python BE/tools/osrm/grid_search.py \\
        --calibration BE/data/snapshots/danang-v1/calibration/vietmap_baseline.json \\
        --pbf <data_dir>/danang.osm.pbf --workdir <tmp> \\
        --scales 1.0,1.1,1.15,1.2 --spreads 0.1,0.2,0.35,0.5

Needs docker and the ghcr.io/project-osrm/osrm-backend:v5.27.1 image.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
IMAGE = "ghcr.io/project-osrm/osrm-backend:v5.27.1"
PROFILE = os.path.join(_REPO_ROOT, "BE", "tools", "osrm", "motorbike.lua")
POIS = os.path.join(_REPO_ROOT, "BE", "data", "snapshots", "danang-v1", "pois.json")
CONTAINER = "osrm-grid-search"


def variant(profile: str, scale: float, spread: float) -> str:
    """motorbike.lua text with the two knobs replaced (must both exist)."""
    out, n1 = re.subn(r"^SPEED_SCALE = .*$", f"SPEED_SCALE = {scale}", profile,
                      flags=re.M)
    out, n2 = re.subn(r"^CLASS_SPREAD = .*$", f"CLASS_SPREAD = {spread}", out,
                      flags=re.M)
    if (n1, n2) != (1, 1):
        raise ValueError("motorbike.lua must define SPEED_SCALE and CLASS_SPREAD once")
    return out


def _run(*cmd: str) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def build_graph(directory: str, pbf: str, profile_text: str) -> None:
    if os.path.exists(os.path.join(directory, "danang.osrm.mldgr")):
        return
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "motorbike.lua"), "w", encoding="utf-8") as f:
        f.write(profile_text)
    shutil.copy(pbf, os.path.join(directory, "danang.osm.pbf"))
    mount = ["-v", f"{directory}:/data"]
    _run("docker", "run", "--rm", *mount, "-v",
         f"{directory}/motorbike.lua:/opt/motorbike.lua:ro", IMAGE,
         "osrm-extract", "-p", "/opt/motorbike.lua", "/data/danang.osm.pbf")
    _run("docker", "run", "--rm", *mount, IMAGE, "osrm-partition", "/data/danang.osrm")
    _run("docker", "run", "--rm", *mount, IMAGE, "osrm-customize", "/data/danang.osrm")


def route(port: int, a: dict, b: dict) -> tuple[float, float]:
    url = (f"http://127.0.0.1:{port}/route/v1/driving/{a['lon']},{a['lat']};"
           f"{b['lon']},{b['lat']}?overview=false")
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        r = json.loads(resp.read())["routes"][0]
    return r["duration"] / 60.0, r["distance"] / 1000.0


def serve(directory: str, port: int) -> None:
    subprocess.run(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    _run("docker", "run", "-d", "--name", CONTAINER, "-p", f"127.0.0.1:{port}:5000",
         "-v", f"{directory}:/data", IMAGE, "osrm-routed", "--algorithm", "mld",
         "/data/danang.osrm")


def score(rows: list[tuple[float, float, float, float, int]]) -> dict:
    """rows: (osrm_min, vietmap_min, osrm_km, vietmap_km, band)."""
    def mape(pairs):
        return round(statistics.mean(abs(o - v) / v for o, v in pairs), 4)

    fit, holdout = rows[0::2], rows[1::2]
    bias = {}
    for band in sorted({r[4] for r in rows}):
        members = [r for r in rows if r[4] == band]
        bias[str(band)] = round(statistics.mean(r[0] / r[1] for r in members) - 1, 3)
    return {"fit": mape([(r[0], r[1]) for r in fit]),
            "holdout": mape([(r[0], r[1]) for r in holdout]),
            "all": mape([(r[0], r[1]) for r in rows]),
            "km_mape": mape([(r[2], r[3]) for r in rows]),
            "bias_by_band": bias}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--calibration", required=True,
                    help="MATRIX_CALIBRATION.json-shaped file with VietMap answers")
    ap.add_argument("--pbf", required=True, help="danang.osm.pbf from build_osrm.sh")
    ap.add_argument("--workdir", required=True, help="scratch dir OUTSIDE the repo")
    ap.add_argument("--scales", default="1.0,1.1,1.15,1.2")
    ap.add_argument("--spreads", default="0.1,0.2,0.35,0.5")
    ap.add_argument("--port", type=int, default=5010)
    ap.add_argument("--out", default="", help="write results JSON here")
    args = ap.parse_args(argv)

    with open(args.calibration, encoding="utf-8") as f:
        calibration = json.load(f)
    with open(POIS, encoding="utf-8") as f:
        pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
    with open(PROFILE, encoding="utf-8") as f:
        profile = f.read()
    answered = [p for p in calibration["pairs"] if p.get("vietmap_min")]
    results = []
    grid = itertools.product([float(x) for x in args.scales.split(",")],
                             [float(x) for x in args.spreads.split(",")])
    try:
        for scale, spread in grid:
            directory = os.path.join(os.path.abspath(args.workdir),
                                     f"scale{scale}_spread{spread}")
            build_graph(directory, os.path.abspath(args.pbf),
                        variant(profile, scale, spread))
            serve(directory, args.port)
            first = answered[0]
            for _ in range(60):
                try:
                    route(args.port, pois[first["from"]], pois[first["to"]])
                    break
                except Exception:  # noqa: BLE001 - server still loading
                    time.sleep(0.5)
            rows = []
            for p in answered:
                minutes, km = route(args.port, pois[p["from"]], pois[p["to"]])
                rows.append((minutes, p["vietmap_min"], km, p["vietmap_km"], p["band"]))
            result = {"speed_scale": scale, "class_spread": spread, **score(rows)}
            results.append(result)
            print(json.dumps(result), flush=True)
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    best = min(results, key=lambda r: r["fit"])
    print("best by fit:", json.dumps(best))
    if args.out:
        doc = {"calibration": args.calibration.replace(os.sep, "/"),
               "pairs": len(answered), "selection": "min fit MAPE",
               "best": best, "grid": results}
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
