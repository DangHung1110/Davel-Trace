"""Replaceable identity delivery port and explicit local-demo inbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock


@dataclass(frozen=True)
class DevelopmentDelivery:
    email: str
    purpose: str
    token: str
    expires_at: datetime


class DevelopmentOutbox:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], DevelopmentDelivery] = {}
        self._lock = RLock()

    def deliver(self, email: str, purpose: str, token: str, expires_at: datetime) -> None:
        with self._lock:
            self._items[(email, purpose)] = DevelopmentDelivery(
                email=email, purpose=purpose, token=token, expires_at=expires_at
            )

    def latest(self, email: str, purpose: str, now: datetime) -> DevelopmentDelivery | None:
        with self._lock:
            item = self._items.get((email, purpose))
            return item if item and item.expires_at > now else None

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


development_outbox = DevelopmentOutbox()
