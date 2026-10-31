"""Small JSON logger with correlation binding and conservative redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from BE.app.core.request_context import get_correlation_id


_SENSITIVE = re.compile(
    r"(?i)(password|token|secret|api[_-]?key)(\s*[=:]\s*)([^\s,;]+)"
)
_CREDENTIAL_URL = re.compile(r"(://[^:/\s]+:)([^@/\s]+)(@)")


def redact(value: object) -> str:
    text = str(value)
    text = _SENSITIVE.sub(r"\1\2[REDACTED]", text)
    return _CREDENTIAL_URL.sub(r"\1[REDACTED]\3", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "correlation_id": get_correlation_id(),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_davel_trace_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers[:] = [handler]
    root.setLevel(level)
    root._davel_trace_configured = True  # type: ignore[attr-defined]
