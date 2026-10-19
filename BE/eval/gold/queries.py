"""Test-suite query builder (T051-BUILDER, lane A). Deterministic ĐN queries.

Query = {"query_id", "prefs_text" (Vietnamese NL, for future parser
tests), "trip": {budget, start/end_time, must_visit, avoid, order_prefs}}.
30-50 queries full run LATER on the full T003b snapshot; seed trials use
a handful. Deterministic on (seed, n).
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.common import load_pois  # noqa: E402

BUDGETS = [1000000, 3000000, 5000000]
WINDOWS = [("07:00", "18:00"), ("07:00", "12:00"), ("13:00", "18:00")]
PREFS_TEXTS = [
    "cuối tuần đi Đà Nẵng {n} người {budget_text} thích {like}",
    "đi Đà Nẵng {window_text} {budget_text}, ưu tiên {like}",
    "lịch Đà Nẵng 1 ngày: {like}, ngân sách {budget_text}",
]
LIKES = ["biển và hải sản", "leo núi rồi đi biển", "văn hóa và ẩm thực",
         "check-in trung tâm", "yên tĩnh hẹn hò"]
BUDGET_TEXT = {1000000: "1 triệu", 3000000: "3 triệu", 5000000: "5 triệu"}


def build_queries(pois: list[dict], n: int = 5, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    ids = sorted(p["poi_id"] for p in pois if p.get("verified"))
    combos = list(itertools.product(BUDGETS, WINDOWS))
    rng.shuffle(combos)
    queries = []
    for i in range(n):
        budget, (ws, we) = combos[i % len(combos)]
        must = rng.sample(ids, k=min(2, len(ids))) if i % 2 == 0 else []
        avoid = rng.sample([x for x in ids if x not in must],
                           k=1 if len(ids) - len(must) > 2 else 0)
        order = [[must[0], must[1]]] if len(must) == 2 else []
        like = LIKES[i % len(LIKES)]
        queries.append({
            "query_id": f"q{i + 1:02d}",
            "prefs_text": rng.choice(PREFS_TEXTS).format(
                n=rng.choice([1, 2, 4]), budget_text=BUDGET_TEXT[budget], like=like,
                window_text=f"từ {ws} đến {we}"),
            "trip": {"budget": budget, "start_time": ws, "end_time": we,
                     "must_visit": must, "avoid": avoid, "order_prefs": order},
        })
    return queries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T051 query builder")
    ap.add_argument("--snapshot", default=os.path.join("data", "snapshots", "danang-v1"))
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    pois = load_pois(args.snapshot)
    queries = build_queries(pois, args.n, args.seed)
    print(f"built {len(queries)} queries (seed {args.seed})")
    for q in queries:
        print(f"  {q['query_id']}: {q['prefs_text']} | {q['trip']}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(queries, f, ensure_ascii=False, indent=1)
        print(f"wrote -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
