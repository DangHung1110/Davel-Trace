from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from BE.app.modules.expenses.domain import alert_for, normalize_expense
from BE.app.modules.identity.service import IdentityError


def _trip():
    return SimpleNamespace(
        start_date=datetime(2026, 11, 10).date(),
        end_date=datetime(2026, 11, 12).date(),
    )


def test_normalize_whole_vnd_and_thresholds() -> None:
    value = normalize_expense({
        "label": " Mì Quảng ", "amount_vnd": 120000,
        "category": "food",
        "spent_at": datetime(2026, 11, 10, 12, tzinfo=timezone.utc),
    }, _trip())
    assert value["label"] == "Mì Quảng"
    assert int(value["amount"]) == 120000
    assert alert_for(799, 1000) == "none"
    assert alert_for(800, 1000) == "80"
    assert alert_for(1000, 1000) == "100"
    assert alert_for(1, 0) == "100"


@pytest.mark.parametrize("field,value", [
    ("amount_vnd", 0),
    ("category", "unknown"),
    ("spent_at", datetime(2026, 11, 13, tzinfo=timezone.utc)),
])
def test_rejects_invalid_expense(field, value) -> None:
    body = {
        "label": "Chi phí", "amount_vnd": 1, "category": "other",
        "spent_at": datetime(2026, 11, 10, tzinfo=timezone.utc),
    }
    body[field] = value
    with pytest.raises(IdentityError):
        normalize_expense(body, _trip())
