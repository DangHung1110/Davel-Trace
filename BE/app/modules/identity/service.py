"""Identity transaction orchestration over the PostgreSQL adapter."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from threading import RLock
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from BE.app.core.config import Settings
from BE.app.db.models import (
    AccountLifecycleEventModel,
    AccountModel,
    ExportRequestModel,
    IdentitySessionModel,
    OneTimeActionModel,
    PasswordHistoryModel,
    RoleAssignmentModel,
    SecurityAuditEventModel,
)
from BE.app.db.session import session_scope
from BE.app.modules.identity.delivery import development_outbox
from BE.app.modules.identity.domain import Principal, account_public, session_public
from BE.app.modules.identity.infrastructure import IdentityRepository
from BE.app.modules.identity.security import (
    hash_password,
    new_secret,
    normalize_email,
    secret_hash,
    validate_password,
    verify_password,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class _RateLimiter:
    """Small-process limiter for the student demo; production can replace the port."""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], list[datetime]] = defaultdict(list)

    def require(self, purpose: str, subject: str, limit: int, minutes: int) -> None:
        cutoff = now_utc() - timedelta(minutes=minutes)
        key = (purpose, secret_hash(subject))
        events = [item for item in self._events[key] if item > cutoff]
        if len(events) >= limit:
            raise IdentityError("RATE_LIMITED", "Bạn thao tác quá nhanh. Hãy thử lại sau.", 429)
        events.append(now_utc())
        self._events[key] = events


_rate_limiter = _RateLimiter()
_login_idempotency: dict[str, tuple[datetime, dict]] = {}
_login_idempotency_lock = RLock()


class IdentityError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class IdentityService:
    def __init__(self, settings: Settings) -> None:
        if not settings.database_url:
            raise IdentityError("DATABASE_UNAVAILABLE", "Cơ sở dữ liệu chưa được cấu hình.", 503)
        self.settings = settings

    def _audit(self, session, category: str, outcome: str, correlation_id: str,
               account_id=None, session_id=None, metadata: dict | None = None) -> None:
        session.add(SecurityAuditEventModel(
            account_id=account_id, session_id=session_id, category=category,
            outcome=outcome, correlation_id=correlation_id,
            metadata_json=metadata or {},
        ))

    def _lifecycle(self, session, account: AccountModel, event: str,
                   correlation_id: str) -> None:
        session.add(AccountLifecycleEventModel(
            account_id=account.account_id,
            subject_ref=secret_hash(str(account.account_id)),
            event_type=event,
            correlation_id=correlation_id,
            metadata_json={},
        ))

    def _issue_action(self, session, account: AccountModel, purpose: str,
                      correlation_id: str) -> str:
        now = now_utc()
        session.execute(update(OneTimeActionModel).where(
            OneTimeActionModel.account_id == account.account_id,
            OneTimeActionModel.purpose == purpose,
            OneTimeActionModel.used_at.is_(None),
            OneTimeActionModel.superseded_at.is_(None),
        ).values(superseded_at=now))
        token = new_secret()
        expiry = now + (
            timedelta(hours=self.settings.identity_verification_ttl_hours)
            if purpose == "verify_email"
            else timedelta(minutes=self.settings.identity_recovery_ttl_minutes)
        )
        delivery = "sent" if self.settings.identity_dev_outbox_enabled else "failed"
        session.add(OneTimeActionModel(
            account_id=account.account_id, purpose=purpose,
            token_hash=secret_hash(token), expires_at=expiry,
            delivery_status=delivery, correlation_id=correlation_id,
        ))
        if self.settings.identity_dev_outbox_enabled:
            development_outbox.deliver(account.email_normalized, purpose, token, expiry)
        return delivery

    def register(self, email: str, password: str, terms_accepted: bool,
                 correlation_id: str) -> dict:
        normalized = normalize_email(email)
        if not terms_accepted:
            raise IdentityError("VALIDATION_ERROR", "Bạn cần đồng ý điều khoản.", 422)
        encoded = hash_password(password)
        try:
            with session_scope(self.settings.database_url) as session:
                if IdentityRepository(session).account_by_email(normalized):
                    raise IdentityError("CONFLICT", "Email đã được sử dụng.", 409)
                account = AccountModel(
                    email_normalized=normalized,
                    password_hash=encoded,
                    consented_at=now_utc(),
                )
                session.add(account)
                session.flush()
                session.add(RoleAssignmentModel(account_id=account.account_id, role="traveler"))
                delivery = self._issue_action(session, account, "verify_email", correlation_id)
                self._lifecycle(session, account, "registered", correlation_id)
                self._audit(session, "registration", "success", correlation_id, account.account_id)
                return {**account_public(account, ["traveler"]), "delivery_status": delivery}
        except IntegrityError as exc:
            raise IdentityError("CONFLICT", "Email đã được sử dụng.", 409) from exc

    def resend_verification(self, email: str, correlation_id: str) -> dict:
        normalized = normalize_email(email)
        _rate_limiter.require("verification_resend", normalized, 3, 15)
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            account = repo.account_by_email(normalized, lock=True)
            if account and account.status == "unverified":
                self._issue_action(session, account, "verify_email", correlation_id)
            return {"message": "Nếu tài khoản hợp lệ, hướng dẫn đã được gửi."}

    def confirm_verification(self, token: str, correlation_id: str) -> dict:
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            action = repo.usable_action(token, "verify_email", now_utc())
            if not action:
                raise IdentityError("ACTION_INVALID", "Mã xác thực không hợp lệ hoặc đã hết hạn.", 400)
            account = repo.account(action.account_id, lock=True)
            if not account:
                raise IdentityError("ACTION_INVALID", "Mã xác thực không hợp lệ hoặc đã hết hạn.", 400)
            action.used_at = now_utc()
            if account.status == "unverified":
                account.status = "active"
                account.verified_at = now_utc()
                account.updated_at = now_utc()
                account.version += 1
                self._lifecycle(session, account, "verified", correlation_id)
                self._audit(session, "verification", "success", correlation_id, account.account_id)
            return account_public(account, repo.roles(account.account_id))

    def _new_session(self, session, account: AccountModel, device_label: str,
                     client_kind: str, family_id=None) -> tuple[IdentitySessionModel, str, str]:
        access, refresh = new_secret(), new_secret()
        now = now_utc()
        record = IdentitySessionModel(
            account_id=account.account_id,
            family_id=family_id or uuid4(),
            access_hash=secret_hash(access), refresh_hash=secret_hash(refresh),
            access_expires_at=now + timedelta(minutes=self.settings.identity_access_ttl_minutes),
            refresh_expires_at=now + timedelta(days=self.settings.identity_refresh_ttl_days),
            device_label=(device_label.strip() or "Thiết bị không tên")[:120],
            client_kind=client_kind[:32], last_seen_at=now,
        )
        session.add(record)
        session.flush()
        return record, access, refresh

    def _session_payload(self, account, roles, record, access, refresh) -> dict:
        return {
            "account": account_public(account, roles),
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "access_expires_at": record.access_expires_at.isoformat(),
            "refresh_expires_at": record.refresh_expires_at.isoformat(),
        }

    def login(self, email: str, password: str, device_label: str,
              client_kind: str, correlation_id: str,
              idempotency_key: str | None = None) -> dict:
        try:
            normalized = normalize_email(email)
        except ValueError:
            normalized = "invalid@example.invalid"
        cache_key = f"{normalized}:{idempotency_key}" if idempotency_key else None
        if cache_key:
            with _login_idempotency_lock:
                cached = _login_idempotency.get(cache_key)
                if cached and cached[0] > now_utc():
                    return cached[1]
        _rate_limiter.require("login", normalized, 5, 15)
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            account = repo.account_by_email(normalized)
            if not account or not verify_password(password, account.password_hash):
                self._audit(session, "login", "denied", correlation_id)
                raise IdentityError("INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng.", 401)
            if account.status != "active":
                self._audit(session, "login", "ineligible", correlation_id, account.account_id)
                raise IdentityError("ACCOUNT_NOT_ELIGIBLE", "Tài khoản chưa sẵn sàng đăng nhập.", 403)
            record, access, refresh = self._new_session(
                session, account, device_label, client_kind
            )
            roles = repo.roles(account.account_id)
            self._audit(session, "login", "success", correlation_id,
                        account.account_id, record.session_id)
            payload = self._session_payload(account, roles, record, access, refresh)
            if cache_key:
                with _login_idempotency_lock:
                    _login_idempotency[cache_key] = (
                        now_utc() + timedelta(minutes=5), payload,
                    )
            return payload

    def refresh(self, refresh_token: str, correlation_id: str) -> dict:
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            old = repo.session_by_refresh(refresh_token)
            now = now_utc()
            if old and old.rotated_at:
                session.execute(update(IdentitySessionModel).where(
                    IdentitySessionModel.family_id == old.family_id,
                    IdentitySessionModel.revoked_at.is_(None),
                ).values(revoked_at=now, revoke_reason="refresh_replay"))
                raise IdentityError("AUTHENTICATION_REQUIRED", "Phiên đăng nhập không còn hợp lệ.", 401)
            if not old or old.revoked_at or old.refresh_expires_at <= now:
                raise IdentityError("AUTHENTICATION_REQUIRED", "Phiên đăng nhập không còn hợp lệ.", 401)
            account = repo.account(old.account_id)
            if not account or account.status != "active":
                raise IdentityError("AUTHENTICATION_REQUIRED", "Phiên đăng nhập không còn hợp lệ.", 401)
            old.rotated_at = now
            old.revoked_at = now
            old.revoke_reason = "rotated"
            record, access, refresh = self._new_session(
                session, account, old.device_label, old.client_kind, old.family_id
            )
            self._audit(session, "refresh", "success", correlation_id,
                        account.account_id, record.session_id)
            return self._session_payload(account, repo.roles(account.account_id), record, access, refresh)

    def principal(self, access_token: str, correlation_id: str) -> Principal:
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            record = repo.session_by_access(access_token)
            now = now_utc()
            if not record or record.revoked_at or record.access_expires_at <= now:
                raise IdentityError("AUTHENTICATION_REQUIRED", "Bạn cần đăng nhập lại.", 401)
            account = repo.account(record.account_id)
            if not account or account.status != "active":
                raise IdentityError("AUTHENTICATION_REQUIRED", "Bạn cần đăng nhập lại.", 401)
            record.last_seen_at = now
            return Principal(account.account_id, record.session_id,
                             frozenset(repo.roles(account.account_id)), correlation_id)

    def me(self, principal: Principal) -> dict:
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            account = repo.account(principal.account_id)
            count = session.scalar(select(func.count()).select_from(IdentitySessionModel).where(
                IdentitySessionModel.account_id == principal.account_id,
                IdentitySessionModel.revoked_at.is_(None),
                IdentitySessionModel.refresh_expires_at > now_utc(),
            )) or 0
            return account_public(account, repo.roles(account.account_id), count)

    def sessions(self, principal: Principal) -> list[dict]:
        with session_scope(self.settings.database_url) as session:
            rows = list(session.scalars(select(IdentitySessionModel).where(
                IdentitySessionModel.account_id == principal.account_id,
                IdentitySessionModel.revoked_at.is_(None),
                IdentitySessionModel.refresh_expires_at > now_utc(),
            ).order_by(IdentitySessionModel.created_at.desc())))
            return [session_public(row, current=row.session_id == principal.session_id) for row in rows]

    def revoke(self, principal: Principal, session_id: UUID | None = None,
               *, others: bool = False, all_sessions: bool = False) -> None:
        with session_scope(self.settings.database_url) as session:
            statement = update(IdentitySessionModel).where(
                IdentitySessionModel.account_id == principal.account_id,
                IdentitySessionModel.revoked_at.is_(None),
            )
            if session_id:
                statement = statement.where(IdentitySessionModel.session_id == session_id)
            elif others:
                statement = statement.where(IdentitySessionModel.session_id != principal.session_id)
            elif not all_sessions:
                statement = statement.where(IdentitySessionModel.session_id == principal.session_id)
            session.execute(statement.values(revoked_at=now_utc(), revoke_reason="user_logout"))
            self._audit(session, "session_revocation", "success",
                        principal.correlation_id, principal.account_id,
                        principal.session_id)

    def request_recovery(self, email: str, correlation_id: str,
                         purpose: str = "recover_password") -> dict:
        normalized = normalize_email(email)
        _rate_limiter.require(purpose, normalized, 3, 15)
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            account = repo.account_by_email(normalized, lock=True)
            eligible = account and (
                (purpose == "recover_password" and account.status == "active") or
                (purpose == "cancel_deletion" and account.status == "deletion_pending")
            )
            if eligible:
                self._issue_action(session, account, purpose, correlation_id)
                self._audit(session, purpose, "requested", correlation_id, account.account_id)
            return {"message": "Nếu tài khoản hợp lệ, hướng dẫn đã được gửi."}

    def confirm_recovery(self, token: str, new_password: str,
                         correlation_id: str) -> None:
        validate_password(new_password)
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            action = repo.usable_action(token, "recover_password", now_utc())
            if not action:
                raise IdentityError("ACTION_INVALID", "Mã khôi phục không hợp lệ hoặc đã hết hạn.", 400)
            account = repo.account(action.account_id, lock=True)
            if verify_password(new_password, account.password_hash):
                raise IdentityError("VALIDATION_ERROR", "Mật khẩu mới phải khác mật khẩu hiện tại.", 422)
            session.add(PasswordHistoryModel(account_id=account.account_id,
                                             password_hash=account.password_hash))
            account.password_hash = hash_password(new_password)
            account.updated_at = now_utc()
            account.version += 1
            action.used_at = now_utc()
            session.execute(update(OneTimeActionModel).where(
                OneTimeActionModel.account_id == account.account_id,
                OneTimeActionModel.used_at.is_(None),
            ).values(superseded_at=now_utc()))
            session.execute(update(IdentitySessionModel).where(
                IdentitySessionModel.account_id == account.account_id,
                IdentitySessionModel.revoked_at.is_(None),
            ).values(revoked_at=now_utc(), revoke_reason="password_reset"))
            self._lifecycle(session, account, "password_reset", correlation_id)
            self._audit(session, "password_recovery", "success", correlation_id,
                        account.account_id)

    def create_export(self, principal: Principal) -> dict:
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            account = repo.account(principal.account_id)
            payload = {
                "schema_version": 1,
                "account": account_public(account, repo.roles(account.account_id)),
                "exported_at": now_utc().isoformat(),
            }
            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
            export = ExportRequestModel(
                account_id=account.account_id, status="ready", payload=payload,
                checksum=hashlib.sha256(canonical).hexdigest(), ready_at=now_utc(),
                expires_at=now_utc() + timedelta(days=7),
                correlation_id=principal.correlation_id,
            )
            session.add(export)
            session.flush()
            self._audit(session, "account_export", "success",
                        principal.correlation_id, principal.account_id,
                        principal.session_id)
            return self.export(principal, export.export_id, session=session)

    def confirm_current_password(self, principal: Principal, password: str) -> None:
        with session_scope(self.settings.database_url) as session:
            account = IdentityRepository(session).account(principal.account_id)
            if not account or not verify_password(password, account.password_hash):
                self._audit(session, "recent_auth", "denied", principal.correlation_id,
                            principal.account_id, principal.session_id)
                raise IdentityError("INVALID_CREDENTIALS", "Mật khẩu không đúng.", 401)

    def export(self, principal: Principal, export_id: UUID, session=None) -> dict:
        if session is None:
            with session_scope(self.settings.database_url) as own:
                return self.export(principal, export_id, session=own)
        record = session.scalar(select(ExportRequestModel).where(
            ExportRequestModel.export_id == export_id,
            ExportRequestModel.account_id == principal.account_id,
        ))
        if not record:
            raise IdentityError("NOT_FOUND", "Không tìm thấy bản xuất dữ liệu.", 404)
        return {
            "export_id": str(record.export_id), "status": record.status,
            "checksum": record.checksum,
            "created_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
            "payload": record.payload,
        }

    def request_deletion(self, principal: Principal, current_password: str,
                         confirmation: str) -> None:
        if confirmation != "XÓA TÀI KHOẢN":
            raise IdentityError("VALIDATION_ERROR", "Cụm từ xác nhận chưa đúng.", 422)
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            account = repo.account(principal.account_id, lock=True)
            if not verify_password(current_password, account.password_hash):
                raise IdentityError("INVALID_CREDENTIALS", "Mật khẩu không đúng.", 401)
            now = now_utc()
            account.status = "deletion_pending"
            account.deletion_requested_at = now
            account.purge_after = now + timedelta(days=30)
            account.updated_at = now
            account.version += 1
            session.execute(update(IdentitySessionModel).where(
                IdentitySessionModel.account_id == account.account_id,
                IdentitySessionModel.revoked_at.is_(None),
            ).values(revoked_at=now, revoke_reason="account_deletion"))
            self._lifecycle(session, account, "deletion_requested", principal.correlation_id)
            self._audit(session, "account_deletion", "success",
                        principal.correlation_id, account.account_id,
                        principal.session_id)

    def cancel_deletion(self, token: str, correlation_id: str) -> dict:
        with session_scope(self.settings.database_url) as session:
            repo = IdentityRepository(session)
            action = repo.usable_action(token, "cancel_deletion", now_utc())
            if not action:
                raise IdentityError("ACTION_INVALID", "Mã khôi phục không hợp lệ hoặc đã hết hạn.", 400)
            account = repo.account(action.account_id, lock=True)
            if not account or account.status != "deletion_pending":
                raise IdentityError("ACTION_INVALID", "Mã khôi phục không hợp lệ hoặc đã hết hạn.", 400)
            action.used_at = now_utc()
            account.status = "active"
            account.deletion_requested_at = None
            account.purge_after = None
            account.updated_at = now_utc()
            account.version += 1
            self._lifecycle(session, account, "deletion_cancelled", correlation_id)
            self._audit(session, "deletion_cancelled", "success", correlation_id,
                        account.account_id)
            return account_public(account, repo.roles(account.account_id))
