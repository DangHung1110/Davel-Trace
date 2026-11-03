"""Transactional expense and budget orchestration."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from BE.app.core.config import get_settings
from BE.app.core.mutations import receipt, request_fingerprint, save_receipt
from BE.app.db.models import (
    BudgetRevisionModel,
    ExpenseAuditEventModel,
    ExpenseEntryModel,
)
from BE.app.db.session import session_scope
from BE.app.modules.expenses.domain import CATEGORIES, DA_NANG_TZ, alert_for, normalize_expense
from BE.app.modules.expenses.infrastructure import owned_expense, owned_trip, validate_links
from BE.app.modules.identity.service import IdentityError


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value) -> int:
    return int(Decimal(value or 0))


def expense_public(row: ExpenseEntryModel) -> dict:
    return {
        "id": str(row.expense_id), "trip_id": str(row.trip_id),
        "day_id": str(row.day_id) if row.day_id else None,
        "activity_id": str(row.activity_id) if row.activity_id else None,
        "label": row.label, "amount_vnd": _money(row.amount),
        "currency": row.currency, "category": row.category,
        "spent_at": row.spent_at.astimezone(DA_NANG_TZ).isoformat(), "notes": row.notes,
        "version": row.version, "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _snapshot(row: ExpenseEntryModel) -> dict:
    return expense_public(row)


def _query_rows(session, trip_id, local_date: date | None = None,
                category: str | None = None):
    query = select(ExpenseEntryModel).where(ExpenseEntryModel.trip_id == trip_id)
    if local_date:
        query = query.where(
            func.date(func.timezone("Asia/Ho_Chi_Minh", ExpenseEntryModel.spent_at)) == local_date
        )
    if category:
        if category not in CATEGORIES:
            raise IdentityError("VALIDATION_ERROR", "Nhóm chi tiêu không hợp lệ.", 422)
        query = query.where(ExpenseEntryModel.category == category)
    return list(session.scalars(query.order_by(
        ExpenseEntryModel.spent_at.desc(), ExpenseEntryModel.expense_id.desc()
    )))


def _summary(rows: list[ExpenseEntryModel], budget: int) -> dict:
    spent = sum(_money(row.amount) for row in rows)
    by_category = {category: 0 for category in CATEGORIES}
    by_day: dict[str, int] = {}
    for row in rows:
        amount = _money(row.amount)
        by_category[row.category] += amount
        key = row.spent_at.astimezone(DA_NANG_TZ).date().isoformat()
        by_day[key] = by_day.get(key, 0) + amount
    return {
        "budget_vnd": budget, "spent_vnd": spent,
        "remaining_vnd": budget - spent,
        "by_category": by_category, "by_day": dict(sorted(by_day.items())),
        "average_vnd": spent // len(rows) if rows else 0,
        "entry_count": len(rows),
        "utilization_percent": round((spent / budget * 100), 2) if budget else (100.0 if spent else 0.0),
        "alert": alert_for(spent, budget),
    }


class ExpenseService:
    def list(self, principal, trip_id: UUID, local_date: date | None = None,
             category: str | None = None) -> dict:
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id)
            rows = _query_rows(session, trip.trip_id, local_date, category)
            all_rows = _query_rows(session, trip.trip_id)
            return {"items": [expense_public(row) for row in rows],
                    "summary": _summary(all_rows, _money(trip.indicative_budget))}

    def summary(self, principal, trip_id: UUID) -> dict:
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id)
            return _summary(_query_rows(session, trip.trip_id), _money(trip.indicative_budget))

    def create(self, principal, trip_id: UUID, data: dict, key: str) -> dict:
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id, lock=True)
            if trip.lifecycle_state != "available":
                raise IdentityError("TRIP_READ_ONLY", "Chuyến đi lưu trữ chỉ có thể xem.", 409)
            clean = normalize_expense(data, trip)
            validate_links(session, trip.trip_id, clean["day_id"], clean["activity_id"])
            fingerprint = request_fingerprint(clean)
            found, key_hash = receipt(session, principal.account_id, "create_expense", str(trip_id), key, fingerprint)
            if found:
                row = session.get(ExpenseEntryModel, UUID(found.result_resource_id))
                if not row:
                    raise IdentityError("IDEMPOTENCY_CONFLICT", "Khoản chi của lần thử trước không còn tồn tại.", 409)
                return {"expense": expense_public(row),
                        "summary": _summary(_query_rows(session, trip.trip_id), _money(trip.indicative_budget))}
            row = ExpenseEntryModel(
                trip_id=trip.trip_id, created_by=principal.account_id, currency="VND", **clean
            )
            session.add(row)
            session.flush()
            session.add(ExpenseAuditEventModel(
                trip_id=trip.trip_id, expense_id=row.expense_id,
                actor_id=principal.account_id, event_type="created",
                before_payload=None, after_payload=_snapshot(row),
                correlation_id=principal.correlation_id,
            ))
            save_receipt(session, principal.account_id, "create_expense", str(trip_id),
                         key_hash, fingerprint, row.expense_id, 201)
            return {"expense": expense_public(row),
                    "summary": _summary(_query_rows(session, trip.trip_id), _money(trip.indicative_budget))}

    def update(self, principal, expense_id: UUID, data: dict, expected_version: int) -> dict:
        with session_scope(get_settings().database_url) as session:
            row, trip = owned_expense(session, principal.account_id, expense_id, lock=True)
            if trip.lifecycle_state != "available":
                raise IdentityError("TRIP_READ_ONLY", "Chuyến đi lưu trữ chỉ có thể xem.", 409)
            if row.version != expected_version:
                raise IdentityError("VERSION_CONFLICT", "Khoản chi đã thay đổi trên thiết bị khác.", 409)
            before = _snapshot(row)
            merged = {
                "label": data.get("label", row.label),
                "amount_vnd": data.get("amount_vnd", _money(row.amount)),
                "category": data.get("category", row.category),
                "spent_at": data.get("spent_at", row.spent_at),
                "notes": data.get("notes", row.notes),
                "day_id": data.get("day_id", row.day_id),
                "activity_id": data.get("activity_id", row.activity_id),
            }
            clean = normalize_expense(merged, trip)
            validate_links(session, trip.trip_id, clean["day_id"], clean["activity_id"])
            for name, value in clean.items():
                setattr(row, name, value)
            row.version += 1
            row.updated_at = _now()
            session.flush()
            session.add(ExpenseAuditEventModel(
                trip_id=trip.trip_id, expense_id=row.expense_id,
                actor_id=principal.account_id, event_type="updated",
                before_payload=before, after_payload=_snapshot(row),
                correlation_id=principal.correlation_id,
            ))
            return {"expense": expense_public(row),
                    "summary": _summary(_query_rows(session, trip.trip_id), _money(trip.indicative_budget))}

    def delete(self, principal, expense_id: UUID, expected_version: int) -> dict:
        with session_scope(get_settings().database_url) as session:
            row, trip = owned_expense(session, principal.account_id, expense_id, lock=True)
            if trip.lifecycle_state != "available":
                raise IdentityError("TRIP_READ_ONLY", "Chuyến đi lưu trữ chỉ có thể xem.", 409)
            if row.version != expected_version:
                raise IdentityError("VERSION_CONFLICT", "Khoản chi đã thay đổi trên thiết bị khác.", 409)
            before = _snapshot(row)
            event = ExpenseAuditEventModel(
                trip_id=trip.trip_id, expense_id=row.expense_id,
                actor_id=principal.account_id, event_type="deleted",
                before_payload=before, after_payload=None,
                correlation_id=principal.correlation_id,
            )
            session.delete(row)
            session.flush()
            session.add(event)
            return _summary(_query_rows(session, trip.trip_id), _money(trip.indicative_budget))

    def budget(self, principal, trip_id: UUID) -> dict:
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id)
            revisions = list(session.scalars(select(BudgetRevisionModel).where(
                BudgetRevisionModel.trip_id == trip.trip_id
            ).order_by(BudgetRevisionModel.changed_at.desc())))
            return {
                "trip_id": str(trip.trip_id), "budget_vnd": _money(trip.indicative_budget),
                "currency": trip.currency, "trip_version": trip.version,
                "revisions": [{
                    "id": str(row.revision_id),
                    "previous_amount_vnd": _money(row.previous_amount) if row.previous_amount is not None else None,
                    "new_amount_vnd": _money(row.new_amount), "reason": row.reason,
                    "changed_at": row.changed_at.isoformat(),
                } for row in revisions],
            }

    def revise_budget(self, principal, trip_id: UUID, amount: int, reason: str,
                      expected_trip_version: int) -> dict:
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id, lock=True)
            if trip.lifecycle_state != "available":
                raise IdentityError("TRIP_READ_ONLY", "Chuyến đi lưu trữ chỉ có thể xem.", 409)
            if trip.version != expected_trip_version:
                raise IdentityError("VERSION_CONFLICT", "Chuyến đi đã thay đổi trên thiết bị khác.", 409)
            if amount < 0:
                raise IdentityError("VALIDATION_ERROR", "Ngân sách không được âm.", 422)
            previous = trip.indicative_budget
            trip.indicative_budget = Decimal(amount)
            trip.currency = "VND"
            trip.version += 1
            trip.updated_at = _now()
            session.add(BudgetRevisionModel(
                trip_id=trip.trip_id, previous_amount=previous,
                new_amount=Decimal(amount), currency="VND",
                reason=reason.strip()[:500], changed_by=principal.account_id,
            ))
            session.flush()
            return {
                "budget": {"trip_id": str(trip.trip_id), "budget_vnd": amount,
                           "currency": "VND", "trip_version": trip.version},
                "summary": _summary(_query_rows(session, trip.trip_id), amount),
            }

    def export(self, principal, trip_id: UUID, local_date: date | None = None,
               category: str | None = None) -> dict:
        with session_scope(get_settings().database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id)
            rows = _query_rows(session, trip.trip_id, local_date, category)
            return {
                "schema_version": 1, "generated_at": _now().isoformat(),
                "trip_id": str(trip.trip_id),
                "filters": {"date": local_date.isoformat() if local_date else None,
                            "category": category},
                "items": [expense_public(row) for row in rows],
                "summary": _summary(rows, _money(trip.indicative_budget)),
            }


def remaining_budget(principal, trip_id: UUID) -> dict:
    """Neutral projection for later deterministic planning/replan adapters."""
    summary = ExpenseService().summary(principal, trip_id)
    return {"trip_id": str(trip_id), "currency": "VND",
            "budget_vnd": summary["budget_vnd"], "spent_vnd": summary["spent_vnd"],
            "remaining_vnd": summary["remaining_vnd"], "by_category": summary["by_category"]}
