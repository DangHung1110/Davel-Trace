"""POST /v1/accept (NOTE(test-local), do NOT PR as-is). "Chốt plan" logging.

The harness operator compares generated plans and accepts the day they would
actually ship. This endpoint persists that decision so future weight-learning
/ RAG work has real preference data instead of synthetic labels:

    BE/data/accepted_days.jsonl   (append-only, one JSON object per line)

Line shape: {ts, query, profile, picked_plan, picked_index, all_plan_ids, note}

Deliberately dumb: no auth (local test tool), no LLM call, no re-scoring. It
only validates that the pick is addressable and writes the line. Anything
richer (reward snapshots, learned weights) belongs in a later feature.

In:  {"query": "...", "profile": "balanced", "plans": [...],
      "picked_index": 0, "note": "optional"}
Out: {"ok": true, "n": <total lines in the log after the append>}

Bad request (empty plans / out-of-range index) -> 400 envelope.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.routers import error

router = APIRouter(prefix="/v1", tags=["accept"])

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data")
DEFAULT_LOG_PATH = os.path.join(_DATA_DIR, "accepted_days.jsonl")

# One writer at a time: the harness fires a single request, but a stray
# double-click must not interleave half-written lines.
_LOCK = threading.Lock()


class AcceptIn(BaseModel):
    query: str = ""
    profile: str = ""
    plans: list[dict] | None = None
    picked_index: int = 0
    note: str | None = None


def log_path() -> str:
    """Accepted-days JSONL path; ACCEPTED_DAYS_PATH overrides (tests)."""
    return os.environ.get("ACCEPTED_DAYS_PATH") or DEFAULT_LOG_PATH


def _count_lines(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except FileNotFoundError:
        return 0


def append_accepted(entry: dict) -> int:
    """Append one JSONL line; -> total number of entries in the log."""
    path = log_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with _LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return _count_lines(path)


@router.post("/accept")
def accept(body: AcceptIn):
    plans = body.plans or []
    if not plans:
        return error("VALIDATION_ERROR", "plans khong duoc rong", 400)
    if not 0 <= body.picked_index < len(plans):
        return error(
            "VALIDATION_ERROR",
            f"picked_index {body.picked_index} ngoai pham vi "
            f"0..{len(plans) - 1}", 400)

    picked = plans[body.picked_index]
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "query": body.query,
        "profile": body.profile,
        "picked_plan": picked,
        "picked_index": body.picked_index,
        "all_plan_ids": [p.get("itinerary_id") for p in plans],
        "note": body.note or "",
    }
    return {"ok": True, "n": append_accepted(entry)}
