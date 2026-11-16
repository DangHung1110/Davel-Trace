"""Groq uses its own credentials/model; tests never call a hosted provider."""
import json
import urllib.error

import pytest

from BE.app.core.config import Settings
from BE.app.core.logging import redact
from BE.app.modules.ai_assistance.domain import InterpretationDraft
from BE.app.modules.ai_assistance.service import AiAssistanceService
from BE.app.services.llm import LLMError, complete_json, provider_metadata


def settings(**kwargs):
    return Settings(llm_provider="groq", groq_api_key="test-groq-secret", _env_file=None, **kwargs)


def test_groq_endpoint_model_json_mode_and_readiness_ignore_stale_gemini_settings():
    seen = {}
    def transport(url, headers, body):
        seen.update(url=url, headers=headers, body=body)
        return {"text": '{"travelers": 2, "budget": 3000000}'}
    config = settings(llm_model="gemini-old-model", llm_api_url="https://old.example")
    result = complete_json("Đi 2 người, 3 triệu", InterpretationDraft, transport, config)
    assert result["travelers"] == 2
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer test-groq-secret"
    assert seen["body"]["model"] == "qwen/qwen3.8-27b"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["reasoning_effort"] == "none"
    assert seen["body"]["max_completion_tokens"] == 2048
    assert "schema" in seen["body"]["messages"][0]["content"]
    meta = AiAssistanceService(config).readiness()
    assert meta["provider"] == "groq" and meta["external_processing"] is True
    assert meta["model"] == "qwen/qwen3.8-27b" and meta["available"] is True
    assert config.groq_api_key not in repr(config)
    assert config.groq_api_key not in json.dumps(meta)


def test_missing_groq_key_fails_before_transport():
    config = Settings(llm_provider="groq", _env_file=None)
    assert provider_metadata(config)["configured"] is False
    with pytest.raises(LLMError) as error:
        complete_json("JSON", transport=lambda *args: pytest.fail("must not call provider"), settings=config)
    assert error.value.reason == "config"


@pytest.mark.parametrize("status,reason", [(401,"auth"), (403,"auth"), (429,"quota"), (400,"config"), (404,"config")])
def test_groq_http_failures_are_secret_safe_and_not_retried(monkeypatch, status, reason):
    calls = []
    config = settings()
    def fail(request, timeout):
        from io import BytesIO
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, status, "provider error", {},
                                     BytesIO(config.groq_api_key.encode()))
    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(LLMError) as error:
        complete_json("Return JSON", settings=config)
    assert error.value.reason == reason
    assert len(calls) == 1
    assert config.groq_api_key not in str(error.value)


def test_json_mode_and_schema_validation_still_reject_invalid_travelers():
    calls = []
    def invalid(*args):
        calls.append(1)
        return {"text": '{"travelers": -2}'}
    with pytest.raises(LLMError) as error:
        complete_json("JSON", InterpretationDraft, invalid, settings())
    assert error.value.reason == "schema" and len(calls) == 2


def test_groq_key_removed_from_prompt_logs_and_normalized_provider_error():
    fake_key = "gsk_test_fake_credential_12345678"
    seen = {}
    def complete(prompt, schema, config):
        seen["prompt"] = prompt
        return {"travelers": 2}
    service = AiAssistanceService(settings(), completer=complete)
    service.interpret("Đi hai người " + fake_key, catalog=[], trip_context={})
    assert fake_key not in seen["prompt"]
    assert fake_key not in redact("provider failed: " + fake_key)
    def failure(*args):
        raise LLMError("quota", "echo " + fake_key)
    config = Settings(llm_provider="groq", groq_api_key=fake_key, _env_file=None)
    with pytest.raises(LLMError) as error:
        complete_json("JSON", transport=failure, settings=config)
    assert fake_key not in str(error.value)
