"""Are climate + time-of-day travel enough to build the architecture on?

    python BE/tools/context_sufficiency.py      # writes reports/p0/16_context_sufficiency.json

Same 30 gold_v2 trips, same candidates and CP-SAT as ut_sufficiency.py.

E1 climate (June = hot, November = rainy):
   U  : u(t) only (season-blind)
   UW : u(t) x w(poi, climate) through the same state_bands hook, where
        w = 1 - 0.6*sun_exposure*heat - 0.8*open_air*rain_prob,
        heat = clamp((feels_c - 32) / 8, 0, 1), open_air = open 1 / mixed .5 / enclosed 0.
        (experiment formula; the architecture owns the final weather rule)
   Measured: heat-exposed stops (feels >= 36 C and sun_exposure >= 0.7),
   rain-exposed stops (rain_prob >= 0.2 and rain_cover = open), feasibility, stops.

E2 travel by time of day:
   R  : the U plans (free-flow OSRM matrix) re-timed with the traffic factors:
        how many plans still hold (every stop inside hours and the trip window)?
   T  : solved again on a matrix scaled by each pair's worst factor inside the
        trip window (what a static solver must do without time-dependent arcs).
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

from BE.common import load_json, load_matrix_cells, to_min, view_pois  # noqa: E402
from BE.app.services.climate import climate_at  # noqa: E402
from BE.app.services.optimizer import StubTrip, optimize, stubs_from_pois  # noqa: E402
import BE.app.services.optimizer as _opt  # noqa: E402

_opt.STATE_WEIGHT = 1.0   # experiment weight (main ships 0.5); same as the 20/11 runs
from BE.app.services.profiles import _travel_from_cells  # noqa: E402
from BE.app.services.retrieval import retrieve  # noqa: E402
from BE.app.services.time_utility import u_at, u_mean  # noqa: E402
from BE.app.services.travel_time import factor  # noqa: E402

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
GOLD = os.path.join(ROOT, "BE", "eval", "gold", "gold_v2.json")
OUT = os.path.join(ROOT, "reports", "p0", "16_context_sufficiency.json")
DAYS = {"jun": dt.date(2026, 6, 15), "nov": dt.date(2026, 11, 15)}
BAND, MAX_CAND = 30, 25
DET = float(os.environ.get("CTX_DET", "5"))
OPEN_AIR = {"open": 1.0, "mixed": 0.5, "enclosed": 0.0}


def w_at(tags: dict, zone: str, month: int, minute: float) -> float:
    c = climate_at(zone, month, minute)
    heat = min(1.0, max(0.0, (c["feels_c"] - 32) / 8))
    sun = tags.get("sun_exposure") or 0.0
    air = OPEN_AIR.get(tags.get("rain_cover"), 0.0)
    return max(0.0, 1 - 0.6 * sun * heat - 0.8 * air * c["rain_prob"])


def solve(stubs, travel, trip_window, must, score_fn=None):
    st_, en = trip_window
    kw = {}
    if score_fn:
        bands = [(a, min(a + BAND, en)) for a in range(st_, en, BAND) if min(a + BAND, en) - a >= 15]
        kw = {"state_bands": bands,
              "state_score": {(s.poi_id, k): score_fn(s.poi_id, (lo + hi) / 2)
                              for k, (lo, hi) in enumerate(bands) for s in stubs}}
    t0 = time.monotonic()
    out = optimize(stubs, travel, StubTrip(st_, en, origin_id=None), must_visit=must, workers=1,
                   deterministic_time=DET, timeout_s=2 * DET, **kw)
    return out.get("itinerary"), round(time.monotonic() - t0, 2)


def exposure(itin, raw, month):
    if not itin:
        return None
    heat = rain = 0
    for a in itin["activities"]:
        p = raw[a["poi_id"]]
        tags, z = p["tags"], p["zone"]
        dwell = (p["dwell"] or {}).get("p50") or 60
        mid = to_min(a["start"]) + dwell / 2
        c = climate_at(z, month, mid)
        heat += c["feels_c"] >= 36 and (tags.get("sun_exposure") or 0) >= 0.7
        rain += c["rain_prob"] >= 0.2 and tags.get("rain_cover") == "open"
    return {"stops": len(itin["activities"]), "heat_exposed": heat, "rain_exposed": rain}


def retime(itin, stub_by, base_travel, raw, window):
    """Replay a plan's order with traffic-factored legs; count broken stops."""
    acts = itin["activities"]
    clock, prev, broken, delay = to_min(acts[0]["start"]), None, 0, 0
    for a in acts:
        s = stub_by[a["poi_id"]]
        if prev is not None:
            base = base_travel.get((prev, s.poi_id), 0)
            dep = clock
            leg = round(base * factor(raw[prev]["zone"], raw[s.poi_id]["zone"], dep))
            clock = dep + leg
        start = max(clock, s.open_min, to_min(a["start"]))
        delay += start - to_min(a["start"])
        wins = list(s.windows) or [(s.open_min, s.close_min)]
        if not any(o <= start and start + s.visit_min <= c for o, c in wins) or start + s.visit_min > window[1]:
            broken += 1
        clock, prev = start + s.visit_min, s.poi_id
    return {"broken_stops": broken, "delay_min": delay}


def main() -> int:
    raw_list = load_json(os.path.join(SNAP, "pois.json"))["pois"]
    raw = {p["poi_id"]: p for p in raw_list}
    pois = view_pois(raw_list, SNAP, "cach_ly")
    by_id = {p["poi_id"]: p for p in pois}
    cells = load_matrix_cells(SNAP)
    rows = []
    for q in load_json(GOLD)["suite_v2"]:
        trip = dict(q["trip"])
        cand = [c["poi_id"] for c in retrieve(trip, pois, cells)["candidates"]]
        must = [m for m in trip.get("must_visit", []) if m in by_id]
        prize = {pid: raw[pid]["popularity"].get("prize_prior") or 0.3 for pid in set(cand) | set(must)}
        cand = sorted(set(must) | set(sorted(cand, key=lambda x: -prize[x])[:MAX_CAND]))
        stubs = stubs_from_pois([by_id[c] for c in cand], trip, lambda p: prize[p["poi_id"]])
        stub_by = {s.poi_id: s for s in stubs}
        travel = _travel_from_cells(cells, cand)
        win = (to_min(trip.get("start_time", "07:00")), to_min(trip.get("end_time", "18:00")))
        row = {"query_id": q["query_id"], "window": f'{trip["start_time"]}-{trip["end_time"]}'}
        for key, day in DAYS.items():
            prof = lambda pid, m, day=day: u_at(raw[pid]["time_profile"], m, day)
            uw = lambda pid, m, day=day: prof(pid, m) * w_at(raw[pid]["tags"], raw[pid]["zone"], day.month, m)
            iu, su = solve(stubs, travel, win, must, prof)
            iw, sw = solve(stubs, travel, win, must, uw)
            row[key] = {"U": exposure(iu, raw, day.month), "UW": exposure(iw, raw, day.month),
                        "U_s": su, "UW_s": sw}
            if key == "jun":
                row["R"] = retime(iu, stub_by, travel, raw, win) if iu else None
                worst = {(a, b): round(m * max(factor(raw[a]["zone"], raw[b]["zone"], t)
                                               for t in range(win[0], win[1], 30)))
                         for (a, b), m in travel.items()}
                it, stt = solve(stubs, worst, win, must, prof)
                row["T"] = {"stops": len(it["activities"]) if it else None, "s": stt,
                            "R": retime(it, stub_by, travel, raw, win) if it else None}
        rows.append(row)
        print(q["query_id"], json.dumps({k: row[k] for k in ("jun", "nov")}, ensure_ascii=False)[:160],
              "R", row["R"], "T", row["T"]["stops"], flush=True)

    def tot(month, arm, f):
        return sum((r[month][arm] or {}).get(f, 0) for r in rows)

    summ = {"queries": len(rows)}
    for m in DAYS:
        summ[m] = {arm: {"feasible": sum(bool(r[m][arm]) for r in rows),
                         "stops": tot(m, arm, "stops"),
                         "heat_exposed": tot(m, arm, "heat_exposed"),
                         "rain_exposed": tot(m, arm, "rain_exposed")} for arm in ("U", "UW")}
    rr = [r["R"] for r in rows if r["R"]]
    tr = [r["T"]["R"] for r in rows if r["T"]["R"]]
    summ["traffic"] = {
        "free_flow_plans": len(rr),
        "plans_broken_under_traffic": sum(x["broken_stops"] > 0 for x in rr),
        "broken_stops": sum(x["broken_stops"] for x in rr),
        "mean_delay_min": round(st.mean(x["delay_min"] for x in rr), 1) if rr else None,
        "worst_case_matrix": {"feasible": sum(r["T"]["stops"] is not None for r in rows),
                              "stops": sum(r["T"]["stops"] or 0 for r in rows),
                              "stops_free_flow": tot("jun", "U", "stops"),
                              "plans_broken_under_traffic": sum(x["broken_stops"] > 0 for x in tr)}}
    print(json.dumps(summ, ensure_ascii=False))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"summary": summ, "rows": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
