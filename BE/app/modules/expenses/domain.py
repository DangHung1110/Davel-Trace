"""Pure expense validation and accounting rules."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from BE.app.modules.identity.service import IdentityError

CATEGORIES = ("food", "ticket", "transport", "accommodation", "shopping", "other")
DA_NANG_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def normalize_expense(data: dict, trip) -> dict:
    label = str(data.get("label", "")).strip()
    if not label:
        raise IdentityError("VALIDATION_ERROR", "Nội dung khoản chi là bắt buộc.", 422)
    amount = Decimal(str(data.get("amount_vnd", 0)))
    if amount <= 0 or amount != amount.to_integral_value():
        raise IdentityError("VALIDATION_ERROR", "Số tiền VND phải là số nguyên dương.", 422)
    category = str(data.get("category", ""))
    if category not in CATEGORIES:
        raise IdentityError("VALIDATION_ERROR", "Nhóm chi tiêu không hợp lệ.", 422)
    spent_at = data.get("spent_at")
    if not isinstance(spent_at, datetime):
        raise IdentityError("VALIDATION_ERROR", "Thời gian chi tiêu không hợp lệ.", 422)
    if spent_at.tzinfo is None:
        spent_at = spent_at.replace(tzinfo=DA_NANG_TZ)
    local_date = spent_at.astimezone(DA_NANG_TZ).date()
    if not trip.start_date <= local_date <= trip.end_date:
        raise IdentityError("VALIDATION_ERROR", "Ngày chi phải nằm trong thời gian chuyến đi.", 422)
    return {
        "label": label[:200], "amount": amount, "category": category,
        "spent_at": spent_at, "notes": str(data.get("notes", "")).strip()[:2000],
        "day_id": data.get("day_id"), "activity_id": data.get("activity_id"),
    }


def alert_for(spent: int, budget: int) -> str:
    if budget <= 0:
        return "100" if spent > 0 else "none"
    if spent >= budget:
        return "100"
    if spent * 100 >= budget * 80:
        return "80"
    return "none"
