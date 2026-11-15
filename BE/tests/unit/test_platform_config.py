from __future__ import annotations

import pytest
from pydantic import ValidationError

from BE.app.core.config import AppMode, Settings


def test_demo_defaults_are_explicit_and_local() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_mode is AppMode.demo
    assert "http://127.0.0.1:5501" in settings.cors_origins
    assert settings.database_required is False
    assert settings.llm_provider == "disabled"


def test_production_requires_postgresql_database_url() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(app_mode="production", database_url="", _env_file=None)
    assert "DATABASE_URL" in str(exc.value)


def test_secret_database_url_is_not_in_repr() -> None:
    secret = "postgresql+psycopg://davel:very-secret@localhost/davel_trace"
    settings = Settings(
        app_mode="production",
        database_url=secret,
        allowed_origins="https://app.example",
        _env_file=None,
    )
    assert "very-secret" not in repr(settings)
    assert settings.database_url == secret


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_mode="production",
            database_url="postgresql+psycopg://davel:test@localhost/davel_trace",
            allowed_origins="*",
            _env_file=None,
        )


def test_llm_provider_and_bounds_are_typed() -> None:
    settings = Settings(
        llm_provider="gemini",
        gemini_api_key="not-a-real-key",
        llm_model="gemini-test",
        llm_timeout_seconds=9,
        llm_max_retries=1,
        _env_file=None,
    )
    assert settings.llm_provider == "gemini"
    assert settings.llm_timeout_seconds == 9
    assert settings.llm_max_retries == 1
    assert "not-a-real-key" not in repr(settings)


@pytest.mark.parametrize("provider", ["disabled", "local", "gemini", "compatible"])
def test_supported_llm_providers(provider: str) -> None:
    assert Settings(llm_provider=provider, _env_file=None).llm_provider == provider


def test_unknown_llm_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider="openai", _env_file=None)
