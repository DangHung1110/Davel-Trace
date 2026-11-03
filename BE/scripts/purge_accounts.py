"""Idempotently purge accounts whose 30-day grace period has elapsed.

Run manually: python -m BE.scripts.purge_accounts
"""

from __future__ import annotations

from sqlalchemy import delete, select

from BE.app.core.config import get_settings
from BE.app.db.models import (
    AccountModel,
    ExportRequestModel,
    IdentitySessionModel,
    OneTimeActionModel,
    PasswordHistoryModel,
    RoleAssignmentModel,
    ActiveTripSelectionModel,
    MutationReceiptModel,
    TravelerProfileModel,
    TripActivityModel,
    TripDayModel,
    TripLifecycleEventModel,
    TripModel,
)
from BE.app.db.session import session_scope
from BE.app.modules.identity.service import now_utc
from BE.app.modules.identity.security import secret_hash


def purge_due_accounts() -> int:
    settings = get_settings()
    now = now_utc()
    count = 0
    with session_scope(settings.database_url) as session:
        session.execute(delete(OneTimeActionModel).where(
            OneTimeActionModel.expires_at <= now,
        ))
        session.execute(delete(ExportRequestModel).where(
            ExportRequestModel.expires_at.is_not(None),
            ExportRequestModel.expires_at <= now,
        ))
        accounts = list(session.scalars(select(AccountModel).where(
            AccountModel.status == "deletion_pending",
            AccountModel.purge_after.is_not(None),
            AccountModel.purge_after <= now,
        ).with_for_update()))
        for account in accounts:
            account_id = account.account_id
            trip_ids = select(TripModel.trip_id).where(
                TripModel.account_id == account_id
            )
            day_ids = select(TripDayModel.day_id).where(
                TripDayModel.trip_id.in_(trip_ids)
            )
            session.execute(delete(TripActivityModel).where(
                TripActivityModel.day_id.in_(day_ids)
            ))
            session.execute(delete(TripDayModel).where(
                TripDayModel.trip_id.in_(trip_ids)
            ))
            session.execute(delete(ActiveTripSelectionModel).where(
                ActiveTripSelectionModel.account_id == account_id
            ))
            session.execute(delete(MutationReceiptModel).where(
                MutationReceiptModel.account_id == account_id
            ))
            session.execute(delete(TripModel).where(
                TripModel.account_id == account_id
            ))
            session.execute(delete(TravelerProfileModel).where(
                TravelerProfileModel.account_id == account_id
            ))
            session.execute(delete(TripLifecycleEventModel).where(
                TripLifecycleEventModel.account_id == account_id
            ))
            for model in (IdentitySessionModel, OneTimeActionModel,
                          PasswordHistoryModel, RoleAssignmentModel,
                          ExportRequestModel):
                session.execute(delete(model).where(model.account_id == account_id))
            account.email_normalized = f"purged-{secret_hash(str(account_id))}@invalid.local"
            account.password_hash = "purged"
            account.status = "purged"
            account.verified_at = None
            account.deletion_requested_at = None
            account.updated_at = now
            account.version += 1
            count += 1
    return count


if __name__ == "__main__":
    print(f"purged_accounts={purge_due_accounts()}")
