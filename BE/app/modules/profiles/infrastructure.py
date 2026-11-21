"""Profile persistence helpers."""

from sqlalchemy.orm import Session

from BE.app.db.models import TravelerProfileModel


def owned_profile(session: Session, account_id, *, lock: bool = False):
    query = session.query(TravelerProfileModel).filter_by(account_id=account_id)
    return query.with_for_update().one_or_none() if lock else query.one_or_none()
