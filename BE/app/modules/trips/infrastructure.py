"""Trip persistence and idempotency helpers."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from BE.app.db.models import MutationReceiptModel, TripModel
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


def request_fingerprint(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def receipt(session, account_id, operation, scope, key, fingerprint):
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    found = session.scalar(select(MutationReceiptModel).where(
        MutationReceiptModel.account_id == account_id,
        MutationReceiptModel.operation == operation,
        MutationReceiptModel.resource_scope == scope,
        MutationReceiptModel.key_hash == key_hash,
    ))
    if found and found.request_fingerprint != fingerprint:
        raise IdentityError("IDEMPOTENCY_CONFLICT", "Khóa thao tác đã được dùng cho dữ liệu khác.", 409)
    return found, key_hash


def save_receipt(session, account_id, operation, scope, key_hash, fingerprint, result_id, status=200):
    session.add(MutationReceiptModel(
        account_id=account_id, operation=operation, resource_scope=scope,
        key_hash=key_hash, request_fingerprint=fingerprint,
        result_resource_id=str(result_id), response_status=status,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    ))
