#!/usr/bin/env python3
"""Gold suite v2 (30 queries) under one objective: python eval_gold.py <repo> <out.jsonl> <legacy|v1> [workers]"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_objective as E  # noqa: E402


def main():
    repo, out, config = sys.argv[1:4]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    suite = json.load(open(os.path.join(repo, "BE", "eval", "gold", "gold_v2.json"),
                           encoding="utf-8"))["suite_v2"]
    recs = [{"id": q["query_id"], "trip": q["trip"], "profile": q.get("profile") or {},
             "solution": [], "elapsed_s": 0.0} for q in suite]
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, initializer=E.init, initargs=(repo, config, "")) as p, \
            open(out, "w", encoding="utf-8") as fh:
        for res in p.imap_unordered(E.solve, recs, chunksize=1):
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
            fh.flush()


if __name__ == "__main__":
    main()
