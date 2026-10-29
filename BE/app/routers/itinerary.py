"""POST /v1/itinerary (T020, lane C). TripRequest -> profile plans.

Onboarding profile (shared FE/BE contract, catalog freeze): `trip.profile`
allergy/must_avoid/accessibility is a HARD pre-filter (before retrieval and
rank), and party/fitness/pace selects one of three day templates (family-slow,
friends-fast, couple-calm) that constrains the optimizer (stop band, required
categories, locked rest window, late end). Drops are surfaced as warnings.
A legacy request that never sent `profile` keeps the previous unconstrained
behaviour (template name None).

Retrieval/ranking are lane C; feasibility planning is owned by lane B. Until
that service is present, the endpoint fails explicitly instead of presenting
the former rank-order stub as a real itinerary.

GET /v1/itinerary/{id} (contracts/api.md "đọc lịch", offline cache key) reads
a stored plan back. The body is the same public plan object POST /v1/itinerary
returns (leading-underscore context keys stripped), so a client can cache the
POST response and re-read it by id. Unknown id -> 404 envelope.

`?diverse=true` (default OFF) asks each profile for a CP-SAT solution pool
(>=95 % of the optimum), validates every member and returns the greedy MMR
top-3 by (quality - POI-set Jaccard).

USER DECISION (default contract): `profiles` may be omitted, in which case the
three structural objectives (savings/balanced/experience) are returned. In
BOTH modes the final plans are checked pairwise: a pair whose POI-set Jaccard
exceeds `pool.MAX_PAIRWISE_JACCARD` (0.6) loses its lower-quality plan, which
is replaced by the next MMR pick from its own solution pool. The distances and
replacement evidence travel in `solution_pool`.
"""

from __future__ import annotations

import importlib
import json
import os
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.routers import select as select_svc
from BE.app.schemas.trip import TripRequest
from BE.app.services import pool as pool_svc
from BE.app.services import profile_filter
from BE.app.services import rank as rank_svc
from BE.app.services import ranker as ranker_svc
from BE.app.services import retrieval as retrieval_svc
from BE.app.services import templates
from BE.app.services import trip_ctx
from BE.app.services.optimizer import POOL_DEFAULT_BAND

router = APIRouter(prefix="/v1", tags=["itinerary"])

# Assumption-style warnings: verified hard-filter drops are listed, capped so a
# broad allergy does not turn the plan response into a 200-line changelog.
MAX_FILTER_WARNINGS = 30
# FR-013 "can xac minh" list in the response: enough to act on, not the
# whole unverified snapshot (~700 POIs today).
MAX_NEEDS_VERIFICATION = 20

# Diverse mode (?diverse=true): solutions enumerated per profile, plans returned.
# N=8 matches the "N>=8 where feasible" requirement; MMR returns 3.
DIVERSE_POOL = 8
DIVERSE_K = 3

# On-demand replacement pool for the cross-option Jaccard guarantee. Only a
# conflicting profile pays for enumeration; 5 members is enough to find a
# genuinely different day without spending the full 25 s default budget.
ALT_POOL = 5
# The first pool solve can consume the profile's wall-clock budget, so give the
# enumeration room for 2-3 nogood re-solves (each capped at 5 s internally).
ALT_POOL_TIMEOUT_S = 15.0
ALT_FIRST_SOLVE_S = 3.0


class ItineraryIn(BaseModel):
    trip: TripRequest
    # USER DECISION: /v1/itinerary always returns genuinely different options.
    # Omitting `profiles` now means all three structural objectives, not the
    # old single "balanced" plan. An explicit list is still honoured verbatim.
    profiles: list[str] = ["savings", "balanced", "experience"]


def _get_plan_builder():
    """Return lane B's profile planner when available, otherwise fail closed."""
    module_name = "BE.app.services.profiles"
    try:
        profiles_svc = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return None
        raise
    builder = getattr(profiles_svc, "build_plan", None)
    return builder if callable(builder) else None


def _load_cells(snapshot_dir: str) -> dict:
    try:
        with open(os.path.join(snapshot_dir, "matrix.json"), encoding="utf-8") as f:
            return json.load(f).get("cells", {})
    except (FileNotFoundError, NotADirectoryError):
        return {}


@router.post("/itinerary")
def itinerary(body: ItineraryIn, diverse: bool = False):
    """One plan per requested profile; omitted profiles = all three.

    Default (no `profiles`): savings/balanced/experience, i.e. cost-first,
    rating-first and novelty-first. Every request is checked with the pairwise
    Jaccard ceiling and reports it under `solution_pool`.
    With `diverse=true` every profile enumerates a CP-SAT solution pool
    (>=95 % OPT), every member is validated, and greedy MMR picks 3
    pairwise-different plans by (quality - POI-set Jaccard); the enumeration
    stats travel in each plan's `solution_pool`.
    """
    settings = get_settings()
    try:
        pois = retrieval_svc.load_pois_json(
            os.path.join(settings.snapshot_dir, "pois.json"))
    except (FileNotFoundError, NotADirectoryError):
        return error("SNAPSHOT_MISSING",
                     f"snapshot dir {settings.snapshot_dir} chua co (doi lane A T003b)", 503)

    # The lane-B planner is intentionally optional on this branch. Do not
    # silently substitute a fake itinerary if its real feasibility seam is absent.
    builder = _get_plan_builder()
    if builder is None:
        return error("PLANNER_UNAVAILABLE",
                     "dich vu lap lich lane B chua kha dung tren branch nay", 501)

    trip = body.trip.model_dump()
    profile = trip.get("profile") or {}
    by_id = {p["poi_id"]: p for p in pois}

    # Hard profile pre-filter (onboarding): allergy / must_avoid /
    # accessibility drop POIs BEFORE retrieval and ranking. Every drop is
    # reported as an assumption-style warning; missing tags never crash.
    pois, profile_drops = profile_filter.hard_filter(pois, profile)
    dropped_ids = {d["poi_id"] for d in profile_drops}
    # The planner only ever sees what survived the hard filter; `by_id`
    # (full snapshot) stays for drop reporting and must_visit name lookup.
    allowed_by_id = {p["poi_id"]: p for p in pois}

    # Day template V1: one of three hard archetypes, selected from the profile.
    # Only an explicitly onboarded request gets one; a legacy client that never
    # sent `profile` keeps the previous unconstrained behaviour.
    profile_provided = "profile" in body.trip.model_fields_set
    if not profile_provided:
        # TripRequest fills a neutral default profile; an omitted profile is
        # NOT onboarding, so it must not trigger the universal lunch/rest lock
        # (or a template) downstream.
        trip.pop("profile", None)
    tpl_name = templates.select_template(profile) if profile_provided else ""

    # NOTE(test-local, chua commit): luoi an toan — must_visit rac tu parser
    # (ten mon an thay vi dia diem) se lam optimizer infeasible -> plan rong.
    # Chi giu muc khop poi_id hoac ten POI trong snapshot; con lai rot xuong
    # warnings chu khong giet ca plan. Cung loai bo must_visit bi hard-filter
    # ho so hoac khong hop template (ly do ghi vao warnings).
    name_to_id = {(p.get("name") or "").strip().lower(): pid
                  for pid, p in by_id.items()}
    kept_must, dropped_must = [], []
    for m in trip.get("must_visit", []):
        key = (m or "").strip()
        pid = key if key in by_id else name_to_id.get(key.lower())
        if pid is None:
            dropped_must.append((m, "khong co trong du lieu"))
        elif pid in dropped_ids:
            dropped_must.append((m, "bi loai boi ho so ca nhan"))
        elif tpl_name and not templates.allows(by_id[pid], tpl_name):
            dropped_must.append((m, f"khong hop template {tpl_name}"))
        else:
            kept_must.append(pid)
    trip["must_visit"] = kept_must
    retired_warnings = [
        f"khong dua vao lich '{m}': {why}" for m, why in dropped_must]

    retrieval = retrieval_svc.retrieve(trip, pois)
    candidate_ids = [c["poi_id"] for c in retrieval["candidates"]]
    # Trip context (dynamic state): live weather for the trip hours + the
    # conditional meal rhythm + the hourly traveler state. It closes the
    # rank rain_prob dead branch (rain_at per hour, max over the trip) and
    # feeds the satiety/fatigue/heat/dip/evening rules. Built even without a
    # profile (weather/time are universal) but only a profile turns on the
    # state multipliers (dynamic_state), so legacy requests stay identical.
    ctx = trip_ctx.build(trip, profile if profile_provided else {})
    # C1 + onboarding: rank sees the real trip AND profile preferences
    # (food_prefs/activities drive pref_match, fitness effort fit,
    # outdoor_bias and spending_level the taste/price fit).
    user = {"budget": trip["budget"]}
    for key in ("fitness", "spending_level", "pace", "outdoor_bias",
                "accessibility"):
        if profile.get(key) is not None:
            user[key] = profile[key]
    for key in ("food_prefs", "activities"):
        merged = _merge_lists(trip.get(key), profile.get(key))
        if merged:
            user[key] = merged
    ranked = rank_svc.rank(
        [by_id[poi_id] for poi_id in candidate_ids],
        user,
        {**ctx, "hour": trip["start_time"]},
    )
    cells = _load_cells(settings.snapshot_dir)

    drop_counts: dict[str, int] = {}
    verified_drops = [d for d in profile_drops
                      if (by_id.get(d["poi_id"]) or {}).get("verified")]
    for drop in verified_drops:
        drop_counts[drop["rule"]] = drop_counts.get(drop["rule"], 0) + 1

    # --- profile plans -----------------------------------------------------
    # Default (no `profiles`): three STRUCTURAL objectives. Explicit profiles
    # are still honoured verbatim and in order.
    base_warnings = ([f"hard-filter ho so: loai {len(verified_drops)} POI "
                      f"da xac minh"] if verified_drops else [])
    base_warnings += [profile_filter.warning(d)
                      for d in verified_drops[:MAX_FILTER_WARNINGS]]
    if len(verified_drops) > MAX_FILTER_WARNINGS:
        base_warnings.append(
            f"... va {len(verified_drops) - MAX_FILTER_WARNINGS} POI khac")
    base_warnings += retired_warnings
    if ctx.get("weather_source") == "none":
        base_warnings.append(
            "khong lay duoc du bao thoi tiet, dung nhiet do gia dinh "
            f"{ctx.get('temp_c')}C (mua coi nhu 0%)")
    elif ctx.get("weather_stale"):
        base_warnings.append("du bao thoi tiet dang la cache cu")

    def decorate(plan: dict, profile_name: str) -> dict:
        """Router fields + shared warnings, applied to argmax AND replacements."""
        plan = dict(plan)
        plan["itinerary_id"] = str(uuid4())
        plan["trip_id"] = body.trip.trip_id
        plan["profile"] = profile_name
        plan["profile_filter"] = {"dropped": len(verified_drops),
                                  "dropped_all": len(profile_drops),
                                  "rules": drop_counts}
        warnings = base_warnings + list(plan.get("warnings") or [])
        if warnings:
            plan["warnings"] = warnings
        else:
            plan.pop("warnings", None)
        return plan

    def build_one(profile_name: str, pool_size: int = 1,
                  pool_timeout_s: float | None = None,
                  timeout_s: float | None = None) -> dict:
        plan = dict(builder(profile=profile_name, trip=trip, ranked=ranked,
                            pois_by_id=allowed_by_id, cells=cells,
                            template=tpl_name,
                            ctx=ctx, pool_size=pool_size,
                            pool_timeout_s=pool_timeout_s,
                            timeout_s=timeout_s))
        plan["profile"] = profile_name
        return plan

    raw = [build_one(name,
                     DIVERSE_POOL if diverse and index == 0 else 1)
           for index, name in enumerate(body.profiles)]

    def refill(plan: dict) -> list[dict]:
        """Lazily enumerate this profile's solution pool for a replacement.

        Only called when a pair exceeds the Jaccard ceiling, so the common
        case does not pay for 3x enumeration.
        """
        profile_name = plan.get("profile")
        if profile_name not in body.profiles:
            return []
        fresh = build_one(profile_name, ALT_POOL, ALT_POOL_TIMEOUT_S,
                          timeout_s=ALT_FIRST_SOLVE_S)
        return [dict(alt) for alt in (fresh.get("_pool_plans") or [])]

    guarantee = None
    pool_stats = None
    if diverse:
        # Diverse mode: the first profile's pool + every profile's argmax are
        # merged, then greedy MMR picks the top-3 pairwise-different plans.
        merged: list[dict] = []
        for plan in raw:
            stats = plan.get("solution_pool") or {}
            members = plan.get("_pool_plans") or []
            if not members:
                argmax = dict(plan)
                argmax["_quality"] = 1.0
                merged.append(argmax)
                continue
            floor = stats.get("floor_objective")
            qs = pool_svc.normalize_quality(
                [{"objective": m.get("_objective")} for m in members],
                band=POOL_DEFAULT_BAND,
                floor=float(floor) if floor is not None else None)
            for member, q in zip(members, qs):
                member["_quality"] = q
                merged.append(member)
        picked = pool_svc.mmr_select(
            merged, k=DIVERSE_K, qualities=[m["_quality"] for m in merged])
        # USER DECISION: the returned options must be genuinely different, in
        # BOTH modes. MMR is greedy, so a late pick can still cross the
        # ceiling; replace the loser from the same merged pool.
        picked, guarantee = pool_svc.enforce_pairwise(
            picked, pool_svc.MAX_PAIRWISE_JACCARD,
            refill=lambda _plan: merged)
        first_stats = (raw[0].get("solution_pool") or {}) if raw else {}
        pool_stats = pool_svc.pool_report(
            {"found": len(merged), "in_band": len(merged),
             "requested": DIVERSE_POOL, "band": POOL_DEFAULT_BAND,
             "band_base_objective": first_stats.get("band_base_objective"),
             "best_objective": first_stats.get("best_objective"),
             "floor_objective": first_stats.get("floor_objective"),
             "best_status": first_stats.get("best_status"),
             "attempts": first_stats.get("attempts"),
             "elapsed_s": round(sum(float(
                 (p.get("solution_pool") or {}).get("enumeration_s") or 0.0)
                 for p in raw), 3)},
            picked, len(merged))
        pool_stats.update(_guarantee_fields(guarantee))
        plans = []
        previous: list[dict] = []
        for rank, member in enumerate(picked, start=1):
            plan = decorate(member, member.get("profile") or "balanced")
            plan["diverse_rank"] = rank
            sets = pool_svc.poi_set(plan)
            sims = [pool_svc.jaccard(sets, pool_svc.poi_set(p))
                    for p in previous]
            mmr = {"rank": rank,
                   "quality": round(pool_svc.plan_quality(member), 4),
                   "similarity": round(max(sims, default=0.0), 4),
                   "score": round(pool_svc.plan_quality(member)
                                  - max(sims, default=0.0), 4),
                   "jaccard_to_selected": [round(s, 4) for s in sims]}
            plan["solution_pool"] = {**pool_stats, "mmr": mmr}
            previous.append(plan)
            plans.append(plan)
    else:
        if len(raw) > 1:
            raw, guarantee = pool_svc.enforce_pairwise(
                raw, pool_svc.MAX_PAIRWISE_JACCARD, refill=refill)
        else:
            _picked, guarantee = pool_svc.enforce_pairwise(raw)
        plans = [decorate(plan, plan.get("profile") or "balanced")
                 for plan in raw]
        if len(plans) > 1:
            report_items = []
            for rank, plan in enumerate(plans, start=1):
                report_items.append({
                    "profile": plan.get("profile"),
                    "activities": plan.get("activities") or [],
                    "mmr": {"rank": rank,
                            "quality": round(pool_svc.plan_quality(plan), 4),
                            "similarity": None, "score": None},
                })
            pool_stats = pool_svc.pool_report(
                {"requested": len(body.profiles), "found": len(plans),
                 "in_band": len(plans), "elapsed_s": 0.0},
                report_items, len(plans))
            pool_stats.update(_guarantee_fields(guarantee))

    # Make every returned itinerary immediately selectable. The store keeps
    # the full plan (incl. T061e `_context` for /replan); the public
    # response drops leading-underscore keys.
    select_svc.register(plans)
    public = [_public(plan) for plan in plans]
    out = {"plans": public, "selected": None,
           "retrieval": _retrieval_report(retrieval, by_id,
                                          trip.get("activities") or [])}
    if pool_stats is not None:
        out["solution_pool"] = pool_stats
    # Shadow LLM ranker (Hướng 3): log-only, never on the response path.
    # Default OFF keeps the old behaviour and adds zero latency; when ON the
    # daemon thread may still be running after this response is returned.
    if os.environ.get("RANKER_SHADOW", "0") == "1":
        try:
            ranker_svc.spawn_shadow(
                query=_shadow_query(trip), plans=public,
                reference=_shadow_reference(public, by_id))
        except Exception:  # pragma: no cover - spawn_shadow itself never raises
            pass
    return out


def _retrieval_report(retrieval: dict, by_id: dict,
                      activities: list[str]) -> dict:
    """FR-013/FR-024: what retrieval kept out of the plan, and why.

    `needs_verification` lists unverified POIs as "can xac minh" (must_visit
    first, then those matching a requested activity, then by rating), capped
    at MAX_NEEDS_VERIFICATION; `excluded` counts verified drops per reason.
    """
    wanted = retrieval_svc.wanted_types(activities)

    def order(entry: dict) -> tuple:
        poi = by_id.get(entry["poi_id"]) or {}
        return (not entry.get("must_visit"),
                retrieval_svc.poi_category(poi) not in wanted,
                -float(poi.get("rating") or 0))

    pending = sorted(retrieval["needs_verification"], key=order)
    excluded: dict[str, int] = {}
    for entry in retrieval["excluded"]:
        excluded[entry["reason"]] = excluded.get(entry["reason"], 0) + 1
    return {
        "candidates": len(retrieval["candidates"]),
        "needs_verification_total": len(pending),
        "needs_verification": [
            {"poi_id": e["poi_id"],
             "name": (by_id.get(e["poi_id"]) or {}).get("name", ""),
             "cat": retrieval_svc.poi_category(by_id.get(e["poi_id"]) or {}),
             "must_visit": bool(e.get("must_visit")),
             "reasons": e.get("reasons") or [],
             "uncertainty": e.get("uncertainty") or []}
            for e in pending[:MAX_NEEDS_VERIFICATION]],
        "excluded": excluded,
        "unmatched_activities": retrieval.get("unmatched_activities") or [],
    }


def _shadow_query(trip: dict) -> dict:
    """Request facts for the ranker prompt (no user ids, no secrets)."""
    keys = ("city", "days", "start_time", "end_time", "budget", "travelers",
            "transport", "activities", "food_prefs", "must_visit", "avoid")
    return {k: trip[k] for k in keys if trip.get(k) not in (None, "", [])}


def _shadow_reference(plans: list[dict], by_id: dict) -> list[dict]:
    """Solver verdicts + POI facts per plan for the ranker's reference block."""
    refs = []
    for index, plan in enumerate(plans):
        pois = []
        for act in plan.get("activities") or []:
            poi = by_id.get(act.get("poi_id")) or {}
            pois.append({"poi_id": act.get("poi_id"),
                         "type": poi.get("type"),
                         "price_level": poi.get("price_level"),
                         "fee": poi.get("fee"),
                         "rating": poi.get("rating"),
                         "intensity": poi.get("intensity")})
        refs.append({
            "plan_id": plan.get("itinerary_id") or index,
            "feasible": (bool(plan.get("passed", True))
                         and not (plan.get("violations") or [])),
            "cost": plan.get("total_cost"),
            "violations": plan.get("violations") or [],
            "soft_violations": plan.get("soft_violations") or [],
            "travel_min": plan.get("travel_min"),
            "preference": plan.get("preference"),
            "pois": pois,
        })
    return refs


def _guarantee_fields(report: dict | None) -> dict:
    """Cross-option Jaccard evidence -> `solution_pool` fields."""
    report = report or {}
    return {
        "max_jaccard": report.get("max_jaccard"),
        "jaccard_ok": report.get("satisfied"),
        "satisfied": report.get("satisfied"),
        "max_pairwise_similarity": report.get("max_pairwise_similarity"),
        "pairwise_distances": report.get("pairwise_distances", []),
        "replaced": report.get("replaced", []),
        "exhausted": report.get("exhausted", []),
    }


def _merge_lists(*values) -> list[str]:
    """Ordered de-dupe merge of trip + profile preference lists (missing-safe)."""
    out: list[str] = []
    for value in values:
        for item in value or []:
            item = str(item)
            if item and item not in out:
                out.append(item)
    return out


def _public(plan: dict) -> dict:
    """Plan -> public shape (drop private leading-underscore keys)."""
    return {k: v for k, v in plan.items() if not k.startswith("_")}


@router.get("/itinerary/{itinerary_id}")
def get_itinerary(itinerary_id: str):
    plan = select_svc.get_store()["plans"].get(itinerary_id)
    if plan is None:
        return error("UNKNOWN_ITINERARY",
                     f"khong co plan {itinerary_id}", 404)
    return _public(plan)
