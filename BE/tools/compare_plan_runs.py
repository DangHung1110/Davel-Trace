"""Two audit_plans.py runs of the same scenarios, plan by plan: how close are they?

Pairs the plans by (scenario, round, profile) and counts the same stops at the same
times, the same stops in the same order, the same set of stops, the POI-set Jaccard,
how far the first stop of a day moved, the travel minutes and the gate verdict. Made
for "what does this change do to the plans": a GPS fix near a hotel against the hotel
itself, a planner before and after a change.

Usage (repo root):
  python BE/tools/compare_plan_runs.py hotel.json gps.json [--show 10] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys


def _minutes(hhmm: str) -> int:
    h, m = str(hhmm).split(":")[:2]
    return int(h) * 60 + int(m)


def plans_of(path: str) -> dict[tuple, dict]:
    doc = json.load(open(path, encoding="utf-8"))
    out = {}
    for row in doc.get("rows") or []:
        for index, plan in enumerate((row.get("body") or {}).get("plans") or []):
            out[(row["key"], row.get("round", 0), plan.get("profile") or index)] = plan
    return out


def stops(plan: dict) -> list[tuple]:
    return [(a.get("day", 1), a["poi_id"], a["start"]) for a in plan.get("activities") or []]


def first_starts(plan: dict) -> dict:
    out: dict = {}
    for a in plan.get("activities") or []:
        day = a.get("day", 1)
        out[day] = min(out.get(day, 10_000), _minutes(a["start"]))
    return out


def compare(a_path: str, b_path: str) -> dict:
    a_plans, b_plans = plans_of(a_path), plans_of(b_path)
    keys = sorted(set(a_plans) & set(b_plans), key=str)
    rows = []
    for key in keys:
        a, b = a_plans[key], b_plans[key]
        sa, sb = stops(a), stops(b)
        ids_a, ids_b = {s[1] for s in sa}, {s[1] for s in sb}
        union = ids_a | ids_b
        fa, fb = first_starts(a), first_starts(b)
        shifts = [abs(fa[d] - fb[d]) for d in fa if d in fb]
        rows.append({
            "key": list(key), "identical": sa == sb,
            "same_order": [s[:2] for s in sa] == [s[:2] for s in sb],
            "same_set": ids_a == ids_b,
            "jaccard": len(ids_a & ids_b) / len(union) if union else 1.0,
            "first_shift_min": max(shifts) if shifts else None,
            "travel_a": a.get("travel_min"), "travel_b": b.get("travel_min"),
            "passed_a": bool(a.get("passed")), "passed_b": bool(b.get("passed")),
            "only_a": sorted(ids_a - ids_b), "only_b": sorted(ids_b - ids_a),
        })
    n = len(rows) or 1
    shifts = [r["first_shift_min"] for r in rows if r["first_shift_min"] is not None]
    travel = [(r["travel_b"] or 0) - (r["travel_a"] or 0) for r in rows]
    summary = {
        "pairs": len(rows),
        "only_in_a": len(set(a_plans) - set(b_plans)), "only_in_b": len(set(b_plans) - set(a_plans)),
        "identical": sum(r["identical"] for r in rows),
        "same_order": sum(r["same_order"] for r in rows),
        "same_set": sum(r["same_set"] for r in rows),
        "mean_jaccard": round(sum(r["jaccard"] for r in rows) / n, 3),
        "first_shift_mean_min": round(sum(shifts) / len(shifts), 1) if shifts else None,
        "first_shift_max_min": max(shifts) if shifts else None,
        "travel_delta_mean_min": round(sum(travel) / n, 1),
        "passed_a": sum(r["passed_a"] for r in rows), "passed_b": sum(r["passed_b"] for r in rows),
    }
    return {"a": a_path, "b": b_path, "summary": summary, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--show", type=int, default=10, help="print this many differing plans")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    result = compare(args.a, args.b)
    s = result["summary"]
    print(f"{s['pairs']} plan pairs ({s['only_in_a']} only in a, {s['only_in_b']} only in b)")
    print(f"  identical stops and times {s['identical']}, same stops in order {s['same_order']}, "
          f"same set {s['same_set']}, mean Jaccard {s['mean_jaccard']}")
    print(f"  first stop of a day moved: mean {s['first_shift_mean_min']} min, "
          f"max {s['first_shift_max_min']} min; travel b - a: mean {s['travel_delta_mean_min']} min")
    print(f"  gate passed: a {s['passed_a']}, b {s['passed_b']}")
    shown = 0
    for r in result["rows"]:
        if r["identical"] or shown >= args.show:
            continue
        shown += 1
        print(f"  - {r['key']}: jaccard {r['jaccard']:.2f}, first stop moved "
              f"{r['first_shift_min']} min, travel {r['travel_a']} -> {r['travel_b']}, "
              f"-{r['only_a']} +{r['only_b']}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
