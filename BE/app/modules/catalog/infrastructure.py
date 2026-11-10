"""Read and validate versioned JSON place snapshots."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from BE.app.core.config import get_settings
from BE.app.modules.catalog.domain import CatalogUnavailable, place_id, valid_place


def _snapshot_path(configured: str) -> Path:
    path = Path(configured)
    full_project_snapshot = Path("BE/data/snapshots") / path.name / "pois.json"
    # The app's general planning seed remains at data/snapshots/danang-v1;
    # catalog search uses the curated, versioned product snapshot when present.
    if path == Path("data/snapshots/danang-v1") and full_project_snapshot.is_file():
        return full_project_snapshot
    if path.is_file():
        return path
    if path.name != "pois.json":
        candidate = path / "pois.json"
        if candidate.is_file():
            return candidate
    # Preserve the established repo-relative config while supporting checkout roots.
    candidate = Path("BE") / path / "pois.json"
    if candidate.is_file():
        return candidate
    fallback = Path("BE/data/snapshots") / path.name / "pois.json"
    if fallback.is_file():
        return fallback
    raise CatalogUnavailable("catalog snapshot is unavailable")


@lru_cache(maxsize=4)
def _load_path(path_text: str, modified_ns: int) -> dict[str, Any]:
    del modified_ns
    try:
        payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogUnavailable("catalog snapshot could not be read") from exc
    version = str(payload.get("snapshot", "")).strip()
    rows = payload.get("pois")
    if not version or not isinstance(rows, list) or not rows:
        raise CatalogUnavailable("catalog snapshot metadata is invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not valid_place(row):
            raise CatalogUnavailable("catalog snapshot contains an invalid place")
        identifier = place_id(row)
        if identifier in seen:
            raise CatalogUnavailable("catalog snapshot contains duplicate place IDs")
        seen.add(identifier)
    return payload


def load_catalog() -> dict[str, Any]:
    settings = get_settings()
    path = _snapshot_path(settings.snapshot_dir).resolve()
    return _load_path(str(path), path.stat().st_mtime_ns)


