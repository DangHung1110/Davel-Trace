"""LLM-guided, gate-checked plan repair (test-local; max 2 rounds).

Why: the deterministic gate can prove a plan is *feasible*, and the narrow
LLM review can point at plans that are semantically poor (all-food day,
double lunch, repeated type, nightlife in the morning). This module turns
those review issues into SAFE, minimal repairs:

1. call the same narrow review used by POST /v1/review (one LLM round);
2. for each high/medium issue pick the offending activity (or, for the SOFT
   F1 quota, the over-represented half of the day) and try to swap ONLY its
   POI for the highest-ranked alternative of a different category that fits
   the exact same [start, end] slot (verified + opening hours + matrix
   cells + budget);
3. re-run the canonical gate validator; the swap is kept only if every HARD
   gate still passes, otherwise it is reverted.

Times are never edited by hand: the replacement inherits the activity's
start/end and the gate re-checks VROH/B3/ETC for it. Totals/segments are
recomputed from the shared helpers (never hand-written). The optional F1
issue is synthesised from the deterministic soft check so an all-food day
can be repaired even when the LLM misses it.

Hard limits: 2 rounds, one swap attempt per issue per round, no new
dependencies, no LLM arithmetic/rewrite. An LLM failure returns the current
plan with a note (never raises to the HTTP layer).
"""

from __future__ import annotations

import re
from collections import Counter

from BE.app.services import rank as rank_svc
from BE.app.services import soft_rules
from BE.app.services.common import status_map, to_min, total_fee
from BE.app.services.gate import SOFT_CHECKS, check_f1
from BE.app.services.soft_rules import (
    RESTAURANT_PAIR_MAX_GAP,
    is_food,
    is_sightseeing,
    poi_category,
)
from BE.app.services.validator import validate
from BE.common import poi_open_windows, trusted_rating

MAX_ROUNDS = 2
ACTIONABLE = ("high", "medium")
F1_ISSUE = ("[F1] ngay chi toan do an uong, thieu diem van hoa / "
            "thien nhien / tham quan (category quota)")
A2_ISSUE = ("[A2] 2 nha hang cach nhau duoi 2.5 gio (inter-meal distance)")


def _activities(plan: dict) -> list[dict]:
    acts = plan.get("activities")
    if acts is None:
        acts = (plan.get("itinerary") or {}).get("activities") or []
    return sorted(acts, key=lambda a: a.get("start", ""))


def _trip_user(trip: dict) -> dict:
    user = {"budget": trip.get("budget", 3000000)}
    for key in ("fitness", "food_prefs", "activities"):
        if trip.get(key) is not None:
            user[key] = trip[key]
    return user


def _rank_scores(pool: list[dict], trip: dict) -> dict:
    """Rank score per poi_id at the trip's start context (fallback order)."""
    user = _trip_user(trip)
    ctx = {"trip": trip, "hour": trip.get("start_time", "07:00")}
    return {p.get("poi_id"): rank_svc.score_poi(p, user, ctx)["score"]
            for p in pool if p.get("poi_id")}


def _f1_target(acts: list[dict], pois: dict, trip: dict,
               ranks: dict) -> tuple[dict | None, str | None]:
    """Pick the activity to replace so the missing F1 half appears."""
    report = check_f1({"activities": acts}, trip, pois, {})
    if report["passed"]:
        return None, None
    has_food = any(is_food(pois.get(a.get("poi_id"), {})) for a in acts)
    want = "sightseeing" if has_food else "food"
    eligible = [a for a in acts
                if (is_food(pois.get(a.get("poi_id"), {})) if has_food
                    else not is_food(pois.get(a.get("poi_id"), {})))]
    must = set(trip.get("must_visit") or [])
    preferred = [a for a in eligible if a.get("poi_id") not in must]
    pool = preferred or eligible or list(acts)
    if not pool:
        return None, want
    return min(pool, key=lambda a: ranks.get(a.get("poi_id"), 0.0)), want


def _mentions(text: str, term: str) -> bool:
    """Whole-word mention: "bar" is not in "barbecue", "an" not in "văn"."""
    return bool(term) and re.search(
        r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


def _named_target(issue: dict, acts: list[dict], pois: dict,
                  ranks: dict) -> dict | None:
    """Lowest-ranked activity whose POI/type/category the issue mentions."""
    text = f"{issue.get('issue', '')} {issue.get('suggestion', '')}".lower()
    by_rank = sorted(acts, key=lambda a: ranks.get(a.get("poi_id"), 0.0))
    for act in by_rank:
        name = str(pois.get(act.get("poi_id"), {}).get("name") or "").strip().lower()
        if _mentions(text, name):
            return act
    for act in by_rank:
        poi = pois.get(act.get("poi_id"), {})
        cat = poi_category(poi)
        if _mentions(text, cat):
            return act
        kind = str(poi.get("type") or "").strip().lower()
        if _mentions(text, kind):
            return act
    # Token overlap (e.g. "ăn chay" -> "Nhà hàng chay ..."): ignore generic
    # venue words so "nhà hàng"/"quán" never match every food POI.
    stop = {"nha", "hang", "quan", "cafe", "coffee", "va", "cua", "and",
            "the", "da", "nang", "nẵng", "đà", "nhà", "hàng", "quán",
            "an", "ăn"}
    words = set(re.findall(r"\w+", text)) - stop
    for act in by_rank:
        name = str(pois.get(act.get("poi_id"), {}).get("name") or "").lower()
        tokens = set(re.findall(r"\w+", name)) - stop
        if tokens & words:
            return act
    return None


def _a2_target(acts: list[dict], pois: dict,
               trip: dict, ranks: dict) -> dict | None:
    """TASK-3: lowest-ranked activity in the first restaurant pair <2.5h.

    A1 (slot membership) can pass while two lunches are 16 minutes apart
    (10:49 vs 11:00); the plan-level A2 check catches it, so repair must be
    able to act on it even when the LLM reviewer misses it (or hallucinates
    something else). Must-visit stops are never chosen.
    """
    restaurants = [a for a in acts
                   if poi_category(pois.get(a.get("poi_id"), {})) == "restaurant"]
    must = set(trip.get("must_visit") or [])
    for prev, cur in zip(restaurants, restaurants[1:]):
        gap = to_min(cur["start"]) - to_min(prev["start"])
        if gap >= RESTAURANT_PAIR_MAX_GAP:
            continue
        pair = [a for a in (prev, cur) if a.get("poi_id") not in must]
        if pair:
            return min(pair, key=lambda a: ranks.get(a.get("poi_id"), 0.0))
    return None


def _fallback_target(acts: list[dict], pois: dict, ranks: dict) -> dict | None:
    """Lowest-ranked activity in an over-represented category, else lowest."""
    counts = Counter(poi_category(pois.get(a.get("poi_id"), {})) for a in acts)
    failed = [a for a in acts
              if counts.get(poi_category(pois.get(a.get("poi_id"), {})), 0) > 1]
    pool = failed or list(acts)
    if not pool:
        return None
    return min(pool, key=lambda a: ranks.get(a.get("poi_id"), 0.0))


def _alternatives(target: dict, want: str | None, pool: list[dict],
                  trip: dict, pois: dict, acts: list[dict],
                  index: int, matrix: dict) -> list[dict]:
    """Verified, different-category, same-slot, matrix-connected candidates.

    Pre-filtering mirrors the hard gates so the repair log's "N candidates"
    is the number of genuinely safe options, not a raw pool count:
    - opening hours must cover the target's exact [start, end];
    - the matrix must connect the previous/next activity (B3);
    - the fee must keep the plan inside budget (BCS).
    Gate validation still has the final say.
    """
    target_cat = poi_category(pois.get(target.get("poi_id"), {}))
    start, end = to_min(target["start"]), to_min(target["end"])
    user = _trip_user(trip)
    ctx = {"trip": trip, "hour": target["start"]}
    current_ids = {a.get("poi_id") for a in acts}
    prev = acts[index - 1]["poi_id"] if index > 0 else None
    nxt = acts[index + 1]["poi_id"] if index + 1 < len(acts) else None
    budget = int(trip.get("budget", 0))
    other_fee = sum(int((pois.get(a.get("poi_id"), {}) or {}).get("fee", 0))
                    for i, a in enumerate(acts) if i != index)
    out = []
    for poi in pool:
        pid = poi.get("poi_id")
        if not pid or pid in current_ids or not poi.get("verified"):
            continue
        cat = poi_category(poi)
        if not cat or cat == target_cat:
            continue
        if want == "sightseeing" and not is_sightseeing(poi):
            continue
        if want == "food" and not is_food(poi):
            continue
        if not _fits_slot(poi, start, end):
            continue
        if prev and not matrix.get(f"{prev}->{pid}"):
            continue
        if nxt and not matrix.get(f"{pid}->{nxt}"):
            continue
        if budget and other_fee + int(poi.get("fee", 0) or 0) > budget:
            continue
        out.append({"score": rank_svc.score_poi(poi, user, ctx)["score"],
                    "poi": poi})
    out.sort(key=lambda item: item["score"], reverse=True)
    return out


def _fits_slot(poi: dict, start: int, end: int) -> bool:
    """Same slot only: a window of `poi_open_windows` (the optimizer's view:
    real hours, else the category's safe hours) covers [start, end]; a POI
    with neither is ok."""
    wins = poi_open_windows(poi)
    return wins is None or any(lo <= start and end <= hi for lo, hi in wins)


def _gate_pois(pois: dict, pool: list[dict]) -> dict:
    merged = dict(pois)
    for poi in pool:
        pid = poi.get("poi_id")
        if pid:
            merged.setdefault(pid, poi)
    return merged


def _trial(acts: list[dict], index: int, new_poi: dict, issue: dict) -> list[dict]:
    """Copy activities and swap one POI, keeping the exact start/end slot."""
    trial = [dict(a) for a in acts]
    old = trial[index]
    trial[index] = {
        **old,
        "poi_id": new_poi["poi_id"],
        "explanation": {
            "claim": f"repair: chon {new_poi['poi_id']}",
            "evidence": [f"repair: {issue.get('issue', '')[:120]}"],
            "inference": "",
            "source": "repair",
        },
    }
    return trial


def _refresh(plan: dict, acts: list[dict], trip: dict, pois: dict,
             matrix: dict) -> tuple[dict, dict]:
    """Recompute derived totals/segments/status from the new activity list."""
    out = dict(plan)
    out["activities"] = acts
    segments, total_km, travel_min = [], 0.0, 0
    for x, y in zip(acts, acts[1:]):
        cell = matrix.get(f"{x['poi_id']}->{y['poi_id']}", {}) or {}
        km = float(cell.get("km", 0.0))
        minutes = int(cell.get("minutes", 0))
        segments.append({"from_id": x["poi_id"], "to_id": y["poi_id"],
                         "mode": "motorbike", "km": km, "minutes": minutes,
                         "source": "cache"})
        total_km += km
        travel_min += minutes
    visit_min = sum(to_min(a["end"]) - to_min(a["start"]) for a in acts)
    ratings = [trusted_rating(pois.get(a["poi_id"]) or {}) for a in acts]
    out["segments"] = segments
    out["total_cost"] = total_fee(acts, pois)
    out["total_km"] = round(total_km, 2)
    out["travel_min"] = travel_min
    out["total_min"] = visit_min + travel_min
    out["preference"] = round(sum(ratings) / len(ratings), 3) if ratings else 0.0
    out["soft_penalties"] = soft_rules.plan_penalties(acts, pois, trip)

    rep = validate({"activities": acts}, trip, pois, matrix)
    hard = {name: ok for name, ok in rep["checks"].items()
            if name not in SOFT_CHECKS}
    out["constraint_status"] = status_map(hard)
    out["violations"] = rep["violations"]
    out["soft_violations"] = rep["soft_violations"]
    out["passed"] = rep["passed"]
    if "scores" in plan:
        from BE.app.services.profiles import score_plan
        out["scores"] = score_plan(out)
    return out, rep


def repair_plan(plan: dict, trip: dict, pois: dict, matrix: dict,
                pool: list[dict], review_fn, max_rounds: int = MAX_ROUNDS) -> dict:
    """Run the bounded repair loop.

    `review_fn(plan) -> list[{issue,severity,suggestion}]` is the narrow LLM
    review (injected so tests never call the model). `pool` is the ranked
    candidate list; alternatives never come from outside it.
    """
    gate_pois = _gate_pois(pois, pool)
    working = dict(plan)
    acts = [dict(a) for a in _activities(plan)]
    repairs: list[dict] = []
    review_ms: list[int] = []
    rounds = 0
    note = None

    import time

    def attempt(issue: dict, target: dict | None, want: str | None,
                replaced: set[int]) -> bool:
        """Try safe swaps for one issue; log the outcome. True if kept."""
        text = str(issue.get("issue") or "").strip()
        if target is None:
            repairs.append({"issue": text, "action": "khong co diem de doi",
                            "kept": False})
            return False
        index = next((i for i, a in enumerate(acts) if a == target), None)
        if index is None or index in replaced:
            return False
        alternatives = _alternatives(target, want, pool, trip, gate_pois,
                                     acts, index, matrix)
        for alt in alternatives:
            new_poi = alt["poi"]
            trial = _trial(acts, index, new_poi, issue)
            if not validate({"activities": trial}, trip, gate_pois,
                            matrix)["passed"]:
                continue
            old_id = target.get("poi_id")
            acts[:] = trial
            replaced.add(index)
            repairs.append({
                "issue": text,
                "action": (f"swap {old_id} ({poi_category(gate_pois.get(old_id, {}))})"
                           f" -> {new_poi['poi_id']} ({poi_category(new_poi)})"),
                "kept": True,
            })
            return True
        repairs.append({
            "issue": text,
            "action": (f"khong co lua chon an toan cho {target.get('poi_id')} "
                       f"({len(alternatives)} ung vien khac loai)"),
            "kept": False,
        })
        return False

    # Hard cap: never more than MAX_ROUNDS, whatever the caller asks for.
    for _ in range(min(max(0, max_rounds), MAX_ROUNDS)):
        ranks = _rank_scores(pool, trip)
        t0 = time.monotonic()
        try:
            issues = list(review_fn({**working, "activities": acts}) or [])
        except Exception as exc:  # noqa: BLE001 - never 500 the harness
            review_ms.append(int((time.monotonic() - t0) * 1000))
            note = f"LLM_UNAVAILABLE: {type(exc).__name__}"
            break
        review_ms.append(int((time.monotonic() - t0) * 1000))
        rounds += 1

        actionable = [i for i in issues
                      if str(i.get("severity") or "medium").lower() in ACTIONABLE]
        kept_this_round = 0
        replaced: set[int] = set()
        for issue in actionable:
            if issue.get("rule") == "F1":
                target, want = _f1_target(acts, gate_pois, trip, ranks)
            else:
                target, want = _named_target(issue, acts, gate_pois, ranks), None
                if target is None:
                    target = _fallback_target(acts, gate_pois, ranks)
            if attempt(issue, target, want, replaced):
                kept_this_round += 1

        # Deterministic F1 quota: add it only if the review round did not
        # already fix variety, so one all-food day gets one swap, not two.
        if not check_f1({"activities": acts}, trip, gate_pois, matrix)["passed"]:
            target, want = _f1_target(acts, gate_pois, trip, ranks)
            if attempt({"issue": F1_ISSUE, "severity": "medium",
                        "suggestion": "doi 1 diem an sang diem tham quan",
                        "rule": "F1"}, target, want, replaced):
                kept_this_round += 1

        # TASK-3 deterministic A2: a restaurant pair <2.5h apart is a real
        # defect even when A1 passes. Fix it if the LLM/review round missed it.
        a2 = _a2_target(acts, gate_pois, trip, ranks)
        if a2 is not None:
            if attempt({"issue": A2_ISSUE, "severity": "medium",
                        "suggestion": "doi 1 nha hang sang diem khac loai",
                        "rule": "A2"}, a2, None, replaced):
                kept_this_round += 1

        if kept_this_round == 0:
            break

    final, rep = _refresh(working, acts, trip, gate_pois, matrix)
    result = {"plan": final, "rounds": rounds, "repairs": repairs,
              "gate": rep, "review_ms": review_ms}
    if note:
        result["note"] = note
    return result
