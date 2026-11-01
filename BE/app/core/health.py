"""Honest liveness and component readiness without secret disclosure."""

from __future__ import annotations

import os

from BE.app.core.config import Settings
from BE.app.db.migrations import inspect_database


def _component(name: str, required: bool, status: str, **metadata) -> dict:
    return {"name": name, "required": required, "status": status, **metadata}


def build_readiness(settings: Settings, *, correlation_id: str) -> dict:
    components: list[dict] = []
    if settings.database_url:
        try:
            database = inspect_database(settings.database_url)
            components.append(_component("database", True, "ready"))
            components.append(
                _component(
                    "schema",
                    True,
                    "ready" if database["schema_ready"] else "not_ready",
                    revision=database["current_revision"],
                    expected_revision=database["head_revision"],
                )
            )
        except Exception:
            components.append(_component("database", True, "unavailable"))
            components.append(_component("schema", True, "not_ready"))
    else:
        required = settings.database_required
        components.append(
            _component("database", required, "unavailable" if required else "degraded")
        )
        components.append(
            _component("schema", required, "not_ready" if required else "degraded")
        )

    catalog_ready = all(
        os.path.isfile(os.path.join(settings.snapshot_dir, name))
        for name in ("pois.json", "matrix.json")
    )
    components.append(
        _component(
            "catalog",
            True,
            "ready" if catalog_ready else "not_ready",
            version=settings.snapshot_name,
        )
    )
    components.append(
        _component("osrm", False, "ready" if settings.osrm_base_url else "degraded")
    )
    components.append(
        _component(
            "ai",
            False,
            "ready" if settings.llm_provider in {"local", "api"} else "degraded",
        )
    )
    ready = all(
        item["status"] == "ready" for item in components if item["required"]
    )
    return {
        "status": "ready" if ready else "not_ready",
        "mode": settings.app_mode.value,
        "components": components,
        "correlation_id": correlation_id,
    }
