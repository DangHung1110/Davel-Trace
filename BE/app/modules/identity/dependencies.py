"""Public authentication dependency for product capability modules."""

from fastapi import Header

from BE.app.core.config import get_settings
from BE.app.core.request_context import get_correlation_id
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError, IdentityService


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise IdentityError("AUTHENTICATION_REQUIRED", "Bạn cần đăng nhập.", 401)
    token = authorization.split(" ", 1)[1].strip()
    return IdentityService(get_settings()).principal(token, get_correlation_id())
