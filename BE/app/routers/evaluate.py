"""POST /v1/evaluate (T052, lane C wiring; contracts/api.md, quickstart S4).

Tier-1 deterministic evaluator: `BE/eval/metrics.evaluate` runs the canonical
`BE.app.services.gate.CHECKS` registry. No LLM, no new dependencies.

In: `{"itinerary", "trip"}` exactly per contracts/api.md. The POI snapshot +
route matrix come from the configured snapshot dir — the same source
POST /v1/itinerary plans against, so a cached itinerary can be re-evaluated
without resending committed POI/matrix data.

Out: `{"gate": {"passed", "violations"}, "soft": {...}, "reward": 0.0}`.
Contract rule (FR-035): a failing gate yields NO quality scores (`soft == {}`).
`violations` names the failed checks; `soft` holds the six quality scores.
Missing snapshot -> 503 SNAPSHOT_MISSING envelope.
"""

from __future__ import annotations

import json
import os

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.config import get_settings
from BE.app.routers import error
from BE.eval.metrics import evaluate as tier1_evaluate

router = APIRouter(prefix="/v1", tags=["evaluate"])


class EvaluateIn(BaseModel):
    itinerary: dict
    trip: dict


def load_eval_context(snapshot_dir: str) -> tuple[dict, dict] | None:
    """(pois by id, matrix cells) from the snapshot; None when pois missing."""
    try:
        with open(os.path.join(snapshot_dir, "pois.json"), encoding="utf-8") as f:
            pois = {p["poi_id"]: p for p in json.load(f)["pois"]}
    except (FileNotFoundError, NotADirectoryError):
        return None
    try:
        with open(os.path.join(snapshot_dir, "matrix.json"), encoding="utf-8") as f:
            cells = json.load(f).get("cells", {})
    except (FileNotFoundError, NotADirectoryError):
        cells = {}
    return pois, cells


@router.post("/evaluate")
def evaluate_endpoint(body: EvaluateIn):
    settings = get_settings()
    ctx = load_eval_context(settings.snapshot_dir)
    if ctx is None:
        return error("SNAPSHOT_MISSING",
                     f"snapshot dir {settings.snapshot_dir} chua co (doi lane A T003b)",
                     503)
    pois, matrix = ctx
    report = tier1_evaluate(body.itinerary, body.trip, pois, matrix)
    return {"gate": report["gate"], "soft": report["soft"], "reward": 0.0}
