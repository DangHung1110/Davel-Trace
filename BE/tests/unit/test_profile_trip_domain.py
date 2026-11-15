from datetime import date, time

import pytest

from BE.app.modules.profiles.domain import normalized_list, normalized_profile
from BE.app.modules.trips.domain import dates_between, validate_trip


def test_profile_lists_are_trimmed_deduplicated_and_bounded() -> None:
    assert normalized_list(["  Hải sản ", "hải SẢN", "Bảo tàng"]) == [
        "Hải sản", "Bảo tàng"
    ]
    profile = normalized_profile({"display_name": " Hùng ", "pace": 3,
                                  "fitness": 2, "allergies": ["Đậu phộng"]})
    assert profile["display_name"] == "Hùng"
    assert profile["allergies"] == ["Đậu phộng"]


def test_trip_limits_and_hard_override_are_enforced() -> None:
    valid = {"title": "Đà Nẵng", "start_date": date(2026, 11, 3),
             "end_date": date(2026, 11, 5), "traveler_count": 2,
             "day_start": time(8), "day_end": time(21),
             "preference_overrides": {"pace": 1}}
    validate_trip(valid)
    assert len(dates_between(valid["start_date"], valid["end_date"])) == 3
    with pytest.raises(ValueError):
        validate_trip({**valid, "preference_overrides": {"allergies": []}})
    with pytest.raises(ValueError):
        validate_trip({**valid, "end_date": date(2026, 12, 1)})
