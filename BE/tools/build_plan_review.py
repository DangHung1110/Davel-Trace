"""Blind human review of real plans (docs/plan-accuracy.md, step 10).

Every accuracy number so far comes from rules a machine or Claude applied. This plans
a fixed set of real requests through the app and writes a page where a person rates
each plan as a traveller would: no scores, no gate results, no hint of what the audit
found. Answers stay with the reviewer until they save or copy them.

    python BE/tools/build_plan_review.py            # plans, FE/plan_review.html
    python BE/tools/build_plan_review.py --reuse    # keep the plans, rebuild the page

Outputs: BE/eval/human/plan_review_v1.json (what was asked and what was planned),
FE/plan_review.html (open it through server.py), and with --fragment PATH the same
page without its document skeleton, for publishing as an Artifact.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from BE.common import effective_fee, fee_is_estimate, load_matrix_cells  # noqa: E402

SNAPSHOT = _REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1"
PLANS_PATH = _REPO_ROOT / "BE" / "eval" / "human" / "plan_review_v1.json"
PAGE_PATH = _REPO_ROOT / "FE" / "plan_review.html"
TEMPLATE_PATH = Path(__file__).with_name("plan_review_template.html")

COUPLE = {"party_type": "couple", "pace": 2, "fitness": 2}
FAMILY = {"party_type": "family", "pace": 1, "fitness": 1}
FRIENDS = {"party_type": "friends", "pace": 3, "fitness": 3}
SOLO = {"party_type": "solo", "pace": 2, "fitness": 2}
DAY = {"start_time": "08:00", "end_time": "20:00", "budget": 3_000_000, "days": 1, "travelers": 2}

# (id, the plan of the three to show, request). One plan per request, so a reviewer
# judges 24 different days and the three profiles come up about equally.
REQUESTS = [
    ("neutral", "balanced", {}),
    ("couple", "experience", {"profile": COUPLE}),
    ("family", "savings", {"profile": FAMILY, "travelers": 4}),
    ("couple-beach", "balanced", {"profile": COUPLE, "activities": ["tắm biển"]}),
    ("family-museum", "experience", {"profile": FAMILY, "travelers": 4, "activities": ["bảo tàng"]}),
    ("pagoda-low", "savings", {"profile": COUPLE, "activities": ["chùa"], "budget": 600_000}),
    ("beach-seafood", "balanced", {"activities": ["tắm biển", "hải sản"]}),
    ("friends-night", "experience", {"profile": FRIENDS, "travelers": 4, "activities": ["quán bar"],
                                     "start_time": "14:00", "end_time": "23:00"}),
    ("family-2m", "balanced", {"profile": FAMILY, "travelers": 4, "budget": 2_000_000}),
    ("solo-300k", "savings", {"profile": SOLO, "travelers": 1, "budget": 300_000}),
    ("sunset", "balanced", {"profile": COUPLE, "activities": ["ngắm hoàng hôn"]}),
    ("church", "experience", {"activities": ["nhà thờ"]}),
    ("mi-quang", "savings", {"profile": FAMILY, "travelers": 4, "activities": ["mì quảng"]}),
    ("night-market", "balanced", {"profile": COUPLE, "activities": ["chợ đêm"]}),
    ("hike", "experience", {"profile": COUPLE, "activities": ["leo núi"]}),
    ("seafood-evening", "balanced", {"profile": COUPLE, "activities": ["hải sản"],
                                     "start_time": "15:00", "end_time": "21:30"}),
    ("gift", "savings", {"activities": ["mua quà"]}),
    ("cave", "balanced", {"profile": COUPLE, "activities": ["hang động"]}),
    ("monday", "balanced", {"profile": COUPLE, "date": "2026-11-02"}),
    ("sunday-museum", "experience", {"profile": FAMILY, "travelers": 4, "activities": ["bảo tàng"],
                                     "date": "2026-11-08"}),
    ("two-couple", "balanced", {"profile": COUPLE, "days": 2}),
    ("two-family", "savings", {"profile": FAMILY, "travelers": 4, "days": 2}),
    ("two-beach", "experience", {"profile": COUPLE, "days": 2, "activities": ["tắm biển"]}),
    ("two-friends", "balanced", {"profile": FRIENDS, "travelers": 4, "days": 2}),
]
# A fixed shuffle, so similar requests do not sit together and everyone sees one order.
ORDER = [7, 20, 2, 12, 18, 5, 23, 0, 10, 15, 3, 21, 8, 16, 1, 19, 13, 6, 22, 9, 17, 4, 14, 11]
# The offline planning run says the first; the page itself marks estimated prices.
HIDDEN_WARNINGS = ("khong lay duoc du bao thoi tiet", "chi phi la uoc tinh", "ngay 1: chi phi la uoc tinh",
                   "ngay 2: chi phi la uoc tinh")
PARTY = {"couple": "Cặp đôi", "family": "Gia đình có người già và trẻ nhỏ", "friends": "Nhóm bạn", "solo": "Đi một mình"}
PROFILE = {"savings": "Tiết kiệm", "balanced": "Cân bằng", "experience": "Trải nghiệm"}
KIND = {"restaurant": "Quán ăn", "cafe": "Cà phê", "bar": "Bar", "beach": "Biển", "museum": "Bảo tàng",
        "park": "Công viên", "market": "Chợ", "shop": "Cửa hàng", "temple": "Chùa, nhà thờ", "landmark": "Thắng cảnh",
        "attraction": "Điểm tham quan", "nature": "Thiên nhiên", "viewpoint": "Điểm ngắm cảnh", "spa": "Spa"}
WEEKDAY = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")


def _when(date: str) -> str:
    if not date:
        return ""
    day = datetime.date.fromisoformat(date)
    return f"{WEEKDAY[day.weekday()]}, {day.day:02d}/{day.month:02d}/{day.year}"


def _maps_url(poi: dict) -> str:
    from urllib.parse import quote
    name = quote(f"{poi.get('name')} Đà Nẵng")
    pid = str(poi.get("poi_id"))
    place = f"&query_place_id={quote(pid)}" if pid.startswith("ChIJ") else ""
    return f"https://www.google.com/maps/search/?api=1&query={name}{place}"


def plan_row(key: str, trip: dict, plan: dict, by_id: dict, cells: dict) -> dict:
    profile = trip.get("profile") or {}
    stops = []
    previous = None
    for act in plan["activities"]:
        poi = by_id[act["poi_id"]]
        same_day = previous and previous.get("day") == act.get("day")
        leg = (cells.get(f"{previous['poi_id']}->{act['poi_id']}") or {}).get("minutes") if same_day else None
        fee = effective_fee(poi)
        stops.append({
            "day": act.get("day"), "start": act["start"], "end": act["end"], "name": poi.get("name"),
            "kind": KIND.get(poi.get("cat"), poi.get("type") or ""), "leg_min": leg,
            "fee": fee, "fee_estimated": bool(fee) and fee_is_estimate(poi),
            "hours": ", ".join(poi.get("opening_hours") or []), "maps": _maps_url(poi),
            "poi_id": act["poi_id"]})
        previous = act
    return {
        "id": key, "profile": plan.get("profile"), "profile_label": PROFILE.get(plan.get("profile"), ""),
        "party": PARTY.get(profile.get("party_type"), "Chưa rõ nhóm khách"),
        "travelers": trip.get("travelers"), "budget": trip.get("budget"), "days": trip.get("days"),
        "start_time": trip.get("start_time"), "end_time": trip.get("end_time"),
        "date": _when(trip.get("date") or ""), "wishes": trip.get("activities") or [],
        "total_cost": plan.get("total_cost"), "travel_min": plan.get("travel_min"), "stops": stops,
        "notes": [w for w in plan.get("warnings") or [] if not w.startswith(HIDDEN_WARNINGS)],
    }


def make_plans() -> list[dict]:
    from fastapi.testclient import TestClient
    from BE.app import main as main_mod
    from BE.app.config import Settings
    from BE.app.routers import itinerary as itinerary_mod
    from BE.app.services import trip_ctx

    settings = Settings(snapshot_dir=str(SNAPSHOT), snapshot_name=SNAPSHOT.name)
    pois = json.loads((SNAPSHOT / "pois.json").read_text(encoding="utf-8"))["pois"]
    by_id = {p["poi_id"]: p for p in pois}
    cells = load_matrix_cells(str(SNAPSHOT))
    client = TestClient(main_mod.app)
    rows = []
    # No live weather: a reviewer must judge the plan, not one rainy forecast.
    with mock.patch.object(itinerary_mod, "get_settings", lambda: settings), \
            mock.patch.object(trip_ctx.weather_svc, "fetch_forecast", side_effect=RuntimeError("offline")):
        for key, profile, extra in REQUESTS:
            trip = {**DAY, **extra}
            body = client.post("/v1/itinerary", json={"trip": trip}).json()
            plan = next(p for p in body["plans"] if p.get("profile") == profile)
            rows.append(plan_row(key, trip, plan, by_id, cells))
            print(f"{key}: {len(plan['activities'])} stops, passed {plan.get('passed')}", flush=True)
    return [rows[i] for i in ORDER]


def render(plans: list[dict]) -> str:
    data = json.dumps(plans, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE_PATH.read_text(encoding="utf-8").replace("__PLANS_JSON__", data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse", action="store_true", help="keep the saved plans, rebuild the page only")
    parser.add_argument("--fragment", type=Path, default=None, help="also write the page without its skeleton")
    args = parser.parse_args(argv)
    if args.reuse:
        doc = json.loads(PLANS_PATH.read_text(encoding="utf-8"))
    else:
        doc = {"version": "plan-review-v1", "built_at": datetime.date.today().isoformat(), "plans": make_plans()}
        PLANS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLANS_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    page = render(doc["plans"])
    PAGE_PATH.write_text("<!doctype html>\n<html lang=\"vi\"><head><meta charset=\"utf-8\">"
                         "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head>"
                         f"<body>{page}</body></html>\n", encoding="utf-8")
    if args.fragment:
        args.fragment.write_text(page, encoding="utf-8")
    print(f"{len(doc['plans'])} plans -> {PAGE_PATH.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
