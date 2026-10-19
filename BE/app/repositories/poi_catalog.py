from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from threading import Lock
from typing import Any


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    return "".join(character for character in normalized if not unicodedata.combining(character))


class PoiCatalog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._payload: dict[str, Any] = {}
        self._lock = Lock()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        mtime = self.path.stat().st_mtime
        with self._lock:
            if self._mtime != mtime:
                self._payload = json.loads(self.path.read_text(encoding="utf-8"))
                self._mtime = mtime
        return self._payload

    def metadata(self) -> tuple[str, str]:
        payload = self._load()
        return str(payload.get("snapshot", "danang-v1")), str(payload.get("fetched_at", ""))

    def search(
        self, query: str = "", *, limit: int = 20, verified_only: bool = True
    ) -> list[dict[str, Any]]:
        payload = self._load()
        normalized_query = _normalize(query.strip())
        matches: list[dict[str, Any]] = []
        for poi in payload.get("pois", []):
            if verified_only and not poi.get("verified", False):
                continue
            haystack = " ".join(
                [
                    str(poi.get("name", "")),
                    str(poi.get("type", "")),
                    *[str(tag) for tag in poi.get("tags", [])],
                ]
            )
            if normalized_query and normalized_query not in _normalize(haystack):
                continue
            matches.append(poi)
            if len(matches) >= limit:
                break
        return matches

    def get(self, poi_id: str) -> dict[str, Any] | None:
        return next(
            (poi for poi in self._load().get("pois", []) if poi.get("poi_id") == poi_id),
            None,
        )
