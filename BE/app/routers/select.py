"""POST /v1/itinerary/select (T033e, lane C — closes US4). Chốt plan.

In: {"itinerary_id"}. Out: {"active_id"}. Plan được chọn thành lịch
chính, các plans khác giữ lại để so sánh (STUB-NOTE: in-memory store;
state store runtime + version là lane B T045, wire ở phase-PR).
Unknown id -> 404 envelope (không crash).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.routers import error

router = APIRouter(prefix="/v1", tags=["itinerary"])

_STORE: dict = {"plans": {}, "active_id": None}


class SelectIn(BaseModel):
    itinerary_id: str


def register(plans: list[dict]) -> None:
    for p in plans:
        _STORE["plans"][p["itinerary_id"]] = p


def get_store() -> dict:
    return _STORE


def reset_store() -> None:
    _STORE["plans"] = {}
    _STORE["active_id"] = None


@router.post("/itinerary/select")
def select(body: SelectIn):
    if body.itinerary_id not in _STORE["plans"]:
        return error("UNKNOWN_ITINERARY",
                     f"khong co plan {body.itinerary_id}", 404)
    _STORE["active_id"] = body.itinerary_id
    return {"active_id": body.itinerary_id}
