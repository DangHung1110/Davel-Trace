#!/usr/bin/env python3
"""Step 2 check: do J's features describe the plan a judge sees, and do they add up
to what CP-SAT maximised?

    python reports/objective_v1/scripts/features_check.py run <out.json> [--wet] [--only A,B]
    python reports/objective_v1/scripts/features_check.py report <out.json> [<out2.json> ...]

`run` plans the audit scenarios (BE/tools/audit_plans.SCENARIOS, 67 requests) and the
30 gold requests (BE/eval/gold/gold_v2.json) through POST /v1/itinerary in-process,
then keeps the `_features` of every returned plan (one entry per day). Weather is
offline, or with --wet a fixed forecast (90 % rain 12:00-17:00, 10 % otherwise) on a
date every request is moved to, so the rain term has work to do.

`report` counts, per file:
  - formula: |J(raw features) - J reported by CP-SAT| <= 0.01 U (the features read off
    the solver's own times must reproduce its objective);
  - re-timing: days whose features at the shown times differ from the raw times, by
    term, and how much J the shown day lost or gained.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WET_DATE = "2026-11-28"
TOLERANCE = 0.01


def _wet_forecast(*_args, **_kwargs) -> dict:
    hourly = [{"at": f"{WET_DATE}T{h:02d}:00", "temp_c": 29.0,
               "rain_prob": 0.9 if 12 <= h < 17 else 0.1} for h in range(24)]
    return {"fetched_at": "2026-11-26T00:00:00", "hourly": hourly,
            "source": "features_check-wet", "stale": False}


def _requests() -> list[tuple[str, dict]]:
    from BE.tools import audit_plans

    out = [(key, {**audit_plans.DAY, **extra}) for key, extra in audit_plans.SCENARIOS]
    gold = json.load(open(REPO_ROOT / "BE" / "eval" / "gold" / "gold_v2.json",
                          encoding="utf-8"))["suite_v2"]
    for q in gold:
        out.append((f"G-{q['query_id']}", {**q["trip"], "profile": q.get("profile") or {}}))
    return out


def run(out_path: str, wet: bool, only: list[str] | None) -> None:
    from fastapi.testclient import TestClient

    from BE.app import main as main_mod
    from BE.app.config import Settings
    from BE.app.routers import itinerary as itinerary_mod
    from BE.app.routers import select as select_svc
    from BE.app.services import trip_ctx

    os.chdir(REPO_ROOT)
    snap = str(REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v2")
    settings = Settings(snapshot_dir=snap, snapshot_name="danang-v2")
    client = TestClient(main_mod.app)
    weather = (mock.patch.object(trip_ctx.weather_svc, "fetch_forecast", side_effect=_wet_forecast)
               if wet else
               mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                                 side_effect=RuntimeError("offline")))
    rows = []
    with mock.patch.object(itinerary_mod, "get_settings", lambda: settings), weather:
        for key, trip in _requests():
            if only and not any(key.startswith(p) for p in only):
                continue
            if wet:
                trip = {**trip, "date": WET_DATE}
            t0 = time.perf_counter()
            resp = client.post("/v1/itinerary", json={"trip": trip})
            wall = time.perf_counter() - t0
            body = resp.json()
            store = select_svc.get_store()["plans"]
            for public in body.get("plans") or []:
                full = store.get(public.get("itinerary_id")) or {}
                days = full.get("_features_by_day") or [full.get("_features")]
                for number, feats in enumerate(days, start=1):
                    rows.append({"key": key, "profile": public.get("profile"), "day": number,
                                 "passed": public.get("passed"), "features": feats})
            print(f"{key}: {resp.status_code} {wall:5.1f}s "
                  + " ".join(f"{p.get('profile')}:{len(p.get('activities') or [])}"
                             for p in body.get("plans") or []), flush=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"wet": wet, "rows": rows}, fh, ensure_ascii=False)


def report(paths: list[str]) -> dict:
    from BE.app.services.objective import FEATURES

    summary = {}
    for path in paths:
        data = json.load(open(path, encoding="utf-8"))
        rows = [r for r in data["rows"] if r.get("features")]
        resid = [r["features"]["raw"]["j"] - r["features"]["solver_j"] for r in rows]
        bad = [(r, d) for r, d in zip(rows, resid) if abs(d) > TOLERANCE]
        changed, terms, lost = 0, Counter(), []
        for r in rows:
            raw, shown = r["features"]["raw"], r["features"]["shown"]
            moved = [k for k in FEATURES if k in raw["features"]  # files from before `wait`
                     and abs(raw["features"][k] - shown["features"][k]) > 1e-9]
            if moved:
                changed += 1
                terms.update(moved)
                lost.append(round(shown["j"] - raw["j"], 4))
        rain = sum(1 for r in rows if r["features"]["shown"]["features"]["rain"] > 0)
        out = {"days": len(rows), "missing": len(data["rows"]) - len(rows),
               "formula_ok": len(rows) - len(bad),
               "formula_worst": sorted((round(d, 4), r["key"], r["profile"]) for r, d in bad)[:10],
               "retimed_days": changed, "retimed_terms": dict(terms.most_common()),
               "retimed_dj": {"lower": sum(1 for d in lost if d < 0),
                              "higher": sum(1 for d in lost if d > 0),
                              "min": min(lost, default=0.0), "max": max(lost, default=0.0),
                              "mean": round(sum(lost) / len(lost), 4) if lost else 0.0},
               "days_with_rain": rain,
               "days_with_meal_far": sum(1 for r in rows
                                         if r["features"]["shown"]["features"]["meal_far"] > 0),
               "days_with_rest": sum(1 for r in rows
                                     if r["features"]["shown"]["features"]["rest"] > 0)}
        # Step 2b: the shown day keeps the solver's stops; re-timing kept or dropped;
        # idle minutes at both times; plans the gate failed.
        shown_rows = [r for r in rows if "retimed" in r["features"]]
        out["kept_retiming"] = sum(1 for r in shown_rows if r["features"]["retimed"])
        out["same_stops"] = sum(1 for r in shown_rows if r["features"]["same_stops"])
        out["days_with_rain_raw"] = sum(1 for r in rows
                                        if r["features"]["raw"]["features"]["rain"] > 0)
        for side in ("raw", "shown"):
            waits = sorted(r["features"][side]["features"].get("wait", 0.0) for r in rows)
            if waits:
                out[f"wait_{side}"] = {"mean": round(sum(waits) / len(waits), 1),
                                       "p90": waits[int(len(waits) * 0.9)], "max": waits[-1],
                                       "days_30plus": sum(1 for w in waits if w >= 30)}
        out["gate_failed_plans"] = sum(1 for r in data["rows"] if r.get("passed") is False)
        summary[os.path.basename(path)] = out
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "run":
        only = None
        if "--only" in argv:
            only = argv[argv.index("--only") + 1].split(",")
        run(argv[1], "--wet" in argv, only)
        return 0
    if len(argv) >= 2 and argv[0] == "report":
        report(argv[1:])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
