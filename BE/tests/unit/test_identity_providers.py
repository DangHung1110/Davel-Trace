from datetime import datetime, timedelta, timezone
import io
import json
import logging
import smtplib
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from BE.app.core.config import Settings
from BE.app.core.logging import OAuthAccessFilter, redact
from BE.app.modules.identity.delivery import send_identity_email
from BE.app.modules.identity.google_oauth import exchange_google_code
from BE.app.modules.identity.service import IdentityError


def configured(**overrides):
    return Settings(_env_file=None, **{
        "smtp_host": "smtp.example.test", "smtp_username": "sender@example.test",
        "smtp_password": "smtp-secret-fixture", "smtp_from_email": "sender@example.test",
        "google_client_id": "fixture.apps.googleusercontent.com",
        "google_client_secret": "oauth-secret-fixture", **overrides,
    })


def test_smtp_starttls_authentication_precedes_send(monkeypatch):
    smtp = MagicMock()
    smtp.send_message.return_value = {}
    connection = MagicMock()
    connection.__enter__.return_value = smtp
    factory = MagicMock(return_value=connection)
    monkeypatch.setattr(smtplib, "SMTP", factory)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    assert send_identity_email(configured(), "recipient@example.test", "recover_password", "one-time-code", expiry) == "sent"
    factory.assert_called_once_with("smtp.example.test", 587, timeout=10)
    names = [call[0] for call in smtp.method_calls]
    assert names == ["ehlo", "starttls", "ehlo", "login", "send_message"]
    context = smtp.starttls.call_args.kwargs["context"]
    assert context.check_hostname
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "recipient@example.test"
    assert "one-time-code" in message.get_content()


@pytest.mark.parametrize("failure", [smtplib.SMTPAuthenticationError(535, b"private"), TimeoutError(), OSError()])
def test_smtp_failures_are_not_success_or_demo_fallback(monkeypatch, failure):
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(side_effect=failure))
    assert send_identity_email(configured(), "recipient@example.test", "verify_email", "code", datetime.now(timezone.utc)) == "failed"


def test_smtp_ssl_mode_and_refused_recipient(monkeypatch):
    smtp = MagicMock()
    smtp.send_message.return_value = {"recipient@example.test": (550, b"rejected")}
    connection = MagicMock()
    connection.__enter__.return_value = smtp
    monkeypatch.setattr(smtplib, "SMTP_SSL", MagicMock(return_value=connection))
    assert send_identity_email(configured(smtp_ssl=True, smtp_starttls=False, smtp_port=465),
                               "recipient@example.test", "verify_email", "code", datetime.now(timezone.utc)) == "failed"
    smtp.starttls.assert_not_called()


def test_config_rejects_plaintext_mail_and_masks_secrets():
    with pytest.raises(ValidationError):
        configured(smtp_starttls=False)
    with pytest.raises(ValidationError):
        configured(google_redirect_uri="http://evil.example/v1/auth/google/callback")
    rendered = repr(configured())
    assert "smtp-secret-fixture" not in rendered
    assert "oauth-secret-fixture" not in rendered


def test_callback_query_never_appears_in_application_or_uvicorn_logs():
    path = "/v1/auth/google/callback?code=private-code&state=private-state"
    assert "private-code" not in redact(path)
    record = logging.LogRecord("uvicorn.access", 20, __file__, 1,
                               '%s - "%s %s HTTP/%s" %s', ("127.0.0.1", "GET", path, "1.1", 200), None)
    assert OAuthAccessFilter().filter(record)
    assert "private-state" not in record.getMessage()


def test_google_exchange_does_not_expose_provider_error(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(side_effect=ValueError("oauth-secret-fixture")))
    with pytest.raises(IdentityError) as exc:
        exchange_google_code(configured(), "private-code", "private-verifier")
    assert exc.value.code == "GOOGLE_PROVIDER_ERROR"
    assert "oauth-secret-fixture" not in str(exc.value)
    assert "private-code" not in str(exc.value)


@pytest.mark.parametrize("audience,expired,tampered,future_seconds,valid", [
    ("fixture.apps.googleusercontent.com", False, False, 0, True),
    ("other-client", False, False, 0, False),
    ("fixture.apps.googleusercontent.com", True, False, 0, False),
    ("fixture.apps.googleusercontent.com", False, True, 0, False),
    ("fixture.apps.googleusercontent.com", False, False, 5, True),
    ("fixture.apps.googleusercontent.com", False, False, 120, False),
])
def test_google_verifier_checks_real_rsa_signature_expiry_and_audience(monkeypatch, audience, expired, tampered, future_seconds, valid):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from google.auth import jwt
    from google.auth.crypt import RSASigner

    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-only")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256()))
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    token = jwt.encode(RSASigner.from_string(private, key_id="test-key"), {
        "iss": "https://accounts.google.com", "aud": audience, "sub": "fixture-subject",
        "iat": int(now.timestamp()) + (-7200 if expired else future_seconds),
        "exp": int(now.timestamp()) + (-3600 if expired else 3600),
    }).decode()
    if tampered:
        pieces = token.split(".")
        pieces[2] = ("A" if pieces[2][0] != "A" else "B") + pieces[2][1:]
        token = ".".join(pieces)
    response = io.BytesIO(json.dumps({"id_token": token}).encode())
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: response)
    certificate = cert.public_bytes(serialization.Encoding.PEM).decode()

    class CertificateResponse:
        status = 200
        data = json.dumps({"test-key": certificate}).encode()

    monkeypatch.setattr("BE.app.modules.identity.google_oauth.GoogleRequest", lambda: lambda *a, **kw: CertificateResponse())
    if valid:
        assert exchange_google_code(configured(), "code", "verifier")["sub"] == "fixture-subject"
    else:
        with pytest.raises(IdentityError):
            exchange_google_code(configured(), "code", "verifier")
