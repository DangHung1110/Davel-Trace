"""NL parser VI -> TripRequest (T014, lane C) via LLM gateway (T005).

Contract (spec FR-001..006):
- FR-001/002/003: extract city, origin, date/time, party, budget,
  transport + activity/food/space/pace/fitness/crowd/order preferences.
- FR-004: separate hard_constraints / soft_prefs / assumptions /
  uncertainties — soft is NEVER copied into hard slots (FR-006).
- FR-005: missing city -> needs_clarification ["city"] (cannot assume
  the destination); missing time -> stated default assumption
  (07:00-18:00, 1 day) recorded in `assumptions`, never silent.

`llm_fn` (default llm.complete_json) is injectable for mock tests.
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pydantic import BaseModel, Field  # noqa: E402

from BE.app.schemas.trip import TripRequest  # noqa: E402
from BE.app.services import llm as llm_gateway  # noqa: E402

DEFAULT_START, DEFAULT_END, DEFAULT_DAYS = "07:00", "18:00", 1


class TripSlots(BaseModel):
    """Raw slots the LLM must return as JSON (all optional except intent)."""

    city: str = ""
    date: str = ""
    start_time: str = ""
    end_time: str = ""
    days: int = 0
    travelers: int = 0
    budget: int = 0
    transport: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    food_prefs: list[str] = Field(default_factory=list)
    order_prefs: list[list[str]] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_prefs: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


PROMPT_TEMPLATE = (
    "Trích xuất yêu cầu du lịch tiếng Việt thành JSON đúng schema, "
    "chỉ trả JSON, không giải thích.\n"
    "Schema: city, date, start_time/end_time (HH:MM), days, travelers, "
    "budget (VND số nguyên), transport[], must_visit[] (CHỈ khi user nói "
    "bắt buộc/phải ghé), avoid[] (CHỈ khi user nói tránh/không đi), "
    "activities[], food_prefs[], order_prefs[] (cặp [trước, sau]), "
    "hard_constraints[], soft_prefs[] (sở thích mềm, KHÔNG đưa vào "
    "must_visit/avoid), uncertainties[] (thông tin chưa chắc chắn).\n"
    "Câu: {text}"
)


def parse(text: str, user_id: str = "u1", llm_fn=None) -> dict:
    """Return {"trip": TripRequest} | {"needs_clarification": [...]}.

    Always includes "assumptions" and "soft_prefs" lists for transparency.
    """
    llm_fn = llm_fn or llm_gateway.complete_json
    slots = TripSlots(**llm_fn(PROMPT_TEMPLATE.format(text=text), TripSlots))
    assumptions: list[str] = []
    if not slots.city.strip():
        return {"needs_clarification": ["city"], "assumptions": assumptions,
                "soft_prefs": slots.soft_prefs}
    start = slots.start_time or DEFAULT_START
    end = slots.end_time or DEFAULT_END
    days = slots.days or DEFAULT_DAYS
    if not slots.start_time or not slots.end_time or not slots.days:
        assumptions.append(f"gio mac dinh {start}-{end}, {days} ngay (user xac nhan lai)")
    trip = TripRequest(
        user_id=user_id, city=slots.city.strip().lower().replace(" ", "-"),
        date=slots.date, start_time=start, end_time=end, days=days,
        travelers=slots.travelers or 2, budget=slots.budget,
        transport=slots.transport or ["motorbike"],
        must_visit=slots.must_visit, avoid=slots.avoid,
        activities=slots.activities, food_prefs=slots.food_prefs,
        order_prefs=slots.order_prefs)
    return {"trip": trip, "assumptions": assumptions,
            "soft_prefs": slots.soft_prefs,
            "hard_constraints": slots.hard_constraints,
            "uncertainties": slots.uncertainties}
