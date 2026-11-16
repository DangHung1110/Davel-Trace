"""Browser-facing OAuth routes. Callback HTML contains only a one-time handoff."""

import json
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from BE.app.core.config import get_settings
from BE.app.core.request_context import get_correlation_id
from BE.app.modules.identity.google_oauth import GoogleFlow, cookie_name, exchange_google_code
from BE.app.modules.identity.service import IdentityError

router = APIRouter(tags=["identity"])
CALLBACK_PATH = "/v1/auth/google/callback"


class GoogleExchangeBody(BaseModel):
    handoff: str = Field(min_length=32, max_length=256)


def popup_result(origin: str | None, payload: dict, status: int = 200) -> HTMLResponse:
    # JSON literals in inline script must not permit a closing script element.
    encoded = json.dumps({"type": "davel.google", **payload}, ensure_ascii=True).replace("<", "\\u003c")
    target = json.dumps(origin).replace("<", "\\u003c")
    nonce = secrets.token_urlsafe(18)
    response = HTMLResponse(
        '<!doctype html><html lang="vi"><meta charset="utf-8"><title>Davel Trace</title>'
        '<p>Quay lại cửa sổ Davel Trace để xem kết quả đăng nhập.</p>'
        f'<script nonce="{nonce}">if(window.opener && {target}) {{'
        f'window.opener.postMessage({encoded}, {target}); window.close();'
        '}</script></html>', status_code=status,
    )
    response.headers.update({
        "Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; frame-ancestors 'none'; base-uri 'none'",
        "X-Content-Type-Options": "nosniff",
    })
    return response


@router.get("/v1/auth/google/start")
def start(request: Request, origin: str, terms_accepted: bool = False):
    settings = get_settings()
    url, state, browser = GoogleFlow(settings).start(
        origin, terms_accepted, request.client.host if request.client else "unknown",
    )
    response = RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    response.set_cookie(cookie_name(state), browser, max_age=600, httponly=True,
                        secure=urlsplit(settings.google_redirect_uri).scheme == "https",
                        samesite="lax", path=CALLBACK_PATH)
    return response


@router.get(CALLBACK_PATH)
def callback(request: Request, state: str = "", code: str = "", error: str = ""):
    settings = get_settings()
    origin = None
    try:
        flow = GoogleFlow(settings)
        browser = request.cookies.get(cookie_name(state), "")
        origin, nonce_hash, attempt_id = flow.consume_callback(state, browser)
        if error:
            raise IdentityError("GOOGLE_CANCELLED", "Bạn đã hủy đăng nhập Google.", 400)
        if not code or len(code) > 4096:
            raise IdentityError("GOOGLE_LOGIN_INVALID", "Google không trả về mã đăng nhập hợp lệ.", 400)
        claims = exchange_google_code(settings, code, browser)
        handoff = flow.finish(attempt_id, claims, nonce_hash, get_correlation_id())
        response = popup_result(origin, {"handoff": handoff})
    except IdentityError as exc:
        response = popup_result(origin, {"error": exc.code, "message": exc.message}, exc.status)
    response.delete_cookie(cookie_name(state), path=CALLBACK_PATH)
    return response


@router.post("/v1/auth/google/exchange")
def exchange(body: GoogleExchangeBody, origin: str = Header(default="")):
    payload = GoogleFlow(get_settings()).exchange(body.handoff, origin, get_correlation_id())
    from fastapi.responses import JSONResponse
    return JSONResponse(payload, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
