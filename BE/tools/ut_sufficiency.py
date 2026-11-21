"""Is u(t) enough to build the architecture on? (pre-architecture experiment)

    python BE/tools/ut_sufficiency.py            # writes reports/p0/15_ut_sufficiency.json

Three checks on danang-v2.1, no network:

1. coverage  - every active non-lodging POI has a time_profile that exists in
               BE/data/priors/time_profiles.json.
2. hours fit - inside its own opening hours, can the POI reach a good time
               (max u >= 0.6)? and does u vary there (range >= 0.2), i.e.
               does u(t) carry a signal the solver can act on?
3. solver    - the 30 gold_v2 trips are planned twice with the CURRENT
               CP-SAT (same candidates, prize = prize_prior): A without u(t),
               B with u(t) fed through the existing `state_bands/state_score`
               hook (30-min bands). Compare the TRUE objective sum(prize * u_mean),
               stops at a bad time (u_mean < 0.5), stop count and solve time.
               B must not lose feasibility or stops and must raise sum(prize * u_mean).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from BE.common import load_json, load_matrix_cells, parse_windows, to_min, view_pois  # noqa: E402
from BE.app.services.optimizer import StubTrip, optimize, stubs_from_pois  # noqa: E402
from BE.app.services.profiles import _travel_from_cells  # noqa: E402
from BE.app.services.retrieval import retrieve  # noqa: E402
from BE.app.services.time_utility import load_profiles, u_at, u_mean  # noqa: E402

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
GOLD = os.path.join(ROOT, "BE", "eval", "gold", "gold_v2.json")
OUT = os.path.join(ROOT, "reports", "p0", "15_ut_sufficiency.json")
DAY = dt.date(2026, 6, 15)          # peak season (07-08 window kept all year)
BAND = 30
MAX_CAND = 25
DET = float(os.environ.get("UT_DET", "5"))          # solver work budget per solve
ONLY = os.environ.get("UT_ONLY")                   # e.g. "q07,q11" for a spot rerun


def static_checks(raw: list[dict]) -> dict:
    profiles = load_profiles()
    pois = [p for p in raw if p["status"] == "active" and p["category"] != "lodging"]
    missing = [p["poi_id"] for p in pois if p["time_profile"] not in profiles]
    no_good, flat, by_cat = [], [], {}
    for p in pois:
        wins = parse_windows([", ".join(p["hours"].get("open") or [])]) or [(0, 1440)]
        dwell = (p.get("dwell") or {}).get("p50") or 60
        us = [u_mean(p["time_profile"], s, dwell, DAY)
              for lo, hi in wins for s in range(lo, max(lo + 1, hi - dwell + 1), 15)]
        if not us:
            continue
        c = by_cat.setdefault(p["category"], {"n": 0, "no_good": 0, "flat": 0, "range": []})
        c["n"] += 1
        c["range"].append(max(us) - min(us))
        if max(us) < 0.6:
            no_good.append((p["poi_id"], p["name"], p["category"], p["hours"].get("open")))
            c["no_good"] += 1
        if max(us) - min(us) < 0.2:
            flat.append(p["poi_id"])
            c["flat"] += 1
    for c in by_cat.values():
        c["median_range"] = round(st.median(c.pop("range")), 2)
    return {"active_non_lodging": len(pois), "missing_profile": missing,
            "no_good_time_in_hours": len(no_good), "no_good_examples": no_good[:15],
            "flat_in_hours": len(flat), "by_category": by_cat}


def ut_state(stubs, start: int, end: int, prof_of: dict):
    bands = [(a, min(a + BAND, end)) for a in range(start, end, BAND) if min(a + BAND, end) - a >= 15]
    score = {}
    for k, (lo, hi) in enumerate(bands):
        for s in stubs:
            score[(s.poi_id, k)] = u_at(prof_of[s.poi_id], (lo + hi) / 2, DAY)
    return bands, score


def realized(itin, prize, prof_of, dwell_of):
    if not itin:
        return None
    acts = itin["activities"]
    um = [u_mean(prof_of[a["poi_id"]], to_min(a["start"]), dwell_of[a["poi_id"]], DAY) for a in acts]
    return {"stops": len(acts),
            "objective": round(sum(prize[a["poi_id"]] * u for a, u in zip(acts, um)), 3),
            "prize_sum": round(sum(prize[a["poi_id"]] for a in acts), 3),
            "mean_u": round(st.mean(um), 3) if um else None,
            "bad_time_stops": sum(u < 0.5 for u in um),
            "plan": [(a["start"], prof_of[a["poi_id"]], round(u, 2)) for a, u in zip(acts, um)]}


def solver_check(raw: list[dict]) -> dict:
    pois = view_pois(raw, SNAP, "cach_ly")
    by_id = {p["poi_id"]: p for p in pois}
    rawby = {p["poi_id"]: p for p in raw}
    cells = load_matrix_cells(SNAP)
    rows = []
    for q in load_json(GOLD)["suite_v2"]:
        if ONLY and q["query_id"] not in ONLY.split(","):
            continue
        trip = dict(q["trip"])
        cand = [c["poi_id"] for c in retrieve(trip, pois, cells)["candidates"]]
        must = [m for m in trip.get("must_visit", []) if m in by_id]
        prize = {pid: (rawby[pid]["popularity"].get("prize_prior") or 0.3) for pid in cand}
        cand = sorted(set(must) | set(sorted(cand, key=lambda x: -prize[x])[:MAX_CAND]))
        prize.update({m: rawby[m]["popularity"].get("prize_prior") or 0.3 for m in must})
        prof_of = {pid: rawby[pid]["time_profile"] for pid in cand}
        dwell_of = {pid: (rawby[pid]["dwell"] or {}).get("p50") or 60 for pid in cand}
        stubs = stubs_from_pois([by_id[c] for c in cand], trip, lambda p: prize[p["poi_id"]])
        travel = _travel_from_cells(cells, cand)
        st_, en = to_min(trip.get("start_time", "07:00")), to_min(trip.get("end_time", "18:00"))
        strip = StubTrip(st_, en, origin_id=None)
        row = {"query_id": q["query_id"], "window": f'{trip.get("start_time")}-{trip.get("end_time")}',
               "candidates": len(cand)}
        for key in ("A_no_u", "B_with_u"):
            kw = {}
            if key == "B_with_u":
                kw["state_bands"], kw["state_score"] = ut_state(stubs, st_, en, prof_of)
                kw["state_weight"] = 1.0
            t0 = time.monotonic()
            out = optimize(stubs, travel, strip, must_visit=must, workers=1,
                           deterministic_time=DET, timeout_s=2 * DET, **kw)
            row[key] = realized(out.get("itinerary"), prize, prof_of, dwell_of)
            row[key + "_s"] = round(time.monotonic() - t0, 2)
            row[key + "_status"] = out.get("status")
        rows.append(row)
        print(row["query_id"], row["A_no_u"] and row["A_no_u"]["objective"],
              row["B_with_u"] and row["B_with_u"]["objective"], flush=True)
    both = [r for r in rows if r["A_no_u"] and r["B_with_u"]]
    agg = lambda k, f: round(sum(r[k][f] for r in both), 3)
    return {"queries": len(rows), "feasible_A": sum(bool(r["A_no_u"]) for r in rows),
            "feasible_B": sum(bool(r["B_with_u"]) for r in rows),
            "objective_A": agg("A_no_u", "objective"), "objective_B": agg("B_with_u", "objective"),
            "stops_A": agg("A_no_u", "stops"), "stops_B": agg("B_with_u", "stops"),
            "bad_time_A": agg("A_no_u", "bad_time_stops"), "bad_time_B": agg("B_with_u", "bad_time_stops"),
            "mean_u_A": round(st.mean(r["A_no_u"]["mean_u"] for r in both), 3) if both else None,
            "mean_u_B": round(st.mean(r["B_with_u"]["mean_u"] for r in both), 3) if both else None,
            "solve_s_A_max": max((r["A_no_u_s"] for r in rows), default=0),
            "solve_s_B_max": max((r["B_with_u_s"] for r in rows), default=0),
            "rows": rows}


def main() -> int:
    raw = load_json(os.path.join(SNAP, "pois.json"))["pois"]
    rep = {"day": DAY.isoformat(), "static": static_checks(raw)}
    print(json.dumps({k: v for k, v in rep["static"].items() if k != "by_category"}, ensure_ascii=False))
    rep["solver"] = solver_check(raw)
    print(json.dumps({k: v for k, v in rep["solver"].items() if k != "rows"}, ensure_ascii=False))
    if ONLY:
        return 0
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
