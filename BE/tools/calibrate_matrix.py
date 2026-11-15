"""Calibrate the OSRM motorbike matrix against VietMap motorcycle routes (Phase 3).

Samples POI pairs from `matrix.json`, stratified by matrix distance so short
city hops and cross-city trips are both measured, asks VietMap Route v4
(`vehicle=motorcycle`) for the same pairs and reports the error of the
minutes/km the planner actually uses:

- MAPE, median and p90 absolute % error, and signed bias (mean osrm/vietmap
  - 1), overall and per distance band, for time and distance;
- with `--osrm-url`, the same stats on OSRM's exact seconds too: the matrix
  stores whole minutes, so a 2-minute hop carries up to 25 % rounding error
  that no speed change can fix; the exact numbers isolate the model error;
- a single SPEED_SCALE suggestion for BE/tools/osrm/motorbike.lua, FITTED on
  half of the pairs and EVALUATED on the other half (projected: durations
  are scaled, turn/signal penalties are not, so rebuild and rerun to
  confirm). It uses exact OSRM times when available.

Usage (repo root; key in .env as VIETMAP_API_KEY=..., never committed):
    python BE/tools/calibrate_matrix.py --dry-run          # sample only
    python BE/tools/calibrate_matrix.py                    # 50 pairs
    python BE/tools/calibrate_matrix.py --pairs 50 --seed 20261029
    python BE/tools/calibrate_matrix.py --osrm-url http://127.0.0.1:5001

Writes MATRIX_CALIBRATION.json + .md next to the matrix. The key is read from
the environment or `--env-file` and is never printed or written (request
errors are reported with `apikey=REDACTED`).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services.matrix import load_matrix_doc  # noqa: E402

DEFAULT_SNAPSHOT = os.path.join("BE", "data", "snapshots", "danang-v1")
ENDPOINT = "https://maps.vietmap.vn/api/route/v4"
KEY_NAME = "VIETMAP_API_KEY"
# Matrix-km bands: short hops dominate a day plan, long trips test the graph.
BANDS = ((0.5, 2.0), (2.0, 5.0), (5.0, 10.0), (10.0, 20.0), (20.0, float("inf")))
TARGET_MAPE = 0.20


def read_key(env_file: str) -> str:
    """VIETMAP_API_KEY from the environment, else from a KEY=VALUE file."""
    key = os.environ.get(KEY_NAME, "").strip()
    if key or not env_file or not os.path.exists(env_file):
        return key
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            name, sep, value = line.strip().partition("=")
            if sep and name.strip() == KEY_NAME:
                return value.strip().strip("'\"")
    return ""


def band_of(km: float) -> int | None:
    for index, (lo, hi) in enumerate(BANDS):
        if lo <= km < hi:
            return index
    return None


def sample_pairs(ids: list[str], cells, n_pairs: int, seed: int) -> list[dict]:
    """`n_pairs` ordered pairs spread evenly over BANDS (seeded, reproducible)."""
    buckets: list[list[tuple[str, str]]] = [[] for _ in BANDS]
    for a in ids:
        for b in ids:
            if a == b:
                continue
            cell = cells.get(f"{a}->{b}")
            band = band_of(float(cell["km"])) if cell else None
            if band is not None:
                buckets[band].append((a, b))
    rng = random.Random(seed)
    per_band = [n_pairs // len(BANDS)] * len(BANDS)
    for index in range(n_pairs % len(BANDS)):
        per_band[index] += 1
    pairs = []
    for band, (bucket, want) in enumerate(zip(buckets, per_band)):
        for a, b in rng.sample(bucket, min(want, len(bucket))):
            cell = cells[f"{a}->{b}"]
            pairs.append({"from": a, "to": b, "band": band,
                          "osrm_km": float(cell["km"]),
                          "osrm_min": float(cell["minutes"])})
    return pairs


def _http_get_json(url: str, timeout_s: float) -> dict:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def vietmap_route(key: str, a: tuple[float, float], b: tuple[float, float], *,
                  endpoint: str = ENDPOINT, vehicle: str = "motorcycle",
                  transport=_http_get_json, timeout_s: float = 20.0) -> dict:
    """(lat, lon) -> {"km", "min"} from VietMap; raises RuntimeError (redacted)."""
    query = urllib.parse.urlencode([("apikey", key),
                                    ("point", f"{a[0]},{a[1]}"),
                                    ("point", f"{b[0]},{b[1]}"),
                                    ("vehicle", vehicle),
                                    ("points_encoded", "true")])
    try:
        data = transport(f"{endpoint}?{query}", timeout_s)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {endpoint}") from None
    except Exception as exc:  # noqa: BLE001 - message may echo the URL
        raise RuntimeError(str(exc).replace(key, "REDACTED")) from None
    paths = (data or {}).get("paths") or []
    if not paths or paths[0].get("distance") is None or paths[0].get("time") is None:
        message = (data or {}).get("messages") or (data or {}).get("message") \
            or (data or {}).get("code") or "no paths"
        raise RuntimeError(str(message).replace(key, "REDACTED"))
    return {"km": float(paths[0]["distance"]) / 1000.0,
            "min": float(paths[0]["time"]) / 60000.0}


def osrm_route(base_url: str, a: tuple[float, float], b: tuple[float, float], *,
               transport=_http_get_json, timeout_s: float = 20.0) -> dict:
    """Exact OSRM duration/distance for one pair (same graph as the matrix)."""
    url = (f"{base_url.rstrip('/')}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}"
           "?overview=false")
    data = transport(url, timeout_s)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(f"OSRM {data.get('code')}")
    route = data["routes"][0]
    return {"km": route["distance"] / 1000.0, "min": route["duration"] / 60.0}


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[int(q * (len(ordered) - 1))]


def error_stats(pairs: list[dict], kind: str, scale: float = 1.0,
                osrm_key: str = "") -> dict | None:
    """APE stats of `osrm_key` (default osrm_<kind>) * scale vs vietmap_<kind>."""
    osrm_key = osrm_key or f"osrm_{kind}"
    rows = [(p[osrm_key] * scale, p[f"vietmap_{kind}"]) for p in pairs
            if p.get(f"vietmap_{kind}") and p.get(osrm_key) is not None]
    if not rows:
        return None
    ape = [abs(o - v) / v for o, v in rows]
    ratio = [o / v for o, v in rows]
    return {"n": len(rows),
            "mape": round(statistics.mean(ape), 4),
            "median_ape": round(statistics.median(ape), 4),
            "p90_ape": round(_quantile(ape, 0.9), 4),
            "bias": round(statistics.mean(ratio) - 1.0, 4),
            "median_ratio": round(statistics.median(ratio), 4)}


def report(pairs: list[dict], target: float = TARGET_MAPE) -> dict:
    """Overall + per-band stats and a fit/holdout SPEED_SCALE suggestion."""
    ok = [p for p in pairs if p.get("vietmap_min")]
    exact = all(p.get("osrm_exact_min") is not None for p in ok) and bool(ok)
    out = {"pairs_requested": len(pairs), "pairs_ok": len(ok),
           "time": error_stats(ok, "min"), "distance": error_stats(ok, "km"),
           "time_exact": (error_stats(ok, "min", osrm_key="osrm_exact_min")
                          if exact else None),
           "bands": []}
    for index, (lo, hi) in enumerate(BANDS):
        members = [p for p in ok if p["band"] == index]
        out["bands"].append({
            "km": [lo, None if hi == float("inf") else hi],
            "time": error_stats(members, "min"),
            "time_exact": (error_stats(members, "min", osrm_key="osrm_exact_min")
                           if exact else None),
            "distance": error_stats(members, "km")})
    fit, holdout = ok[0::2], ok[1::2]
    if fit and holdout:
        key = "osrm_exact_min" if exact else "osrm_min"
        # osrm/vietmap > 1 means OSRM is too slow: speeds go UP by that ratio.
        factor = statistics.median(p[key] / p["vietmap_min"] for p in fit)
        out["speed_scale"] = {
            "multiply_speed_scale_by": round(factor, 3),
            "fitted_on": len(fit),
            "fitted_with": key,
            "holdout": error_stats(holdout, "min", osrm_key=key),
            "holdout_projected": error_stats(holdout, "min", scale=1.0 / factor,
                                             osrm_key=key),
            "note": "projected: scales durations only; rebuild and rerun to confirm",
        }
    time_mape = (out["time"] or {}).get("mape")
    out["target_mape"] = target
    out["passed"] = time_mape is not None and time_mape <= target
    return out


def markdown(doc: dict) -> str:
    rep = doc["report"]

    def row(label: str, stats: dict | None) -> str:
        if not stats:
            return f"| {label} | 0 | - | - | - | - |"
        return (f"| {label} | {stats['n']} | {stats['mape']:.1%} | "
                f"{stats['median_ape']:.1%} | {stats['p90_ape']:.1%} | "
                f"{stats['bias']:+.1%} |")

    lines = [
        "# Matrix calibration vs VietMap (motorcycle)",
        "",
        f"- Matrix: `{doc['matrix']}` ({doc['matrix_mode']}, OSM "
        f"{doc['osm_timestamp']}, profile sha256 `{doc['profile_sha256'][:12]}`)",
        f"- Reference: VietMap Route v4 `vehicle={doc['vehicle']}`, run {doc['run_date']}",
        f"- Pairs: {rep['pairs_ok']}/{rep['pairs_requested']} answered, seed "
        f"{doc['seed']}, stratified by matrix km",
        f"- Target: time MAPE <= {rep['target_mape']:.0%} -> "
        f"**{'PASS' if rep['passed'] else 'FAIL'}**",
        "",
        "| Time (minutes) | n | MAPE | median APE | p90 APE | bias |",
        "|---|---|---|---|---|---|",
        row("all (matrix minutes)", rep["time"]),
    ]
    for band in rep["bands"]:
        lo, hi = band["km"]
        lines.append(row(f"{lo}-{hi if hi else '+'} km", band["time"]))
    if rep.get("time_exact"):
        lines.append(row("all (exact OSRM seconds)", rep["time_exact"]))
        for band in rep["bands"]:
            lo, hi = band["km"]
            lines.append(row(f"{lo}-{hi if hi else '+'} km exact",
                             band["time_exact"]))
    lines += ["", "| Distance (km) | n | MAPE | median APE | p90 APE | bias |",
              "|---|---|---|---|---|---|", row("all", rep["distance"])]
    scale = rep.get("speed_scale")
    if scale:
        lines += ["", f"SPEED_SCALE suggestion: multiply by "
                      f"**{scale['multiply_speed_scale_by']}** (fitted on "
                      f"{scale['fitted_on']} pairs). Holdout time MAPE "
                      f"{scale['holdout']['mape']:.1%} now, "
                      f"{scale['holdout_projected']['mape']:.1%} projected "
                      f"({scale['note']})."]
    errors = [p for p in doc["pairs"] if p.get("error")]
    if errors:
        lines += ["", f"{len(errors)} pair(s) failed: "
                      + "; ".join(sorted({p['error'] for p in errors}))[:300]]
    return "\n".join(lines) + "\n"


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--pairs", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261029)
    ap.add_argument("--env-file", default=".env")
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument("--vehicle", default="motorcycle")
    ap.add_argument("--sleep", type=float, default=0.3,
                    help="seconds between VietMap requests")
    ap.add_argument("--target-mape", type=float, default=TARGET_MAPE)
    ap.add_argument("--osrm-url", default="",
                    help="also fetch exact OSRM times (same graph as the matrix)")
    ap.add_argument("--out-dir", default="", help="default: --snapshot-dir")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the sampled pairs, no network")
    return ap.parse_args(argv)


def main(argv=None, transport=_http_get_json, wait=time.sleep) -> int:
    args = parse_args(argv)
    matrix_path = os.path.join(args.snapshot_dir, "matrix.json")
    matrix = load_matrix_doc(matrix_path)
    with open(os.path.join(args.snapshot_dir, "pois.json"), encoding="utf-8") as f:
        pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
    pairs = sample_pairs(matrix["ids"], matrix["cells"], args.pairs, args.seed)
    for p in pairs:
        p["from_name"] = pois.get(p["from"], {}).get("name", "")
        p["to_name"] = pois.get(p["to"], {}).get("name", "")
    print(f"sampled {len(pairs)} pairs over {len(BANDS)} km bands (seed {args.seed})")
    if args.dry_run:
        for p in pairs:
            print(f"  band {p['band']} {p['osrm_km']:6.2f} km {p['osrm_min']:4.0f} min  "
                  f"{p['from_name'][:30]} -> {p['to_name'][:30]}")
        return 0

    key = read_key(args.env_file)
    if not key:
        print(f"ERROR: {KEY_NAME} not set (environment or {args.env_file})",
              file=sys.stderr)
        return 2
    for index, p in enumerate(pairs):
        a, b = pois[p["from"]], pois[p["to"]]
        try:
            vm = vietmap_route(key, (a["lat"], a["lon"]), (b["lat"], b["lon"]),
                               endpoint=args.endpoint, vehicle=args.vehicle,
                               transport=transport)
            p["vietmap_km"] = round(vm["km"], 3)
            p["vietmap_min"] = round(vm["min"], 2)
        except RuntimeError as exc:
            p["error"] = str(exc)
        if args.osrm_url:
            try:
                exact = osrm_route(args.osrm_url, (a["lat"], a["lon"]),
                                   (b["lat"], b["lon"]), transport=transport)
                p["osrm_exact_min"] = round(exact["min"], 2)
                p["osrm_exact_km"] = round(exact["km"], 3)
            except Exception as exc:  # noqa: BLE001 - exact numbers are optional
                p["osrm_error"] = str(exc)
        if index + 1 < len(pairs):
            wait(args.sleep)

    rep = report(pairs, args.target_mape)
    osrm_meta = matrix.get("osrm") or {}
    doc = {"matrix": matrix_path.replace(os.sep, "/"),
           "matrix_mode": matrix.get("mode", "unspecified"),
           "osm_timestamp": osrm_meta.get("osm_timestamp", "unknown"),
           "profile_sha256": osrm_meta.get("profile_sha256", "unknown"),
           "vehicle": args.vehicle, "endpoint": args.endpoint,
           "run_date": date.today().isoformat(), "seed": args.seed,
           "report": rep, "pairs": pairs}
    out_dir = args.out_dir or args.snapshot_dir
    with open(os.path.join(out_dir, "MATRIX_CALIBRATION.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    text = markdown(doc)
    with open(os.path.join(out_dir, "MATRIX_CALIBRATION.md"), "w",
              encoding="utf-8") as f:
        f.write(text)
    print(text)
    if rep["pairs_ok"] == 0:
        print("ERROR: VietMap answered no pair", file=sys.stderr)
        return 2
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
