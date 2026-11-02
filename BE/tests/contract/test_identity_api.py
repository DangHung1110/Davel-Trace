from __future__ import annotations

from uuid import uuid4
from datetime import timedelta
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from BE.app.core.config import get_settings
from BE.app.db.models import AccountModel, RoleAssignmentModel, SecurityAuditEventModel
from BE.app.db.session import session_scope
from BE.app.main import app
from BE.app.modules.identity.service import now_utc
from BE.app.modules.identity.security import hash_password
from BE.scripts.purge_accounts import purge_due_accounts


def _cleanup(email: str) -> None:
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        account = session.scalar(select(AccountModel).where(AccountModel.email_normalized == email))
        if account:
            session.delete(account)


def test_register_verify_login_refresh_revoke_recover_and_delete(monkeypatch) -> None:
    monkeypatch.setenv("IDENTITY_DEV_OUTBOX_ENABLED", "true")
    email = f"identity-{uuid4().hex}@example.com"
    password = "TravelDemo123"
    client = TestClient(app)
    try:
        registered = client.post("/v1/auth/register", json={
            "email": email.upper(), "password": password, "terms_accepted": True,
        })
        assert registered.status_code == 202, registered.text
        assert registered.json()["status"] == "unverified"
        assert "password" not in registered.text.lower()

        blocked = client.post("/v1/auth/login", json={"email": email, "password": password})
        assert blocked.status_code == 403

        outbox = client.get("/v1/dev/identity/outbox", params={
            "email": email, "purpose": "verify_email",
        })
        assert outbox.status_code == 200
        token = outbox.json()["token"]
        verified = client.post("/v1/auth/verification/confirm", json={"token": token})
        assert verified.status_code == 200
        assert verified.json()["status"] == "active"
        assert client.post("/v1/auth/verification/confirm", json={"token": token}).status_code == 400

        login_body = {"email": email, "password": password, "device_label": "Chrome test"}
        login_key = f"login-{uuid4().hex}"
        login_started = perf_counter()
        login = client.post("/v1/auth/login", headers={"Idempotency-Key": login_key},
                            json=login_body)
        assert perf_counter() - login_started < 2.0
        assert login.status_code == 200, login.text
        credentials = login.json()
        repeated = client.post("/v1/auth/login", headers={"Idempotency-Key": login_key},
                               json=login_body)
        assert repeated.json()["access_token"] == credentials["access_token"]
        assert credentials["access_token"] not in str(registered.json())
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        auth_started = perf_counter()
        assert client.get("/v1/account/me", headers=headers).status_code == 200
        assert perf_counter() - auth_started < 0.1
        with session_scope(get_settings().database_url) as session:
            account = session.scalar(select(AccountModel).where(
                AccountModel.email_normalized == email
            ))
            assignment = RoleAssignmentModel(account_id=account.account_id, role="administrator")
            session.add(assignment)
        assert "administrator" in client.get("/v1/account/me", headers=headers).json()["roles"]
        with session_scope(get_settings().database_url) as session:
            assignment = session.scalar(select(RoleAssignmentModel).where(
                RoleAssignmentModel.account_id == account.account_id,
                RoleAssignmentModel.role == "administrator",
            ))
            assignment.revoked_at = now_utc()
        assert "administrator" not in client.get("/v1/account/me", headers=headers).json()["roles"]
        sessions = client.get("/v1/account/sessions", headers=headers).json()
        assert sessions["count"] == 1

        refreshed = client.post("/v1/auth/refresh", json={
            "refresh_token": credentials["refresh_token"],
        })
        assert refreshed.status_code == 200
        assert client.post("/v1/auth/refresh", json={
            "refresh_token": credentials["refresh_token"],
        }).status_code == 401
        headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}

        assert client.post("/v1/account/exports", headers=headers, json={
            "current_password": "wrong-password", "confirmation": "XUẤT DỮ LIỆU",
        }).status_code == 401
        export = client.post("/v1/account/exports", headers=headers, json={
            "current_password": password, "confirmation": "XUẤT DỮ LIỆU",
        })
        assert export.status_code == 201
        assert export.json()["payload"]["account"]["email"] == email

        recovery = client.post("/v1/auth/recovery/request", json={"email": email})
        unknown = client.post("/v1/auth/recovery/request", json={
            "email": f"unknown-{uuid4().hex}@example.com",
        })
        assert recovery.status_code == unknown.status_code == 202
        assert recovery.json() == unknown.json()
        reset_token = client.get("/v1/dev/identity/outbox", params={
            "email": email, "purpose": "recover_password",
        }).json()["token"]
        new_password = "TravelDemo456"
        assert client.post("/v1/auth/recovery/confirm", json={
            "token": reset_token, "new_password": new_password,
        }).status_code == 204
        assert client.get("/v1/account/me", headers=headers).status_code == 401
        assert client.post("/v1/auth/login", json={
            "email": email, "password": password,
        }).status_code == 401
        relogin = client.post("/v1/auth/login", json={
            "email": email, "password": new_password,
        }).json()
        headers = {"Authorization": f"Bearer {relogin['access_token']}"}
        assert client.post("/v1/account/deletion", headers=headers, json={
            "current_password": new_password, "confirmation": "XÓA TÀI KHOẢN",
        }).status_code == 204
        assert client.get("/v1/account/me", headers=headers).status_code == 401

        assert client.post("/v1/auth/deletion-cancel/request", json={"email": email}).status_code == 202
        cancel_token = client.get("/v1/dev/identity/outbox", params={
            "email": email, "purpose": "cancel_deletion",
        }).json()["token"]
        cancelled = client.post("/v1/auth/deletion-cancel/confirm", json={"token": cancel_token})
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "active"
        with session_scope(get_settings().database_url) as session:
            account = session.scalar(select(AccountModel).where(
                AccountModel.email_normalized == email
            ))
            categories = set(session.scalars(select(SecurityAuditEventModel.category).where(
                SecurityAuditEventModel.account_id == account.account_id
            )))
        assert {
            "registration", "verification", "login", "refresh",
            "account_export", "recover_password", "password_recovery",
            "account_deletion", "cancel_deletion", "deletion_cancelled",
        } <= categories
    finally:
        _cleanup(email)


def test_due_account_purge_is_scoped_and_idempotent() -> None:
    email = f"purge-{uuid4().hex}@example.com"
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        account = AccountModel(
            email_normalized=email,
            password_hash=hash_password("TravelDemo123"),
            status="deletion_pending",
            consented_at=now_utc(),
            deletion_requested_at=now_utc() - timedelta(days=31),
            purge_after=now_utc() - timedelta(days=1),
        )
        session.add(account)
        session.flush()
        account_id = account.account_id
    try:
        assert purge_due_accounts() >= 1
        assert purge_due_accounts() == 0
        with session_scope(settings.database_url) as session:
            account = session.get(AccountModel, account_id)
            assert account is not None
            assert account.status == "purged"
            assert account.password_hash == "purged"
            assert email != account.email_normalized
    finally:
        with session_scope(settings.database_url) as session:
            account = session.get(AccountModel, account_id)
            if account:
                session.delete(account)
