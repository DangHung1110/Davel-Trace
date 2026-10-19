"""In-memory expense context used by the AI re-planning pipeline."""

from __future__ import annotations

import time

KINDS = ("food", "ticket", "transport", "other")
DEFAULT_BUDGET = 3000000

_expenses: dict[str, list[dict]] = {}
_budgets: dict[str, int] = {}


def reset() -> None:
    _expenses.clear()
    _budgets.clear()


def set_budget(trip_id: str, budget: int) -> None:
    _budgets[trip_id] = int(budget)


def add(trip_id: str, label: str, amount: int, kind: str, at: str = "") -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if int(amount) < 0:
        raise ValueError("amount must be >= 0")
    entry = {
        "trip_id": trip_id,
        "label": label,
        "amount": int(amount),
        "kind": kind,
        "at": at or time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _expenses.setdefault(trip_id, []).append(entry)
    return entry


def summary(trip_id: str) -> dict:
    budget = _budgets.get(trip_id, DEFAULT_BUDGET)
    spent = sum(entry["amount"] for entry in _expenses.get(trip_id, []))
    ratio = spent / budget if budget > 0 else 0.0
    alert = "100%" if ratio >= 1.0 else ("80%" if ratio >= 0.8 else "")
    return {"budget": budget, "spent": spent, "left": budget - spent, "alert": alert}


def replan_budget(trip_id: str) -> dict:
    current = summary(trip_id)
    by_kind: dict[str, int] = {kind: 0 for kind in KINDS}
    for entry in _expenses.get(trip_id, []):
        by_kind[entry["kind"]] = by_kind.get(entry["kind"], 0) + entry["amount"]
    return {
        "trip_id": trip_id,
        "budget": current["budget"],
        "spent": current["spent"],
        "left": current["left"],
        "by_kind": by_kind,
        "alert": current["alert"],
    }
