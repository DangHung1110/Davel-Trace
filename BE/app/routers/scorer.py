"""POST /v1/score-transition (S7, contracts/api.md PATM pre-check).

Deterministic, offline transition score for a POI pair: the scorer service
answers from the LightGBM model when present, else the nac-1 rule. No
network, no LLM.

In: `{"a": {poi+ctx}, "b": {poi+ctx}, "user": {...}}` (contracts/api.md).
Out: `{"score": float}` (positive = a -> b preferred, <5ms target).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.services import scorer as scorer_svc

router = APIRouter(prefix="/v1", tags=["scorer"])


class ScoreTransitionIn(BaseModel):
    a: dict
    b: dict
    user: dict


@router.post("/score-transition")
def score_transition_endpoint(body: ScoreTransitionIn):
    return {"score": scorer_svc.score_transition(body.a, body.b, body.user)}
