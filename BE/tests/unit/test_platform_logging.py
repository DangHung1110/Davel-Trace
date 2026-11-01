from __future__ import annotations

import json
import logging

from BE.app.core.logging import JsonFormatter, redact


def test_redact_masks_credentials_and_named_secrets() -> None:
    value = redact(
        "postgresql://davel:very-secret@localhost/db password=hunter2 token=abc"
    )
    assert "very-secret" not in value
    assert "hunter2" not in value
    assert "token=abc" not in value


def test_json_formatter_contains_safe_correlation(monkeypatch) -> None:
    monkeypatch.setattr(
        "BE.app.core.logging.get_correlation_id", lambda: "test-correlation-0001"
    )
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 1, "password=hidden", (), None
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["correlation_id"] == "test-correlation-0001"
    assert "hidden" not in payload["message"]
