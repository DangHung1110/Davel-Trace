"""Identity HTTP contract under /v1/auth and /v1/account."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from BE.app.core.config import AppMode, get_settings
from BE.app.core.request_context import get_correlation_id
from BE.app.modules.identity.service import IdentityError, IdentityService, now_utc
from BE.app.modules.identity.delivery import development_outbox
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.security import normalize_email


router = APIRouter(tags=["identity"])


class RegisterBody(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)
    terms_accepted: bool


class EmailBody(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class TokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class LoginBody(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    device_label: str = Field(default="Trình duyệt", max_length=120)
    client_kind: str = Field(default="web", max_length=32)


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=256)


class ResetBody(TokenBody):
    new_password: str = Field(min_length=10, max_length=128)


class DeleteBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    confirmation: str = Field(min_length=1, max_length=64)


class ExportBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    confirmation: str = Field(min_length=1, max_length=64)


def service() -> IdentityService:
    return IdentityService(get_settings())


def principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise IdentityError("AUTHENTICATION_REQUIRED", "Bạn cần đăng nhập.", 401)
    return service().principal(authorization.split(" ", 1)[1].strip(), get_correlation_id())


def identity_error_response(exc: IdentityError) -> JSONResponse:
    return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)


@router.post("/v1/auth/register", status_code=202)
def register(body: RegisterBody):
    return service().register(body.email, body.password, body.terms_accepted, get_correlation_id())


@router.post("/v1/auth/verification/resend", status_code=202)
def resend(body: EmailBody):
    return service().resend_verification(body.email, get_correlation_id())


@router.post("/v1/auth/verification/confirm")
def verify(body: TokenBody):
    return service().confirm_verification(body.token, get_correlation_id())


@router.post("/v1/auth/login")
def login(body: LoginBody, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if idempotency_key is not None and not (8 <= len(idempotency_key) <= 128):
        raise IdentityError("VALIDATION_ERROR", "Idempotency-Key phải dài 8-128 ký tự.", 422)
    return service().login(body.email, body.password, body.device_label,
                           body.client_kind, get_correlation_id(), idempotency_key)


@router.post("/v1/auth/refresh")
def refresh(body: RefreshBody):
    return service().refresh(body.refresh_token, get_correlation_id())


@router.post("/v1/auth/recovery/request", status_code=202)
def recovery_request(body: EmailBody):
    return service().request_recovery(body.email, get_correlation_id())


@router.post("/v1/auth/recovery/confirm", status_code=204)
def recovery_confirm(body: ResetBody):
    service().confirm_recovery(body.token, body.new_password, get_correlation_id())


@router.post("/v1/auth/deletion-cancel/request", status_code=202)
def deletion_cancel_request(body: EmailBody):
    return service().request_recovery(
        body.email, get_correlation_id(), purpose="cancel_deletion"
    )


@router.post("/v1/auth/deletion-cancel/confirm")
def deletion_cancel_confirm(body: TokenBody):
    return service().cancel_deletion(body.token, get_correlation_id())


@router.get("/v1/account/me")
def me(current: Principal = Depends(principal)):
    return service().me(current)


@router.get("/v1/account/sessions")
def sessions(current: Principal = Depends(principal)):
    items = service().sessions(current)
    return {"items": items, "count": len(items)}


@router.delete("/v1/account/sessions/{session_id}", status_code=204)
def revoke_session(session_id: UUID, current: Principal = Depends(principal)):
    service().revoke(current, session_id)


@router.post("/v1/account/sessions/revoke-others", status_code=204)
def revoke_others(current: Principal = Depends(principal)):
    service().revoke(current, others=True)


@router.post("/v1/account/logout", status_code=204)
def logout(current: Principal = Depends(principal)):
    service().revoke(current)


@router.post("/v1/account/logout-all", status_code=204)
def logout_all(current: Principal = Depends(principal)):
    service().revoke(current, all_sessions=True)


@router.post("/v1/account/exports", status_code=201)
def create_export(body: ExportBody, current: Principal = Depends(principal)):
    if body.confirmation != "XUẤT DỮ LIỆU":
        raise IdentityError("VALIDATION_ERROR", "Cụm từ xác nhận chưa đúng.", 422)
    service().confirm_current_password(current, body.current_password)
    return service().create_export(current)


@router.get("/v1/account/exports/{export_id}")
def get_export(export_id: UUID, current: Principal = Depends(principal)):
    return service().export(current, export_id)


@router.get("/v1/account/exports/{export_id}/download")
def download_export(export_id: UUID, current: Principal = Depends(principal)):
    record = service().export(current, export_id)
    if record["status"] != "ready":
        raise IdentityError("CONFLICT", "Bản xuất dữ liệu chưa sẵn sàng.", 409)
    return JSONResponse(
        record["payload"],
        headers={"Content-Disposition": f'attachment; filename="davel-trace-{export_id}.json"'},
    )


@router.post("/v1/account/deletion", status_code=204)
def delete_account(body: DeleteBody, current: Principal = Depends(principal)):
    service().request_deletion(current, body.current_password, body.confirmation)


@router.get("/v1/dev/identity/outbox")
def dev_outbox(email: str = Query(...), purpose: str = Query(...)):
    settings = get_settings()
    if settings.app_mode not in {AppMode.demo, AppMode.test} or not settings.identity_dev_outbox_enabled:
        raise IdentityError("NOT_FOUND", "Không tìm thấy.", 404)
    item = development_outbox.latest(normalize_email(email), purpose, now_utc())
    if not item:
        raise IdentityError("NOT_FOUND", "Chưa có mã phát triển còn hiệu lực.", 404)
    return {
        "development_only": True,
        "purpose": item.purpose,
        "token": item.token,
        "expires_at": item.expires_at.isoformat(),
    }
