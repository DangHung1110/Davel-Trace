"""Authenticated HTTP API for optional AI assistance."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from BE.app.modules.ai_assistance.service import AiAssistanceService
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.routers import error
from BE.app.services.llm import LLMError

router = APIRouter(tags=["ai-assistance"])

ERROR_CODES = {
    "disabled": "LLM_DISABLED",
    "config": "LLM_CONFIG",
    "auth": "LLM_AUTH",
    "quota": "LLM_QUOTA",
    "safety": "LLM_SAFETY",
    "timeout": "LLM_TIMEOUT",
    "transport": "LLM_TRANSPORT",
    "bad_json": "LLM_BAD_JSON",
    "schema": "LLM_SCHEMA",
}


class InterpretationBody(BaseModel):
    text: str = Field(min_length=3, max_length=4000)


def _provider_error(exc: LLMError):
    code = ERROR_CODES.get(exc.reason, "LLM_TRANSPORT")
    messages = {
        "quota": "Trợ lý AI đã chạm giới hạn lượt hoặc token của nhà cung cấp. Chờ hạn mức hồi phục rồi thử lại; bạn vẫn có thể tạo lịch không dùng AI.",
        "auth": "Nhà cung cấp từ chối API key của trợ lý AI. Cần kiểm tra lại cấu hình backend.",
        "config": "Model hoặc cấu hình trợ lý AI chưa hợp lệ. Cần kiểm tra lại cấu hình backend.",
        "schema": "Trợ lý AI trả về thông tin chưa đúng định dạng. Hãy rút gọn yêu cầu rồi thử lại, hoặc tạo lịch không dùng AI.",
        "bad_json": "Trợ lý AI trả về thông tin chưa đúng định dạng. Hãy thử lại, hoặc tạo lịch không dùng AI.",
        "timeout": "Trợ lý AI phản hồi quá lâu. Hãy thử lại, hoặc tạo lịch không dùng AI.",
    }
    return error(
        code,
        messages.get(exc.reason, "Không thể dùng trợ lý AI lúc này; bạn vẫn có thể nhập yêu cầu có cấu trúc."),
        503,
    )


@router.get("/v1/ai/readiness")
def readiness():
    return AiAssistanceService().readiness()


@router.post("/v1/trips/{trip_id}/ai/interpretations")
def interpret(
    trip_id: UUID,
    body: InterpretationBody,
    current: Principal = Depends(current_principal),
):
    try:
        return AiAssistanceService().interpret_owned(current, trip_id, body.text)
    except LLMError as exc:
        return _provider_error(exc)
    except ValueError as exc:
        raise IdentityError("VALIDATION_ERROR", str(exc), 422) from exc


@router.post("/v1/itinerary-alternatives/{alternative_id}/ai/explanation")
def explain(
    alternative_id: UUID,
    current: Principal = Depends(current_principal),
):
    return AiAssistanceService().explain_owned(current, alternative_id)


@router.post("/v1/planning-requests/{request_id}/ai/shadow")
def shadow(
    request_id: UUID,
    current: Principal = Depends(current_principal),
):
    return AiAssistanceService().shadow_owned(current, request_id)
