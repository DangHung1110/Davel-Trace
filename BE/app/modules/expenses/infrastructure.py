"""Expense persistence queries."""

from sqlalchemy import select

from decimal import Decimal

from BE.app.db.models import (
    BudgetRevisionModel,
    ExpenseEntryModel,
    TripActivityModel,
    TripDayModel,
    TripModel,
)
from BE.app.modules.identity.service import IdentityError


def owned_expense(session, account_id, expense_id, *, lock=False):
    query = select(ExpenseEntryModel).join(
        TripModel, ExpenseEntryModel.trip_id == TripModel.trip_id,
    ).where(
        ExpenseEntryModel.expense_id == expense_id,
        TripModel.account_id == account_id,
        TripModel.lifecycle_state.notin_(("deleted", "purged")),
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if not row:
        raise IdentityError("NOT_FOUND", "Không tìm thấy khoản chi.", 404)
    return row, owned_trip(session, account_id, row.trip_id, lock=lock)


def owned_trip(session, account_id, trip_id, *, lock=False):
    query = select(TripModel).where(
        TripModel.trip_id == trip_id,
        TripModel.account_id == account_id,
        TripModel.lifecycle_state.notin_(("deleted", "purged")),
    )
    if lock:
        query = query.with_for_update()
    trip = session.scalar(query)
    if not trip:
        raise IdentityError("NOT_FOUND", "Không tìm thấy chuyến đi.", 404)
    return trip


def validate_links(session, trip_id, day_id, activity_id) -> None:
    if day_id:
        day = session.scalar(select(TripDayModel).where(
            TripDayModel.day_id == day_id, TripDayModel.trip_id == trip_id
        ))
        if not day:
            raise IdentityError("VALIDATION_ERROR", "Ngày không thuộc chuyến đi.", 422)
    if activity_id:
        activity = session.scalar(select(TripActivityModel).join(
            TripDayModel, TripActivityModel.day_id == TripDayModel.day_id
        ).where(
            TripActivityModel.activity_id == activity_id,
            TripDayModel.trip_id == trip_id,
        ))
        if not activity:
            raise IdentityError("VALIDATION_ERROR", "Hoạt động không thuộc chuyến đi.", 422)


def record_budget_revision(session, trip, account_id, new_amount, reason="") -> bool:
    """Apply one budget change inside the caller's existing transaction."""
    amount = Decimal(str(new_amount))
    if amount < 0:
        raise IdentityError("VALIDATION_ERROR", "Ngân sách không được âm.", 422)
    previous = trip.indicative_budget
    if previous is not None and Decimal(previous) == amount:
        return False
    session.add(BudgetRevisionModel(
        trip_id=trip.trip_id, previous_amount=previous, new_amount=amount,
        currency="VND", reason=str(reason).strip()[:500], changed_by=account_id,
    ))
    trip.indicative_budget = amount
    trip.currency = "VND"
    return True
