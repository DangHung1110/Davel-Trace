"""Purge only expired soft-deleted trip aggregates; repeat-safe."""

from datetime import datetime, timezone

from sqlalchemy import select

from BE.app.core.config import get_settings
from BE.app.db.models import TripLifecycleEventModel, TripModel
from BE.app.db.session import session_scope


def purge_due_trips() -> int:
    count = 0
    with session_scope(get_settings().database_url) as session:
        rows = list(session.scalars(select(TripModel).where(
            TripModel.lifecycle_state == "deleted",
            TripModel.purge_after <= datetime.now(timezone.utc),
        ).with_for_update(skip_locked=True)))
        for row in rows:
            session.add(TripLifecycleEventModel(
                trip_id=None, account_id=row.account_id, event_type="purged",
                outcome="success", correlation_id="maintenance-purge",
                metadata_json={"subject_ref": str(row.trip_id)[:8]},
            ))
            session.delete(row)
            count += 1
    return count


if __name__ == "__main__":
    print(f"purged={purge_due_trips()}")
