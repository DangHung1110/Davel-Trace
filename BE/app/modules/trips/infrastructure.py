"""Trip persistence and idempotency helpers."""

from sqlalchemy import select

from BE.app.core.mutations import receipt, request_fingerprint, save_receipt
from BE.app.db.models import TripModel
from BE.app.modules.identity.service import IdentityError


def owned_trip(session, account_id, trip_id, *, lock=False, include_deleted=False):
    query = select(TripModel).where(TripModel.trip_id == trip_id, TripModel.account_id == account_id)
    if not include_deleted:
        query = query.where(TripModel.lifecycle_state.notin_(("deleted", "purged")))
    if lock:
        query = query.with_for_update()
    trip = session.scalar(query)
    if not trip:
        raise IdentityError("NOT_FOUND", "Không tìm thấy chuyến đi.", 404)
    return trip
__all__ = ["owned_trip", "receipt", "request_fingerprint", "save_receipt"]
