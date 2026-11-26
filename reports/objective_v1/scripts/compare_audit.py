#!/usr/bin/env python3
"""Before/after of two BE/tools/audit_plans.py runs: gate, how many plans changed, per profile.

python compare_audit.py <before.json> <before_flags.json> <after.json> <after_flags.json> [out.json]

The flags files are the audits' --flags output. A plan is "identical" (same stops, same
times), "retimed" (same stops in the same order, other times), "reordered" (same stops,
other order) or "other_pois". `pair_jaccard_*` is the POI-set Jaccard between the three
plans of one request (services/pool.py), `router_replacements` the plans the router
replaced to keep it under 0.6.
"""
import itertools
import json
import statistics as st
import sys
from collections import Counter, defaultdict

PROFILES = ("savings", "balanced", "experience")


def load(audit_path, flags_path):
    doc = json.load(open(audit_path, encoding="utf-8"))
    flags = json.load(open(flags_path, encoding="utf-8"))
    plans = {}
    for row in doc["rows"]:
        for plan in row["body"].get("plans") or []:
            plans[f"{row['key']}/{plan.get('profile')}"] = plan
    days = defaultdict(list)
    for d in flags["day_stats"]:
        days[d["plan"]].append(d)
    return doc["rows"], plans, flags["plan_flags"], days


def stops(plan, times=False):
    acts = sorted(plan.get("activities") or [], key=lambda a: (a.get("day") or 1, a["start"]))
    return [(a["poi_id"], a.get("day") or 1) + ((a["start"], a["end"]) if times else ())
            for a in acts]


def poi_set(plan):
    return {a["poi_id"] for a in plan.get("activities") or []}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def kind(before, after):
    if stops(before, True) == stops(after, True):
        return "identical"
    if stops(before) == stops(after):
        return "retimed"
    if set(stops(before)) == set(stops(after)):
        return "reordered"
    return "other_pois"


def side(rows, plans, flags, days):
    hard = ("ERR_", "EMPTY", "GATE_FAILED")
    out = {"plans": len(plans),
           "empty": sum(1 for p in plans.values() if not p.get("activities")),
           "gate_failed": sum(1 for p in plans.values() if not p.get("passed")),
           "followable": sum(1 for pid in plans
                             if not any(f.startswith(hard) for f in flags.get(pid, [])))}
    out["per_profile"] = {}
    for prof in PROFILES:
        mine = {pid: p for pid, p in plans.items() if pid.endswith("/" + prof)}
        d = [x for pid in mine for x in days.get(pid, []) if x["stops"]]
        out["per_profile"][prof] = {
            "stops_per_day": round(st.mean(x["stops"] for x in d), 2),
            "travel_per_day_mean": round(st.mean(x["travel"] for x in d), 1),
            "max_leg_mean": round(st.mean(x["max_leg"] for x in d), 1),
            "idle_per_day_mean": round(st.mean(x["idle"] for x in d), 1),
            "cost_per_plan_mean": round(st.mean(p.get("total_cost") or 0 for p in mine.values())),
            "flags": dict(Counter(f.split()[0] for pid in mine for f in flags.get(pid, []))),
        }
    sims, replaced = [], 0
    for row in rows:
        sets = [poi_set(p) for p in row["body"].get("plans") or []]
        sims += [jaccard(a, b) for a, b in itertools.combinations(sets, 2) if a and b]
        replaced += len((row["body"].get("solution_pool") or {}).get("replaced") or [])
    out.update(pair_jaccard_mean=round(st.mean(sims), 3), pair_jaccard_max=round(max(sims), 3),
               pairs_over_0_6=sum(1 for s in sims if s > 0.6 + 1e-9), pairs=len(sims),
               router_replacements=replaced)
    return out


def main():
    before, after = load(*sys.argv[1:3]), load(*sys.argv[3:5])
    report = {"before": side(*before), "after": side(*after), "change": {}}
    for prof in PROFILES:
        ids = sorted(pid for pid in before[1] if pid.endswith("/" + prof) and pid in after[1])
        kinds = Counter(kind(before[1][pid], after[1][pid]) for pid in ids)
        report["change"][prof] = {k: kinds.get(k, 0)
                                  for k in ("identical", "retimed", "reordered", "other_pois")}
    report["other_pois"] = {
        pid: {"travel_min": [before[1][pid].get("travel_min"), after[1][pid].get("travel_min")],
              "total_cost": [before[1][pid].get("total_cost"), after[1][pid].get("total_cost")]}
        for pid in sorted(before[1]) if pid in after[1]
        and kind(before[1][pid], after[1][pid]) == "other_pois"}
    print(json.dumps({k: v for k, v in report.items() if k != "other_pois"}, ensure_ascii=False,
                     indent=1))
    if len(sys.argv) > 5:
        json.dump(report, open(sys.argv[5], "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
