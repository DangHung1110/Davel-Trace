"""NL parser VI -> TripRequest (T014, lane C) via LLM gateway (T005).

Contract (spec FR-001..006):
- FR-001/002/003: extract city, origin, date/time, party, budget,
  transport + activity/food/space/pace/fitness/crowd/order preferences.
- FR-004: separate hard_constraints / soft_prefs / assumptions /
  uncertainties — soft is NEVER copied into hard slots (FR-006).
- FR-005: missing city/budget -> needs clarification; missing time -> stated
  default assumption (07:00-18:00, 1 day) recorded in `assumptions`, never
  silent.

`llm_fn` (default llm.complete_json) is injectable for mock tests.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from BE.app.schemas.trip import TripRequest
from BE.app.services import llm as llm_gateway

DEFAULT_START, DEFAULT_END, DEFAULT_DAYS = "07:00", "18:00", 1


class TripSlots(BaseModel):
    """Raw slots the LLM must return as JSON (all optional except intent)."""

    city: str = ""
    date: str = ""
    start_time: str = ""
    end_time: str = ""
    # Optional ints: qwen3 sometimes emits "" for a missing number. Normalise
    # that to None BEFORE validation so the existing defaults apply instead of
    # failing the whole parse three times and returning 503.
    days: int | None = None
    travelers: int | None = None
    budget: int | None = None
    transport: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    food_prefs: list[str] = Field(default_factory=list)
    order_prefs: list[list[str]] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_prefs: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)

    @field_validator("days", "travelers", "budget", mode="before")
    @classmethod
    def _blank_int(cls, value):
        """Gateway-boundary guard: qwen3 sends "" for a missing number.

        `llm.complete_json` validates the model response against this schema
        BEFORE `parse` sees it, so the same normalisation must live here too:
        otherwise the gateway retries 3x and returns 503 (the live bug).
        """
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                return None
        return value


_INT_SLOTS = ("days", "travelers", "budget")
_STR_SLOTS = ("city", "date", "start_time", "end_time")
_LIST_SLOTS = ("transport", "must_visit", "avoid", "activities", "food_prefs",
               "hard_constraints", "soft_prefs", "uncertainties")


def _normalize_slots(raw) -> dict:
    """Pre-validate the LLM dict (qwen3 emits "" where a number is expected).

    - "" / null for days/travelers/budget -> None (TripSlots defaults then
      apply; budget None still asks for clarification, days/travelers fall
      back to 1/2 in `parse`).
    - numeric strings -> int ("3000000" -> 3000000).
    - an unparseable number -> None, i.e. the same fail-open default instead
      of a schema error that would retry the LLM and end in a 503.
    - strings are stripped, list items are stripped and empties dropped.
    """
    if not isinstance(raw, dict):
        return raw
    out = dict(raw)
    for key in _STR_SLOTS:
        value = out.get(key)
        if isinstance(value, str):
            out[key] = value.strip()
    for key in _INT_SLOTS:
        value = out.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "":
            out[key] = None
            continue
        try:
            out[key] = int(value)
        except (TypeError, ValueError):
            out[key] = None
    for key in _LIST_SLOTS:
        value = out.get(key)
        if not isinstance(value, list):
            continue
        cleaned = []
        for item in value:
            if isinstance(item, str):
                item = item.strip()
                if item:
                    cleaned.append(item)
            elif item is not None:
                cleaned.append(item)
        out[key] = cleaned
    order = out.get("order_prefs")
    if isinstance(order, list):
        out["order_prefs"] = [
            [str(part).strip() for part in pair if str(part).strip()]
            for pair in order if isinstance(pair, (list, tuple))]
    return out


PROMPT_TEMPLATE = (
    "Trích xuất yêu cầu du lịch tiếng Việt thành JSON đúng schema, "
    "chỉ trả JSON, không giải thích.\n"
    "Schema: city, date, start_time/end_time (HH:MM), days, travelers, "
    "budget (VND số nguyên nếu user nêu, null nếu chưa nêu), transport[], "
    "must_visit[] (CHỈ khi user nói "
    "bắt buộc/phải ghé), avoid[] (CHỈ khi user nói tránh/không đi), "
    "activities[], food_prefs[], order_prefs[] (cặp [trước, sau]), "
    "hard_constraints[], soft_prefs[] (sở thích mềm, KHÔNG đưa vào "
    "must_visit/avoid), uncertainties[] (thông tin chưa chắc chắn).\n"
    "VÍ DỤ: 'thích hải sản' → food_prefs=[\"hải sản\"], soft_prefs+=[\"hải sản\"]; "
    "TUYỆT ĐỐI KHÔNG cho món ăn/sở thích vào must_visit. must_visit chỉ "
    "chứa TÊN ĐỊA ĐIỂM CỤ THỂ user nêu (ví dụ 'Cầu Rồng', 'chợ Cồn').\n"
    "Câu: {text}\n"
    "/no_think"  # NOTE(test-local): tat thinking mode cua qwen3 (cham,
    # treo timeout). Xoa khi dung model khac.
)


def parse(text: str, user_id: str = "u1", llm_fn=None) -> dict:
    """Return {"trip": TripRequest} | {"needs_clarification": [...]}.

    Always includes "assumptions" and "soft_prefs" lists for transparency.
    """
    llm_fn = llm_fn or llm_gateway.complete_json
    raw = llm_fn(PROMPT_TEMPLATE.format(text=text), TripSlots)
    slots = TripSlots(**_normalize_slots(raw))
    assumptions: list[str] = []
    missing: list[str] = []
    if not slots.city.strip():
        missing.append("city")
    if slots.budget is None:
        missing.append("budget")
    if missing:
        return {"needs_clarification": missing, "assumptions": assumptions,
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
