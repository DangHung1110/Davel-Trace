"""Pure trip validation helpers."""

from datetime import date, timedelta
from typing import Any

from BE.app.modules.profiles.domain import HARD_FIELDS
from BE.app.schemas.trip import AREA_CODES


def validate_trip(data: dict[str, Any]) -> None:
    title = str(data.get("title", "")).strip()
    start, end = data.get("start_date"), data.get("end_date")
    if not title:
        raise ValueError("Tên chuyến đi là bắt buộc.")
    if not isinstance(start, date) or not isinstance(end, date) or end < start or (end - start).days > 13:
        raise ValueError("Chuyến đi phải kéo dài từ 1 đến 14 ngày.")
    if not 1 <= int(data.get("traveler_count", 0)) <= 20:
        raise ValueError("Số người phải từ 1 đến 20.")
    if data.get("day_start") >= data.get("day_end"):
        raise ValueError("Giờ bắt đầu ngày phải trước giờ kết thúc.")
    if any(key in HARD_FIELDS for key in (data.get("preference_overrides") or {})):
        raise ValueError("Không thể làm yếu ràng buộc an toàn của hồ sơ.")
    # The zones the planner keeps to (planning_lifecycle `_areas`): codes, not labels.
    areas = (data.get("preference_overrides") or {}).get("areas")
    if areas is not None and (not isinstance(areas, list)
                              or any(code not in AREA_CODES for code in areas)):
        raise ValueError("Khu vực phải là danh sách mã: " + ", ".join(AREA_CODES) + ".")


def dates_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=index) for index in range((end - start).days + 1)]
