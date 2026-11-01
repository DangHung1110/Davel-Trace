"""PostgreSQL identity repository helpers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from BE.app.db.models import (
    AccountModel,
    IdentitySessionModel,
    OneTimeActionModel,
    RoleAssignmentModel,
)
from BE.app.modules.identity.security import secret_hash


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def account_by_email(self, email: str, *, lock: bool = False) -> AccountModel | None:
        statement = select(AccountModel).where(AccountModel.email_normalized == email)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def account(self, account_id, *, lock: bool = False) -> AccountModel | None:
        statement = select(AccountModel).where(AccountModel.account_id == account_id)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def roles(self, account_id) -> list[str]:
        return list(self.session.scalars(select(RoleAssignmentModel.role).where(
            RoleAssignmentModel.account_id == account_id,
            RoleAssignmentModel.revoked_at.is_(None),
        )))

    def session_by_access(self, token: str) -> IdentitySessionModel | None:
        return self.session.scalar(select(IdentitySessionModel).where(
            IdentitySessionModel.access_hash == secret_hash(token)
        ))

    def session_by_refresh(self, token: str) -> IdentitySessionModel | None:
        return self.session.scalar(select(IdentitySessionModel).where(
            IdentitySessionModel.refresh_hash == secret_hash(token)
        ))

    def usable_action(self, token: str, purpose: str, now: datetime) -> OneTimeActionModel | None:
        return self.session.scalar(select(OneTimeActionModel).where(
            OneTimeActionModel.token_hash == secret_hash(token),
            OneTimeActionModel.purpose == purpose,
            OneTimeActionModel.used_at.is_(None),
            OneTimeActionModel.superseded_at.is_(None),
            OneTimeActionModel.expires_at > now,
        ).with_for_update())
