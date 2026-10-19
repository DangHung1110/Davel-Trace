"""T053 full-suite run: baselines vs hybrid on the T051 gold (lane A). No LLM
in scoring; the tier-1 evaluator (`BE/eval/metrics.evaluate`) is the judge.

Three planners over the SAME scoped gold queries (T051: 30 Approach-B
queries over the 5/764 matrix-covered verified POIs; 23 feasible):

- distance-only baseline: the T051 Approach-B gold itself (OR-Tools TSP on
  real OSRM minutes, preference-blind). It is the shortest-path reference
  SC-009 is measured against, not an independent "better" plan.
- hybrid (the system): the real app pipeline retrieval -> rank ->
  `profiles.build_plan("balanced")` = CP-SAT objective (rating preference)
  + PATM q_ij edge bonuses (scorer) + gate validation. Distance AND
  preference AND the transition model, hence "hybrid".
- LLM-only baseline: the LLM alone orders the candidate POIs (no matrix, no
  distance, no preference model); the order is placed by the SAME chaining
  seam the gold uses, so the comparison isolates ORDERING. Needs a live LLM
  (Ollama `qwen3:14b` or an api provider). When none is reachable the run
  records `status: SKIP` with the transport reason and NEVER fabricates
  numbers — the other two systems still run.

Then records SC-005..SC-010 from the evaluator results (SC-010 via a
replan recovery probe, since static golds have no incident; T051 note).

Usage (repo root):
  python BE/eval/baselines.py \
      --suite BE/eval/gold/t051_scoped_suite.json \
      --snapshot BE/data/snapshots/danang-v1 \
      --out BE/eval/gold/t053_baselines.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.services.gate import CHECKS as GATE_CHECKS  # noqa: E402
from BE.common import load_json, load_matrix_cells, load_pois  # noqa: E402
from BE.eval.gold.approach_b import chain_order, filter_pois  # noqa: E402
from BE.eval.gold.build import coverage_summary, eligible_ids  # noqa: E402
from BE.eval.metrics import evaluate  # noqa: E402

DEFAULT_SUITE = os.path.join("BE", "eval", "gold", "t051_scoped_suite.json")
DEFAULT_SNAPSHOT = os.path.join("BE", "data", "snapshots", "danang-v1")
HYBRID_PROFILE = "balanced"
# CP-SAT with >1 worker is wall-clock dependent: two runs can return two
# different optima. The harness pins one worker so a published SC table is
# reproducible; the product endpoint keeps the solver default (0).
EVAL_WORKERS = 1
ZERO_FEE_NOTE = ("all candidate fees are 0 in the scoped snapshot -> BCS is "
                 "vacuous: SC-008 is reported but cannot be exercised here "
                 "(T051 note: T053 must extend fee coverage)")


class LLMUnavailable(RuntimeError):
    """Raised when the LLM-only baseline cannot reach a live LLM."""


# --- the three planners ----------------------------------------------------

def distance_only_itinerary(record: dict) -> dict | None:
    """The T051 Approach-B gold IS the distance-only (shortest-path) plan."""
    return record.get("itinerary")


def hybrid_itinerary(record: dict, pois_list: list[dict], by_id: dict,
                     cells: dict, profile: str = HYBRID_PROFILE,
                     workers: int = EVAL_WORKERS) -> dict:
    """Real app pipeline: retrieval -> rank -> profiles.build_plan (hybrid)."""
    from BE.app.services import profiles, rank, retrieval

    trip = record["trip"]
    found = retrieval.retrieve(trip, pois_list)
    cids = [c["poi_id"] for c in found["candidates"]]
    ranked = rank.rank([by_id[i] for i in cids], {"budget": trip["budget"]},
                       {"trip": trip, "hour": trip.get("start_time", "07:00")})
    plan = profiles.build_plan(profile, trip, ranked, by_id, cells,
                               workers=workers)
    return {"activities": plan.get("activities", []),
            "total_cost": plan.get("total_cost")}


def llm_order_prompt(record: dict, cand_ids: list[str], by_id: dict) -> str:
    """Prompt asking the LLM alone to order the candidate POIs (JSON only)."""
    trip = record["trip"]
    rows = []
    for pid in cand_ids:
        p = by_id[pid]
        rows.append(f"- {pid}: {p.get('name', '?')} "
                    f"({p.get('type', '?')}, rating {p.get('rating')}, "
                    f"gio {p.get('opening_hours')})")
    return ("Ban la bo lap lich THUAN LLM: khong co ban do, khong co khoang cach, "
            "khong co mo hinh so thich. Sap thu tu cac dia diem duoi day thanh "
            "mot lich 1 ngay hop ly theo yeu cau. Chi tra JSON "
            "{\"order\": [poi_id, ...]} giu DUNG id, khong giai thich.\n"
            f"Yeu cau: {record.get('prefs_text', '')}\n"
            f"Khung gio {trip.get('start_time')}-{trip.get('end_time')}, "
            f"ngan sach {trip.get('budget')}, "
            f"must_visit {trip.get('must_visit', [])}.\n"
            "Dia diem:\n" + "\n".join(rows))


def llm_only_itinerary(record: dict, pois: dict, matrix: dict,
                       complete) -> dict:
    """LLM orders candidates; the shared chain seam places them.

    `complete(prompt) -> {"order": [poi_id, ...]}` (raises on transport
    failure -> LLMUnavailable). Ordering/must_visit/budget failures are the
    baseline's own failures (returned infeasible), never patched by us.
    """
    cands, bad = filter_pois(record["trip"], pois)
    if bad or not cands:
        return {"itinerary": None, "infeasible": bad or "no candidates"}
    try:
        res = complete(llm_order_prompt(record, cands, pois))
    except LLMUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - any LLM failure = unavailable
        raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
    order = [pid for pid in (res.get("order") or []) if pid in cands]
    if not order:
        return {"itinerary": None, "infeasible": "llm returned no usable order"}
    acts, reason = chain_order(order, record["trip"], pois, matrix,
                               evidence="baseline:llm-only")
    if acts is None:
        return {"itinerary": None, "infeasible": reason}
    return {"itinerary": {"activities": acts}, "infeasible": ""}


def default_complete(prompt: str) -> dict:
    """Live LLM via the app gateway; wraps failures as LLMUnavailable."""
    from BE.app.services import llm

    try:
        from pydantic import BaseModel

        class _Order(BaseModel):
            order: list[str] = []

        return llm.complete_json(prompt, schema=_Order)
    except llm.LLMError as exc:
        raise LLMUnavailable(f"llm transport: {exc}") from exc


# --- SC-010 recovery probe -------------------------------------------------

def recovery_probe(record: dict, activities: list[dict], pois: dict,
                   matrix: dict) -> dict:
    """Rain incident after the first activity: does a plan survive intact?

    SC-010: recovery succeeds (a NEW versioned feasible plan) AND every
    completed activity is preserved. Probes only plans with >=2 activities
    (a 1-activity plan has nothing left to replan).
    """
    if len(activities) < 2:
        return {"ok": None, "reason": "fewer than 2 activities"}
    from BE.app.services import replan as replan_svc
    from BE.app.services import state as store

    trip = record["trip"]
    state = store.new_state("t053-probe", activities,
                            start_time=trip.get("start_time", "07:00"))
    done = activities[:1]
    for a in done:
        state = store.complete(state, a["poi_id"], at=a["end"])
    travel = {}
    for a in activities:
        for b in activities:
            cell = matrix.get(f"{a['poi_id']}->{b['poi_id']}")
            if a["poi_id"] != b["poi_id"] and cell is not None:
                travel[(a["poi_id"], b["poi_id"])] = int(cell["minutes"])
    res = replan_svc.replan(state, {"type": "rain", "text": "troi mua"},
                            list(pois.values()), travel, trip)
    done_ids = [a["poi_id"] for a in done]
    preserved = all(pid in res.get("preserved_completed", []) for pid in done_ids)
    ok = (res.get("mode") == "plan" and res.get("itinerary") is not None
          and preserved)
    return {"ok": ok, "mode": res.get("mode"), "preserved": preserved}


# --- aggregation -----------------------------------------------------------

def _system_metrics(reports: list[dict]) -> dict:
    """Reports (one per feasible query) -> gate pass / violations / soft."""
    n = len(reports)
    passed = sum(1 for r in reports if r["gate"]["passed"])
    viol = {name: 0 for name, _ in GATE_CHECKS}
    for r in reports:
        for v in r["gate"]["violations"]:
            viol[v] = viol.get(v, 0) + 1
    soft_mean: dict[str, float | None] = {}
    for key in ("STR", "DTU", "SSR", "CSM", "EDI", "AQE"):
        vals = [r["soft"][key] for r in reports if r["soft"]]
        soft_mean[key] = round(sum(vals) / len(vals), 4) if vals else None
    ratings = [a for r in reports for a in r.get("_ratings", [])]
    return {"n": n, "gate_pass": passed,
            "pass_rate": round(passed / n, 4) if n else 0.0,
            "violations": viol, "soft_mean": soft_mean,
            "mean_rating": round(sum(ratings) / len(ratings), 4) if ratings else None}


def _sc_table(dist: dict, hyb: dict, recovery: dict, zero_fee: bool,
              uniform_ratings: bool = False) -> dict:
    """SC-005..SC-010 as target-vs-actual rows (distance-only vs hybrid)."""
    s005 = {"target": ">=90% feasible tasks yield a gate-passing plan",
            "distance_only": dist["pass_rate"], "hybrid": hyb["pass_rate"],
            "pass": dist["pass_rate"] >= 0.9 and hyb["pass_rate"] >= 0.9}
    s006 = {"target": "opening-hours violations = 0",
            "distance_only": dist["violations"].get("VROH", 0),
            "hybrid": hyb["violations"].get("VROH", 0), "pass": True}
    s006["pass"] = (s006["distance_only"] == 0 and s006["hybrid"] == 0)
    s007 = {"target": "no overlaps / missing travel (B3+TCS violations = 0)",
            "distance_only": dist["violations"].get("B3", 0) + dist["violations"].get("TCS", 0),
            "hybrid": hyb["violations"].get("B3", 0) + hyb["violations"].get("TCS", 0),
            "pass": True}
    s007["pass"] = s007["distance_only"] == 0 and s007["hybrid"] == 0
    s008 = {"target": "budget violations = 0 when budget is a hard constraint",
            "distance_only": dist["violations"].get("BCS", 0),
            "hybrid": hyb["violations"].get("BCS", 0),
            "vacuous": zero_fee, "pass": True}
    s008["pass"] = (s008["distance_only"] == 0 and s008["hybrid"] == 0)
    d_fit, h_fit = dist.get("mean_rating"), hyb.get("mean_rating")
    ratio = (h_fit / d_fit) if (d_fit and h_fit) else None
    # A uniform-rating pool cannot discriminate preference: the ratio is then
    # 1.0 by construction, so SC-009 is "undecidable here", not "proven equal".
    s009 = {"target": "hybrid taste-fit >= 1.10x shortest-path baseline",
            "metric": "mean POI rating of the plan (preference proxy)",
            "distance_only": d_fit, "hybrid": h_fit,
            "ratio": round(ratio, 4) if ratio is not None else None,
            "undecidable": uniform_ratings,
            "pass": bool(ratio is not None and ratio >= 1.10)}
    probed = recovery.get("probed", 0)
    rec_rate = (recovery.get("ok", 0) / probed) if probed else None
    s010 = {"target": "recovery succeeds >=80% and keeps 100% completed",
            "probed": probed, "recovered": recovery.get("ok", 0),
            "recovery_rate": round(rec_rate, 4) if rec_rate is not None else None,
            "preserved_all": recovery.get("preserved_all", False),
            "pass": bool(probed and rec_rate is not None and rec_rate >= 0.8
                         and recovery.get("preserved_all", False))}
    return {"SC-005": s005, "SC-006": s006, "SC-007": s007,
            "SC-008": s008, "SC-009": s009, "SC-010": s010}


def run(suite_path: str = DEFAULT_SUITE, snapshot_dir: str = DEFAULT_SNAPSHOT,
        llm_complete=None, profile: str = HYBRID_PROFILE,
        limit: int | None = None) -> dict:
    """Run distance-only + hybrid + (LLM-only or SKIP) -> report dict.

    `limit` caps the number of feasible queries (smoke runs / tests); the
    published run leaves it None to cover the whole scoped suite.
    """
    suite = load_json(suite_path)
    pois_list = load_pois(snapshot_dir)
    by_id = {p["poi_id"]: p for p in pois_list}
    matrix = load_matrix_cells(snapshot_dir)
    eligible = eligible_ids(by_id, matrix)
    coverage = coverage_summary(by_id, matrix, eligible)
    feasible = [r for r in suite if r.get("itinerary") is not None]
    if limit is not None:
        feasible = feasible[:limit]

    dist_reports, hyb_reports, hyb_plans = [], [], []
    for rec in feasible:
        d = distance_only_itinerary(rec) or {"activities": []}
        h = hybrid_itinerary(rec, pois_list, by_id, matrix, profile)
        dr = {"_ratings": _ratings(d["activities"], by_id),
              **evaluate(d, rec["trip"], by_id, matrix)}
        hr = {"_ratings": _ratings(h["activities"], by_id),
              **evaluate(h, rec["trip"], by_id, matrix)}
        dist_reports.append(dr)
        hyb_reports.append(hr)
        hyb_plans.append(h)
    dist = _system_metrics(dist_reports)
    hyb = _system_metrics(hyb_reports)

    # LLM-only: real call if a client is reachable, else an explicit SKIP.
    complete = llm_complete or default_complete
    llm: dict = {}
    try:
        llm_reports = []
        for rec in feasible:
            out = llm_only_itinerary(rec, by_id, matrix, complete)
            it = out["itinerary"] or {"activities": []}
            llm_reports.append({"_ratings": _ratings(it["activities"], by_id),
                                **evaluate(it, rec["trip"], by_id, matrix)})
        llm = {"status": "RUN", **_system_metrics(llm_reports)}
    except LLMUnavailable as exc:
        llm = {"status": "SKIP", "reason": str(exc),
               "note": "no live LLM (Ollama/api) reachable; distance-only and "
                       "hybrid still ran, no numbers fabricated"}

    # SC-010 recovery probe over the hybrid plans (incident + preservation).
    ok = probed = 0
    preserved_all = True
    for rec, h in zip(feasible, hyb_plans):
        probe = recovery_probe(rec, h["activities"], by_id, matrix)
        if probe["ok"] is None:
            continue
        probed += 1
        ok += int(probe["ok"])
        preserved_all = preserved_all and probe["preserved"]
    recovery = {"probed": probed, "ok": ok, "preserved_all": preserved_all}

    zero_fee = all(int(p.get("fee", 0)) == 0 for pid in eligible
                   for p in [by_id[pid]])
    ratings = {by_id[pid].get("rating") for pid in eligible}
    uniform_ratings = len(ratings) == 1
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "suite": suite_path, "snapshot": snapshot_dir,
        "coverage": coverage,
        "feasible": len(feasible),
        "infeasible": len(suite) - len(feasible),
        "hybrid": {"profile": profile},
        "systems": {"distance-only": dist, "hybrid": hyb, "llm-only": llm},
        "recovery": recovery,
        "notes": _notes(zero_fee, uniform_ratings),
        "sc": _sc_table(dist, hyb, recovery, zero_fee, uniform_ratings),
    }
    _attach_backends(report)
    return report


def _notes(zero_fee: bool, uniform_ratings: bool) -> dict:
    notes = {}
    if zero_fee:
        notes["zero_fee"] = ZERO_FEE_NOTE
    if uniform_ratings:
        notes["uniform_ratings"] = (
            "every eligible POI has the same rating -> SC-009 ratio is 1.0 by "
            "construction (undecidable on this pool, not evidence of parity); "
            "T053 needs rating/type/fee breadth to measure preference lift")
    return notes


def _ratings(activities: list[dict], by_id: dict) -> list[float]:
    out = []
    for a in activities:
        r = by_id.get(a.get("poi_id"), {}).get("rating")
        if r is not None:
            out.append(float(r))
    return out


def _attach_backends(report: dict) -> None:
    try:
        from BE.app.services import scorer
        report["hybrid"]["transition_backend"] = scorer.describe()
    except Exception:  # noqa: BLE001 - reporting only
        pass


def _print_report(report: dict) -> None:
    cov = report["coverage"]
    print(f"coverage (SCOPED): {cov['eligible']}/{cov['total_pois']} eligible "
          f"({cov['eligible']}/{cov['verified']} verified intersect matrix)")
    print(f"feasible {report['feasible']} / infeasible {report['infeasible']}")
    for name, m in report["systems"].items():
        if m.get("status") == "SKIP":
            print(f"  {name:14s} SKIP: {m.get('reason')}")
            continue
        print(f"  {name:14s} gate {m['gate_pass']}/{m['n']} "
              f"({m['pass_rate']:.0%}) viol {m['violations']} "
              f"mean_rating {m['mean_rating']}")
    print("SC table:")
    for sc, row in report["sc"].items():
        print(f"  {sc}: pass={row['pass']} target={row['target']}")
    if report.get("notes"):
        for key, text in report["notes"].items():
            print(f"note [{key}]: {text}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T053 baselines vs hybrid")
    ap.add_argument("--suite", default=DEFAULT_SUITE)
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--profile", default=HYBRID_PROFILE)
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap feasible queries (smoke run; omit for full)")
    args = ap.parse_args(argv)
    report = run(args.suite, args.snapshot, profile=args.profile,
                 limit=args.limit)
    _print_report(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"wrote -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
