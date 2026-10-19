"""Expense routers (T035, lane C). POST /v1/expenses + GET summary.

Invalid kind/amount -> 400 envelope (not 422): client-correctable input
errors stay in the {error, message} shape per contracts/api.md.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.routers import error
from BE.app.services import expenses as expenses_svc

router = APIRouter(prefix="/v1", tags=["expenses"])


class ExpenseIn(BaseModel):
    trip_id: str
    label: str
    amount: int
    kind: str = "other"
    at: str = ""


@router.post("/expenses", status_code=201)
def log_expense(body: ExpenseIn):
    try:
        entry = expenses_svc.add(body.trip_id, body.label, body.amount,
                                 body.kind, body.at)
    except ValueError as e:
        return error("BAD_EXPENSE", str(e), 400)
    return entry


@router.get("/expenses/summary")
def expense_summary(trip_id: str):
    return expenses_svc.summary(trip_id)
