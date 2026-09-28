"""Suite entry (T051-BUILDER, lane A): queries -> Approach-B golds -> T049 gate.

Usage:
  python BE/eval/gold/build.py --snapshot data/snapshots/danang-v1 --n 5 --out <TEMP>/suite.json
Exit nonzero if any feasible query yields a gold that FAILS the gate.
30-50 queries full run LATER on the full T003b snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.eval.gold.approach_b import make_gold  # noqa: E402
from BE.eval.gold.queries import build_queries  # noqa: E402
from BE.eval.metrics import evaluate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T051 suite builder")
    ap.add_argument("--snapshot", default=os.path.join("data", "snapshots", "danang-v1"))
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
    with open(os.path.join(args.snapshot, "matrix.json"), encoding="utf-8") as f:
        matrix = json.load(f)["cells"]
    suite, bad = [], 0
    for q in build_queries(pois_list(pois), args.n, args.seed):
        gold = make_gold(q, pois, matrix)
        if gold["itinerary"] is None:
            print(f"  {q['query_id']}: INFEASIBLE ({gold['infeasible']})")
            suite.append({**q, **gold, "gate": None})
            continue
        rep = evaluate(gold["itinerary"], q["trip"], pois, matrix)
        ok = rep["gate"]["passed"]
        bad += not ok
        n = len(gold["itinerary"]["activities"])
        print(f"  {q['query_id']}: gold {n} acts gate {'PASS' if ok else 'FAIL ' + str(rep['gate']['violations'])}")
        suite.append({**q, **gold, "gate": rep["gate"], "soft": rep["soft"]})
    print(f"suite: {len(suite)} queries, {bad} gate failures")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(suite, f, ensure_ascii=False, indent=1)
        print(f"wrote -> {args.out}")
    return 1 if bad else 0


def pois_list(pois: dict) -> list[dict]:
    return list(pois.values())


if __name__ == "__main__":
    raise SystemExit(main())
