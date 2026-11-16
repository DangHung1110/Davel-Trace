from datetime import timedelta
import json
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from BE.app.core.config import get_settings
from BE.app.db.models import AccountModel, OneTimeActionModel
from BE.app.db.session import session_scope
from BE.app.main import app
from BE.app.modules.identity import google_api
from BE.app.modules.identity.provider_models import GoogleLoginAttemptModel
from BE.app.modules.identity.security import hash_password, secret_hash
from BE.app.modules.identity.service import _rate_limiter, now_utc

ORIGIN = "http://127.0.0.1:5501"


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fixture.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "not-a-real-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/v1/auth/google/callback")
    monkeypatch.setenv("IDENTITY_DEV_OUTBOX_ENABLED", "true")
    _rate_limiter._events.clear()
    client = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    email = f"oauth-{uuid4().hex}@example.test"
    subject = uuid4().hex
    attempt_ids = []

    def begin(**changes):
        response = client.get("/v1/auth/google/start", params={"origin": ORIGIN, "terms_accepted": True, **changes})
        assert response.status_code == 302
        params = parse_qs(urlsplit(response.headers["location"]).query)
        assert params["code_challenge_method"] == ["S256"]
        assert params["scope"] == ["openid email profile"]
        assert "refresh_token" not in response.headers["location"]
        with session_scope(get_settings().database_url) as session:
            attempt_ids.append(session.scalar(select(GoogleLoginAttemptModel.attempt_id).where(
                GoogleLoginAttemptModel.state_hash == secret_hash(params["state"][0]))))
        claims = {"iss": "https://accounts.google.com", "aud": "fixture.apps.googleusercontent.com",
                  "sub": subject, "email": email, "email_verified": True, "nonce": params["nonce"][0]}
        monkeypatch.setattr(google_api, "exchange_google_code", lambda *a: claims)
        return params["state"][0], claims

    yield client, email, begin
    client.close()
    with session_scope(get_settings().database_url) as session:
        session.execute(delete(GoogleLoginAttemptModel).where(GoogleLoginAttemptModel.attempt_id.in_(attempt_ids)))
        account = session.scalar(select(AccountModel).where(AccountModel.email_normalized == email))
        if account:
            session.delete(account)


def finish(client, state):
    response = client.get("/v1/auth/google/callback", params={"state": state, "code": "test-only-code"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "access_token" not in response.text and "refresh_token" not in response.text
    assert 'postMessage(' in response.text
    handoff = re.search(r'"handoff": "([^"]+)"', response.text).group(1)
    return handoff


def exchange(client, handoff, origin=ORIGIN):
    return client.post("/v1/auth/google/exchange", json={"handoff": handoff}, headers={"Origin": origin})


def test_google_login_handoff_refresh_and_recovery(flow):
    client, email, begin = flow
    state, _ = begin()
    handoff = finish(client, state)
    denied_origin = exchange(client, handoff, "https://evil.example")
    assert denied_origin.status_code == 400
    login = exchange(client, handoff)
    assert login.status_code == 200
    credentials = login.json()
    assert credentials["account"]["email"] == email
    assert credentials["account"]["roles"] == ["traveler"]
    assert exchange(client, handoff).status_code == 400
    assert client.get("/v1/auth/google/callback", params={"state": state, "code": "test-only-code"}).status_code == 400
    headers = {"Authorization": "Bearer " + credentials["access_token"]}
    assert client.get("/v1/account/me", headers=headers).status_code == 200
    rotated = client.post("/v1/auth/refresh", json={"refresh_token": credentials["refresh_token"]})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != credentials["refresh_token"]
    assert client.get("/v1/account/me", headers=headers).status_code == 401
    headers = {"Authorization": "Bearer " + rotated.json()["access_token"]}
    # A Google-created account can set its first Davel password via recovery.
    assert client.post("/v1/auth/recovery/request", json={"email": email}).status_code == 202
    token = client.get("/v1/dev/identity/outbox", params={"email": email, "purpose": "recover_password"}).json()["token"]
    assert client.post("/v1/auth/recovery/confirm", json={"token": token, "new_password": "TravelGoogle123"}).status_code == 204
    assert client.get("/v1/account/me", headers=headers).status_code == 401
    assert client.post("/v1/auth/login", json={"email": email, "password": "TravelGoogle123"}).status_code == 200
    # Stable subject signs back into the same account, without another email link.
    state2, _ = begin()
    assert exchange(client, finish(client, state2)).json()["account"]["account_id"] == credentials["account"]["account_id"]


@pytest.mark.parametrize("change", ["nonce", "aud", "iss", "email_verified", "sub"])
def test_google_claim_mismatch_does_not_create_account(flow, change):
    client, email, begin = flow
    state, claims = begin()
    claims[change] = False if change == "email_verified" else ""
    response = client.get("/v1/auth/google/callback", params={"state": state, "code": "test-only-code"})
    assert response.status_code == 400
    with session_scope(get_settings().database_url) as session:
        assert session.scalar(select(AccountModel).where(AccountModel.email_normalized == email)) is None


def test_google_state_requires_same_browser_and_expires(flow):
    client, _, begin = flow
    state, _ = begin()
    other = TestClient(app, base_url="http://localhost:8000")
    assert other.get("/v1/auth/google/callback", params={"state": state, "code": "test-only-code"}).status_code == 400
    other.close()
    with session_scope(get_settings().database_url) as session:
        attempt = session.scalar(select(GoogleLoginAttemptModel).where(GoogleLoginAttemptModel.state_hash == secret_hash(state)))
        attempt.expires_at = now_utc() - timedelta(seconds=1)
    assert client.get("/v1/auth/google/callback", params={"state": state, "code": "test-only-code"}).status_code == 400


def test_google_handoff_expires_and_suspended_account_cannot_exchange(flow):
    client, email, begin = flow
    state, _ = begin()
    handoff = finish(client, state)
    with session_scope(get_settings().database_url) as session:
        account = session.scalar(select(AccountModel).where(AccountModel.email_normalized == email))
        account.status = "suspended"
    assert exchange(client, handoff).status_code == 403
    state2, _ = begin()
    assert client.get("/v1/auth/google/callback", params={"state": state2, "code": "test-only-code"}).status_code == 403
    with session_scope(get_settings().database_url) as session:
        account = session.scalar(select(AccountModel).where(AccountModel.email_normalized == email))
        account.status = "active"
        attempt = session.scalar(select(GoogleLoginAttemptModel).where(GoogleLoginAttemptModel.handoff_hash == secret_hash(handoff)))
        attempt.handoff_expires_at = now_utc() - timedelta(seconds=1)
    assert exchange(client, handoff).status_code == 400


def test_google_email_collision_does_not_link_existing_account(flow):
    client, email, begin = flow
    with session_scope(get_settings().database_url) as session:
        session.add(AccountModel(email_normalized=email, password_hash=hash_password("ExistingPass123"), status="active"))
    state, _ = begin()
    response = client.get("/v1/auth/google/callback", params={"state": state, "code": "test-only-code"})
    assert response.status_code == 409
    assert "ACCOUNT_LINK_REQUIRED" in response.text


def test_google_consent_denial_origin_terms_and_disabled_client(flow, monkeypatch):
    client, _, begin = flow
    capabilities = client.get("/v1/auth/capabilities").json()
    assert capabilities["google_authorization_origin"] == "http://localhost:8000"
    assert capabilities["development_inbox"] is True
    assert client.get("/v1/auth/google/start", params={"origin": "https://evil.example", "terms_accepted": True}).status_code == 400
    assert client.get("/v1/auth/google/start", params={"origin": ORIGIN}).status_code == 422
    state, _ = begin()
    denied = client.get("/v1/auth/google/callback", params={"state": state, "error": "access_denied"})
    assert denied.status_code == 400 and "GOOGLE_CANCELLED" in denied.text
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    assert client.get("/v1/auth/google/start", params={"origin": ORIGIN, "terms_accepted": True}).status_code == 503


def test_smtp_failure_is_persisted_without_exposing_recovery_tokens(flow, monkeypatch):
    client, email, _ = flow
    monkeypatch.setenv("IDENTITY_DEV_OUTBOX_ENABLED", "false")
    monkeypatch.setattr("BE.app.modules.identity.service.send_identity_email", lambda *a: "failed")
    registered = client.post("/v1/auth/register", json={"email": email, "password": "TravelDemo123", "terms_accepted": True})
    assert registered.status_code == 202 and registered.json()["delivery_status"] == "failed"
    assert client.get("/v1/dev/identity/outbox", params={"email": email, "purpose": "verify_email"}).status_code == 404
    with session_scope(get_settings().database_url) as session:
        account = session.scalar(select(AccountModel).where(AccountModel.email_normalized == email))
        action = session.scalar(select(OneTimeActionModel).where(OneTimeActionModel.account_id == account.account_id))
        assert action.delivery_status == "failed" and action.superseded_at is not None
        account.status = "active"
    known = client.post("/v1/auth/recovery/request", json={"email": email})
    unknown = client.post("/v1/auth/recovery/request", json={"email": "unknown@example.test"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
