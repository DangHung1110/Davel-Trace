from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from BE.app.schemas.common import OrmModel

ExpenseCategory = Literal["food", "ticket", "transport", "other"]


class ExpenseCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    amount_vnd: int = Field(ge=0)
    category: ExpenseCategory = "other"
    spent_at: datetime | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ExpenseUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    amount_vnd: int | None = Field(default=None, ge=0)
    category: ExpenseCategory | None = None
    spent_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)
    version: int = Field(ge=1)


class ExpenseRead(OrmModel):
    id: str
    trip_id: str
    label: str
    amount_vnd: int
    category: str
    spent_at: datetime
    notes: str
    version: int
    created_at: datetime
    updated_at: datetime


class ExpenseSummary(BaseModel):
    budget_vnd: int
    spent_vnd: int
    remaining_vnd: int
    by_category: dict[str, int]
    alert: Literal["none", "80", "100"]


class ExpenseMutation(BaseModel):
    expense: ExpenseRead
    summary: ExpenseSummary


class ExpenseList(BaseModel):
    items: list[ExpenseRead]
    summary: ExpenseSummary
