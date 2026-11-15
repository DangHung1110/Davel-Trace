"""Provider-neutral JSON LLM gateway.

The deterministic planner never calls this module. AI capabilities use it for
optional interpretation, explanation and shadow observations only. Gemini is
called through Google's OpenAI-compatible REST surface without an SDK.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

from BE.app.config import Settings, get_settings

try:
    from pydantic import BaseModel, ValidationError
except ImportError:  # pragma: no cover
    BaseModel, ValidationError = None, Exception

TEMPERATURE = 0.1
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
RETRYABLE = frozenset({"transport", "timeout", "bad_json", "schema"})


class LLMError(RuntimeError):
    """A normalized, secret-safe provider failure."""

    def __init__(self, reason: str, detail: str = ""):
        safe = str(detail or "provider request failed").replace("\r", " ").replace("\n", " ")
        super().__init__(f"llm failed [{reason}]: {safe[:200]}")
        self.reason = reason
        self.detail = safe[:200]


def _safe_detail(detail: object, settings: Settings) -> str:
    text = str(detail or "provider request failed")
    for secret in (settings.gemini_api_key, settings.llm_api_key):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def _endpoint(settings: Settings) -> tuple[str, dict[str, str], dict]:
    """Return URL, headers and provider request fields; never log the result."""
    provider = settings.llm_provider
    if provider == "disabled":
        raise LLMError("disabled", "AI assistance is disabled")
    if provider == "local":
        if not settings.ollama_url or not settings.judge_model:
            raise LLMError("config", "local endpoint and model are required")
        return (
            settings.ollama_url.rstrip("/") + "/api/chat",
            {"Content-Type": "application/json"},
            {
                "model": settings.judge_model,
                "stream": False,
                "format": "json",
                "options": {"temperature": TEMPERATURE},
            },
        )
    if provider == "gemini":
        if not settings.gemini_api_key or not settings.llm_model:
            raise LLMError("config", "Gemini API key and model are required")
        base = settings.llm_api_url or GEMINI_OPENAI_BASE
        key = settings.gemini_api_key
    else:  # compatible
        if not settings.llm_api_url or not settings.llm_api_key or not settings.llm_model:
            raise LLMError("config", "compatible endpoint, key and model are required")
        base = settings.llm_api_url
        key = settings.llm_api_key
    return (
        base.rstrip("/") + "/chat/completions",
        {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        {"model": settings.llm_model, "temperature": TEMPERATURE},
    )


def _classify_http(status: int, body: str) -> str:
    lowered = body.lower()
    if status in {401, 403}:
        return "auth"
    if status == 429:
        return "quota"
    if "safety" in lowered or "blocked" in lowered or "refusal" in lowered:
        return "safety"
    if status in {408, 504}:
        return "timeout"
    return "transport"


def _urllib_transport(
    url: str,
    headers: dict[str, str],
    body: dict,
    timeout_s: float,
) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raw = exc.read(4096).decode("utf-8", errors="replace")
        raise LLMError(_classify_http(exc.code, raw), f"provider HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LLMError("timeout", "provider request timed out") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise LLMError("transport", "provider is unavailable") from exc
    if "message" in data:  # Ollama response
        return {"text": (data.get("message") or {}).get("content", "")}
    choices = data.get("choices") or []
    if choices and (choices[0].get("finish_reason") == "content_filter"
                    or (choices[0].get("message") or {}).get("refusal")):
        raise LLMError("safety", "provider declined this request")
    return {"text": (choices[0].get("message") or {}).get("content", "") if choices else ""}


def _extract_json(text: str) -> dict:
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except (TypeError, ValueError):
        pass
    text = str(text or "")
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        value = json.loads(text[start:end + 1])
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object in response")


def complete_json(
    prompt: str,
    schema=None,
    transport=None,
    settings: Settings | None = None,
    timeout_s: float | None = None,
) -> dict:
    """Return validated JSON or raise a normalized :class:`LLMError`."""
    settings = settings or get_settings()
    url, headers, provider_fields = _endpoint(settings)
    effective_timeout = timeout_s or settings.llm_timeout_seconds
    sender = transport or (
        lambda target, request_headers, request_body: _urllib_transport(
            target, request_headers, request_body, effective_timeout
        )
    )
    if schema is not None and hasattr(schema, "model_json_schema"):
        prompt += "\nReturn ONLY a JSON object matching this schema:\n" + json.dumps(
            schema.model_json_schema(), ensure_ascii=False
        )
    body = {**provider_fields, "messages": [{"role": "user", "content": prompt}]}
    last = LLMError("transport", "no attempt made")
    for attempt in range(settings.llm_max_retries + 1):
        try:
            response = sender(url, headers, body)
            value = _extract_json(response.get("text", ""))
            if schema is not None and BaseModel is not None and issubclass(schema, BaseModel):
                return schema.model_validate(value).model_dump(mode="json")
            return value
        except LLMError as exc:
            last = LLMError(exc.reason, _safe_detail(exc.detail, settings))
        except (TimeoutError, socket.timeout) as exc:
            last = LLMError("timeout", _safe_detail(exc, settings))
        except ValidationError:
            last = LLMError("schema", "provider JSON did not match the schema")
        except (ValueError, json.JSONDecodeError) as exc:
            last = LLMError("bad_json", _safe_detail(exc, settings))
        except Exception:  # noqa: BLE001 - provider messages can contain secrets
            last = LLMError("transport", "provider is unavailable")
        if last.reason not in RETRYABLE or attempt >= settings.llm_max_retries:
            break
    raise last


def provider_metadata(settings: Settings | None = None) -> dict:
    """Non-secret provider information for readiness responses."""
    settings = settings or get_settings()
    configured = settings.llm_provider == "local" or (
        settings.llm_provider == "gemini" and bool(settings.gemini_api_key)
    ) or (
        settings.llm_provider == "compatible"
        and bool(settings.llm_api_url and settings.llm_api_key)
    )
    model = settings.judge_model if settings.llm_provider == "local" else settings.llm_model
    return {
        "provider": settings.llm_provider,
        "model": model if settings.llm_provider != "disabled" else None,
        "configured": bool(configured and model),
        "external_processing": settings.llm_provider in {"gemini", "compatible"},
    }
