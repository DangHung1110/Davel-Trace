"""Suite entry (T051-BUILDER, lane A): queries -> Approach-B golds -> T049 gate.

SCOPED build, not a full gold suite. Query generation AND the gold/gate
inputs are restricted to the eligible pool = POIs that are BOTH `verified`
AND matrix-covered with every ordered candidate-to-candidate cell present.
On the current T003b snapshot that pool is only 5 of 764 POIs (5 of 48
verified; 43 verified POIs lack matrix coverage), and the 30-record output
is the 30 Approach-B queries over that pool. Fee/category/duration breadth
and SC-010 recovery remain open for T053.

Usage:
  python BE/eval/gold/build.py --snapshot BE/data/snapshots/danang-v1 \
      --n 30 --seed 7 --out BE/eval/gold/t051_scoped_suite.json

Exit nonzero if any feasible query yields a gold that FAILS the gate
(infeasible queries are separate records, not gate failures).
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

from BE.common import load_matrix_cells, load_pois  # noqa: E402
from BE.eval.gold.approach_b import make_gold  # noqa: E402
from BE.eval.gold.queries import build_queries  # noqa: E402
from BE.eval.metrics import evaluate  # noqa: E402


def matrix_ids(matrix: dict) -> set[str]:
    """Every POI id that appears on either side of a matrix cell."""
    ids: set[str] = set()
    for key in matrix:
        a, _, b = key.partition("->")
        if a:
            ids.add(a)
        if b:
            ids.add(b)
    return ids


def eligible_ids(pois_by_id: dict, matrix: dict) -> list[str]:
    """Verified POIs fully matrix-covered over the eligible set itself.

    A POI is eligible only if it is `verified`, present in the matrix, and
    every ordered cell to/from every other verified-matrix POI exists — so a
    missing OSRM pair can never quietly become a 0-minute edge downstream.
    """
    mids = matrix_ids(matrix)
    base = sorted(pid for pid, p in pois_by_id.items()
                  if p.get("verified") and pid in mids)
    return [pid for pid in base
            if all(matrix.get(f"{pid}->{q}") and matrix.get(f"{q}->{pid}")
                   for q in base)]


def coverage_summary(pois_by_id: dict, matrix: dict, eligible: list[str]) -> dict:
    verified = [pid for pid, p in pois_by_id.items() if p.get("verified")]
    return {
        "total_pois": len(pois_by_id),
        "verified": len(verified),
        "matrix_ids": len(matrix_ids(matrix)),
        "eligible": len(eligible),
        "missing_verified": len(verified) - len(eligible),
        "eligible_ids": list(eligible),
    }


def build_suite(pois_by_id: dict, matrix: dict, n: int, seed: int
                ) -> tuple[list[dict], int, int, dict]:
    """Deterministic (suite, gate_failures, infeasible, coverage).

    `suite` is a list of {query + gold + gate + soft} records (gate/soft
    None on infeasible records), exactly the CLI JSON schema. Query
    generation and the gold/evaluate calls all use the eligible pool.
    """
    eligible = eligible_ids(pois_by_id, matrix)
    pool = {pid: pois_by_id[pid] for pid in eligible}
    coverage = coverage_summary(pois_by_id, matrix, eligible)
    suite: list[dict] = []
    bad = infeasible = 0
    for q in build_queries(list(pool.values()), n, seed):
        gold = make_gold(q, pool, matrix)
        if gold["itinerary"] is None:
            infeasible += 1
            suite.append({**q, **gold, "gate": None, "soft": None})
            continue
        rep = evaluate(gold["itinerary"], q["trip"], pool, matrix)
        bad += not rep["gate"]["passed"]
        suite.append({**q, **gold, "gate": rep["gate"], "soft": rep["soft"]})
    return suite, bad, infeasible, coverage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T051 SCOPED suite builder")
    ap.add_argument("--snapshot", default=os.path.join("data", "snapshots", "danang-v1"))
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    pois = load_pois(args.snapshot, by_id=True)
    matrix = load_matrix_cells(args.snapshot)
    suite, bad, infeasible, cov = build_suite(pois, matrix, args.n, args.seed)
    print("coverage (SCOPED, not full gold): "
          f"{cov['eligible']}/{cov['total_pois']} POIs eligible "
          f"({cov['eligible']}/{cov['verified']} verified intersect matrix, "
          f"{cov['missing_verified']} verified missing matrix); "
          f"matrix ids {cov['matrix_ids']}")
    print(f"eligible ids: {cov['eligible_ids']}")
    for rec in suite:
        if rec["itinerary"] is None:
            print(f"  {rec['query_id']}: INFEASIBLE ({rec['infeasible']})")
        else:
            n = len(rec["itinerary"]["activities"])
            ok = rec["gate"]["passed"]
            print(f"  {rec['query_id']}: gold {n} acts gate "
                  f"{'PASS' if ok else 'FAIL ' + str(rec['gate']['violations'])}")
    print(f"suite: {len(suite)} records, {bad} gate failures, "
          f"{infeasible} infeasible")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(suite, f, ensure_ascii=False, indent=1)
        print(f"wrote -> {args.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
