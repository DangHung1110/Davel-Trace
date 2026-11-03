"""Pure profile normalization and snapshot rules."""

from typing import Any


HARD_FIELDS = ("must_avoid", "allergies", "accessibility_needs")
LIST_FIELDS = ("food_preferences", "preferred_activities", "usual_transport", *HARD_FIELDS)


def normalized_list(value: list[str] | None, limit: int = 30) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in value or []:
        item = raw.strip()
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item[:120])
        if len(result) >= limit:
            break
    return result


def normalized_profile(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    result["display_name"] = str(data.get("display_name", "")).strip()[:120]
    if not result["display_name"]:
        raise ValueError("Tên hiển thị là bắt buộc.")
    for field in LIST_FIELDS:
        result[field] = normalized_list(data.get(field))
    pace, fitness = int(data.get("pace", 2)), int(data.get("fitness", 2))
    if pace not in (1, 2, 3) or fitness not in (1, 2, 3):
        raise ValueError("Nhịp đi và thể lực phải từ 1 đến 3.")
    result["pace"], result["fitness"] = pace, fitness
    return result


def profile_snapshot(profile) -> dict[str, Any]:
    return {
        "party_type": profile.party_type, "trip_purpose": profile.trip_purpose,
        "pace": profile.pace, "fitness": profile.fitness,
        "spending_style": profile.spending_style,
        "food_preferences": list(profile.food_preferences),
        "preferred_activities": list(profile.preferred_activities),
        "usual_transport": list(profile.usual_transport),
        "must_avoid": list(profile.must_avoid), "allergies": list(profile.allergies),
        "accessibility_needs": list(profile.accessibility_needs),
    }
