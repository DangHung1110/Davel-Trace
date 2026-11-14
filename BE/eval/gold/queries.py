"""Test-suite query builder (T051-BUILDER, lane A). Deterministic ĐN queries.

Query = {"query_id", "prefs_text" (Vietnamese NL, for future parser
tests), "trip": {budget, travelers, start/end_time, must_visit, avoid,
order_prefs, activities}, "profile"}. `profile` stays outside the trip: with a
profile the gate adds the day rules (lunch, caps), which only the hybrid run
plans for; the distance-only gold is judged on the core gate.
must_visit picks are POIs that can fit the query's window and that the party's day
template allows (the router drops the others with a warning, before planning), so a
query is infeasible only when the plan really cannot hold them.
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

from BE.app.schemas.trip import TripProfile  # noqa: E402
from BE.app.services import templates  # noqa: E402
from BE.common import load_pois, poi_open_windows, to_min  # noqa: E402

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
LIKE_ACTIVITIES = {"biển và hải sản": ["tắm biển", "hải sản"],
                   "leo núi rồi đi biển": ["leo núi", "tắm biển"],
                   "văn hóa và ẩm thực": ["bảo tàng"],
                   "check-in trung tâm": [], "yên tĩnh hẹn hò": []}
PROFILES = [{"party_type": "couple", "pace": 2, "fitness": 2},
            {"party_type": "family", "pace": 1, "fitness": 1},
            {"party_type": "friends", "pace": 3, "fitness": 3}]


def _fits_window(poi: dict, ws: str, we: str) -> bool:
    """Open long enough in the window, and short enough to leave room for others."""
    start, end = to_min(ws), to_min(we)
    dur = int((poi.get("visit_min") or {}).get("p50") or 60)
    windows = poi_open_windows(poi)
    if dur > (end - start) / 3:
        return False
    return windows is None or any(max(o, start) + dur <= min(c, end) for o, c in windows)


def build_queries(pois: list[dict], n: int = 5, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    verified = [p for p in pois if p.get("verified")]
    ids = sorted(p["poi_id"] for p in verified)
    combos = list(itertools.product(BUDGETS, WINDOWS))
    rng.shuffle(combos)
    queries = []
    for i in range(n):
        budget, (ws, we) = combos[i % len(combos)]
        profile = TripProfile(**PROFILES[i % len(PROFILES)]).model_dump()
        day = templates.select_template(profile)
        fit = sorted(p["poi_id"] for p in verified
                     if _fits_window(p, ws, we) and templates.allows(p, day)
                     and p.get("plan_tier") != "excluded")
        must = rng.sample(fit, k=min(2, len(fit))) if i % 2 == 0 else []
        avoid = rng.sample([x for x in ids if x not in must],
                           k=1 if len(ids) - len(must) > 2 else 0)
        order = [[must[0], must[1]]] if len(must) == 2 else []
        like = LIKES[i % len(LIKES)]
        template, people = rng.choice(PREFS_TEXTS), rng.choice([1, 2, 4])
        queries.append({
            "query_id": f"q{i + 1:02d}",
            "prefs_text": template.format(
                n=people, budget_text=BUDGET_TEXT[budget], like=like,
                window_text=f"từ {ws} đến {we}"),
            "trip": {"budget": budget, "travelers": people, "start_time": ws, "end_time": we,
                     "must_visit": must, "avoid": avoid, "order_prefs": order,
                     "activities": LIKE_ACTIVITIES[like]},
            "profile": profile,
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
