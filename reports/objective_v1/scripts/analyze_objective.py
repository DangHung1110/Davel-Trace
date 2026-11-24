#!/usr/bin/env python3
"""Compare eval_objective.py outputs: legacy vs v1 on the same held-out requests.

python analyze_objective.py <repo> <legacy.jsonl> <v1.jsonl> [out.json]
"""
from __future__ import annotations

import collections
import json
import os
import statistics as st
import sys


def load(path):
    rows = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        rows[r["id"]] = r
    return rows


def main():
    repo, legacy_path, v1_path = sys.argv[1:4]
    out_path = sys.argv[4] if len(sys.argv) > 4 else None
    os.chdir(repo)
    sys.path.insert(0, repo)
    from BE.app.services import objective
    from BE.app.services.matrix import travel_minutes
    from BE.app.services.soft_rules import meal_window_present
    from BE.common import load_matrix_cells, to_min

    snap = os.path.join("BE", "data", "snapshots", "danang-v2")
    pois = json.load(open(os.path.join(snap, "pois.json"), encoding="utf-8"))["pois"]
    by_id = {p["poi_id"]: p for p in pois}
    cells = load_matrix_cells(snap)
    group = {pid: objective.diversity_group(p) for pid, p in by_id.items()}

    runs = {"legacy": load(legacy_path), "v1": load(v1_path)}
    common = sorted(set(runs["legacy"]) & set(runs["v1"]))
    report = {"n": len(common)}
    for name, rows in runs.items():
        m = collections.defaultdict(list)
        slots = collections.Counter()
        pace_stops = collections.defaultdict(list)
        for rid in common:
            r = rows[rid]
            sol = r["solution"]
            m["solved"].append(1 if sol else 0)
            m["elapsed"].append(r["elapsed"])
            if not sol:
                continue
            ids = [s[0] for s in sol]
            slots.update(ids)
            trav = travel_minutes(cells, ids)
            legs = [trav.get((a, b), 0) for a, b in zip(ids, ids[1:])]
            m["stops"].append(len(ids))
            m["ride"].append(sum(legs))
            m["longest_leg"].append(max(legs) if legs else 0)
            zones = [by_id[p].get("zone") for p in ids]
            m["zone_changes"].append(sum(1 for a, b in zip(zones, zones[1:]) if a != b))
            gs = [group[p] for p in ids if group[p]]
            cnt = collections.Counter(gs)
            m["distinct_groups"].append(len(cnt))
            m["repeat_plan"].append(1 if any(c >= 2 for c in cnt.values()) else 0)
            m["two_beaches"].append(1 if cnt.get("beach", 0) >= 2 else 0)
            m["adjacent_same"].append(sum(1 for a, b in zip(ids, ids[1:])
                                          if group[a] and group[a] == group[b]))
            trip = r["trip"]
            if (trip.get("profile") or {}) and meal_window_present(trip, "lunch"):
                lunch = any(group[p] == "" and by_id[p]["category"] == "restaurant"
                            and 11 * 60 <= to_min(s) < 13 * 60 for p, s, _e in sol)
                m["lunch_ok"].append(1 if lunch else 0)
            pace = (trip.get("profile") or {}).get("pace") or 2
            pace_stops[int(pace)].append(len(ids))
            g = r.get("gate") or {}
            m["gate_pass"].append(1 if g.get("passed") else 0)
            for soft in g.get("soft_failed") or []:
                m["soft_" + soft].append(1)
        total = sum(slots.values()) or 1
        top20 = sum(c for _p, c in slots.most_common(20)) / total
        solved = len(m["stops"])

        def mean(key):
            return round(st.mean(m[key]), 3) if m[key] else None

        report[name] = {
            "solved": f"{sum(m['solved'])}/{len(common)}",
            "elapsed_median_s": round(st.median(m["elapsed"]), 2),
            "stops_mean": mean("stops"),
            "ride_min_median": st.median(m["ride"]) if m["ride"] else None,
            "ride_min_mean": mean("ride"),
            "longest_leg_mean": mean("longest_leg"),
            "zone_changes_mean": mean("zone_changes"),
            "distinct_groups_mean": mean("distinct_groups"),
            "plans_with_repeat_group": f"{sum(m['repeat_plan'])}/{solved}",
            "plans_with_two_beaches": f"{sum(m['two_beaches'])}/{solved}",
            "adjacent_same_group_mean": mean("adjacent_same"),
            "lunch_in_window": f"{sum(m['lunch_ok'])}/{len(m['lunch_ok'])}",
            "stops_by_pace": {k: round(st.mean(v), 2) for k, v in sorted(pace_stops.items())},
            "top20_share": round(top20, 3),
            "distinct_pois": len(slots),
            "gate_pass": f"{sum(m['gate_pass'])}/{solved}",
            "soft_failed": {k[5:]: len(v) for k, v in sorted(m.items()) if k.startswith("soft_")},
        }
    text = json.dumps(report, ensure_ascii=False, indent=1)
    print(text)
    if out_path:
        open(out_path, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main()
