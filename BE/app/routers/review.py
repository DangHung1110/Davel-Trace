"""POST /v1/review (NOTE(test-local), do NOT PR as-is). LLM layer-3 review.

The deterministic gate (A1/FAR/...) catches arithmetic and hard feasibility;
this endpoint asks the local LLM for the *semantic* absurdities the rules
cannot express: double lunch, taste mismatch vs food_prefs, nightlife in the
morning. The HARD NO_ADJACENT_FOOD rule (any two restaurants back-to-back,
BBQ->vegan included) and REST_FOLLOWS_LUNCH are reported as facts so the
reviewer cannot re-raise a defect the plan provably does not have.

Grounding (TASK-3): the narrow model is prone to re-listing its own checklist
("ăn trưa 2 lần", "bar buổi sáng") even when the plan has no such defect. The
prompt therefore carries the deterministic A1/A2/B1/E2 facts, and every
returned issue that a passing deterministic rule *refutes* is dropped
(`_ground_issues`). The LLM can still add semantic issues the rules cannot
express; it just cannot re-report a defect the plan provably does not have.

In:  {"itinerary_id": "..."}  (read from the select store) or {"plan": {...}}
Out: {"issues": [{"issue", "severity", "suggestion"}, ...]}

The LLM is a NARROW reviewer: no arithmetic, no rewrite, JSON only, and the
prompt ends with /no_think (qwen3 thinking mode hangs on this box). Any LLM
failure returns {"issues": [], "note": "LLM_UNAVAILABLE"} — the test harness
must always get a 200 it can render, never a 500.
"""

from __future__ import annotations

import os
import unicodedata

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.routers import select as select_svc
from BE.app.services import llm as llm_gateway
from BE.app.services import retrieval as retrieval_svc
from BE.app.services import soft_rules
from BE.app.services.gate import (
    check_a1,
    check_cafe_cap,
    check_no_adjacent_food,
    check_no_consecutive,
    check_rest_follows_lunch,
)
from BE.common import deadline

router = APIRouter(prefix="/v1", tags=["review"])

PROMPT = (
    "Bạn review một lịch trình du lịch. CHỈ nêu điểm VÔ LÝ VỀ NGHĨA. "
    "KHÔNG tính toán, KHÔNG viết lại lịch, KHÔNG bịa địa điểm.\n"
    "Bắt các lỗi: ăn trưa 2 lần, HAI NHÀ HÀNG LIỀN NHAU (bất kể món, "
    "kể cả BBQ rồi ăn chay), lặp cùng loại điểm liên tiếp, món không khớp "
    "sở thích, bar/hộp đêm buổi sáng, nghỉ trưa không sát giờ ăn trưa.\n"
    "Mỗi lỗi trả về: ISSUE, SEVERITY (high|medium|low), SUGGESTION.\n"
    "Chỉ JSON: {{\"issues\": [{{\"issue\": \"...\", \"severity\": \"medium\", "
    "\"suggestion\": \"...\"}}]}}\n"
    "Sở thích ăn uống: {food_prefs}\n"
    "Lịch trình:\n{plan}\n"
    "DỮ KIỆN ĐÃ KIỂM TRA TỰ ĐỘNG (chỉ báo lỗi KHÔNG bị các mục PASS phủ định):\n"
    "{facts}\n"
    "/no_think"
)

SEVERITIES = ("high", "medium", "low")


class ReviewIn(BaseModel):
    itinerary_id: str | None = None
    plan: dict | None = None


def _activities(plan: dict) -> list[dict]:
    acts = plan.get("activities")
    if acts is None:
        acts = (plan.get("itinerary") or {}).get("activities") or []
    return sorted(acts, key=lambda a: (a.get("day") or 1, a.get("start", "")))


def _food_prefs(plan: dict) -> list[str]:
    trip = (plan.get("_context") or {}).get("trip") or {}
    return list(trip.get("food_prefs") or plan.get("food_prefs") or [])


def _clean_issues(obj: dict) -> list[dict]:
    """Keep only well-formed issues; clamp severity; cap text length."""
    issues = []
    for item in obj.get("issues") or []:
        if not isinstance(item, dict):
            continue
        issue = str(item.get("issue") or "").strip()
        if not issue:
            continue
        severity = str(item.get("severity") or "medium").strip().lower()
        issues.append({
            "issue": issue[:300],
            "severity": severity if severity in SEVERITIES else "medium",
            "suggestion": str(item.get("suggestion") or "").strip()[:300],
        })
    return issues


def _poi_index() -> dict:
    try:
        pois = retrieval_svc.load_pois_json(
            os.path.join(get_settings().snapshot_dir, "pois.json"))
    except (FileNotFoundError, NotADirectoryError):
        return {}
    return {p["poi_id"]: p for p in pois}


def plan_lines(plan: dict, pois: dict) -> list[str]:
    """Human-readable activity lines, one per activity (shared w/ repair)."""
    lines = []
    for act in _activities(plan):
        poi = pois.get(act.get("poi_id"), {})
        name = poi.get("name") or act.get("poi_id")
        kind = poi.get("cat") or poi.get("type") or "?"
        day = f"Ngày {act['day']}, " if act.get("day") else ""
        lines.append(f"- {day}{act.get('start')}-{act.get('end')}: {name} ({kind})")
    return lines


def _fold(text: str) -> str:
    """lowercase + accent-free (VI) for keyword matching."""
    text = unicodedata.normalize("NFD", str(text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace("đ", "d")


def _poi_text(poi: dict) -> str:
    parts = [poi.get("name"), poi.get("cat"), poi.get("type")]
    parts += list(poi.get("tags") or [])
    return _fold(" ".join(str(p) for p in parts if p))


def _adjacent_food_claim(text: str) -> bool:
    """Does the (folded) issue text claim two restaurants back-to-back?"""
    food = ("nha hang" in text or "quan an" in text or "bbq" in text
            or "nuong" in text or "chay" in text or "hai san" in text
            or "do an" in text or "mon an" in text)
    adjacent = ("lien" in text or "canh nhau" in text or "ke tiep" in text
                or "ngay sau" in text or "roi an" in text or "sau do" in text)
    return food and adjacent


def _review_facts(plan: dict, pois: dict, trip: dict | None = None) -> tuple[str, dict]:
    """Deterministic rule facts for the prompt + the pass/fail map used to
    drop review issues the plan provably does not have."""
    acts = _activities(plan)
    itinerary = {"activities": acts}
    if trip is None:
        trip = (plan.get("_context") or {}).get("trip") or {}
    penalties = soft_rules.plan_penalties(acts, pois, trip)
    rules = {i.get("rule") for i in penalties.get("issues", [])}
    checks = {
        "A1": check_a1(itinerary, trip, pois, {})["passed"],
        "CAFE_CAP": check_cafe_cap(itinerary, trip, pois, {})["passed"],
        "NO_CONSECUTIVE": check_no_consecutive(itinerary, trip, pois,
                                               {})["passed"],
        "NO_ADJACENT_FOOD": check_no_adjacent_food(itinerary, trip, pois,
                                                   {})["passed"],
        "REST_FOLLOWS_LUNCH": check_rest_follows_lunch(
            itinerary, trip, pois, {})["passed"],
        "A2": "A2" not in rules,
        "B1": "B1" not in rules,
        "B2": "B2" not in rules,
        "E2": "E2" not in rules,
    }
    rest_note = ""
    if checks["REST_FOLLOWS_LUNCH"] and (trip or {}).get("profile"):
        span = soft_rules.rest_span(acts, pois, trip.get("profile"),
                                    deadline(trip))
        if span:
            rest_note = (f" (bua trua ket thuc {span['start'] // 60:02d}:"
                         f"{span['start'] % 60:02d} -> nghi den "
                         f"{span['end'] // 60:02d}:{span['end'] % 60:02d}, "
                         f"{span['minutes']} phut)")
    facts = "\n".join([
        f"- A1 (toi da 1 nha hang moi bua): {'PASS' if checks['A1'] else 'FAIL'}",
        "- CAFE_CAP (toi da 1 quan cafe/ngay, 2 chi khi khac buoi sang/chieu "
        f"va ho so co nhu cau cafe): {'PASS' if checks['CAFE_CAP'] else 'FAIL'}",
        "- NO_CONSECUTIVE (khong 2 diem cung loai lien tiep): "
        f"{'PASS' if checks['NO_CONSECUTIVE'] else 'FAIL'}",
        "- NO_ADJACENT_FOOD (khong 2 NHA HANG lien nhau, bat ke mon): "
        f"{'PASS - khong co cap nha hang nao lien nhau' if checks['NO_ADJACENT_FOOD'] else 'FAIL'}",
        "- REST_FOLLOWS_LUNCH (nghi trua bat dau ngay khi bua trua ket thuc, "
        "dung do dai theo nhip, khong POI nao nam trong): "
        f"{('PASS' + rest_note) if checks['REST_FOLLOWS_LUNCH'] else 'FAIL'}",
        "- A2 (2 nha hang cach nhau duoi 150 phut, bat ke nhan bua): "
        f"{'PASS - khong co cap nao' if checks['A2'] else 'FAIL'}",
        f"- B1 (2 diem cung loai lien tiep): {'PASS' if checks['B1'] else 'FAIL'}",
        f"- B2 (qua 2 diem cung loai trong ngay): {'PASS' if checks['B2'] else 'FAIL'}",
        f"- E2 (bar/hop dem truoc 17:00): {'PASS' if checks['E2'] else 'FAIL'}",
    ])
    return facts, checks


def _ground_issues(issues: list[dict], checks: dict, plan: dict,
                   pois: dict) -> list[dict]:
    """Drop LLM issues a passing deterministic rule refutes.

    Only claims that map to a concrete rule are filtered; semantic issues the
    rules cannot express (taste, weather, ...) always survive. This is the
    fix for the local reviewer re-listing "double lunch" / "bar in the
    morning" from its prompt even when A1/A2/E2 pass.
    """
    acts = _activities(plan)
    poi_rows = [pois.get(a.get("poi_id"), {}) for a in acts]
    # Refutation needs evidence: if a POI is not in the catalog we cannot
    # prove the claim false, so the LLM issue is kept (conservative).
    known = all(a.get("poi_id") in pois for a in acts)
    vegan = known and any(("chay" in _poi_text(p) or "vegan" in _poi_text(p))
                          for p in poi_rows)
    bbq = known and any(("bbq" in _poi_text(p) or "nuong" in _poi_text(p))
                        for p in poi_rows)
    kept = []
    for issue in issues:
        text = _fold(issue.get("issue", ""))
        refuted = False
        if (("an trua" in text and "2" in text)
                or "double lunch" in text
                or ("trua" in text and "lap" in text)):
            refuted = known and checks["A1"] and checks["A2"]
        elif (("nghi" in text and "trua" in text) or "siesta" in text
              or "rest window" in text):
            refuted = known and checks["REST_FOLLOWS_LUNCH"]
        elif "bar" in text or "hop dem" in text or "nightlife" in text:
            refuted = known and checks["E2"]
        elif _adjacent_food_claim(text):
            refuted = known and checks["NO_ADJACENT_FOOD"]
        elif ("lap" in text and ("loai" in text or "lien tiep" in text)
              or "cung loai" in text):
            refuted = (known and checks["NO_CONSECUTIVE"]
                       and checks["B1"] and checks["B2"])
        elif "chay" in text or "bbq" in text or "nuong" in text:
            # "BBQ roi an chay": only real if BOTH kinds are on the plan.
            refuted = known and not (vegan and bbq)
        if refuted:
            continue
        kept.append(issue)
    return kept


def review_prompt(plan: dict, pois: dict, trip: dict | None = None) -> str:
    prefs = ", ".join(list((trip or {}).get("food_prefs") or [])
                      or _food_prefs(plan))
    facts, _checks = _review_facts(plan, pois, trip)
    return PROMPT.format(food_prefs=prefs or "(khong co)",
                         plan="\n".join(plan_lines(plan, pois)) or "(rong)",
                         facts=facts)


def review_plan(plan: dict, pois: dict,
                trip: dict | None = None) -> list[dict]:
    """Run the NARROW semantic review and return cleaned, grounded issues.

    Shared by POST /v1/review and POST /v1/repair so both use the exact same
    prompt (and the same /no_think contract). Issues that contradict a
    passing deterministic rule are dropped before they reach the caller (see
    `_ground_issues`); the rest are the LLM's semantic value-add. Raises
    LLMError on failure; callers decide how soft to be.
    """
    _facts, checks = _review_facts(plan, pois, trip)
    issues = _clean_issues(
        llm_gateway.complete_json(review_prompt(plan, pois, trip)))
    return _ground_issues(issues, checks, plan, pois)


@router.post("/review")
def review(body: ReviewIn):
    plan = body.plan
    if plan is None:
        if not body.itinerary_id:
            return error("VALIDATION_ERROR",
                         "can itinerary_id hoac plan", 422)
        plan = select_svc.get_store()["plans"].get(body.itinerary_id)
        if plan is None:
            return error("UNKNOWN_ITINERARY",
                         f"khong co plan {body.itinerary_id}", 404)

    pois = _poi_index()
    try:
        issues = review_plan(plan, pois)
    except Exception:  # noqa: BLE001 - never 500 the harness
        return {"issues": [], "note": "LLM_UNAVAILABLE"}
    return {"issues": issues}
