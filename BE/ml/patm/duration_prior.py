"""Dwell duration prior via Empirical Bayes (T064 M2, lane A). NO TICK (gold pending).

(1) Dwells from Foursquare-TKY: consecutive same-venue check-ins by one
user, gap 5min..4h (beyond = re-visit, unidentifiable; transport
excluded as commute noise). Raw TSVs stay in TEMP, never committed.
(2) Per-category empirical {p25,p50,p75} shrunk toward nac-1
CATEGORY_DEFAULTS by sample count: post = (n*emp + k*default)/(n+k),
k=20. Cap-pinned medians (revisit-dominated) ABSTAIN -> nac-1 default.
Confidence: n<20 low, <200 medium, else high.
(3) Hook (phase-PR): optimizer reads get_p50(), validator p75-buffer
reads get_p75() — replacing nac-1 constants, nac-1 kept as fallback
inside get_* when the JSON/category is missing.
(4) Smoke on seed 7 (log-MAE vs defaults, preliminary). REAL eval
(coverage >=80%, MAE >=10% better) waits for user checklist (gold
durations) — PENDING, see docs/dwell-prior.md.

Usage:
  python BE/ml/patm/duration_prior.py --data-dir <tsmc-txt-dir> --out BE/ml/patm/duration_prior.json
  python BE/ml/patm/duration_prior.py --smoke
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import math
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.ml.patm.build_prior import load_crosswalk, parse_time, resolve  # noqa: E402
from BE.ml.patm.estimate_duration import CATEGORY_DEFAULTS, canonical_category  # noqa: E402

SHRINK_K = 20
MIN_GAP_MIN, MAX_GAP_MIN = 5.0, 4.0 * 60
# Dwell = same-venue consecutive gap. Beyond 4h = re-visit (unidentifiable
# from 2 check-ins), NOT a visit — filtered. Transport excluded outright:
# commuter re-checkins (median 9h) don't transfer to tourist transit dwell.
DWELL_EXCLUDED = {"transport"}

_prior = None


def extract_dwells(data_dir: str) -> dict[str, list[float]]:
    xw = load_crosswalk()
    explicit: dict[str, str] = {}
    for canon, names in xw.items():
        if canon.startswith("_") or canon in ("rules", "excluded"):
            continue
        for n in names:
            explicit[n] = canon
    for n in xw.get("excluded", []):
        explicit[n] = "EXCLUDE"
    dwells: dict[str, list[float]] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "*.txt"))):
        if "readme" in path.lower() or "_TKY" not in path:
            continue
        last: dict[str, tuple] = {}
        with open(path, encoding="ISO-8859-1") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) < 8:
                    continue
                try:
                    dt = parse_time(p[7])
                except ValueError:
                    continue
                u, venue = p[0], p[1]
                if u in last and last[u][1] == venue:
                    gap = (dt - last[u][0]).total_seconds() / 60
                    if MIN_GAP_MIN < gap <= MAX_GAP_MIN:
                        cat = resolve(p[3], xw, explicit)
                        if cat not in (None, "EXCLUDE") and cat not in DWELL_EXCLUDED:
                            dwells.setdefault(cat, []).append(gap)
                last[u] = (dt, venue)
    return dwells


def _pct(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = (len(sorted_vals) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def shrink(cat: str, emp: dict[str, float], n: int) -> dict[str, float]:
    default = CATEGORY_DEFAULTS.get(cat, 60)
    targets = {"p25": default * 0.7, "p50": default, "p75": default * 1.4}
    return {k: round((n * emp[k] + SHRINK_K * targets[k]) / (n + SHRINK_K), 1)
            for k in ("p25", "p50", "p75")}


def build(data_dir: str) -> dict:
    dwells = extract_dwells(data_dir)
    cats = {}
    for cat, vals in dwells.items():
        vals.sort()
        n = len(vals)
        emp = {"p25": _pct(vals, 0.25), "p50": _pct(vals, 0.5),
               "p75": _pct(vals, 0.75)}
        if emp["p50"] >= MAX_GAP_MIN:
            # Cap-pinned = revisit-dominated, prior abstains -> nac-1 default.
            default = CATEGORY_DEFAULTS.get(cat, 60)
            cats[cat] = {"p25": round(default * 0.7, 1), "p50": float(default),
                         "p75": round(default * 1.4, 1), "n": n,
                         "confidence": "low", "note": "capped-abstain"}
            continue
        post = shrink(cat, emp, n)
        conf = "low" if n < 20 else ("medium" if n < 200 else "high")
        cats[cat] = {**post, "n": n, "confidence": conf}
    for canon, default in CATEGORY_DEFAULTS.items():
        cats.setdefault(canon, {"p25": round(default * 0.7, 1), "p50": float(default),
                                "p75": round(default * 1.4, 1), "n": 0,
                                "confidence": "low"})
    return {"shrink_k": SHRINK_K, "cats": cats,
            "meta": {"n_dwells": sum(len(v) for v in dwells.values()),
                     "source": "Foursquare-TKY consecutive same-venue gaps 5m..12h"}}


def load(path: str = ""):
    global _prior
    if _prior is None:
        with open(path or os.path.join(os.path.dirname(__file__),
                                       "duration_prior.json"),
                  encoding="utf-8") as f:
            _prior = json.load(f)
    return _prior


def get_p50(category: str) -> float:
    """Phase-PR hook for optimizer (fallback: nac-1 default)."""
    canon = canonical_category(category)
    try:
        return float(load()["cats"][canon]["p50"])
    except (KeyError, TypeError):
        return float(CATEGORY_DEFAULTS.get(canon, 60))


def get_p75(category: str) -> float:
    """Phase-PR hook for validator p75 buffer (fallback: nac-1 default)."""
    canon = canonical_category(category)
    try:
        return float(load()["cats"][canon]["p75"])
    except (KeyError, TypeError):
        return float(CATEGORY_DEFAULTS.get(canon, 60) * 1.4)


def smoke() -> int:
    from BE.ml.patm.make_pairs import load_pois
    pois = load_pois(os.path.join("data", "snapshots", "danang-v1"))
    errs, rows = [], []
    for p in pois:
        canon = canonical_category(p.get("type", ""))
        eb = get_p50(canon)
        nac1 = float(CATEGORY_DEFAULTS.get(canon, 60))
        if p.get("rating") and p["rating"] >= 4.5:
            nac1 *= 1.2
        rows.append((p["poi_id"], canon, eb, round(nac1, 1)))
        errs.append(abs(math.log(eb / nac1)) if nac1 > 0 else 0.0)
    for r in rows:
        print(f"  {r[0]} [{r[1]}]: eb {r[2]} vs nac-1 {r[3]}")
    print(f"seed smoke: log-MAE {sum(errs) / len(errs):.3f} (preliminary; "
          f"real eval needs gold checklist)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T064 dwell duration prior")
    ap.add_argument("--data-dir", default="")
    ap.add_argument("--out", default="BE/ml/patm/duration_prior.json")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.smoke:
        return smoke()
    prior = build(args.data_dir)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(prior, f, indent=1)
    print(f"dwells: {prior['meta']['n_dwells']}, cats: {len(prior['cats'])} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
