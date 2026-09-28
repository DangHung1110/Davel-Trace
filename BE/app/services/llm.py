"""LLM gateway (T005, lane C). JSON mode + temp 0.1 + Pydantic validate.

Provider switch via .env (config.py): LLM_PROVIDER=local (Ollama demo
day, default) | api (test env, OpenAI-compatible endpoint for
GPT-4o-mini / Gemini Flash). No URL/key is hardcoded — everything comes
from Settings; keys live only in env/BE/.env (never committed).

Retry: at most 2 retries (3 attempts total) on transport error, bad
JSON, or schema-validation failure; exhaustion raises LLMError with a
machine-readable reason. `transport` is injectable for mock tests.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.app.config import Settings, get_settings  # noqa: E402

try:
    from pydantic import BaseModel, ValidationError
except ImportError:  # pragma: no cover
    BaseModel, ValidationError = None, Exception

MAX_RETRIES = 2
TEMPERATURE = 0.1


class LLMError(RuntimeError):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"llm failed [{reason}]: {detail[:200]}")
        self.reason = reason


def _endpoint(settings: Settings) -> tuple[str, dict, dict]:
    """Return (url, headers, extra_body) per provider. No hardcoded secrets."""
    if settings.llm_provider == "api":
        base = os.environ.get("LLM_API_URL", "https://api.openai.com/v1")
        key = os.environ.get("LLM_API_KEY", "")
        return (base.rstrip("/") + "/chat/completions",
                {"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
                {"model": os.environ.get("LLM_API_MODEL", "gpt-4o-mini"),
                 "response_format": {"type": "json_object"}})
    return (settings.ollama_url.rstrip("/") + "/api/chat",  # local Ollama
            {"Content-Type": "application/json"},
            {"model": settings.judge_model})


def _urllib_transport(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    if "message" in data:  # Ollama shape
        return {"text": data["message"].get("content", "")}
    choices = data.get("choices", [])  # OpenAI-compatible shape
    return {"text": choices[0]["message"]["content"] if choices else ""}


def _extract_json(text: str) -> dict:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        obj = json.loads(text[start:end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("no JSON object in response")


def complete_json(prompt: str, schema=None, transport=None,
                  settings: Settings | None = None) -> dict:
    """Prompt -> validated dict. `schema`: pydantic model (optional but
    recommended). Raises LLMError(reason=transport|bad_json|schema)."""
    settings = settings or get_settings()
    transport = transport or _urllib_transport
    url, headers, extra = _endpoint(settings)
    body = {**extra, "temperature": TEMPERATURE,
            "messages": [{"role": "user", "content": prompt}]}
    last: LLMError = LLMError("transport", "no attempt made")
    for _ in range(MAX_RETRIES + 1):
        try:
            text = transport(url, headers, body).get("text", "")
        except Exception as e:  # noqa: BLE001
            last = LLMError("transport", str(e))
            continue
        try:
            obj = _extract_json(text)
        except ValueError as e:
            last = LLMError("bad_json", str(e))
            continue
        if schema is not None and BaseModel is not None and issubclass(schema, BaseModel):
            try:
                return schema(**obj).model_dump()
            except ValidationError as e:
                last = LLMError("schema", str(e))
                continue
        return obj
    raise last
