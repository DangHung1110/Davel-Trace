"""Accepted-plan audit, shadow comparison, and readiness endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from BE.app.config import get_settings
from BE.app.routers import error
from BE.app.routers import select as select_router
from BE.app.services import llm
from BE.app.services.acceptance_store import AcceptanceStore
from BE.app.services.planning_readiness import build_readiness
from BE.app.services.shadow_rank import evaluate

router = APIRouter(prefix="/v1", tags=["planning-evidence"])


def _store() -> AcceptanceStore:
    return AcceptanceStore(get_settings().acceptance_db_path)


class ShadowIn(BaseModel):
    trip_id: str
    itinerary_ids: list[str] = Field(min_length=2, max_length=5)


def _judge(candidates: list[dict]) -> dict:
    prompt = (
        "Bạn chỉ xếp hạng các phương án lịch trình đã qua cổng cứng. "
        "Không sửa lịch, không thêm địa điểm, không đánh giá thương hiệu. "
        "Trả JSON duy nhất {\"winner\":\"A\",\"reason\":\"...\"}.\n"
        + json.dumps(candidates, ensure_ascii=False)
        + "\n/no_think"
    )
    return llm.complete_json(prompt, timeout_s=20)


@router.get("/acceptances")
def list_acceptances(trip_id: str | None = None,
                     limit: int = Query(default=50, ge=1, le=200)):
    items = _store().list_acceptances(trip_id, limit)
    return {"items": items, "count": len(items)}


@router.get("/acceptances/{acceptance_id}")
def get_acceptance(acceptance_id: str):
    item = _store().get_acceptance(acceptance_id)
    if item is None:
        return error("UNKNOWN_ACCEPTANCE",
                     f"khong co acceptance {acceptance_id}", 404)
    return item


@router.post("/shadow/evaluate")
def shadow_evaluate(body: ShadowIn):
    plans = []
    for itinerary_id in body.itinerary_ids:
        plan = select_router.get_store()["plans"].get(itinerary_id)
        if plan is None:
            return error("UNKNOWN_ITINERARY",
                         f"khong co plan {itinerary_id}", 404)
        report = select_router.evaluate_plan(plan) or plan.get("gate")
        if report is not None and not report.get("passed", False):
            return error("GATE_FAILED",
                         f"plan {itinerary_id} khong qua cong", 422)
        plans.append({key: value for key, value in plan.items()
                      if not key.startswith("_")})
    settings = get_settings()
    observation = evaluate(
        plans, body.trip_id, settings.snapshot_name, _judge
    )
    stored = _store().save_shadow(observation)
    return {**stored, "authoritative": False}


@router.get("/planning/readiness")
def planning_readiness():
    settings = get_settings()
    return build_readiness(
        _store(), canary_rate=settings.shadow_judge_rate
    )
