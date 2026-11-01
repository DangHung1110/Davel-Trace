from __future__ import annotations

from BE.app.core.config import Settings
from BE.app.core.health import build_readiness


def test_demo_can_be_ready_with_optional_providers_degraded(tmp_path) -> None:
    (tmp_path / "pois.json").write_text('{"pois": []}', encoding="utf-8")
    (tmp_path / "matrix.json").write_text('{"cells": {}}', encoding="utf-8")
    settings = Settings(snapshot_dir=str(tmp_path), _env_file=None)
    result = build_readiness(settings, correlation_id="test-correlation")
    optional = [item for item in result["components"] if not item["required"]]
    assert result["status"] == "ready"
    assert optional
    assert all(item["status"] in {"ready", "degraded"} for item in optional)


def test_production_database_failure_is_not_ready(tmp_path) -> None:
    (tmp_path / "pois.json").write_text('{"pois": []}', encoding="utf-8")
    (tmp_path / "matrix.json").write_text('{"cells": {}}', encoding="utf-8")
    settings = Settings(
        app_mode="production",
        database_url="postgresql+psycopg://none:none@127.0.0.1:1/none",
        allowed_origins="https://app.example",
        snapshot_dir=str(tmp_path),
        _env_file=None,
    )
    result = build_readiness(settings, correlation_id="test-correlation")
    assert result["status"] == "not_ready"
    database = next(item for item in result["components"] if item["name"] == "database")
    assert database["status"] == "unavailable"
    assert "none:none" not in str(result)


def test_schema_behind_or_ahead_is_never_reported_ready(tmp_path, monkeypatch) -> None:
    (tmp_path / "pois.json").write_text('{"pois": []}', encoding="utf-8")
    (tmp_path / "matrix.json").write_text('{"cells": {}}', encoding="utf-8")
    settings = Settings(
        app_mode="production",
        database_url="postgresql+psycopg://davel:test@localhost/davel_trace",
        allowed_origins="https://app.example",
        snapshot_dir=str(tmp_path),
        _env_file=None,
    )
    for current, head in (("004_999", "005_001"), ("006_001", "005_001")):
        monkeypatch.setattr(
            "BE.app.core.health.inspect_database",
            lambda _url, current=current, head=head: {
                "reachable": True,
                "current_revision": current,
                "head_revision": head,
                "schema_ready": False,
            },
        )
        result = build_readiness(settings, correlation_id="schema-test")
        schema = next(
            item for item in result["components"] if item["name"] == "schema"
        )
        assert result["status"] == "not_ready"
        assert schema["status"] == "not_ready"
        assert schema["revision"] == current
        assert schema["expected_revision"] == head
