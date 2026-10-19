from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from BE.app.database import get_db
from BE.app.errors import AppError
from BE.app.routers import error
from BE.app.schemas.expense import (
    ExpenseCreate,
    ExpenseList,
    ExpenseMutation,
    ExpenseSummary,
    ExpenseUpdate,
)
from BE.app.services import expenses as service
from BE.app.services import agent_expenses

router = APIRouter(prefix="/v1", tags=["expenses"])


class AgentExpenseIn(BaseModel):
    trip_id: str
    label: str
    amount: int
    kind: str = "other"
    at: str = ""


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def log_agent_expense(command: AgentExpenseIn):
    try:
        return agent_expenses.add(
            command.trip_id, command.label, command.amount, command.kind, command.at
        )
    except ValueError as exc:
        return error("BAD_EXPENSE", str(exc), 400)


@router.get("/trips/{trip_id}/expenses", response_model=ExpenseList)
def list_expenses(trip_id: str, session: Session = Depends(get_db)):
    items, summary = service.list_with_summary(session, trip_id)
    return {"items": items, "summary": summary}


@router.post(
    "/trips/{trip_id}/expenses",
    response_model=ExpenseMutation,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    trip_id: str, command: ExpenseCreate, session: Session = Depends(get_db)
):
    expense, summary = service.create_expense(session, trip_id, command)
    return {"expense": expense, "summary": summary}


@router.patch("/expenses/{expense_id}", response_model=ExpenseMutation)
def update_expense(
    expense_id: str, command: ExpenseUpdate, session: Session = Depends(get_db)
):
    expense, summary = service.update_expense(session, expense_id, command)
    return {"expense": expense, "summary": summary}


@router.delete("/expenses/{expense_id}", response_model=ExpenseSummary)
def delete_expense(
    expense_id: str,
    version: int = Query(ge=1),
    session: Session = Depends(get_db),
):
    return service.delete_expense(session, expense_id, version)


@router.get("/expenses/summary")
def expense_summary(trip_id: str, session: Session = Depends(get_db)):
    try:
        _, summary = service.list_with_summary(session, trip_id)
        return summary
    except (AppError, SQLAlchemyError):
        session.rollback()
        return agent_expenses.summary(trip_id)
