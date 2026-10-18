"""POST /v1/parse (T020, lane C). NL -> TripRequest per contracts/api.md.

In: {"text": "...", "user_id": "u1"}. Out: TripRequest JSON (+
assumptions/soft_prefs/hard_constraints/uncertainties) OR
{"needs_clarification": [...]} when the city is missing.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from BE.app.services import parser as parser_svc

router = APIRouter(prefix="/v1", tags=["parse"])


class ParseIn(BaseModel):
    text: str
    user_id: str = "u1"


@router.post("/parse")
def parse(body: ParseIn) -> dict:
    out = parser_svc.parse(body.text, body.user_id)
    if "needs_clarification" in out:
        return {"needs_clarification": out["needs_clarification"],
                "assumptions": out.get("assumptions", []),
                "soft_prefs": out.get("soft_prefs", [])}
    trip = out["trip"]
    return {**trip.model_dump(), "assumptions": out.get("assumptions", []),
            "soft_prefs": out.get("soft_prefs", []),
            "hard_constraints": out.get("hard_constraints", []),
            "uncertainties": out.get("uncertainties", [])}
