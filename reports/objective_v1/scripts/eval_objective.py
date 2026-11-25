#!/usr/bin/env python3
"""Objective v1 vs legacy on the held-out requests (same cap of 40 for both).

python eval_objective.py <repo> <data_dir> <test_ids.json> <out.jsonl> <legacy|v1> [workers] [limit]
"""
from __future__ import annotations

import glob
import json
import multiprocessing as mp
import os
import sys
import time

_G: dict = {}


def init(repo: str, config: str, model_dir: str):
    os.environ["DAVEL_SOLVER_CANDIDATES"] = "40"
    os.environ.pop("DAVEL_LEARNED_FILTER", None)
    mode, _, prof = config.partition(":")
    os.environ["DAVEL_OBJECTIVE"] = mode
    _G["profile_name"] = prof or "balanced"
    os.chdir(repo)
    sys.path.insert(0, repo)
    import warnings
    warnings.filterwarnings("ignore")
    from BE.eval import baselines as B
    from BE.common import load_matrix_cells
    from BE.app.services import gate, profiles, rank, retrieval
    snap = os.path.join("BE", "data", "snapshots", "danang-v2")
    pois = B.load_pois(snap)
    _G.update(profile_name=_G.get("profile_name"), pois=pois, by_id={p["poi_id"]: p for p in pois}, cells=load_matrix_cells(snap),
              gate=gate, profiles=profiles, rank=rank, retrieval=retrieval, config=config)


def solve(rec: dict) -> dict:
    t0 = time.time()
    trip = {**rec["trip"], "profile": rec["profile"], "meals": True}
    # an old request may name a record merged into another one ("gộp vào"): the
    # kept one, as the API does (routers/itinerary)
    from BE.common import merged_into
    by_id = _G["by_id"]
    trip["must_visit"] = [merged_into(by_id.get(m)) or m for m in trip.get("must_visit") or []]
    found = _G["retrieval"].retrieve(trip, _G["pois"])
    cids = [c["poi_id"] for c in found["candidates"]]
    ranked = _G["rank"].rank([_G["by_id"][i] for i in cids], {"budget": trip["budget"]},
                             {"trip": trip, "hour": trip.get("start_time", "07:00")})
    plan = _G["profiles"].build_plan(_G.get("profile_name") or "balanced", trip, ranked,
                                     _G["by_id"], _G["cells"], workers=1, timeout_s=60,
                                     deterministic_time=rec.get("det_time") or 5.0, diagnose=False)
    acts = [[a["poi_id"], a.get("start"), a.get("end")] for a in plan.get("activities") or []]
    rep = None
    if acts:
        itin = {"activities": [{"poi_id": p, "start": s, "end": e} for p, s, e in acts]}
        g = _G["gate"].report(itin, trip, _G["by_id"], _G["cells"])
        rep = {"passed": g["passed"], "failed": g["failed"], "soft_failed": g.get("soft_failed")}
    return {"id": rec["id"], "config": _G["config"], "trip": trip, "teacher": rec["solution"],
            "teacher_elapsed": rec["elapsed_s"], "solution": acts, "gate": rep,
            "pool": len((plan.get("_context") or {}).get("pois") or []),
            "elapsed": round(time.time() - t0, 2)}


def main():
    repo, data_dir, test_ids, out, config = sys.argv[1:6]
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    limit = int(sys.argv[7]) if len(sys.argv) > 7 else 10 ** 9
    model_dir = os.path.dirname(os.path.abspath(test_ids))
    wanted = set(json.load(open(test_ids)))
    recs = {}
    for f in glob.glob(os.path.join(data_dir, "**", "teacher_*.jsonl"), recursive=True):
        for line in open(f, encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("id") in wanted and "error" not in r and r["solution"]:
                recs[r["id"]] = r
    todo = sorted(recs.values(), key=lambda r: r["id"])[:limit]
    print(f"[eval] {config}: {len(todo)} held-out requests", flush=True)
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, initializer=init, initargs=(repo, config, model_dir)) as p, \
            open(out, "w", encoding="utf-8") as fh:
        for i, res in enumerate(p.imap_unordered(solve, todo, chunksize=1), 1):
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 25 == 0:
                print(f"[eval] {config} {i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
