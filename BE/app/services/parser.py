"""NL parser VI -> TripRequest (T014, lane C) via LLM gateway (T005).

Contract (spec FR-001..006):
- FR-001/002/003: extract city, origin, date/time, party, budget,
  transport + activity/food/space/pace/fitness/crowd/order preferences.
- FR-004: separate hard_constraints / soft_prefs / assumptions /
  uncertainties — soft is NEVER copied into hard slots (FR-006).
- FR-005: missing city/budget -> needs clarification; missing time -> stated
  default assumption (07:00-18:00, 1 day) recorded in `assumptions`, never
  silent.

`areas` (the zones the plan stays in) is read from the text itself, not from the
LLM (`areas_in_text`): every request names "Đà Nẵng", and a model that reads it as
"the centre" would lock every plan to one zone.

`llm_fn` (default llm.complete_json) is injectable for mock tests.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field, field_validator

from BE.app.schemas.trip import TripRequest
from BE.app.services import llm as llm_gateway

DEFAULT_START, DEFAULT_END, DEFAULT_DAYS = "07:00", "18:00", 1

# How a traveller names a planning zone (`TripRequest.areas`). Matched on whole
# words, longest phrase first; a matched phrase is consumed, so "trung tâm Hội An"
# is Hội An and not also the centre. An empty list only blocks its words: a
# "trung tâm thương mại" is a mall, not the centre.
AREA_PHRASES = {
    "trung tâm": ["trung_tam"], "hải châu": ["trung_tam"],
    "trung tâm thương mại": [], "trung tâm mua sắm": [], "trung tâm hội nghị": [],
    "trung tâm vui chơi": [], "trung tâm triển lãm": [],
    "sơn trà": ["son_tra_my_khe"], "mỹ khê": ["son_tra_my_khe"],
    "ngũ hành sơn": ["ngu_hanh_son"], "non nước": ["ngu_hanh_son"],
    "hội an": ["hoi_an"], "phố cổ": ["hoi_an"],
    "trung tâm hội an": ["hoi_an"], "trung tâm phố cổ": ["hoi_an"],
    "hải vân": ["hai_van_lien_chieu"], "liên chiểu": ["hai_van_lien_chieu"],
    "bà nà": ["ba_na_tay"],
}
# A zone named right after one of these (up to 3 words, same clause) is one the
# traveller does NOT want: "không đi Hội An", "tránh Sơn Trà". Accented on purpose:
# folded, "tranh" is a painting and "bo" a walk ("đi bộ").
AREA_NEGATIONS = {"không", "khong", "tránh", "trừ", "khỏi", "đừng", "chẳng", "bỏ"}
_NEGATION_WINDOW = 3


def _fold(word: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFD", word)
                    if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", plain).replace("đ", "d")


# (words, the same words without accents, zones), longest phrase first.
_AREA_RULES = sorted(
    ((tuple(phrase.split()), tuple(_fold(word) for word in phrase.split()), codes)
     for phrase, codes in AREA_PHRASES.items()),
    key=lambda rule: len(rule[0]), reverse=True)


def areas_in_text(text: str) -> list[str]:
    """The zones a request names, in the order it names them.

    A phrase matches with its accents, or typed entirely without them ("hoi an");
    a word with other accents is another word ("hai vạn" is not Hải Vân).
    """
    found: list[str] = []
    lowered = unicodedata.normalize("NFC", str(text or "")).lower()
    for clause in re.split(r"[,.;:!?\n]+", lowered):
        words = re.findall(r"\w+", clause)
        i = 0
        while i < len(words):
            rule = next((r for r in _AREA_RULES
                         if tuple(words[i:i + len(r[0])]) in (r[0], r[1])), None)
            if rule is None:
                i += 1
                continue
            phrase, _plain, codes = rule
            if not AREA_NEGATIONS.intersection(words[max(0, i - _NEGATION_WINDOW):i]):
                found += [code for code in codes if code not in found]
            i += len(phrase)
    return found


class TripSlots(BaseModel):
    """Raw slots the LLM must return as JSON (all optional except intent)."""

    city: str = ""
    date: str = ""
    start_time: str = ""
    end_time: str = ""
    # Optional ints: qwen3 sometimes emits "" for a missing number.
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
        """"" or an unparseable number -> None, so the defaults apply (budget None
        still asks for clarification) instead of a schema error that retries the
        LLM and ends in a 503. "3000000" -> 3000000.
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


_STR_SLOTS = ("city", "date", "start_time", "end_time")
_LIST_SLOTS = ("transport", "must_visit", "avoid", "activities", "food_prefs",
               "hard_constraints", "soft_prefs", "uncertainties")


def _normalize_slots(raw) -> dict:
    """Strip the strings of the LLM dict, drop empty list items.

    Numbers are `TripSlots._blank_int`'s: it also runs behind the LLM gateway.
    """
    if not isinstance(raw, dict):
        return raw
    out = dict(raw)
    for key in _STR_SLOTS:
        value = out.get(key)
        if isinstance(value, str):
            out[key] = value.strip()
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
    "/no_think"  # tat thinking mode cua qwen3 (cham, treo timeout)
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
        order_prefs=slots.order_prefs, areas=areas_in_text(text))
    return {"trip": trip, "assumptions": assumptions,
            "soft_prefs": slots.soft_prefs,
            "hard_constraints": slots.hard_constraints,
            "uncertainties": slots.uncertainties}
