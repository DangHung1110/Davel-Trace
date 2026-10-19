from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from BE.app.errors import AppError
from BE.app.models.expense import Expense
from BE.app.models.trip import Trip
from BE.app.repositories import expenses as repo
from BE.app.schemas.expense import ExpenseCreate, ExpenseUpdate
from BE.app.services import agent_expenses

CATEGORIES = ("food", "ticket", "transport", "other")

# Compatibility seam for the AI planner's in-memory expense context.
reset = agent_expenses.reset
set_budget = agent_expenses.set_budget
add = agent_expenses.add
summary = agent_expenses.summary
replan_budget = agent_expenses.replan_budget


def build_summary(budget_vnd: int, expenses: Iterable[Any]) -> dict[str, Any]:
    by_category = {category: 0 for category in CATEGORIES}
    spent = 0
    for expense in expenses:
        if isinstance(expense, dict):
            amount = int(expense["amount_vnd"])
            category = str(expense["category"])
        else:
            amount = int(expense.amount_vnd)
            category = str(expense.category)
        spent += amount
        by_category[category] = by_category.get(category, 0) + amount
    if spent >= budget_vnd and (spent > 0 or budget_vnd == 0):
        alert = "100"
    elif budget_vnd > 0 and spent * 100 >= budget_vnd * 80:
        alert = "80"
    else:
        alert = "none"
    return {
        "budget_vnd": budget_vnd,
        "spent_vnd": spent,
        "remaining_vnd": budget_vnd - spent,
        "by_category": by_category,
        "alert": alert,
    }


def _trip(session: Session, trip_id: str) -> Trip:
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise AppError("TRIP_NOT_FOUND", "Không tìm thấy chuyến đi", 404)
    return trip


def list_with_summary(session: Session, trip_id: str) -> tuple[list[Expense], dict]:
    trip = _trip(session, trip_id)
    items = repo.list_expenses(session, trip_id)
    return items, build_summary(trip.budget_vnd, items)


def create_expense(
    session: Session, trip_id: str, command: ExpenseCreate
) -> tuple[Expense, dict]:
    trip = _trip(session, trip_id)
    values = command.model_dump(exclude_none=True)
    expense = Expense(trip_id=trip_id, **values)
    session.add(expense)
    session.commit()
    session.refresh(expense)
    items = repo.list_expenses(session, trip_id)
    return expense, build_summary(trip.budget_vnd, items)


def update_expense(
    session: Session, expense_id: str, command: ExpenseUpdate
) -> tuple[Expense, dict]:
    expense = repo.get_expense(session, expense_id)
    if expense is None:
        raise AppError("EXPENSE_NOT_FOUND", "Không tìm thấy khoản chi", 404)
    if expense.version != command.version:
        raise AppError("VERSION_CONFLICT", "Khoản chi đã thay đổi; hãy tải lại", 409)
    for field, value in command.model_dump(exclude={"version"}, exclude_none=True).items():
        setattr(expense, field, value)
    expense.version += 1
    trip = _trip(session, expense.trip_id)
    session.commit()
    session.refresh(expense)
    return expense, build_summary(trip.budget_vnd, repo.list_expenses(session, trip.id))


def delete_expense(session: Session, expense_id: str, version: int) -> dict:
    expense = repo.get_expense(session, expense_id)
    if expense is None:
        raise AppError("EXPENSE_NOT_FOUND", "Không tìm thấy khoản chi", 404)
    if expense.version != version:
        raise AppError("VERSION_CONFLICT", "Khoản chi đã thay đổi; hãy tải lại", 409)
    trip = _trip(session, expense.trip_id)
    trip_id = trip.id
    session.delete(expense)
    session.commit()
    return build_summary(trip.budget_vnd, repo.list_expenses(session, trip_id))
