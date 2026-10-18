"""T030 benchmark — gap between CP-SAT (5s budget) and the exact optimum on
small TOPTW instances over the real OSRM matrix with the wired q_ij.

Purpose: the CP-SAT optimizer (T017/T030) is run against a brute-force
oracle on instances small enough to enumerate completely (all ordered
subsets, empty set included -> objective 0). Instances are built from the
committed snapshot (`BE/data/snapshots/danang-v1/`): real OSRM travel
minutes, real POI metadata (visit_min p50, opening hours, rating) and the
PATM v4 transition scores q_ij from `BE/app/services/scorer.py`.

The oracle mirrors the CP-SAT model's sequential feasibility EXACTLY
(waiting allowed, visit must finish by min(close, trip end)) and uses the
same integer objective expressions the model uses:
    sum(int(score * 1000) * visit) + sum(int(float(q) * 100) * poi_arc)
q is applied only to POI->POI arcs (the depot is not in the model's node
map, so depot arcs never carry a q term).

Usage (repo root):
    python BE/tools/benchmark_optimizer.py                  # k = 6,8
    python BE/tools/benchmark_optimizer.py --k 6,7 --json tmp/gap.json
    python BE/tools/benchmark_optimizer.py --q off          # rule-free baseline

Note: n=8 is ~109k ordered subsets; n>8 is refused by exact_optimum
(ValueError) because the enumeration stops being a benchmark and starts
being a wait.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services import scorer  # noqa: E402
from BE.app.services.common import parse_hours, to_min  # noqa: E402
from BE.app.services.matrix import MatrixService  # noqa: E402
from BE.app.services.optimizer import (  # noqa: E402
    StubPOI, StubTrip, optimize, travel_from_matrix)

DEFAULT_POIS = os.path.join("BE", "data", "snapshots", "danang-v1", "pois.json")
DEFAULT_MATRIX_DIR = os.path.join("BE", "data", "snapshots", "danang-v1")
DEFAULT_DEPOT = "ChIJ03jTTgAXQjERpVQunmJHv2c"  # Sontra Sea Hotel — trip origin
MAX_EXACT_N = 8  # ~109k ordered subsets; beyond this the oracle is not a benchmark


def exact_optimum(pois, travel, trip, edge_scores=None) -> int:
    """Objective of the best feasible ordered subset (empty set -> 0).

    Brute force over every ordered subset. Feasibility is evaluated
    sequentially exactly like the CP-SAT model: waiting is allowed, a
    visit is feasible iff it starts at max(earliest arrival, open) and
    finishes by min(close, trip end). Missing travel legs are infeasible
    (never 0 / estimate, B3). Objective is integral, matching the model:
    int(score*1000) per visit plus int(float(q)*100) per POI->POI arc.
    """
    n = len(pois)
    if n > MAX_EXACT_N:
        raise ValueError(
            f"exact_optimum refuses n={n} > {MAX_EXACT_N} "
            f"(~109k ordered subsets at n=8; brute force stops being a benchmark)")

    best = 0  # empty set is always allowed (objective 0)
    for r in range(1, n + 1):
        for subset in itertools.combinations(pois, r):
            for order in itertools.permutations(subset):
                prev = trip.origin_id
                prev_end = trip.start_min
                obj = 0
                feasible = True
                for poi in order:
                    w = travel.get((prev, poi.poi_id))
                    if w is None:
                        feasible = False
                        break
                    t = max(prev_end + w, poi.open_min)
                    if t + poi.visit_min > min(poi.close_min, trip.end_min):
                        feasible = False
                        break
                    obj += int(poi.score * 1000)
                    if prev != trip.origin_id and edge_scores:
                        q = edge_scores.get((prev, poi.poi_id))
                        if q is not None:
                            obj += int(float(q) * 100)
                    prev_end = t + poi.visit_min
                    prev = poi.poi_id
                if feasible and obj > best:
                    best = obj
    return best


def build_instance(svc, by_id, k, depot, start_min, end_min):
    """(candidates, stubs, travel) for the k first matrix ids that have metadata.

    visit_min: dict -> int(p50); scalar/absent -> int(value or 60).
    window: first opening-hours span; None or close<=open (wraps midnight)
    falls back to the trip window. score: rating (0.0 when absent).
    """
    candidates = [pid for pid in svc.ids if pid != depot and pid in by_id][:k]
    stubs = []
    for pid in candidates:
        p = by_id[pid]
        vm = p.get("visit_min")
        visit_min = int(vm["p50"]) if isinstance(vm, dict) else int(vm or 60)
        win = parse_hours(p.get("opening_hours"))
        if win is None or win[1] <= win[0]:
            open_min, close_min = start_min, end_min
        else:
            open_min, close_min = win
        stubs.append(StubPOI(pid, visit_min, open_min, close_min,
                             float(p.get("rating") or 0.0)))
    travel = travel_from_matrix(svc, [depot] + candidates)
    return candidates, stubs, travel


def parse_k(spec: str) -> list[int]:
    ks = [int(part) for part in str(spec).split(",") if part.strip()]
    if not ks:
        raise ValueError("--k must contain at least one integer")
    return ks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k", default="6,8", help="comma list of instance sizes")
    ap.add_argument("--pois", default=DEFAULT_POIS)
    ap.add_argument("--matrix-dir", default=DEFAULT_MATRIX_DIR)
    ap.add_argument("--depot", default=DEFAULT_DEPOT)
    ap.add_argument("--start", default="07:00")
    ap.add_argument("--end", default="18:00")
    ap.add_argument("--timeout", type=float, default=5.0, help="CP-SAT budget (s)")
    ap.add_argument("--q", choices=("auto", "off"), default="auto",
                    help="auto: PATM q_ij wired; off: no edge scores")
    ap.add_argument("--json", default="", help="optional JSON dump path")
    args = ap.parse_args(argv)

    start_min, end_min = to_min(args.start), to_min(args.end)
    svc = MatrixService(args.matrix_dir)  # cache-first, no network
    with open(args.pois, encoding="utf-8") as f:
        doc = json.load(f)
    by_id = {p["poi_id"]: p for p in doc["pois"]}

    desc = scorer.describe()
    print(f"backend: {desc['backend']}")
    if desc.get("note"):
        print(f"backend_note: {desc['note']}")
    print(f"matrix: {args.matrix_dir} ids={len(svc.ids)} "
          f"q={args.q} timeout={args.timeout}s trip={args.start}-{args.end}")

    records = []
    for k in parse_k(args.k):
        candidates, stubs, travel = build_instance(
            svc, by_id, k, args.depot, start_min, end_min)
        trip = StubTrip(start_min, end_min, args.depot)
        q = scorer.edge_scores(candidates, by_id) if args.q == "auto" else None

        t0 = time.monotonic()
        out = optimize(stubs, travel, trip, edge_scores=q, timeout_s=args.timeout)
        cp_s = time.monotonic() - t0

        rec = {"k": k, "n": len(stubs), "status": out.get("status"),
               "cp_s": round(cp_s, 3), "q": args.q == "auto"}
        if out.get("itinerary") is None:
            print(f"k={k} status={out.get('status')} "
                  f"reason={out.get('reason', '')} cp_s={cp_s:.2f}")
            records.append(rec)
            continue

        cp = int(out["objective"])
        t0 = time.monotonic()
        exact = exact_optimum(stubs, travel, trip, edge_scores=q)
        exact_s = time.monotonic() - t0
        gap_pct = ((exact - cp) / exact * 100.0) if exact > 0 else 0.0

        line = (f"k={k} status={out['status']} cp={cp} exact={exact} "
                f"gap={gap_pct:.2f}% cp_s={cp_s:.2f} exact_s={exact_s:.2f}")
        if cp > exact:
            line += " CP>EXACT(check)"
        print(line)
        rec.update({"cp": cp, "exact": exact, "gap_pct": round(gap_pct, 4),
                    "exact_s": round(exact_s, 3),
                    "cp_gt_exact": cp > exact})
        records.append(rec)

    if args.json:
        out_dir = os.path.dirname(os.path.abspath(args.json))
        os.makedirs(out_dir, exist_ok=True)
        payload = {"backend": desc, "matrix_dir": args.matrix_dir,
                   "pois": args.pois, "depot": args.depot,
                   "start": args.start, "end": args.end,
                   "timeout_s": args.timeout, "q": args.q,
                   "instances": records}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
