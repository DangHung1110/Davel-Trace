"""Independent quality audit of real plans (docs/plan-accuracy.md, "Kiểm tra độc lập").

Plans a fixed set of real requests through POST /v1/itinerary on a snapshot (3 plans a
request, weather mocked offline like bench_latency.py) and judges every plan with rules
written on their own: nothing here calls the app's gate, so a bug the gate shares with
the solver still shows up. Two kinds of flags:

  ERR_*  the plan cannot be followed as written (hours, travel, budget, overlap);
  Q_*    it can be followed but a traveller would call it poor (a hole of hours, a
         late start, a detour, a meal missing, a wish not met, a wrong hour).

Usage (repo root):
  python BE/tools/audit_plans.py --out audit.json                 # plan, then report
  python BE/tools/audit_plans.py --out audit.json --report-only   # report saved plans
  python BE/tools/audit_plans.py --out audit.json --only T,W --plans plans.txt

 writes every plan in readable form with its flags, for reading by eye. The
thresholds are this file's own (a hole is 75 idle minutes, a detour 1.5 times the
shortest path and 15 minutes more): they say what was counted, not what a traveller feels.
"""
from __future__ import annotations

import argparse
import datetime
import itertools
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from BE.common import effective_fee, load_matrix_cells  # noqa: E402

DEFAULT_SNAPSHOT = str(REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1")


def peak_rss_mb() -> float:
    """Peak memory of this process in MB (0 where the platform cannot say: Windows)."""
    try:
        import resource
    except ImportError:
        return 0.0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024

COUPLE = {"party_type": "couple", "pace": 2, "fitness": 2}
FAMILY = {"party_type": "family", "pace": 1, "fitness": 1}
FRIENDS = {"party_type": "friends", "pace": 3, "fitness": 3}
SOLO = {"party_type": "solo", "pace": 2, "fitness": 2}
DAY = {"start_time": "08:00", "end_time": "20:00", "budget": 3_000_000, "days": 1, "travelers": 2}

SCENARIOS: list[tuple[str, dict]] = [
    # --- typical days -------------------------------------------------------
    ("T01-neutral", {}),
    ("T02-couple", {"profile": COUPLE}),
    ("T03-family", {"profile": FAMILY, "travelers": 4}),
    ("T04-friends-late", {"profile": FRIENDS, "travelers": 4, "end_time": "22:00"}),
    ("T05-solo-1m", {"profile": SOLO, "travelers": 1, "budget": 1_000_000}),
    ("T06-couple-0718", {"profile": COUPLE, "start_time": "07:00", "end_time": "18:00"}),
    ("T07-couple-morning", {"profile": COUPLE, "start_time": "07:00", "end_time": "12:00"}),
    ("T08-couple-afternoon", {"profile": COUPLE, "start_time": "13:00", "end_time": "21:00"}),
    ("T09-family-0917-1.5m", {"profile": FAMILY, "travelers": 4, "start_time": "09:00",
                              "end_time": "17:00", "budget": 1_500_000}),
    ("T10-friends-evening", {"profile": FRIENDS, "travelers": 4, "start_time": "16:00",
                             "end_time": "23:00"}),
    ("T11-neutral-0915", {"start_time": "09:00", "end_time": "15:00"}),
    ("T12-couple-600k", {"profile": COUPLE, "budget": 600_000}),
    ("T13-neutral-0718", {"start_time": "07:00", "end_time": "18:00"}),
    ("T14-solo-300k", {"profile": SOLO, "travelers": 1, "budget": 300_000}),
    ("T15-family-2m", {"profile": FAMILY, "travelers": 4, "budget": 2_000_000}),
    ("T16-couple-long", {"profile": COUPLE, "start_time": "06:00", "end_time": "22:00"}),
    # --- wishes -------------------------------------------------------------
    ("W01-beach", {"profile": COUPLE, "activities": ["tắm biển"]}),
    ("W02-seafood", {"profile": COUPLE, "activities": ["hải sản"]}),
    ("W03-museum", {"profile": FAMILY, "travelers": 4, "activities": ["bảo tàng"]}),
    ("W04-pagoda", {"profile": COUPLE, "activities": ["chùa"]}),
    ("W05-coffee", {"profile": COUPLE, "activities": ["cà phê"]}),
    ("W06-night-market", {"profile": COUPLE, "activities": ["chợ đêm"], "end_time": "21:30"}),
    ("W07-sunset", {"profile": COUPLE, "activities": ["ngắm hoàng hôn"]}),
    ("W08-hike", {"profile": COUPLE, "activities": ["leo núi"]}),
    ("W09-mi-quang", {"profile": FAMILY, "travelers": 4, "activities": ["mì quảng"]}),
    ("W10-gift", {"activities": ["mua quà"]}),
    ("W11-bar", {"profile": FRIENDS, "travelers": 4, "activities": ["quán bar"],
                 "start_time": "14:00", "end_time": "23:00"}),
    ("W12-spa", {"profile": COUPLE, "activities": ["massage"]}),
    ("W13-park", {"profile": FAMILY, "travelers": 4, "activities": ["công viên"]}),
    ("W14-bridge", {"profile": COUPLE, "activities": ["cầu"]}),
    ("W15-church", {"activities": ["nhà thờ"]}),
    ("W16-cave", {"profile": COUPLE, "activities": ["hang động"]}),
    ("W17-beach-seafood-coffee", {"profile": COUPLE, "activities": ["tắm biển", "hải sản", "cà phê"]}),
    ("W18-museum-pagoda-market", {"profile": COUPLE, "activities": ["bảo tàng", "chùa", "chợ"]}),
    ("W19-bun", {"profile": COUPLE, "activities": ["bún"]}),
    ("W20-vegan", {"profile": COUPLE, "activities": ["ăn chay"]}),
    ("W21-banh-xeo", {"profile": COUPLE, "activities": ["bánh xèo"]}),
    ("W22-cable-car", {"profile": COUPLE, "activities": ["cáp treo"]}),
    ("W23-sunrise", {"profile": COUPLE, "activities": ["ngắm bình minh"], "start_time": "05:00",
                     "end_time": "17:00"}),
    ("W24-beach-seafood-noprofile", {"activities": ["tắm biển", "hải sản"]}),
    ("W25-seafood-evening", {"profile": COUPLE, "activities": ["hải sản"], "start_time": "15:00",
                             "end_time": "21:30"}),
    ("W26-shopping", {"profile": FRIENDS, "travelers": 4, "activities": ["mua sắm"]}),
    ("W27-history", {"profile": COUPLE, "activities": ["lịch sử"]}),
    ("W28-foodprefs-seafood", {"profile": {**COUPLE, "food_prefs": ["hải sản"]}}),
    # --- named places -------------------------------------------------------
    ("M01-ngu-hanh-son", {"profile": COUPLE, "must_visit": ["Ngũ Hành Sơn"]}),
    ("M02-cau-rong+linh-ung", {"profile": COUPLE, "must_visit": ["Cầu Rồng", "Chùa Linh Ứng - Bãi Bụt Sơn Trà"]}),
    ("M03-three", {"profile": COUPLE, "must_visit": ["Ngũ Hành Sơn", "Bãi biển Mỹ Khê", "Chợ Hàn"]}),
    ("M04-order", {"profile": COUPLE, "must_visit": ["Bảo tàng Điêu khắc Chăm Đà Nẵng", "Chợ Cồn"],
                   "order_prefs": [["Chợ Cồn", "Bảo tàng Điêu khắc Chăm Đà Nẵng"]]}),
    ("M05-ba-na", {"profile": COUPLE, "must_visit": ["Sun World Bà Nà Hills"]}),
    ("M06-family-musts", {"profile": FAMILY, "travelers": 4,
                          "must_visit": ["Bảo Tàng Đà Nẵng", "Công Viên APEC"]}),
    ("M07-noprofile-musts", {"must_visit": ["Ngũ Hành Sơn", "Bãi biển Mỹ Khê"]}),
    ("M08-two-temples", {"profile": COUPLE, "must_visit": ["Chùa Linh Ứng - Bãi Bụt Sơn Trà", "Chùa Quán Thế Âm"]}),
    # --- dates --------------------------------------------------------------
    ("D01-monday", {"profile": COUPLE, "date": "2026-11-16"}),
    ("D02-sunday-museum", {"profile": FAMILY, "travelers": 4, "activities": ["bảo tàng"],
                           "date": "2026-11-15"}),
    ("D03-saturday-beach", {"profile": COUPLE, "activities": ["tắm biển"], "date": "2026-11-14"}),
    # --- two days -----------------------------------------------------------
    ("X01-two-couple", {"profile": COUPLE, "days": 2}),
    ("X02-two-family", {"profile": FAMILY, "travelers": 4, "days": 2}),
    ("X03-two-beach-museum", {"profile": COUPLE, "days": 2, "activities": ["tắm biển", "bảo tàng"]}),
    ("X04-two-friends", {"profile": FRIENDS, "travelers": 4, "days": 2}),
    ("X05-two-neutral", {"days": 2}),
    ("X06-two-low-budget", {"profile": COUPLE, "days": 2, "budget": 800_000}),
    ("X07-two-musts", {"profile": COUPLE, "days": 2,
                       "must_visit": ["Ngũ Hành Sơn", "Chùa Linh Ứng - Bãi Bụt Sơn Trà", "Chợ Hàn"]}),
    # --- hard filters -------------------------------------------------------
    ("E01-allergy-seafood", {"profile": {**COUPLE, "allergy": ["seafood"]}}),
    ("E02-wheelchair", {"profile": {**FAMILY, "accessibility": ["wheelchair"]}, "travelers": 4}),
    ("E03-avoid-nightlife", {"profile": {**FRIENDS, "must_avoid": ["nightlife"]}, "travelers": 4}),
    ("E04-six-people-2m", {"profile": FRIENDS, "travelers": 6, "budget": 2_000_000}),
    ("E05-solo-200k", {"profile": SOLO, "travelers": 1, "budget": 200_000}),
]


def run(out_path: str, snapshot: str, only: list[str] | None = None, repeat: int = 1) -> None:
    """Plan every scenario and save the responses with their wall and CPU seconds."""
    from fastapi.testclient import TestClient

    from BE.app import main as main_mod
    from BE.app.config import Settings
    from BE.app.routers import itinerary as itinerary_mod
    from BE.app.services import scorer, trip_ctx

    os.chdir(REPO_ROOT)  # scorer.MODEL_PATH is relative to the repo root
    settings = Settings(snapshot_dir=snapshot, snapshot_name=os.path.basename(snapshot))
    client = TestClient(main_mod.app)
    rows = []
    print("scorer:", scorer.describe(), flush=True)
    with mock.patch.object(itinerary_mod, "get_settings", lambda: settings), \
            mock.patch.object(trip_ctx.weather_svc, "fetch_forecast",
                              side_effect=RuntimeError("offline")):
        for round_no in range(repeat):
            for key, extra in SCENARIOS:
                if only and not any(key.startswith(p) for p in only):
                    continue
                trip = {**DAY, **extra}
                cpu0 = time.process_time()
                t0 = time.perf_counter()
                resp = client.post("/v1/itinerary", json={"trip": trip})
                wall = time.perf_counter() - t0
                cpu = time.process_time() - cpu0
                body = resp.json()
                plans = body.get("plans") or []
                rss = peak_rss_mb()
                rows.append({"key": key, "round": round_no, "trip": trip, "status": resp.status_code,
                             "wall_s": round(wall, 3), "cpu_s": round(cpu, 3), "rss_mb": round(rss, 1),
                             "body": body})
                print(f"{key} r{round_no}: {resp.status_code} {wall:5.1f}s cpu {cpu:5.1f}s rss {rss:6.0f}MB | "
                      + " | ".join(f"{p.get('profile')}:{len(p.get('activities') or [])}"
                                   f"{'' if p.get('passed') else '!'}" for p in plans), flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"scorer": scorer.describe(), "snapshot": snapshot, "rows": rows}, f, ensure_ascii=False)


def to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def spans(spec: str) -> list[tuple[int, int]]:
    out = []
    for part in (spec or "").split(","):
        part = part.strip()
        if part.count("-") != 1:
            continue
        o, c = (to_min(x.strip()) for x in part.split("-"))
        out.append((o, c if c > o else c + 1440))
    return out


def fits(start: int, end: int, spec: str) -> bool:
    return any(o <= start and end <= c for o, c in spans(spec))


def best_path(ids: list[str], cells) -> int | None:
    """Shortest open path over all the stops, any order (Held-Karp)."""
    n = len(ids)
    if n < 2:
        return 0
    d = [[(cells.get(f"{a}->{b}") or {}).get("minutes") for b in ids] for a in ids]
    INF = 10 ** 9
    dp = {(1 << i, i): 0 for i in range(n)}
    for size in range(2, n + 1):
        for subset in itertools.combinations(range(n), size):
            mask = sum(1 << i for i in subset)
            for last in subset:
                prev_mask = mask ^ (1 << last)
                best = INF
                for k in subset:
                    if k == last or d[k][last] is None:
                        continue
                    cand = dp.get((prev_mask, k), INF) + d[k][last]
                    best = min(best, cand)
                dp[(mask, last)] = best
    full = (1 << n) - 1
    best = min(dp[(full, i)] for i in range(n))
    return None if best >= INF else best


# What a traveller would call the wrong hour, written independently of soft_rules.
def wrong_hour(poi: dict, start: int, end: int) -> str | None:
    cat, sub = poi.get("cat"), poi.get("subcat")
    if cat == "restaurant":
        meal = (10 * 60 + 30 <= start and end <= 15 * 60) or (17 * 60 <= start and end <= 22 * 60 + 30)
        breakfast = sub == "eatery" and start >= 6 * 60 + 30 and end <= 15 * 60
        if not (meal or breakfast):
            return "an ngoai gio bua"
    if cat == "bar" and start < 16 * 60 + 30:
        return "bar truoc 16:30"
    if cat == "beach" and start < 15 * 60 and end > 11 * 60 + 30:
        return "bien giua trua"
    if cat == "temple" and end > 18 * 60:
        return "chua sau 18:00"
    if sub == "night_market" and start < 17 * 60:
        return "cho dem truoc 17:00"
    if cat == "park" and start < 14 * 60 + 30 and end > 11 * 60 + 30:
        return "cong vien giua trua"
    if cat in ("viewpoint", "nature") and end > 18 * 60 + 15:
        return "ngam canh sau khi toi"
    if sub == "sunrise" and end > 9 * 60 + 30:
        return "diem binh minh sau 9:30"
    return None


def audit_day(acts: list[dict], trip: dict, pois: dict, cells, date: str, must: set[str],
              rest_minutes: int | None) -> tuple[list[str], dict]:
    flags: list[str] = []
    acts = sorted(acts, key=lambda a: a["start"])
    ws, we = to_min(trip["start_time"]), to_min(trip["end_time"])
    weekday = None
    try:
        weekday = datetime.date.fromisoformat(date).weekday() if date else None
    except ValueError:
        pass
    travel = 0
    legs = []
    idle_total = 0
    previous = None
    lunch = dinner = None
    restaurant_starts = []
    for a in acts:
        poi = pois[a["poi_id"]]
        s, e = to_min(a["start"]), to_min(a["end"])
        if s < ws or e > we or e <= s:
            flags.append(f"ERR_WINDOW {poi['name']} {a['start']}-{a['end']}")
        # opening hours
        week = poi.get("hours_by_day")
        if weekday is not None and week:
            today = week[weekday]
            if not today:
                flags.append(f"ERR_CLOSED_DAY {poi['name']}")
            elif not fits(s, e, today):
                flags.append(f"ERR_HOURS {poi['name']} {a['start']}-{a['end']} vs {today}")
        else:
            hours = poi.get("opening_hours") or []
            if hours and not any(fits(s, e, h) for h in hours):
                flags.append(f"ERR_HOURS {poi['name']} {a['start']}-{a['end']} vs {hours}")
            elif hours and not all(fits(s, e, h) for h in hours):
                flags.append(f"Q_HOURS_SOME_DAYS {poi['name']} {a['start']}-{a['end']} vs {hours}")
            if week and weekday is None and any(not day for day in week):
                flags.append(f"Q_MAY_BE_CLOSED {poi['name']}")
        if not poi.get("verified"):
            flags.append(f"ERR_UNVERIFIED {poi['name']}")
        if previous is not None:
            pe = to_min(previous["end"])
            cell = cells.get(f"{previous['poi_id']}->{a['poi_id']}")
            need = cell.get("minutes") if cell else None
            if need is None:
                flags.append(f"ERR_NO_ROUTE {pois[previous['poi_id']]['name']} -> {poi['name']}")
                need = 0
            if s < pe:
                flags.append(f"ERR_OVERLAP {pois[previous['poi_id']]['name']} / {poi['name']}")
            elif s - pe < need:
                flags.append(f"ERR_TRAVEL {pois[previous['poi_id']]['name']} -> {poi['name']} "
                             f"can {need}p co {s - pe}p")
            travel += need
            legs.append(need)
            idle = s - pe - need
            prev_poi = pois[previous["poi_id"]]
            allowed = 75
            if prev_poi.get("cat") == "restaurant" and 11 * 60 <= to_min(previous["start"]) < 13 * 60 and rest_minutes:
                allowed = rest_minutes + 45
            if idle > allowed:
                flags.append(f"Q_HOLE {idle}p trong sau {prev_poi['name']} ({previous['end']} -> {a['start']})")
            idle_total += max(0, idle)
            if need > 35:
                flags.append(f"Q_LONG_LEG {need}p {prev_poi['name']} -> {poi['name']}")
        # duration vs the POI's usual stay
        vm = poi.get("visit_min")
        if isinstance(vm, dict):
            length = e - s
            if vm.get("p25") and length < vm["p25"] and a["poi_id"] not in must:
                flags.append(f"Q_TOO_SHORT {poi['name']} {length}p < p25 {vm['p25']}")
            if vm.get("p75") and length > vm["p75"] + 10:
                flags.append(f"Q_TOO_LONG {poi['name']} {length}p > p75 {vm['p75']}")
        if a["poi_id"] not in must:
            why = wrong_hour(poi, s, e)
            if why:
                flags.append(f"Q_WRONG_HOUR {poi['name']} {a['start']}-{a['end']}: {why}")
            if (poi.get("review_count") or 0) < 20:
                flags.append(f"Q_UNKNOWN_PLACE {poi['name']} ({poi.get('review_count')} danh gia)")
            if (poi.get("rating") or 0) < 3.8:
                flags.append(f"Q_LOW_RATING {poi['name']} {poi.get('rating')}")
        if poi.get("cat") == "restaurant":
            restaurant_starts.append(s)
            if 10 * 60 + 45 <= s < 13 * 60 + 15 and lunch is None:
                lunch = a
            if 17 * 60 + 30 <= s <= 20 * 60 + 30:
                dinner = a
        previous = a
    for x, y in zip(restaurant_starts, restaurant_starts[1:]):
        if y - x < 150:
            flags.append(f"Q_MEALS_TOO_CLOSE {y - x}p")
    if acts:
        # A stay of five hours and more through 11:00-13:00 feeds its visitors on site.
        on_site = any(to_min(a["end"]) - to_min(a["start"]) >= 300 and to_min(a["start"]) <= 11 * 60
                      and to_min(a["end"]) >= 13 * 60 and pois[a["poi_id"]].get("cat") != "restaurant"
                      for a in acts)
        if ws <= 11 * 60 + 30 and we >= 13 * 60 + 30 and lunch is None and not on_site:
            flags.append("Q_NO_LUNCH")
        if ws <= 18 * 60 and we >= 19 * 60 + 30 and dinner is None:
            flags.append("Q_NO_DINNER")
        first, last = to_min(acts[0]["start"]), to_min(acts[-1]["end"])
        if first - ws > 60:
            flags.append(f"Q_LATE_START {first - ws}p")
        if we - last > 90:
            flags.append(f"Q_EARLY_END {we - last}p")
        cats = Counter(pois[a["poi_id"]].get("cat") for a in acts)
        food = cats.get("restaurant", 0) + cats.get("cafe", 0) + cats.get("bar", 0)
        if len(acts) >= 4 and food / len(acts) > 0.6:
            flags.append(f"Q_MOSTLY_FOOD {food}/{len(acts)}")
        sights = sum(n for c, n in cats.items() if c in
                     ("attraction", "landmark", "museum", "park", "temple", "beach", "viewpoint", "nature"))
        if len(acts) >= 4 and sights == 0:
            flags.append("Q_NO_SIGHT")
        hours = (we - ws) / 60
        if hours >= 8 and len(acts) < 4:
            flags.append(f"Q_THIN_DAY {len(acts)} diem / {hours:.0f}h")
    ids = [a["poi_id"] for a in acts]
    best = best_path(ids, cells) if 2 <= len(ids) <= 11 else None
    detour = round(travel / best, 2) if best else 1.0
    if best and travel - best >= 15 and detour >= 1.5:
        flags.append(f"Q_DETOUR x{detour} ({travel}p vs {best}p)")
    visit = sum(to_min(a["end"]) - to_min(a["start"]) for a in acts)
    stats = {"stops": len(acts), "travel": travel, "best_travel": best, "detour": detour,
             "idle": idle_total, "visit": visit, "day_min": we - ws,
             "first": acts[0]["start"] if acts else None, "last": acts[-1]["end"] if acts else None,
             "max_leg": max(legs, default=0)}
    return flags, stats


def report(path: str, plans_out: str | None = None, json_out: str | None = None) -> dict:
    """Judge the saved plans; prints the summary and returns {"summary", "counts", ...}."""
    doc = json.load(open(path, encoding="utf-8"))
    snapshot = doc.get("snapshot") or DEFAULT_SNAPSHOT
    pois = {p["poi_id"]: p for p in json.load(open(snapshot + "/pois.json", encoding="utf-8"))["pois"]}
    cells = load_matrix_cells(snapshot)
    name_to_id = {p["name"].strip().lower(): pid for pid, p in pois.items()}

    lines: list[str] = []
    counts: Counter = Counter()
    plan_flags: dict[str, list[str]] = {}
    per_set: dict[str, list[bool]] = defaultdict(list)
    day_stats: list[dict] = []
    walls: dict[str, list[float]] = defaultdict(list)
    cpus: list[float] = []
    wish_total = wish_met = 0
    n_plans = n_empty = n_failed = n_clean = n_followable = 0
    signature: dict[str, list] = defaultdict(list)
    jaccard_bad = 0
    for row in doc["rows"]:
        key, trip, body = row["key"], row["trip"], row["body"]
        days = int(trip.get("days") or 1)
        walls["2day" if days > 1 else "1day"].append(row["wall_s"])
        cpus.append(row["cpu_s"])
        plans = body.get("plans") or []
        if row["status"] != 200:
            lines.append(f"### {key}: HTTP {row['status']} {json.dumps(body, ensure_ascii=False)[:300]}")
            counts["HTTP_ERROR"] += 1
            continue
        must = {name_to_id.get(m.strip().lower(), m) for m in trip.get("must_visit") or []}
        sets = []
        lines.append(f"\n### {key}  {json.dumps({k: v for k, v in trip.items() if k not in ('days',) or v != 1}, ensure_ascii=False)}"
                     f"  [{row['wall_s']}s wall, {row['cpu_s']}s cpu]")
        signature[key].append([[(a.get("day"), a["poi_id"], a["start"], a["end"]) for a in p.get("activities") or []]
                               for p in plans])
        for plan in plans:
            n_plans += 1
            pid = f"{key}/{plan.get('profile')}"
            acts = plan.get("activities") or []
            flags: list[str] = []
            if not acts:
                n_empty += 1
                flags.append("EMPTY")
            if not plan.get("passed"):
                n_failed += 1
                flags.append(f"GATE_FAILED {plan.get('violations')}")
            for soft in plan.get("soft_violations") or []:
                flags.append(f"SOFT_{soft}")
            rest = ((plan.get("template") or {}).get("rest_block") or {}).get("minutes")
            by_day: dict = defaultdict(list)
            for a in acts:
                by_day[a.get("day") or 1].append(a)
            seen = Counter(a["poi_id"] for a in acts)
            for dup, n in seen.items():
                if n > 1:
                    flags.append(f"ERR_DUPLICATE {pois[dup]['name']}")
            if acts and len(by_day) < days:
                flags.append(f"ERR_MISSING_DAY {len(by_day)}/{days}")
            total_fee = 0
            for number in sorted(by_day):
                date = ""
                if trip.get("date"):
                    date = (datetime.date.fromisoformat(trip["date"])
                            + datetime.timedelta(days=number - 1)).isoformat()
                day_rest = rest
                if plan.get("days"):
                    info = next((d for d in plan["days"] if d.get("day") == number), {})
                    day_rest = ((info.get("template") or {}).get("rest_block") or {}).get("minutes")
                day_flags, stats = audit_day(by_day[number], trip, pois, cells, date, must, day_rest)
                flags += [f"{f} [ngay {number}]" if days > 1 else f for f in day_flags]
                stats.update({"plan": pid, "day": number, "profile": plan.get("profile")})
                day_stats.append(stats)
                total_fee += sum(effective_fee(pois[a["poi_id"]]) or 0 for a in by_day[number])
            cost = total_fee * max(1, int(trip.get("travelers") or 1))
            if cost > int(trip.get("budget") or 0):
                flags.append(f"ERR_BUDGET {cost} > {trip.get('budget')}")
            if acts and cost != plan.get("total_cost"):
                flags.append(f"ERR_COST_MISMATCH bao {plan.get('total_cost')} tinh {cost}")
            missing_must = [pois[m]["name"] for m in must if m in pois and m not in seen]
            if missing_must:
                flags.append(f"Q_MUST_MISSING {missing_must}")
            for match in plan.get("activity_match") or []:
                wish_total += 1
                if match.get("status") == "met":
                    wish_met += 1
                else:
                    flags.append(f"Q_WISH_{match.get('status').upper()} {match.get('activity')}")
            sets.append({a["poi_id"] for a in acts})
            hard = [f for f in flags if f.startswith(("ERR_", "EMPTY", "GATE_FAILED"))]
            quality = [f for f in flags if f.startswith(("Q_", "SOFT_"))]
            n_followable += not hard
            n_clean += not hard and not quality
            per_set[key[0]].append(not hard and not quality)
            for f in flags:
                counts[f.split()[0]] += 1
            plan_flags[pid] = flags
            # readable plan
            lines.append(f"  -- {plan.get('profile')}: {len(acts)} diem, {plan.get('total_cost'):,}d, "
                         f"di {plan.get('travel_min')}p, passed={plan.get('passed')} "
                         f"rung={plan.get('template', {}).get('relaxed_step')}")
            previous = None
            for a in sorted(acts, key=lambda a: (a.get("day") or 1, a["start"])):
                poi = pois[a["poi_id"]]
                leg = ""
                if previous and (previous.get("day") or 1) == (a.get("day") or 1):
                    cell = cells.get(f"{previous['poi_id']}->{a['poi_id']}") or {}
                    idle = to_min(a["start"]) - to_min(previous["end"]) - (cell.get("minutes") or 0)
                    leg = f"(+{cell.get('minutes')}p di, {idle}p trong)"
                day = f"D{a.get('day')} " if a.get("day") else ""
                lines.append(f"     {day}{a['start']}-{a['end']} [{poi.get('cat')}/{poi.get('subcat') or '-'}] "
                             f"{poi['name'][:44]} ({poi.get('rating')}*, {poi.get('review_count')}) "
                             f"{(effective_fee(poi) or 0) // 1000}k {leg}")
                previous = a
            for f in flags:
                lines.append(f"     ! {f}")
            for w in plan.get("warnings") or []:
                if not w.startswith(("khong lay duoc du bao", "chi phi la uoc tinh", "ngay 1: chi phi", "ngay 2: chi phi")):
                    lines.append(f"     w {w}")
        for (i, a), (j, b) in itertools.combinations(enumerate(sets), 2):
            if a and b and len(a & b) / len(a | b) > 0.6 + 1e-9:
                jaccard_bad += 1
                lines.append(f"     ! Q_TOO_SIMILAR plans {i},{j}: {len(a & b) / len(a | b):.2f}")
                counts["Q_TOO_SIMILAR"] += 1

    unstable = [k for k, runs in signature.items() if len(runs) > 1 and any(r != runs[0] for r in runs[1:])]
    repeated = sum(1 for runs in signature.values() if len(runs) > 1)

    def pct(a, b):
        return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "0/0"

    full = [d for d in day_stats if d["stops"]]
    summary = [
        f"scorer: {doc.get('scorer')}",
        f"requests: {len(doc['rows'])}, plans: {n_plans}",
        f"empty plans: {pct(n_empty, n_plans)}",
        f"gate failed: {pct(n_failed, n_plans)}",
        f"followable (no ERR/EMPTY/GATE): {pct(n_followable, n_plans)}",
        f"clean (no flag at all): {pct(n_clean, n_plans)}",
        "clean by set: " + ", ".join(f"{k}: {pct(sum(v), len(v))}" for k, v in sorted(per_set.items())),
        f"wishes met: {pct(wish_met, wish_total)}",
        f"repeat check: {repeated} requests repeated, unstable: {unstable}",
        f"days planned: {len(full)}; stops/day median {statistics.median(d['stops'] for d in full)}; "
        f"travel/day mean {statistics.mean(d['travel'] for d in full):.1f}p; "
        f"detour mean x{statistics.mean(d['detour'] for d in full):.2f}, days >1.3: "
        f"{sum(1 for d in full if d['detour'] > 1.3)}; idle/day mean {statistics.mean(d['idle'] for d in full):.0f}p; "
        f"visit share {100 * sum(d['visit'] for d in full) / sum(d['day_min'] for d in full):.0f}%",
    ]
    for group, values in walls.items():
        values = sorted(values)
        summary.append(f"latency {group}: n={len(values)} median {statistics.median(values):.1f}s "
                       f"p95 {values[max(0, round(0.95 * len(values)) - 1)]:.1f}s max {values[-1]:.1f}s")
    summary.append(f"cpu per request: median {statistics.median(cpus):.1f}s max {max(cpus):.1f}s; "
                   f"rss max {max(r['rss_mb'] for r in doc['rows']):.0f}MB")
    summary.append("flags: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
    print("\n".join(summary))
    if plans_out:
        with open(plans_out, "w", encoding="utf-8") as f:
            f.write("\n".join(summary) + "\n" + "\n".join(lines) + "\n")
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "counts": counts, "plan_flags": plan_flags,
                       "day_stats": day_stats}, f, ensure_ascii=False, indent=1)
    return {"summary": summary, "counts": dict(counts), "plan_flags": plan_flags, "day_stats": day_stats}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="where the planned responses are saved (JSON)")
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    parser.add_argument("--only", default="", help="comma-separated scenario prefixes (T, W, M, D, X, E)")
    parser.add_argument("--repeat", type=int, default=1, help="plan every request this many times")
    parser.add_argument("--report-only", action="store_true", help="judge the plans already in --out")
    parser.add_argument("--plans", default=None, help="write every plan with its flags to this text file")
    parser.add_argument("--flags", default=None, help="write the flags and day statistics to this JSON file")
    args = parser.parse_args(argv)
    if not args.report_only:
        run(args.out, os.path.abspath(args.snapshot), [p for p in args.only.split(",") if p], args.repeat)
    report(args.out, args.plans, args.flags)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
