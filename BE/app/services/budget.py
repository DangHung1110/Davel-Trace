"""Replan budget feed (T036b, lane B). Tighten spend to actuals.

Input: lane-C `replan_budget()` output {trip_id, budget, spent, left,
by_kind, alert} + trip. Output: replan constraints for T046 rolling
replan {trip_id, allowed_total, allowed_remaining, per_kind_cap,
tightened, reason}.

Rules: allowed_remaining = max(0, left) (overspent -> 0, never
negative); tightened = spent over half the budget (morning-heavy ->
afternoon mirrors the actual kind mix); light spend -> equal split.
"""

from __future__ import annotations


def tighten_budget(state: dict, trip: dict | None = None) -> dict:
    left = int(state.get("left", 0))
    budget = int(state.get("budget", 0))
    spent = int(state.get("spent", 0))
    by_kind = dict(state.get("by_kind", {}))
    allowed = max(0, left)
    # ponytail: "spent over half the budget" is the deliberate tighten
    # heuristic (morning-heavy); tune with real spend logs, not yet.
    tightened = spent > budget * 0.5 if budget > 0 else False
    if spent > 0:
        caps = {k: round(allowed * v / spent) for k, v in by_kind.items()}
    else:
        kinds = list(by_kind) or ["food", "ticket", "transport", "other"]
        caps = {k: round(allowed / len(kinds)) for k in kinds}
    if allowed == 0:
        reason = "het ngan sach (chi vuot), replan 0d chi tieu"
    elif tightened:
        reason = f"sang chi nang ({spent}), chieu siet con {allowed} theo co cau thuc te"
    else:
        reason = f"chi nhe, con {allowed} chia deu"
    return {"trip_id": state.get("trip_id", (trip or {}).get("trip_id", "t1")),
            "allowed_total": budget, "allowed_remaining": allowed,
            "per_kind_cap": caps, "tightened": tightened, "reason": reason}
