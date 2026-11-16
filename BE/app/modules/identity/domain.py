"""Identity domain values with no HTTP or database dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    account_id: UUID
    session_id: UUID
    roles: frozenset[str]
    correlation_id: str

    def requires(self, *allowed: str) -> "Principal":
        if not self.roles.intersection(allowed):
            raise PermissionError("required role is missing")
        return self


def account_public(account, roles: list[str], session_count: int = 0) -> dict:
    return {
        "account_id": str(account.account_id),
        "email": account.email_normalized,
        "status": account.status,
        "verified_at": account.verified_at.isoformat() if account.verified_at else None,
        "roles": roles,
        "active_session_count": session_count,
        "created_at": account.created_at.isoformat(),
    }


def session_public(session, *, current: bool = False) -> dict:
    return {
        "session_id": str(session.session_id),
        "device_label": session.device_label,
        "client_kind": session.client_kind,
        "created_at": session.created_at.isoformat(),
        "last_seen_at": session.last_seen_at.isoformat(),
        "refresh_expires_at": session.refresh_expires_at.isoformat(),
        "current": current,
    }
