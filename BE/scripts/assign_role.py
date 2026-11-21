"""Trusted operator command for role assignment; no public escalation endpoint."""

from __future__ import annotations

import argparse

from sqlalchemy import select

from BE.app.core.config import get_settings
from BE.app.db.models import AccountModel, RoleAssignmentModel, SecurityAuditEventModel
from BE.app.db.session import session_scope
from BE.app.modules.identity.security import normalize_email


ROLES = {"traveler", "data_curator", "administrator"}


def assign_role(email: str, role: str) -> str:
    if role not in ROLES:
        raise ValueError(f"role must be one of {sorted(ROLES)}")
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        account = session.scalar(select(AccountModel).where(
            AccountModel.email_normalized == normalize_email(email)
        ))
        if not account:
            raise ValueError("account not found")
        assignment = session.scalar(select(RoleAssignmentModel).where(
            RoleAssignmentModel.account_id == account.account_id,
            RoleAssignmentModel.role == role,
        ))
        if assignment:
            assignment.revoked_at = None
        else:
            session.add(RoleAssignmentModel(account_id=account.account_id, role=role))
        session.add(SecurityAuditEventModel(
            account_id=account.account_id,
            category="role_assignment",
            outcome="success",
            correlation_id="trusted-operator-script",
            metadata_json={"role": role},
        ))
        return str(account.account_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ROLES))
    args = parser.parse_args()
    print(f"account_id={assign_role(args.email, args.role)} role={args.role}")


if __name__ == "__main__":
    main()
