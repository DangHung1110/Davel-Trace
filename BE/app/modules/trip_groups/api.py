"""Authenticated HTTP endpoints for private trip groups."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from BE.app.core.config import get_settings
from BE.app.db.session import session_scope
from BE.app.modules.ai_assistance.service import AiAssistanceService
from BE.app.modules.catalog.domain import CatalogUnavailable
from BE.app.modules.catalog.infrastructure import load_catalog
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.services.llm import LLMError

from .service import TripGroupService, require_trip_group

router = APIRouter(prefix="/v1/trip-groups", tags=["trip-groups"])
Actor = Annotated[Principal, Depends(current_principal)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class JoinBody(Body):
    code: str = Field(min_length=16, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)


class GuestBody(Body):
    display_name: str = Field(min_length=1, max_length=120)


class SuggestionBody(Body):
    member_id: UUID | None = None
    poi_id: str | None = Field(default=None, min_length=1, max_length=128)
    kind: Literal["place", "interest", "avoid", "food", "accessibility"]
    title: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=500)
    priority: bool = False
    use_profile: bool = False


class ToggleBody(Body):
    enabled: bool


class SuggestionTextBody(Body):
    text: str = Field(min_length=3, max_length=1600)


class SuggestionsBody(Body):
    items: list[SuggestionBody] = Field(min_length=1, max_length=20)


class MessageBody(Body):
    text: str = Field(default="", max_length=2000)
    poi_id: str | None = Field(default=None, min_length=1, max_length=128)
    reply_to_id: UUID | None = None


class PinBody(Body):
    message_id: UUID | None


class ExpenseBody(Body):
    payer_id: UUID
    member_ids: list[UUID] = Field(min_length=1, max_length=20)
    kind: Literal["expense", "settlement"] = "expense"
    label: str = Field(min_length=1, max_length=200)
    amount_vnd: int = Field(gt=0, le=10**12, strict=True)
    version: int | None = Field(default=None, ge=1)


@router.get("")
def list_groups(current: Actor):
    return TripGroupService().list(current.account_id)


@router.post("/join")
def join(body: JoinBody, current: Actor):
    return TripGroupService().join(current.account_id, body.code, body.display_name)


@router.put("/{trip_id}")
def enable(trip_id: UUID, current: Actor):
    return TripGroupService().enable(current.account_id, trip_id)


@router.get("/{trip_id}")
def group(trip_id: UUID, current: Actor):
    return TripGroupService().detail(current.account_id, trip_id)


@router.post("/{trip_id}/invites", status_code=201)
def create_invite(trip_id: UUID, current: Actor):
    return TripGroupService().create_invite(current.account_id, trip_id)


@router.get("/{trip_id}/invites")
def list_invites(trip_id: UUID, current: Actor):
    return TripGroupService().invites(current.account_id, trip_id)


@router.delete("/{trip_id}/invites/{invite_id}")
def revoke_invite(trip_id: UUID, invite_id: UUID, current: Actor):
    return TripGroupService().revoke_invite(current.account_id, trip_id, invite_id)


@router.post("/{trip_id}/guests", status_code=201)
def add_guest(trip_id: UUID, body: GuestBody, current: Actor):
    return TripGroupService().add_guest(current.account_id, trip_id, body.display_name)


@router.delete("/{trip_id}/members/{member_id}", status_code=204)
def remove_member(trip_id: UUID, member_id: UUID, current: Actor):
    TripGroupService().remove_member(current.account_id, trip_id, member_id)
    return Response(status_code=204)


@router.post("/{trip_id}/suggestions", status_code=201)
def suggest(trip_id: UUID, body: SuggestionBody, current: Actor):
    return TripGroupService().suggest(current.account_id, trip_id, body.model_dump())


@router.post("/{trip_id}/suggestions/bulk", status_code=201)
def confirm_suggestions(trip_id: UUID, body: SuggestionsBody, current: Actor):
    return TripGroupService().suggest_many(
        current.account_id, trip_id, [item.model_dump() for item in body.items]
    )


@router.post("/{trip_id}/suggestions/interpret")
def interpret_suggestions(trip_id: UUID, body: SuggestionTextBody, current: Actor):
    settings = get_settings()
    with session_scope(settings.database_url) as session:
        trip = require_trip_group(session, current.account_id, trip_id)
        if trip.lifecycle_state != "available":
            raise IdentityError("GROUP_READ_ONLY", "Chuyến này chỉ có thể xem.", 409)
    try:
        places = {
            row["poi_id"]: row
            for row in load_catalog()["pois"] if row.get("status") != "excluded"
        }
        draft = AiAssistanceService(settings).interpret(
            body.text, catalog=list(places.values()), trip_context={}
        )
    except (LLMError, CatalogUnavailable, ValueError) as exc:
        raise IdentityError(
            "GROUP_INTERPRETATION_UNAVAILABLE",
            "Chưa đọc được góp ý lúc này. Bạn có thể chọn từng mục.",
            503,
        ) from exc
    hard = draft["hard_constraints"]
    soft = draft["soft_preferences"]
    items = [
        {"kind": kind, "poi_id": poi_id, "title": places[poi_id]["name"]}
        for key, kind in (("must_visit", "place"), ("avoid", "avoid"))
        for poi_id in hard.get(key, []) if poi_id in places
    ]
    items.extend(
        {"kind": kind, "title": title[:200]}
        for values, kind in (
            (hard.get("accessibility", []), "accessibility"),
            (soft.get("activities", []), "interest"),
            (soft.get("food_preferences", []), "food"),
        )
        for title in values
    )
    items.extend(
        {
            "kind": "avoid" if item["constraint"] == "avoid" else "place",
            "title": item["name"][:200],
            "candidates": item["candidates"],
        }
        for item in draft.get("place_resolutions", []) if item.get("candidates")
    )
    return {"items": items[:20], "unresolved": draft.get("unresolved", [])}


@router.delete("/{trip_id}/suggestions/{suggestion_id}")
def retract_suggestion(trip_id: UUID, suggestion_id: UUID, current: Actor):
    return TripGroupService().suggestion_action(
        current.account_id, trip_id, suggestion_id, "delete"
    )


@router.put("/{trip_id}/suggestions/{suggestion_id}/vote")
def vote(trip_id: UUID, suggestion_id: UUID, body: ToggleBody, current: Actor):
    return TripGroupService().suggestion_action(
        current.account_id,
        trip_id,
        suggestion_id,
        "vote",
        body.enabled,
    )


@router.put("/{trip_id}/suggestions/{suggestion_id}/approval")
def approve(trip_id: UUID, suggestion_id: UUID, body: ToggleBody, current: Actor):
    return TripGroupService().suggestion_action(
        current.account_id,
        trip_id,
        suggestion_id,
        "approval",
        body.enabled,
    )


@router.get("/{trip_id}/chat")
def list_messages(
    trip_id: UUID,
    current: Actor,
    before: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    return TripGroupService().chat(current.account_id, trip_id, before, limit)


@router.post("/{trip_id}/chat", status_code=201)
def send_message(trip_id: UUID, body: MessageBody, current: Actor):
    return TripGroupService().post_message(
        current.account_id, trip_id, body.text, body.poi_id, body.reply_to_id
    )


@router.put("/{trip_id}/chat/pinned-meeting")
def pin_meeting(trip_id: UUID, body: PinBody, current: Actor):
    return TripGroupService().pin_meeting(current.account_id, trip_id, body.message_id)


@router.post("/{trip_id}/expenses", status_code=201)
def add_expense(
    trip_id: UUID,
    body: ExpenseBody,
    current: Actor,
    key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=128
    ),
):
    return TripGroupService().save_expense(
        current.account_id, trip_id, body.model_dump(), key=key
    )


@router.patch("/{trip_id}/expenses/{expense_id}")
def edit_expense(trip_id: UUID, expense_id: UUID, body: ExpenseBody, current: Actor):
    return TripGroupService().save_expense(
        current.account_id, trip_id, body.model_dump(), expense_id
    )


@router.delete("/{trip_id}/expenses/{expense_id}")
def delete_expense(trip_id: UUID, expense_id: UUID, current: Actor):
    return TripGroupService().delete_expense(current.account_id, trip_id, expense_id)


@router.get("/{trip_id}/expenses/{expense_id}/history")
def expense_history(trip_id: UUID, expense_id: UUID, current: Actor):
    return TripGroupService().expense_history(current.account_id, trip_id, expense_id)
