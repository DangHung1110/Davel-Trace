"""Build `danang-v2/matrix.json` (dense-v1, motorbike) for every v2 POI.

    python BE/tools/build_matrix_v2.py --car <car matrix.json>

Rows of POIs already in the calibrated motorbike matrix of `danang-v1`
(OSRM `motorbike.lua`, checked against VietMap, MATRIX_CALIBRATION.md) are
copied unchanged. POIs added in v2 (OpenStreetMap, Hội An / Bà Nà / Mỹ Sơn)
have no motorbike row yet; they are ESTIMATED from an OSRM `car` matrix that
covers them (built on feat/p0-data-v2, commit e3aaa66):

    minutes_motorbike = a + b * km_car        (least squares)
    km_motorbike      = km_car * r(km band)   (median ratio per band)

fitted on the pairs both matrices share and measured on held-out POIs (the
same situation as a new POI). A pair whose far end has no car row borrows the
row of the nearest POI that has one (+ 1.3 x straight-line km). Every
estimated id is listed in `coverage.estimated_ids`.

Exact rows need a local OSRM with the motorbike profile; then rebuild the
whole file with `BE/tools/build_poi_matrix.py` (see BE/tools/osrm/build_osrm.sh).

Get the car matrix once (48 MB, not kept in the repo):

    git show 4500c04bf73cf6b25333d064196ba31355089997 > /tmp/car_matrix_v21.json
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import os
import random
import statistics
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V1 = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v1", "matrix.json")
V2 = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
CAR_BLOB = "4500c04bf73cf6b25333d064196ba31355089997"
KM_EDGES = (0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 60)
DETOUR = 1.3
HOLDOUT_POIS = 130
SEED = 20261119


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def haversine_km(a: dict, b: dict) -> float:
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(x))


def band(km: float) -> int:
    return max(0, bisect.bisect_right(KM_EDGES, km) - 1)


class CarToMotorbike:
    """minutes = a + b * km_car; km = km_car * ratio[band]."""

    def __init__(self, a: float, b: float, ratio: dict[int, float]):
        self.a, self.b, self.ratio = a, b, ratio

    @classmethod
    def fit(cls, rows: list[tuple[float, float, float, float]]) -> "CarToMotorbike":
        """rows = (car_km, car_min, motor_km, motor_min)."""
        n = len(rows)
        sx = sum(r[0] for r in rows)
        sy = sum(r[3] for r in rows)
        sxx = sum(r[0] ** 2 for r in rows)
        sxy = sum(r[0] * r[3] for r in rows)
        b = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        a = (sy - b * sx) / n
        by_band: dict[int, list[float]] = {}
        for ck, _, mk, _ in rows:
            if ck > 0:
                by_band.setdefault(band(ck), []).append(mk / ck)
        return cls(a, b, {k: statistics.median(v) for k, v in sorted(by_band.items())})

    def minutes(self, car_km: float) -> int:
        return 0 if car_km <= 0 else max(1, round(self.a + self.b * car_km))

    def km(self, car_km: float) -> float:
        return round(car_km * self.ratio.get(band(car_km), 0.95), 2)

    def describe(self) -> dict:
        return {"model": "minutes = a + b * km_car; km = km_car * ratio[km band]",
                "a": round(self.a, 3), "b": round(self.b, 4),
                "km_band_edges": list(KM_EDGES),
                "km_ratio": {str(KM_EDGES[k]): round(v, 3) for k, v in self.ratio.items()}}


def pair_rows(a_ids, b_ids, car_cells, mot, limit):
    idx = {pid: i for i, pid in enumerate(mot["ids"])}
    out = []
    for a in a_ids:
        for b in b_ids:
            if a == b:
                continue
            c = car_cells.get(f"{a}->{b}")
            m = mot["minutes"][idx[a]][idx[b]]
            if c is None or m is None:
                continue
            out.append((float(c["km"]), float(c["minutes"]), float(mot["km"][idx[a]][idx[b]]), float(m)))
            if len(out) >= limit:
                return out
    return out


def calibrate(car, mot):
    """Fit on shared POIs, test on held-out POIs (-> model, report)."""
    shared = sorted(set(car["ids"]) & set(mot["ids"]))
    rng = random.Random(SEED)
    rng.shuffle(shared)
    hold, train = shared[:HOLDOUT_POIS], shared[HOLDOUT_POIS:]
    model = CarToMotorbike.fit(pair_rows(train, train, car["cells"], mot, 200_000))
    test = pair_rows(hold, train, car["cells"], mot, 50_000)
    ape = [abs(model.minutes(ck) - mm) / mm for ck, _, _, mm in test if mm >= 3]
    abs_err = [abs(model.minutes(ck) - mm) for ck, _, _, mm in test]
    km_ape = [abs(model.km(ck) - mk) / mk for ck, _, mk, _ in test if mk >= 1]
    ape.sort()
    report = {**model.describe(), "train_pois": len(train), "holdout_pois": len(hold),
              "holdout_pairs": len(test),
              "minutes_mape_pct": round(100 * statistics.mean(ape), 1),
              "minutes_median_ape_pct": round(100 * statistics.median(ape), 1),
              "minutes_p90_ape_pct": round(100 * ape[int(0.9 * len(ape))], 1),
              "minutes_median_abs_err": statistics.median(abs_err),
              "minutes_bias": round(statistics.mean(model.minutes(ck) - mm for ck, _, _, mm in test), 2),
              "km_mape_pct": round(100 * statistics.mean(km_ape), 1)}
    return model, report


def build(pois_path, v1_path, car_path, out_path):
    doc = json.load(open(pois_path, encoding="utf-8"))
    pois = {p["poi_id"]: p for p in doc["pois"]}
    mot = json.load(open(v1_path, encoding="utf-8"))
    assert mot.get("format") == "dense-v1", "danang-v1 matrix must be dense-v1"
    m_idx = {pid: i for i, pid in enumerate(mot["ids"])}
    ids = [pid for pid in mot["ids"] if pid in pois] + sorted(pid for pid in pois if pid not in m_idx)
    new_ids = [pid for pid in ids if pid not in m_idx]
    car = json.load(open(car_path, encoding="utf-8")) if new_ids else None
    model, report = calibrate(car, mot) if car else (None, None)
    car_ids = set(car["ids"]) if car else set()
    car_cells = car["cells"] if car else {}

    def nearest_car(pid):
        p = pois[pid]
        best = min((haversine_km(p, pois[c]), c) for c in car_ids if c in pois and c != pid)
        return best[1], best[0]

    proxy = {}
    for pid in ids:
        if pid not in car_ids and new_ids:
            proxy[pid] = nearest_car(pid)

    def car_km(a, b):
        """Car road km a->b, through the nearest car-matrix POI when needed."""
        extra = 0.0
        if a not in car_ids:
            a, d = proxy[a]
            extra += DETOUR * d
        if b not in car_ids:
            b, d = proxy[b]
            extra += DETOUR * d
        if a == b:
            return extra
        cell = car_cells.get(f"{a}->{b}")
        return None if cell is None else float(cell["km"]) + extra

    minutes, km = [], []
    counts = {"osrm_motorbike": 0, "car_calibrated": 0, "via_nearest_poi": 0, "missing": 0}
    for a in ids:
        row_m, row_k = [], []
        for b in ids:
            if a == b:
                row_m.append(0)
                row_k.append(0.0)
                continue
            if a in m_idx and b in m_idx:
                mm, mk = mot["minutes"][m_idx[a]][m_idx[b]], mot["km"][m_idx[a]][m_idx[b]]
                row_m.append(mm)
                row_k.append(mk)
                counts["osrm_motorbike" if mm is not None else "missing"] += 1
                continue
            ck = car_km(a, b)
            if ck is None:
                row_m.append(None)
                row_k.append(None)
                counts["missing"] += 1
                continue
            row_m.append(model.minutes(ck))
            row_k.append(model.km(ck))
            counts["via_nearest_poi" if (a in proxy or b in proxy) else "car_calibrated"] += 1
        minutes.append(row_m)
        km.append(row_k)

    v1_est = list((mot.get("coverage") or {}).get("estimated_ids") or [])
    meta = {
        "snapshot": "danang-v2",
        "format": "dense-v1",
        "mode": "motorbike",
        "method": "osrm_table_mld (danang-v1 rows) + car->motorbike calibration (v2 rows)",
        "generated_by": "BE/tools/build_matrix_v2.py",
        "source": "osrm",
        "confidence": "high for danang-v1 rows, estimated for coverage.estimated_ids",
        "osrm": mot.get("osrm"),
        "built_at": date.today().isoformat(),
        "inputs": {"v1_matrix": "BE/data/snapshots/danang-v1/matrix.json",
                   "v1_matrix_sha256": _sha256(v1_path),
                   "car_matrix_blob": CAR_BLOB if car else None,
                   "car_matrix_sha256": _sha256(car_path) if car else None,
                   "pois": "BE/data/snapshots/danang-v2/pois.json"},
        "coverage": {"pairs_total": len(ids) * len(ids), **counts,
                     "estimated_ids": sorted(set(v1_est) | set(new_ids)),
                     "proxy_of": {pid: {"via": v, "km": round(d, 3)}
                                  for pid, (v, d) in sorted(proxy.items())}},
        "calibration": report,
        "rebuild_exact": "OSRM motorbike (BE/tools/osrm/build_osrm.sh) + BE/tools/build_poi_matrix.py",
        "ids": ids,
        "n": len(ids),
    }
    lines = ["{"]
    for key, value in meta.items():
        lines.append(f" {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},")
    for key, rows in (("minutes", minutes), ("km", km)):
        lines.append(f' "{key}": [')
        lines.append(",\n".join("  " + json.dumps(r, separators=(",", ":")) for r in rows))
        lines.append(" ]," if key == "minutes" else " ]")
    lines.append("}")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--car", help="car-profile matrix covering the new POIs (cells format)")
    ap.add_argument("--v1", default=V1)
    ap.add_argument("--pois", default=os.path.join(V2, "pois.json"))
    ap.add_argument("--out", default=os.path.join(V2, "matrix.json"))
    a = ap.parse_args(argv)
    meta = build(a.pois, a.v1, a.car, a.out)
    print(json.dumps({"n": meta["n"], "coverage": {k: v for k, v in meta["coverage"].items()
                                                   if k not in ("estimated_ids", "proxy_of")},
                      "estimated_ids": len(meta["coverage"]["estimated_ids"]),
                      "calibration": meta["calibration"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
