from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from BE.app.models.expense import Expense


def list_expenses(session: Session, trip_id: str) -> list[Expense]:
    return list(
        session.scalars(
            select(Expense)
            .where(Expense.trip_id == trip_id)
            .order_by(Expense.spent_at.desc(), Expense.created_at.desc())
        )
    )


def get_expense(session: Session, expense_id: str) -> Expense | None:
    return session.get(Expense, expense_id)
