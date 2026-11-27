"""Pairs of plans for the same trip request, for two human raters to judge blind.

The learned objective J will be checked against people: a rater reads one request and
two plans for it, then says which plan they would rather follow (A, B or a tie). Until
J v1 is in code, the two plans come from the planner's three profiles (Tiết kiệm /
Cân bằng / Trải nghiệm = savings / balanced / experience). A pair is two of them that
really differ; identical or near-identical pairs are dropped.

    python BE/eval/human/make_plan_pairs.py --plans-cache plans.json   # plan, write all
    python BE/eval/human/make_plan_pairs.py --reuse plans.json         # no planning

Requests (`collect_requests`): the 67 audit scenarios (BE/tools/audit_plans.py), the
requests of the one-plan review (BE/tools/build_plan_review.py) the audit lacks, and the
30 gold queries (BE/eval/gold/gold_v2.json; party size set to fit the party type, POI
ids the snapshot lacks dropped). Every day starts at one central hotel (BASE_ID), as in
the app once a traveller picks one, and every request is planned through POST
/v1/itinerary on danang-v2 with the weather offline, like audit_plans.py; only plans the
app would show (gate passed, two stops or more) can be paired.

Writes, next to this file:
- plan_pairs_v1.json      what raters see: the request, plan A and plan B, nothing else
- plan_pairs_v1_key.json  hidden: which plan is A / B, the exact requests, dropped pairs
- plan_pairs.html         the rating page, with plan_pairs_v1.json embedded in it

Order and sides: requests are visited round-robin (each gives one pair per round), so any
prefix of the list covers many requests; a request gives at most `--per-request` pairs,
the pair of profiles picked least so far. Within each pair of profiles, exactly half of
the pairs show the first profile as A.

Labels follow BE/ml/patm/make_pairs.py: +1 = first plan better, 0 = tie, -1 = second
better, where first / second is the key's canonical order (savings < balanced <
experience), never the A / B a rater saw. Another source of pairs (for example the
LLM-labelled pairs of a later J run) fits in by producing rows like `run_planner`'s:
{"request_id", "source", "trip", "plans": {variant: plan}}; variants are free names.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from BE.common import (  # noqa: E402
    LEGACY_TYPE_VI, effective_fee, fee_is_estimate, is_v21, load_pois)

HERE = Path(__file__).resolve().parent
SNAPSHOT = REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v2"
GOLD_PATH = REPO_ROOT / "BE" / "eval" / "gold" / "gold_v2.json"
PAIRS_PATH = HERE / "plan_pairs_v1.json"
KEY_PATH = HERE / "plan_pairs_v1_key.json"
PAGE_PATH = HERE / "plan_pairs.html"

SCHEMA = "plan-pairs-v1"
KEY_SCHEMA = "plan-pairs-v1-key"
VARIANTS = ("savings", "balanced", "experience")   # canonical first < second
LABEL_CONVENTION = "+1 = first plan better, 0 = tie, -1 = second plan better (first/second as in this key)"

# Near-identical: two plans whose stop sequences are one edit apart (a stop swapped,
# added or removed), or less than a fifth of the longer plan apart (2-day plans).
MIN_EDIT_STOPS = 2
MIN_EDIT_SHARE = 0.2

# A party the planner knows, and the party size a request of that kind has. The gold
# queries drew both at random (a "couple" of 4, "friends" of 1): raters would read that
# as a mistake, so a gold request takes the size of its party.
PARTY_VI = {"couple": "Cặp đôi", "family": "Gia đình có người già và trẻ nhỏ",
            "friends": "Nhóm bạn", "solo": "Đi một mình"}
PARTY_SIZE = {"couple": 2, "family": 4, "friends": 4, "solo": 1}
PACE_VI = {1: "chậm", 2: "vừa", 3: "nhanh"}
FITNESS_VI = {1: "yếu", 2: "trung bình", 3: "tốt"}
ALLERGY_VI = {"seafood": "hải sản", "peanut": "đậu phộng", "gluten": "gluten"}
AVOID_VI = {"nightlife": "chơi đêm, quán bar", "alcohol": "rượu bia"}
ACCESS_VI = {"wheelchair": "Có người đi xe lăn"}
WEEKDAY_VI = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")

# The audit scenarios name two places by their danang-v1 names, and the planner matches
# a must_visit name exactly: on danang-v2 six requests would get two plans that both
# miss the one place the traveller asked for. Used only when the snapshot has the new name.
V2_NAMES = {"Ngũ Hành Sơn": "Ngũ Hành Sơn (Thủy Sơn)",
            "Chùa Linh Ứng - Bãi Bụt Sơn Trà": "Chùa Linh Ứng Sơn Trà"}
# The planner's warning when a must_visit could not go into the plan (any day).
MUST_DROPPED = "khong dua vao lich '"
# Where every day starts, like the app once a traveller picks a hotel (trip.origin).
# Without one the planner makes an open tour: a day in Hội An starts there and shows
# a few minutes of driving, and a rater cannot judge the travel. Moonlight Hotel is the
# lodging of the central zone nearest the Dragon Bridge (0.9 km); it has a matrix row.
BASE_ID = "ChIJISuvVcsZQjERhnOk-O_w9pI"
# The optimizer keeps this many minutes between two stops on top of the drive (parking,
# walking in): BE/app/services/optimizer.py STOP_OVERHEAD_MIN, checked by a test.
LEG_RESERVE_MIN = 12


# --------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------

def _canonical(trip: dict) -> str:
    return json.dumps(trip, ensure_ascii=False, sort_keys=True)


def gold_trip(query: dict, by_id: dict) -> dict:
    """A gold_v2 query as a request: profile inside the trip, party size that fits the
    party, and only the must_visit / avoid ids the snapshot has as active places."""
    trip = {k: v for k, v in query["trip"].items()}
    profile = dict(query.get("profile") or {})
    party = profile.get("party_type")
    if party in PARTY_SIZE:
        trip["travelers"] = PARTY_SIZE[party]
    active = {pid for pid, p in by_id.items() if p.get("status", "active") == "active"}
    trip["must_visit"] = [m for m in trip.get("must_visit") or [] if m in active]
    trip["avoid"] = [m for m in trip.get("avoid") or [] if m in active]
    trip["order_prefs"] = [o for o in trip.get("order_prefs") or []
                           if all(m in trip["must_visit"] for m in o)]
    trip.update({"days": 1, "profile": {k: profile[k] for k in ("party_type", "pace", "fitness") if k in profile}})
    return trip


def renamed(trip: dict, by_id: dict) -> dict:
    """The trip with V2_NAMES applied to must_visit / order_prefs, where the snapshot
    has the new name and not the old one."""
    names = {(p.get("name") or "").strip().lower() for p in by_id.values()}
    swap = {old: new for old, new in V2_NAMES.items()
            if old.lower() not in names and new.lower() in names}
    if not swap:
        return trip
    out = dict(trip)
    if "must_visit" in trip:
        out["must_visit"] = [swap.get(m, m) for m in trip["must_visit"]]
    if "order_prefs" in trip:
        out["order_prefs"] = [[swap.get(m, m) for m in o] for o in trip["order_prefs"]]
    return out


def prepared(trip: dict, by_id: dict) -> dict:
    """A request as it is planned: danang-v2 names, and the hotel every day starts from."""
    trip = renamed(trip, by_id)
    if BASE_ID in by_id and not trip.get("origin"):
        trip = {**trip, "origin": {"poi_id": BASE_ID, "label": by_id[BASE_ID].get("name") or ""}}
    return trip


def collect_requests(by_id: dict, gold_path: Path = GOLD_PATH) -> list[dict]:
    """Every request once: audit scenarios, the review's extra ones, the gold queries."""
    from BE.tools import audit_plans, build_plan_review

    rows, seen = [], set()

    def add(request_id: str, source: str, trip: dict) -> None:
        key = _canonical(trip)
        if key in seen:
            return
        seen.add(key)
        rows.append({"request_id": request_id, "source": source, "trip": trip})

    for key, extra in audit_plans.SCENARIOS:
        add(key, "audit", prepared({**audit_plans.DAY, **extra}, by_id))
    audit_trips = [r["trip"] for r in rows]
    for key, _profile, extra in build_plan_review.REQUESTS:
        trip = prepared({**build_plan_review.DAY, **extra}, by_id)
        # The review's "monday" / "night-market" differ from an audit scenario only by
        # the date or the end time: near-copies would give near-copies of pairs.
        if any(_same_but_time(trip, other) for other in audit_trips):
            continue
        add(f"R-{key}", "review", trip)
    if gold_path.exists():
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        for query in gold.get("suite_v2") or []:
            add(f"G-{query['query_id']}", "gold", prepared(gold_trip(query, by_id), by_id))
    return rows


def _same_but_time(a: dict, b: dict) -> bool:
    loose = ("date", "end_time")
    return _canonical({k: v for k, v in a.items() if k not in loose}) == \
        _canonical({k: v for k, v in b.items() if k not in loose})


# --------------------------------------------------------------------------
# Planning (the only part that needs the app)
# --------------------------------------------------------------------------

def slim_plan(plan: dict) -> dict:
    """What a pair needs from one /v1/itinerary plan."""
    return {
        "passed": bool(plan.get("passed")),
        "activities": [{k: a.get(k) for k in ("poi_id", "start", "end", "day")}
                       for a in plan.get("activities") or []],
        "segments": [{k: s.get(k) for k in ("from_id", "to_id", "minutes", "day")}
                     for s in plan.get("segments") or []],
        "total_cost": plan.get("total_cost"),
        "travel_min": plan.get("travel_min"),
        "warnings": list(plan.get("warnings") or []),
    }


def cached_rows(cache: Path | None, snapshot: str) -> dict[str, dict]:
    """Rows a previous run saved for this snapshot, by request id."""
    if not cache or not cache.exists():
        return {}
    doc = json.loads(cache.read_text(encoding="utf-8"))
    if doc.get("snapshot") != snapshot:
        return {}
    return {r["request_id"]: r for r in doc.get("rows") or [] if r.get("status") == 200}


def run_planner(requests: list[dict], snapshot: Path = SNAPSHOT, cache: Path | None = None) -> list[dict]:
    """Plan every request (3 profiles each), weather offline. Rows keep the request.

    With `cache`, a request already planned there (same snapshot, same trip) is not
    planned again, and the file is rewritten after every request: an interrupted run
    picks up where it stopped. The planner is deterministic, so this changes nothing."""
    from unittest import mock

    from fastapi.testclient import TestClient

    from BE.app import main as main_mod
    from BE.app.config import Settings
    from BE.app.routers import itinerary as itinerary_mod
    from BE.app.services import trip_ctx

    os.chdir(REPO_ROOT)  # the PATM model path is relative to the repo root
    settings = Settings(snapshot_dir=str(snapshot), snapshot_name=snapshot.name)
    client = TestClient(main_mod.app)
    saved = cached_rows(cache, snapshot.name)
    asked = {req["request_id"] for req in requests}
    others = [r for rid, r in saved.items() if rid not in asked]   # an --only run keeps the rest
    rows = []
    with mock.patch.object(itinerary_mod, "get_settings", lambda: settings), \
            mock.patch.object(trip_ctx.weather_svc, "fetch_forecast", side_effect=RuntimeError("offline")):
        for i, req in enumerate(requests, 1):
            old = saved.get(req["request_id"])
            if old and _canonical(old["trip"]) == _canonical(req["trip"]):
                rows.append(old)
                continue
            t0 = time.perf_counter()
            resp = client.post("/v1/itinerary", json={"trip": req["trip"]})
            body = resp.json() if resp.status_code == 200 else {}
            plans = {p.get("profile"): slim_plan(p) for p in body.get("plans") or []}
            rows.append({**req, "status": resp.status_code, "plans": plans})
            print(f"[{i}/{len(requests)}] {req['request_id']}: {resp.status_code} "
                  f"{time.perf_counter() - t0:4.1f}s | "
                  + " | ".join(f"{k}:{len(v['activities'])}{'' if v['passed'] else '!'}"
                               for k, v in plans.items()), flush=True)
            if cache:
                write_json(cache, {"snapshot": snapshot.name, "rows": rows + others})
    return rows


# --------------------------------------------------------------------------
# What a rater sees
# --------------------------------------------------------------------------

def _when(date: str) -> str:
    if not date:
        return ""
    day = datetime.date.fromisoformat(date)
    return f"{WEEKDAY_VI[day.weekday()]}, {day.day:02d}/{day.month:02d}/{day.year}"


def _name(ref: str, by_id: dict) -> str:
    """A must_visit / avoid entry (POI id or name) as the name a traveller reads."""
    poi = by_id.get(ref)
    return (poi.get("name") or ref) if poi else ref


def request_view(trip: dict, by_id: dict) -> dict:
    """The request as the rater reads it: who, when, how much, what they asked for."""
    profile = trip.get("profile")
    notes = []
    if profile:
        pace, fit = profile.get("pace"), profile.get("fitness")
        if pace in PACE_VI:
            notes.append(f"Nhịp đi {PACE_VI[pace]}")
        if fit in FITNESS_VI:
            notes.append(f"Thể lực {FITNESS_VI[fit]}")
        notes += [f"Thích ăn: {x}" for x in profile.get("food_prefs") or []]
        notes += [f"Dị ứng {ALLERGY_VI.get(x, x)}" for x in profile.get("allergy") or []]
        notes += [ACCESS_VI.get(x, f"Cần hỗ trợ: {x}") for x in profile.get("accessibility") or []]
        notes += [f"Không muốn: {AVOID_VI.get(x, x)}" for x in profile.get("must_avoid") or []]
    notes += [f"Thích ăn: {x}" for x in trip.get("food_prefs") or []]
    origin = trip.get("origin") or {}
    return {
        "base": _name(origin["poi_id"], by_id) if origin.get("poi_id") else (origin.get("label") or ""),
        "party": PARTY_VI.get((profile or {}).get("party_type"), "Chưa rõ nhóm khách"),
        "travelers": trip.get("travelers"), "budget": trip.get("budget"),
        "days": trip.get("days") or 1, "date": _when(trip.get("date") or ""),
        "start_time": trip.get("start_time"), "end_time": trip.get("end_time"),
        "wishes": list(trip.get("activities") or []),
        "must_visit": [_name(m, by_id) for m in trip.get("must_visit") or []],
        "avoid": [_name(m, by_id) for m in trip.get("avoid") or []],
        "order": [f"{_name(a, by_id)} trước {_name(b, by_id)}" for a, b in trip.get("order_prefs") or []],
        "notes": notes,
    }


def _place_id(poi: dict) -> str:
    """The Google place id the page opens Maps with ("" = Maps searches the name)."""
    place = (poi.get("ext_ids") or {}).get("google_place_id") or ""
    if not place and str(poi.get("poi_id", "")).startswith("ChIJ"):
        place = poi["poi_id"]
    return place


def _kind(poi: dict) -> str:
    if is_v21(poi):
        kind = LEGACY_TYPE_VI.get(poi.get("category"), poi.get("category") or "")
    else:
        kind = poi.get("type") or poi.get("cat") or ""
    dishes = poi.get("dishes") or []
    return f"{kind} · {', '.join(dishes)}" if dishes else kind


def _fee_estimated(poi: dict, fee: int | None) -> bool:
    if not fee:
        return False
    if is_v21(poi):
        return ((poi.get("provenance") or {}).get("price") or {}).get("verified_by") == "inferred"
    return fee_is_estimate(poi)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def plan_view(plan: dict, by_id: dict, origin_id: str | None = None) -> dict:
    """One plan as the rater reads it: stops with time, kind, drive and price, and totals.

    `leg_min` is the drive from the stop before, or for a day's first stop from
    `origin_id` (None on an open tour). `idle_min` is the time left over after that drive
    and the optimizer's reserve on every leg (LEG_RESERVE_MIN). Prices are per person,
    the totals for the whole party, as the app shows them. The planner's warnings are left out:
    they are developer messages (template steps, filter drops, a closing day when no
    date was given) that differ between plans in ways that would steer a rater, and
    whatever they say about a traveller's day (a wish not met, no dinner) shows in the
    stops themselves.
    """
    legs = {(s.get("day"), s.get("from_id"), s.get("to_id")): s.get("minutes") for s in plan.get("segments") or []}
    stops, previous = [], None
    for act in plan.get("activities") or []:
        poi = by_id.get(act["poi_id"]) or {"poi_id": act["poi_id"], "name": act["poi_id"]}
        same_day = previous is not None and previous.get("day") == act.get("day")
        leg = legs.get((act.get("day"), origin_id, act["poi_id"])) if origin_id else None
        idle = None
        if same_day:
            leg = legs.get((act.get("day"), previous["poi_id"], act["poi_id"]))
            idle = max(0, _minutes(act["start"]) - _minutes(previous["end"]) - (leg or 0) - LEG_RESERVE_MIN)
        fee = effective_fee(poi)
        stops.append({
            "day": act.get("day"), "start": act["start"], "end": act["end"],
            "name": poi.get("name") or act["poi_id"], "kind": _kind(poi), "poi_id": act["poi_id"],
            "leg_min": leg, "idle_min": idle, "fee": fee, "fee_estimated": _fee_estimated(poi, fee),
            "place_id": _place_id(poi)})
        previous = act
    return {
        "stops": stops, "total_cost": plan.get("total_cost"), "travel_min": plan.get("travel_min"),
        "start": stops[0]["start"] if stops else None, "end": stops[-1]["end"] if stops else None,
    }


# --------------------------------------------------------------------------
# Pairs
# --------------------------------------------------------------------------

def sequence(plan: dict) -> list[str]:
    """The stops in order, day-aware: the same place on another day is another stop."""
    return [f"{a.get('day') or 1}:{a['poi_id']}" for a in plan.get("activities") or []]


def edit_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein distance between two stop sequences (substitute, insert, delete)."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def difference(x: dict, y: dict) -> dict:
    """How far two plans are apart: edit distance of the stop sequences (absolute and
    as a share of the longer plan) and the Jaccard overlap of their places."""
    sx, sy = sequence(x), sequence(y)
    edits = edit_distance(sx, sy)
    longest = max(len(sx), len(sy), 1)
    px = {a["poi_id"] for a in x.get("activities") or []}
    py = {a["poi_id"] for a in y.get("activities") or []}
    union = px | py
    return {"edits": edits, "edit_share": round(edits / longest, 3),
            "jaccard": round(len(px & py) / len(union), 3) if union else 1.0,
            "shared": len(px & py)}


def near_identical(diff: dict, min_edits: int = MIN_EDIT_STOPS, min_share: float = MIN_EDIT_SHARE) -> bool:
    return diff["edits"] < min_edits or diff["edit_share"] < min_share


def showable(plan: dict | None) -> bool:
    """A plan the app would show: it passed the gate and has two stops or more."""
    return bool(plan) and bool(plan.get("passed")) and len(plan.get("activities") or []) >= 2


def _variant_order(variants) -> list[str]:
    known = [v for v in VARIANTS if v in variants]
    return known + sorted(v for v in variants if v not in VARIANTS)


def candidate_pairs(rows: list[dict], min_edits: int = MIN_EDIT_STOPS,
                    min_share: float = MIN_EDIT_SHARE) -> tuple[list[dict], list[dict]]:
    """Every two showable plans of one request that really differ, and why the others
    were left out. A candidate's `first` / `second` are in canonical variant order."""
    keep, dropped = [], []
    for row in rows:
        plans = row.get("plans") or {}
        order = _variant_order(plans)
        for i, first in enumerate(order):
            for second in order[i + 1:]:
                base = {"request_id": row["request_id"], "first": first, "second": second}
                bad = [v for v in (first, second) if not showable(plans.get(v))]
                if bad:
                    dropped.append({**base, "reason": "plan not shown by the app: " + ", ".join(bad)})
                    continue
                diff = difference(plans[first], plans[second])
                if near_identical(diff, min_edits, min_share):
                    dropped.append({**base, "reason": "near-identical", **diff})
                    continue
                keep.append({**base, "combo": f"{first}|{second}", **diff})
    return keep, dropped


def select_pairs(candidates: list[dict], n: int, per_request: int = 2, seed: int = 7) -> list[dict]:
    """Up to `n` pairs, round-robin over requests in a seeded order: round r takes one
    more pair from each request (the pair of variants picked least so far), at most
    `per_request` per request. Any prefix of the result therefore spreads over many
    requests, and the pairs of variants stay balanced."""
    rng = random.Random(seed)
    by_request = defaultdict(list)
    for cand in candidates:
        by_request[cand["request_id"]].append(cand)
    for pool in by_request.values():
        rng.shuffle(pool)
    requests = sorted(by_request)
    picked, used = [], Counter()
    for _round in range(per_request):
        rng.shuffle(requests)
        live = [r for r in requests if by_request[r]]
        if picked and len(live) > 1 and live[0] == picked[-1]["request_id"]:
            live[0], live[1] = live[1], live[0]       # never the same request twice in a row
        for request_id in live:
            if len(picked) >= n:
                return picked
            pool = by_request[request_id]
            best = min(pool, key=lambda c: used[c["combo"]])
            pool.remove(best)
            picked.append(best)
            used[best["combo"]] += 1
    return picked


def assign_sides(picked: list[dict], seed: int = 7) -> list[bool]:
    """Per pair: True when its first variant is shown as A. Within every pair of
    variants exactly half (one more or less when odd) show the first one as A, so a
    rater's habit of picking one side cannot look like a taste for one profile."""
    rng = random.Random(seed + 1)
    by_combo = defaultdict(list)
    for i, cand in enumerate(picked):
        by_combo[cand["combo"]].append(i)
    flips = [False] * len(picked)
    for combo in sorted(by_combo):
        idx = by_combo[combo]
        flags = [True] * (len(idx) // 2) + [False] * (len(idx) - len(idx) // 2)
        if len(idx) % 2:
            flags[-1] = rng.random() < 0.5
        rng.shuffle(flags)
        for i, flag in zip(idx, flags):
            flips[i] = flag
    return flips


def plan_id(request_id: str, variant: str) -> str:
    return f"{request_id}/{variant}"


def dataset_id(pairs: list[dict]) -> str:
    """Names one exact set of pairs: answers saved for another set never mix with it."""
    blob = json.dumps(pairs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{SCHEMA}-{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:10]}"


def build_dataset(rows: list[dict], by_id: dict, n: int = 150, per_request: int = 2, seed: int = 7,
                  min_edits: int = MIN_EDIT_STOPS, min_share: float = MIN_EDIT_SHARE,
                  snapshot: str = SNAPSHOT.name, built_at: str | None = None) -> tuple[dict, dict]:
    """(pairs document for raters, key document) from planned rows."""
    by_request = {row["request_id"]: row for row in rows}
    candidates, dropped = candidate_pairs(rows, min_edits, min_share)
    picked = select_pairs(candidates, n, per_request, seed)
    flips = assign_sides(picked, seed)
    pairs, key_pairs = [], {}
    for i, (cand, first_is_a) in enumerate(zip(picked, flips), 1):
        row = by_request[cand["request_id"]]
        a, b = (cand["first"], cand["second"]) if first_is_a else (cand["second"], cand["first"])
        pair_id = f"P{i:03d}"
        base = (row["trip"].get("origin") or {}).get("poi_id")
        pairs.append({"pair_id": pair_id, "request": request_view(row["trip"], by_id),
                      "A": plan_view(row["plans"][a], by_id, base), "B": plan_view(row["plans"][b], by_id, base)})
        rid = cand["request_id"]
        key_pairs[pair_id] = {
            "request_id": rid,
            "first": plan_id(rid, cand["first"]), "second": plan_id(rid, cand["second"]),
            "A": plan_id(rid, a), "B": plan_id(rid, b),
            "variants": {plan_id(rid, cand["first"]): cand["first"], plan_id(rid, cand["second"]): cand["second"]},
            **{k: cand[k] for k in ("edits", "edit_share", "jaccard", "shared")}}
    dataset = dataset_id(pairs)
    built_at = built_at or datetime.date.today().isoformat()
    used = {k["request_id"] for k in key_pairs.values()}
    pairs_doc = {"schema": SCHEMA, "dataset": dataset, "built_at": built_at, "snapshot": snapshot,
                 "n_pairs": len(pairs), "pairs": pairs}
    key_doc = {
        "schema": KEY_SCHEMA, "dataset": dataset, "built_at": built_at, "snapshot": snapshot,
        "label_convention": LABEL_CONVENTION, "variant_order": list(VARIANTS),
        "settings": {"n": n, "per_request": per_request, "seed": seed,
                     "min_edit_stops": min_edits, "min_edit_share": min_share},
        "stats": stats(rows, candidates, dropped, picked, flips),
        "pairs": key_pairs,
        "requests": {r["request_id"]: {"source": r["source"], "trip": r["trip"]}
                     for r in rows if r["request_id"] in used},
        "dropped": dropped,
    }
    return pairs_doc, key_doc


def stats(rows: list[dict], candidates: list[dict], dropped: list[dict], picked: list[dict],
          flips: list[bool]) -> dict:
    by_request = {r["request_id"]: r for r in rows}
    reasons = Counter("near-identical" if d["reason"] == "near-identical" else "plan not shown"
                      for d in dropped)
    return {
        "requests": len(rows),
        "requests_with_a_pair": len({c["request_id"] for c in candidates}),
        "plans": sum(len(r.get("plans") or {}) for r in rows),
        "plans_shown": sum(showable(p) for r in rows for p in (r.get("plans") or {}).values()),
        "candidate_pairs": len(candidates), "dropped": dict(reasons),
        "picked": len(picked),
        "picked_by_combo": dict(sorted(Counter(c["combo"] for c in picked).items())),
        "first_shown_as_a": sum(flips),
        "picked_by_source": dict(sorted(Counter(by_request[c["request_id"]]["source"] for c in picked).items())),
        "picked_requests": len({c["request_id"] for c in picked}),
        "median_edit_share": sorted(c["edit_share"] for c in picked)[len(picked) // 2] if picked else None,
        # A rater reads "phải đến X" on top and finds X in neither plan: fix such a request.
        "must_visit_dropped": sorted(r["request_id"] for r in rows
                                     if any(w.startswith(MUST_DROPPED) or f": {MUST_DROPPED}" in w
                                            for p in (r.get("plans") or {}).values()
                                            for w in p.get("warnings") or [])),
    }


# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------

DATA_OPEN = '<script type="application/json" id="pairs-data">'
DATA_CLOSE = "</script>"


def embed(page: str, pairs_doc: dict) -> str:
    """The page with `pairs_doc` as its embedded data (whatever was there before)."""
    start = page.index(DATA_OPEN) + len(DATA_OPEN)
    end = page.index(DATA_CLOSE, start)
    data = json.dumps(pairs_doc, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return page[:start] + data + page[end:]


def write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=150, help="pairs to keep (default 150)")
    ap.add_argument("--per-request", type=int, default=2, help="most pairs from one request")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-edit-stops", type=int, default=MIN_EDIT_STOPS)
    ap.add_argument("--min-edit-share", type=float, default=MIN_EDIT_SHARE)
    ap.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    ap.add_argument("--plans-cache", type=Path, default=None,
                    help="keep the planner output here, and resume from it after an interruption")
    ap.add_argument("--reuse", type=Path, default=None, help="read the planner output instead of planning")
    ap.add_argument("--only", default="", help="comma-separated request id prefixes (a quick trial)")
    ap.add_argument("--out-dir", type=Path, default=HERE)
    args = ap.parse_args(argv)

    by_id = load_pois(str(args.snapshot), by_id=True)
    if args.reuse:
        rows = json.loads(args.reuse.read_text(encoding="utf-8"))["rows"]
    else:
        requests = collect_requests(by_id)
        if args.only:
            requests = [r for r in requests if r["request_id"].startswith(tuple(args.only.split(",")))]
        print(f"{len(requests)} requests", flush=True)
        rows = run_planner(requests, args.snapshot, args.plans_cache)
    pairs_doc, key_doc = build_dataset(rows, by_id, args.n, args.per_request, args.seed,
                                       args.min_edit_stops, args.min_edit_share, args.snapshot.name)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / PAIRS_PATH.name, pairs_doc)
    write_json(args.out_dir / KEY_PATH.name, key_doc)
    page = args.out_dir / PAGE_PATH.name
    template = page if page.exists() else PAGE_PATH
    if template.exists():
        page.write_text(embed(template.read_text(encoding="utf-8"), pairs_doc), encoding="utf-8")
    else:
        print(f"no page at {template}: pairs written, page not")
    print(json.dumps(key_doc["stats"], ensure_ascii=False, indent=1))
    print(f"{pairs_doc['n_pairs']} pairs, dataset {pairs_doc['dataset']} -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
