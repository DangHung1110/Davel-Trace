"""Authenticated budget and expense HTTP routes."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from BE.app.modules.expenses.service import ExpenseService
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError

router = APIRouter(tags=["expenses"])
Category = Literal["food", "ticket", "transport", "accommodation", "shopping", "other"]


def require_key(value: str | None) -> str:
    if not value or not 8 <= len(value) <= 128:
        raise IdentityError("VALIDATION_ERROR", "Idempotency-Key phải dài 8-128 ký tự.", 422)
    return value


class ExpenseCreateBody(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    amount_vnd: int = Field(gt=0)
    category: Category
    spent_at: datetime
    notes: str = Field(default="", max_length=2000)
    day_id: UUID | None = None
    activity_id: UUID | None = None


class ExpenseUpdateBody(BaseModel):
    expected_version: int = Field(ge=1, alias="version")
    label: str | None = Field(default=None, min_length=1, max_length=200)
    amount_vnd: int | None = Field(default=None, gt=0)
    category: Category | None = None
    spent_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    day_id: UUID | None = None
    activity_id: UUID | None = None


class BudgetBody(BaseModel):
    budget_vnd: int = Field(ge=0)
    expected_trip_version: int = Field(ge=1)
    reason: str = Field(default="", max_length=500)


@router.get("/v1/trips/{trip_id}/expenses")
def list_expenses(trip_id: UUID, date_filter: date | None = Query(default=None, alias="date"),
                  category: Category | None = None,
                  current: Principal = Depends(current_principal)):
    return ExpenseService().list(current, trip_id, date_filter, category)


@router.post("/v1/trips/{trip_id}/expenses", status_code=201)
def create_expense(trip_id: UUID, body: ExpenseCreateBody,
                   idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                   current: Principal = Depends(current_principal)):
    return ExpenseService().create(current, trip_id, body.model_dump(), require_key(idempotency_key))


@router.get("/v1/trips/{trip_id}/expenses/summary")
def expense_summary(trip_id: UUID, current: Principal = Depends(current_principal)):
    return ExpenseService().summary(current, trip_id)


@router.get("/v1/trips/{trip_id}/expenses/export")
def export_expenses(trip_id: UUID, date_filter: date | None = Query(default=None, alias="date"),
                    category: Category | None = None,
                    current: Principal = Depends(current_principal)):
    return ExpenseService().export(current, trip_id, date_filter, category)


@router.patch("/v1/expenses/{expense_id}")
def update_expense(expense_id: UUID, body: ExpenseUpdateBody,
                   current: Principal = Depends(current_principal)):
    data = body.model_dump(exclude={"expected_version"}, exclude_none=True)
    return ExpenseService().update(current, expense_id, data, body.expected_version)


@router.delete("/v1/expenses/{expense_id}")
def delete_expense(expense_id: UUID, version: int = Query(ge=1),
                   current: Principal = Depends(current_principal)):
    return ExpenseService().delete(current, expense_id, version)


@router.get("/v1/trips/{trip_id}/budget")
def get_budget(trip_id: UUID, current: Principal = Depends(current_principal)):
    return ExpenseService().budget(current, trip_id)


@router.put("/v1/trips/{trip_id}/budget")
def revise_budget(trip_id: UUID, body: BudgetBody,
                  current: Principal = Depends(current_principal)):
    return ExpenseService().revise_budget(current, trip_id, body.budget_vnd,
                                          body.reason, body.expected_trip_version)
