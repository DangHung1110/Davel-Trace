"""WP11: rebuild the gold suite on danang-v2.1 and compare it with v1.

    python BE/eval/gold/build_v2.py                     # n=30, seed=7
    python BE/eval/gold/build_v2.py --policy cach_ly    # Google-free run

Runs the SAME builder (`build.build_suite`: queries -> Approach-B gold ->
T049 gate) on both snapshots with the same n/seed and writes
`BE/eval/gold/gold_v2.json`:

    {"v1": summary, "v2": summary, "policy": ..., "suite_v2": [...]}

summary = {eligible, records, feasible, infeasible, gate_pass, gate_pass_rate}.
`gate_pass_rate` = gate passes / records (an infeasible query counts as a
miss, so a smaller eligible pool cannot look better by refusing queries).
The default SNAPSHOT_DIR is NOT changed here (DATA_FIX_PLAN WP11).
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

from BE.common import load_json, load_matrix_cells, view_pois  # noqa: E402
from BE.eval.gold.build import build_suite  # noqa: E402

SNAPS = {"v1": os.path.join("BE", "data", "snapshots", "danang-v1"),
         "v2": os.path.join("BE", "data", "snapshots", "danang-v2")}
OUT = os.path.join("BE", "eval", "gold", "gold_v2.json")


def summarize(suite: list[dict], coverage: dict) -> dict:
    feasible = [r for r in suite if r.get("itinerary") is not None]
    passed = [r for r in feasible if (r.get("gate") or {}).get("passed")]
    acts = [len(r["itinerary"]["activities"]) for r in feasible]
    return {"eligible": coverage["eligible"], "records": len(suite),
            "feasible": len(feasible), "infeasible": len(suite) - len(feasible),
            "gate_pass": len(passed),
            "gate_pass_rate": round(len(passed) / len(suite), 3) if suite else 0.0,
            "mean_activities": round(sum(acts) / len(acts), 2) if acts else 0.0}


def run(snapshot: str, n: int, seed: int, policy: str) -> tuple[list[dict], dict]:
    pois = view_pois(load_json(os.path.join(snapshot, "pois.json"))["pois"], snapshot, policy)
    by_id = {p["poi_id"]: p for p in pois}
    # caps=True on BOTH snapshots: the distance-only chain skips optional
    # stops that would break a HARD quota, so a gold is gate-valid by
    # construction and the v1/v2 comparison measures the data, not the
    # generator's blindness to cafe/category caps.
    suite, _bad, _inf, cov = build_suite(by_id, load_matrix_cells(snapshot), n, seed, caps=True)
    return suite, summarize(suite, cov)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--policy", default=os.environ.get("GOOGLE_POLICY", "cach_ly"))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    os.environ["GOOGLE_POLICY"] = a.policy
    report = {"n": a.n, "seed": a.seed, "policy": a.policy}
    for key, snap in SNAPS.items():
        suite, summ = run(snap, a.n, a.seed, a.policy)
        report[key] = summ
        if key == "v2":
            report["suite_v2"] = suite
        print(key, json.dumps(summ, ensure_ascii=False))
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote", a.out)
    return 0 if report["v2"]["gate_pass_rate"] >= report["v1"]["gate_pass_rate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
