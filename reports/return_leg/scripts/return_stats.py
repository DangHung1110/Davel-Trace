"""Before/after audit runs from one base: the ride back to it, plan by plan.

The two runs are `BE/tools/audit_plans.py --out <run>.json --origin <poi_id>` (the
`--origin` flag comes with feat/gps-origin), one on a `git archive` copy of each
version. Every leg, the ride back included, is read off the snapshot's dense matrix.

Usage: python return_stats.py before.json after.json --matrix matrix.json --pois pois.json
       --base <poi_id> [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict


def to_min(s: str) -> int:
    h, m = str(s).split(":")[:2]
    return int(h) * 60 + int(m)


class Matrix:
    def __init__(self, path: str):
        doc = json.load(open(path, encoding="utf-8"))
        self.index = {pid: i for i, pid in enumerate(doc["ids"])}
        self.minutes = doc["minutes"]
        self.km = doc["km"]

    def leg(self, a: str, b: str):
        i, j = self.index.get(a), self.index.get(b)
        if i is None or j is None:
            return None, None
        return self.minutes[i][j], self.km[i][j]


def straight_km(p, q) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (p["lat"], p["lon"], q["lat"], q["lon"]))
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0088 * math.asin(math.sqrt(min(1.0, a)))


def plans_of(path: str) -> dict:
    doc = json.load(open(path, encoding="utf-8"))
    out = {}
    for row in doc.get("rows") or []:
        for index, plan in enumerate((row.get("body") or {}).get("plans") or []):
            out[(row["key"], row.get("round", 0), plan.get("profile") or index)] = (row, plan)
    return out


def days_of(plan: dict) -> dict[int, list[dict]]:
    days = defaultdict(list)
    for a in plan.get("activities") or []:
        days[int(a.get("day", 1) or 1)].append(a)
    return {d: sorted(acts, key=lambda a: to_min(a["start"])) for d, acts in sorted(days.items())}


def day_rows(plan: dict, row: dict, m: Matrix, base: str, pois: dict) -> list[dict]:
    trip = row.get("trip") or {}
    end = to_min(trip.get("end_time") or "20:00")
    rt = trip.get("return_time")
    if rt:
        end = min(end, to_min(rt))
    out = []
    for day, acts in days_of(plan).items():
        legs = [(base, acts[0]["poi_id"])] + [(a["poi_id"], b["poi_id"]) for a, b in zip(acts, acts[1:])]
        ride = sum((m.leg(a, b)[0] or 0) for a, b in legs)
        last = acts[-1]["poi_id"]
        back_min, back_km = m.leg(last, base)
        home = to_min(acts[-1]["end"]) + (back_min or 0)
        out.append({
            "day": day, "stops": len(acts), "ride_out_and_between": ride,
            "back_min": back_min, "back_km": back_km,
            "back_straight_km": (round(straight_km(pois[last], pois[base]), 2)
                                 if last in pois and base in pois else None),
            "ride_with_back": ride + (back_min or 0),
            "last": last, "last_name": (pois.get(last) or {}).get("name"),
            "last_end": acts[-1]["end"], "home_at": f"{home // 60:02d}:{home % 60:02d}",
            "home_after_end_min": max(0, home - end), "end": end,
        })
    return out


def wishes(plan: dict) -> tuple[int, int]:
    matches = plan.get("activity_match") or []
    return sum(1 for x in matches if x.get("status") == "met"), len(matches)


def summarise(rows: list[dict], side: str) -> dict:
    days = [d for r in rows for d in r[side]["days"]]
    plans = [r[side] for r in rows]
    backs = [d["back_min"] for d in days if d["back_min"] is not None]
    kms = [d["back_km"] for d in days if d["back_km"] is not None]
    late = [d["home_after_end_min"] for d in days if d["home_after_end_min"] > 0]
    met = sum(p["wishes_met"] for p in plans)
    asked = sum(p["wishes"] for p in plans)
    q = lambda xs, f: round(statistics.quantiles(xs, n=10)[f - 1], 1) if len(xs) >= 10 else None
    return {
        "plans": len(plans), "days": len(days),
        "passed": sum(p["passed"] for p in plans),
        "empty": sum(1 for p in plans if not p["days"]),
        "stops_per_day": round(statistics.mean(d["stops"] for d in days), 2) if days else None,
        "travel_min_per_day_reported": round(sum(p["travel_min"] for p in plans) / len(days), 1) if days else None,
        "ride_per_day_out_and_between": round(statistics.mean(d["ride_out_and_between"] for d in days), 1) if days else None,
        "back_min_mean": round(statistics.mean(backs), 1) if backs else None,
        "back_min_median": statistics.median(backs) if backs else None,
        "back_min_p90": q(backs, 9),
        "back_min_max": max(backs) if backs else None,
        "back_km_mean": round(statistics.mean(kms), 2) if kms else None,
        "back_km_median": round(statistics.median(kms), 2) if kms else None,
        "back_over_20": sum(1 for b in backs if b > 20),
        "back_over_30": sum(1 for b in backs if b > 30),
        "ride_per_day_with_back": round(statistics.mean(d["ride_with_back"] for d in days), 1) if days else None,
        "home_after_end_days": len(late),
        "home_after_end_mean_min": round(statistics.mean(late), 1) if late else 0,
        "home_after_end_max_min": max(late) if late else 0,
        "wishes_met": met, "wishes": asked,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--pois", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    m = Matrix(args.matrix)
    doc = json.load(open(args.pois, encoding="utf-8"))
    pois = {p["poi_id"]: p for p in (doc.get("pois") if isinstance(doc, dict) else doc)}
    a, b = plans_of(args.before), plans_of(args.after)
    rows = []
    for key in sorted(set(a) & set(b), key=str):
        entry = {"key": list(key)}
        for side, (row, plan) in (("before", a[key]), ("after", b[key])):
            met, asked = wishes(plan)
            entry[side] = {"passed": bool(plan.get("passed")), "travel_min": int(plan.get("travel_min") or 0),
                           "wishes_met": met, "wishes": asked,
                           "stops": [x["poi_id"] for x in plan.get("activities") or []],
                           "days": day_rows(plan, row, m, args.base, pois)}
        entry["same_stops"] = entry["before"]["stops"] == entry["after"]["stops"]
        entry["same_set"] = set(entry["before"]["stops"]) == set(entry["after"]["stops"])
        rows.append(entry)
    out = {"pairs": len(rows), "same_stops_in_order": sum(r["same_stops"] for r in rows),
           "same_set": sum(r["same_set"] for r in rows),
           "last_changed": sum(1 for r in rows
                               if [d["last"] for d in r["before"]["days"]] != [d["last"] for d in r["after"]["days"]]),
           "before": summarise(rows, "before"), "after": summarise(rows, "after")}
    # Per profile
    for prof in sorted({r["key"][2] for r in rows}, key=str):
        sub = [r for r in rows if r["key"][2] == prof]
        out[f"profile:{prof}"] = {"before": summarise(sub, "before"), "after": summarise(sub, "after")}
    print(json.dumps({k: v for k, v in out.items()}, indent=1, ensure_ascii=False))
    if args.json:
        json.dump({"summary": out, "rows": rows}, open(args.json, "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
