"""Google authorization-code flow. Google tokens never become Davel tokens."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from BE.app.core.config import Settings
from BE.app.db.models import AccountModel, RoleAssignmentModel
from BE.app.db.session import session_scope
from BE.app.modules.identity.infrastructure import IdentityRepository
from BE.app.modules.identity.provider_models import GoogleIdentityModel, GoogleLoginAttemptModel
from BE.app.modules.identity.security import hash_password, new_secret, normalize_email, secret_hash
from BE.app.modules.identity.service import IdentityError, IdentityService, _rate_limiter, now_utc

logger = logging.getLogger(__name__)
CLOCK_SKEW_SECONDS = 30


def invalid_login() -> IdentityError:
    return IdentityError("GOOGLE_LOGIN_INVALID", "Phiên đăng nhập Google không hợp lệ hoặc đã hết hạn. Hãy thử lại.", 400)


def cookie_name(state: str) -> str:
    return "davel_google_" + secret_hash(state)[:16]


def exchange_google_code(settings: Settings, code: str, verifier: str) -> dict:
    """Exchange only with Google's fixed TLS endpoint; do not log raw responses."""
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "code": code, "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code", "code_verifier": verifier,
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.google_timeout_seconds) as response:
            token = json.load(response).get("id_token")
        if not isinstance(token, str) or not token:
            raise ValueError("missing ID token")
    except urllib.error.HTTPError as exc:
        try:
            reason = json.loads(exc.read(2048)).get("error")
        except (ValueError, AttributeError):
            reason = None
        if reason not in {"invalid_client", "invalid_grant", "invalid_request", "unauthorized_client", "access_denied"}:
            reason = "provider_rejected"
        logger.warning("google_token_exchange_failed http_status=%s reason=%s", exc.code, reason)
        raise IdentityError("GOOGLE_PROVIDER_ERROR", "Google chưa đổi được mã đăng nhập. Hãy thử lại.", 502) from None
    except Exception as exc:
        logger.warning("google_token_exchange_failed failure_type=%s", type(exc).__name__)
        raise IdentityError("GOOGLE_PROVIDER_ERROR", "Chưa kết nối được Google để đổi mã đăng nhập.", 502) from None
    try:
        transport = GoogleRequest()

        def bounded_request(url, method="GET", body=None, headers=None, **kwargs):
            kwargs["timeout"] = settings.google_timeout_seconds
            return transport(url, method=method, body=body, headers=headers, **kwargs)

        # Maintained Google verifier checks signature, expiry, audience and issuer.
        return id_token.verify_oauth2_token(
            token, bounded_request, settings.google_client_id,
            clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
        )
    except Exception as exc:
        # Log only a classification, never provider responses or JWT contents.
        message = str(exc).lower()
        reason = next((word for word in ("audience", "expired", "early", "signature", "issuer", "certificate", "timeout")
                       if word in message), "verification_failed")
        logger.warning("google_id_token_rejected failure_type=%s reason=%s", type(exc).__name__, reason)
        raise IdentityError("GOOGLE_PROVIDER_ERROR", "Google chưa hoàn tất xác thực. Hãy thử đăng nhập lại.", 502) from None


class GoogleFlow:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.identity = IdentityService(settings)

    def start(self, origin: str, terms_accepted: bool, client: str) -> tuple[str, str, str]:
        if not self.settings.google_configured:
            raise IdentityError("GOOGLE_NOT_CONFIGURED", "Đăng nhập Google chưa được cấu hình.", 503)
        if origin not in self.settings.cors_origins or len(origin) > 255:
            raise IdentityError("ORIGIN_NOT_ALLOWED", "Địa chỉ ứng dụng chưa được cho phép.", 400)
        parsed = urllib.parse.urlsplit(origin)
        if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise IdentityError("ORIGIN_NOT_ALLOWED", "Địa chỉ ứng dụng không hợp lệ.", 400)
        if self.settings.app_mode.value == "production" and parsed.scheme != "https":
            raise IdentityError("ORIGIN_NOT_ALLOWED", "Ứng dụng phải dùng HTTPS.", 400)
        if not terms_accepted:
            raise IdentityError("TERMS_REQUIRED", "Bạn cần đồng ý điều khoản để tiếp tục bằng Google.", 422)
        _rate_limiter.require("google_start", client, 10, 15)
        state, browser, nonce = new_secret(), new_secret(), new_secret()
        now = now_utc()
        with session_scope(self.settings.database_url) as session:
            session.execute(delete(GoogleLoginAttemptModel).where(
                GoogleLoginAttemptModel.expires_at < now - timedelta(days=1)
            ))
            session.add(GoogleLoginAttemptModel(
                state_hash=secret_hash(state), browser_hash=secret_hash(browser),
                nonce_hash=secret_hash(nonce), application_origin=origin,
                expires_at=now + timedelta(minutes=10),
            ))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(browser.encode()).digest()).rstrip(b"=").decode()
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "response_type": "code", "scope": "openid email profile",
            "state": state, "nonce": nonce, "code_challenge": challenge,
            "code_challenge_method": "S256", "prompt": "select_account",
        })
        return url, state, browser

    def consume_callback(self, state: str, browser: str) -> tuple[str, str, object]:
        with session_scope(self.settings.database_url) as session:
            attempt = session.scalar(select(GoogleLoginAttemptModel).where(
                GoogleLoginAttemptModel.state_hash == secret_hash(state)
            ).with_for_update())
            if (not state or not browser or not attempt or attempt.callback_used_at
                    or attempt.expires_at <= now_utc()
                    or not secrets.compare_digest(attempt.browser_hash, secret_hash(browser))):
                raise invalid_login()
            attempt.callback_used_at = now_utc()
            return attempt.application_origin, attempt.nonce_hash, attempt.attempt_id

    def finish(self, attempt_id, claims: dict, nonce_hash: str, correlation_id: str) -> str:
        if (claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}
                or claims.get("aud") != self.settings.google_client_id
                or claims.get("email_verified") is not True
                or not isinstance(claims.get("sub"), str)
                or not 1 <= len(claims["sub"]) <= 255
                or not isinstance(claims.get("nonce"), str)
                or not secrets.compare_digest(secret_hash(claims["nonce"]), nonce_hash)):
            raise invalid_login()
        try:
            email = normalize_email(claims.get("email", ""))
        except (ValueError, AttributeError, TypeError):
            raise invalid_login() from None
        try:
            with session_scope(self.settings.database_url) as session:
                attempt = session.get(GoogleLoginAttemptModel, attempt_id, with_for_update=True)
                if (not attempt or not attempt.callback_used_at or attempt.handoff_hash
                        or attempt.expires_at <= now_utc()):
                    raise invalid_login()
                linked = session.get(GoogleIdentityModel, claims["sub"])
                account = session.get(AccountModel, linked.account_id, with_for_update=True) if linked else None
                if linked and (not account or account.status != "active"):
                    raise IdentityError("ACCOUNT_NOT_ELIGIBLE", "Tài khoản chưa sẵn sàng đăng nhập.", 403)
                if not linked:
                    if IdentityRepository(session).account_by_email(email):
                        raise IdentityError("ACCOUNT_LINK_REQUIRED", "Email đã có tài khoản Davel. Hãy đăng nhập bằng mật khẩu; tài khoản không được tự động liên kết.", 409)
                    account = AccountModel(
                        email_normalized=email, password_hash=hash_password("Google-1" + new_secret()),
                        status="active", verified_at=now_utc(), consented_at=now_utc(),
                    )
                    session.add(account)
                    session.flush()
                    session.add(RoleAssignmentModel(account_id=account.account_id, role="traveler"))
                    session.add(GoogleIdentityModel(subject=claims["sub"], account_id=account.account_id))
                    self.identity._lifecycle(session, account, "google_registered", correlation_id)
                handoff = new_secret()
                attempt.account_id = account.account_id
                attempt.handoff_hash = secret_hash(handoff)
                attempt.handoff_expires_at = now_utc() + timedelta(seconds=60)
                return handoff
        except IntegrityError:
            raise IdentityError("ACCOUNT_LINK_REQUIRED", "Tài khoản đã thay đổi. Hãy đăng nhập lại bằng phương thức hiện có.", 409) from None

    def exchange(self, handoff: str, origin: str, correlation_id: str) -> dict:
        with session_scope(self.settings.database_url) as session:
            attempt = session.scalar(select(GoogleLoginAttemptModel).where(
                GoogleLoginAttemptModel.handoff_hash == secret_hash(handoff)
            ).with_for_update())
            if (not attempt or attempt.exchanged_at or not attempt.handoff_expires_at
                    or attempt.handoff_expires_at <= now_utc()
                    or origin != attempt.application_origin or not attempt.account_id):
                raise invalid_login()
            account = session.get(AccountModel, attempt.account_id, with_for_update=True)
            if not account or account.status != "active":
                raise IdentityError("ACCOUNT_NOT_ELIGIBLE", "Tài khoản chưa sẵn sàng đăng nhập.", 403)
            attempt.exchanged_at = now_utc()
            record, access, refresh = self.identity._new_session(session, account, "Google / Davel Web", "web")
            self.identity._audit(session, "google_login", "success", correlation_id,
                                 account.account_id, record.session_id)
            return self.identity._session_payload(
                account, IdentityRepository(session).roles(account.account_id), record, access, refresh,
            )
