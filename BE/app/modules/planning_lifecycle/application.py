"""Pure helpers shared by lifecycle use cases and persistence adapters."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def alternative_fingerprint(plan: dict) -> str:
    """Fingerprint the ordered schedule, not profile labels or generated IDs."""
    activities = []
    for item in plan.get("activities") or []:
        activities.append({
            key: item.get(key)
            for key in ("day", "day_index", "poi_id", "start", "end")
            if item.get(key) is not None
        })
    return canonical_fingerprint(activities)


def internal_acceptance_key(account_id: str, reason: str, key: str) -> str:
    """Fit account-scoped lifecycle keys into the legacy global unique column."""
    digest = canonical_fingerprint([account_id, reason, key])
    return f"lifecycle-{digest[:54]}"
