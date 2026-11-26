from datetime import date, time
from uuid import UUID, uuid4

import pytest

from BE.app.db.base import Base
from BE.app.core.config import AppMode, Settings
from BE.app.db.models import AccountModel, TravelerProfileModel, TripModel
from BE.app.db.session import get_engine, session_scope
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.identity.domain import Principal
from BE.app.modules.trip_groups import api as group_api
from BE.app.modules.trip_groups.models import GroupInviteModel
from BE.app.modules.trip_groups.service import (
    TripGroupService,
    group_actual_spend,
    group_planning_inputs,
    post_plan_event,
)


@pytest.fixture
def group(tmp_path):
    url = f"sqlite:///{tmp_path / 'groups.db'}"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    with session_scope(url) as session:
        leader, member, outsider = uuid4(), uuid4(), uuid4()
        for account_id in (leader, member, outsider):
            session.add(
                AccountModel(
                    account_id=account_id,
                    email_normalized=f"{account_id}@example.test",
                    password_hash="fixture",
                    status="active",
                )
            )
        session.flush()
        for account_id, name in [(leader, "Hà"), (member, "Minh")]:
            session.add(
                TravelerProfileModel(
                    account_id=account_id, display_name=name, fitness=1
                )
            )
        trip = TripModel(
            account_id=leader,
            title="Gia đình đi Đà Nẵng",
            traveler_count=10,
            start_date=date(2027, 1, 8),
            end_date=date(2027, 1, 8),
            day_start=time(8),
            day_end=time(17),
            indicative_budget=2_000_000,
            profile_version=1,
            profile_snapshot={},
        )
        session.add(trip)
        session.flush()
        trip_id = trip.trip_id
    service = TripGroupService(url)
    service.enable(leader, trip_id)
    yield service, trip_id, leader, member, outsider
    engine.dispose()


def test_private_membership_one_time_invite_and_revocation(group):
    service, trip, leader, member, outsider = group
    assert service.enable(leader, trip)["traveler_count"] == 10
    with pytest.raises(IdentityError) as error:
        service.detail(outsider, trip)
    assert error.value.status == 404
    code = service.create_invite(leader, trip)
    with session_scope(service.database_url) as session:
        invite = session.get(GroupInviteModel, UUID(code["id"]))
        assert invite.code_hash != code["code"]
    joined = service.join(member, code["code"], None)
    assert joined["role"] == "member"
    assert service.join(member, code["code"], None)["member_id"] == joined["member_id"]
    assert service.list(member)["items"][0]["role"] == "member"
    with pytest.raises(IdentityError):
        service.join(outsider, code["code"], None)
    with pytest.raises(IdentityError) as error:
        service.create_invite(member, trip)
    assert error.value.status == 403
    active = service.create_invite(leader, trip)
    service.revoke_invite(leader, trip, UUID(active["id"]))
    with pytest.raises(IdentityError):
        service.join(outsider, active["code"], None)
    service.remove_member(leader, trip, UUID(joined["member_id"]))
    with pytest.raises(IdentityError):
        service.detail(member, trip)
    assert not service.list(member)["items"]
    assert any(not row["active"] for row in service.detail(leader, trip)["members"])


def test_aggregation_preserves_attendee_preferences_and_leader_approval(
    group, monkeypatch
):
    service, trip, leader, member, _outsider = group
    monkeypatch.setattr(
        "BE.app.modules.trip_groups.service._catalog_place",
        lambda poi_id: {"name": poi_id},
    )
    invited = service.join(member, service.create_invite(leader, trip)["code"], None)
    guest = service.add_guest(leader, trip, "Bé An")["members"][-1]

    def suggest(account, kind, *, poi=None, member_id=None, title="", profile=False):
        return service.suggest(
            account,
            trip,
            {
                "member_id": member_id,
                "poi_id": poi,
                "kind": kind,
                "title": title,
                "notes": "",
                "priority": True,
                "use_profile": profile,
            },
        )

    suggest(leader, "place", poi="beach", member_id=UUID(guest["id"]))
    suggest(member, "place", poi="museum")
    summary = suggest(leader, "place", poi="beach")
    shared = [row for row in summary["suggestions"] if row["poi_id"] == "beach"]
    assert all(row["support_count"] == 2 for row in shared)
    with pytest.raises(IdentityError):
        suggest(member, "place", poi="park", member_id=UUID(guest["id"]))
    with pytest.raises(IdentityError):
        service.suggestion_action(member, trip, UUID(shared[0]["id"]), "approval", True)
    service.suggestion_action(leader, trip, UUID(shared[0]["id"]), "approval", True)
    suggest(member, "interest", profile=True)
    with session_scope(service.database_url) as session:
        inputs = group_planning_inputs(session, trip)
        assert inputs["priority_poi_ids"] == ["beach", "museum"]
        assert inputs["priority_by_attendee"].count(["beach"]) == 2
        assert inputs["must_visit"] == ["beach"]
        assert inputs["fitness"] == 1
    assert invited["traveler_count"] == 10


def test_shared_expense_exact_split_payment_audit_and_removed_member_balance(group):
    service, trip, leader, member, _outsider = group
    owner_id = UUID(service.detail(leader, trip)["member_id"])
    member_id = UUID(
        service.join(member, service.create_invite(leader, trip)["code"], None)[
            "member_id"
        ]
    )
    expense = {
        "payer_id": owner_id,
        "member_ids": [member_id, owner_id],
        "amount_vnd": 100_001,
        "kind": "expense",
        "label": "Taxi",
    }
    recorded = service.save_expense(leader, trip, expense, key="group-taxi-1")
    retried = service.save_expense(leader, trip, expense, key="group-taxi-1")
    assert retried["expenses"] == recorded["expenses"]
    row = recorded["expenses"][0]
    expense_id = UUID(row["id"])
    assert sum(row["split"].values()) == 100_001
    assert recorded["balance"][str(owner_id)] == row["split"][str(member_id)]
    with pytest.raises(IdentityError):
        service.save_expense(member, trip, expense, expense_id)
    payment = {
        "payer_id": member_id,
        "member_ids": [owner_id],
        "kind": "settlement",
        "amount_vnd": row["split"][str(member_id)],
        "label": "Hoàn tiền taxi",
    }
    settled = service.save_expense(member, trip, payment)
    assert settled["balance"] == {str(owner_id): 0, str(member_id): 0}
    with pytest.raises(IdentityError):
        service.save_expense(member, trip, payment)
    with session_scope(service.database_url) as session:
        assert group_actual_spend(session, trip) == 100_001
    service.remove_member(member, trip, member_id)
    assert service.detail(leader, trip)["spent_vnd"] == 100_001
    service.delete_expense(leader, trip, expense_id)
    history = service.expense_history(leader, trip, expense_id)
    assert [item["action"] for item in history["items"]] == ["delete", "create"]


def test_group_fund_blocks_overdraft_and_keeps_personal_balance_separate(group):
    service, trip, leader, member, outsider = group
    owner_id = UUID(service.detail(leader, trip)["member_id"])
    member_id = UUID(
        service.join(member, service.create_invite(leader, trip)["code"], None)["member_id"]
    )
    contribution = {"amount_vnd": 30_001, "note": "Chuyển khoản ngoài app"}
    first = service.save_contribution(member, trip, contribution, "fund-contribution-1")
    assert first["fund"]["contributed_vnd"] == 30_001
    assert first["fund"]["balance_vnd"] == 30_001
    assert first["spent_vnd"] == 0
    assert first["expenses"] == []
    assert first["balance"] == {}
    assert first["fund"]["contributions"][0]["payer_id"] == str(member_id)
    assert first["fund"]["contributions"][0]["note"] == contribution["note"]
    retried = service.save_contribution(member, trip, contribution, "fund-contribution-1")
    assert retried["fund"]["contributions"] == first["fund"]["contributions"]
    with pytest.raises(IdentityError) as reused:
        service.save_contribution(
            member, trip, {"amount_vnd": 50_000}, "fund-contribution-1"
        )
    assert reused.value.code == "IDEMPOTENCY_CONFLICT"
    with pytest.raises(IdentityError) as forbidden:
        service.save_contribution(
            member, trip, {"amount_vnd": 1_000, "member_id": owner_id}, "fund-on-behalf-1"
        )
    assert forbidden.value.status == 403
    with pytest.raises(IdentityError) as not_member:
        service.save_contribution(outsider, trip, contribution, "fund-outsider-1")
    assert not_member.value.status == 404
    entry = {
        "kind": "expense",
        "source": "fund",
        "payer_id": owner_id,
        "member_ids": [owner_id, member_id],
        "amount_vnd": 20_001,
        "label": "Vé gửi xe",
        "note": "Xe ghé Bảo tàng Chăm",
    }
    with pytest.raises(IdentityError) as member_spend:
        service.save_expense(member, trip, {**entry, "payer_id": member_id})
    assert member_spend.value.status == 403
    with pytest.raises(IdentityError) as overdraft:
        service.save_expense(leader, trip, {**entry, "amount_vnd": 30_002})
    assert overdraft.value.code == "GROUP_FUND_INSUFFICIENT"
    paid = service.save_expense(leader, trip, entry, key="fund-expense-1")
    row = paid["expenses"][0]
    expense_id = UUID(row["id"])
    assert row["source"] == "fund"
    assert row["note"] == entry["note"]
    assert sorted(row["split"].values()) == [10_000, 10_001]
    assert paid["fund"]["balance_vnd"] == 10_000
    assert paid["fund"]["spent_vnd"] == paid["spent_vnd"] == 20_001
    assert paid["balance"] == {}
    contribution_id = UUID(first["fund"]["contributions"][0]["id"])
    with pytest.raises(IdentityError) as spent_contribution:
        service.delete_expense(member, trip, contribution_id)
    assert spent_contribution.value.code == "GROUP_FUND_INSUFFICIENT"
    with pytest.raises(IdentityError):
        service.save_expense(leader, trip, {**entry, "source": "personal"}, expense_id)
    updated = service.save_expense(
        leader, trip, {**entry, "amount_vnd": 25_001, "version": 1}, expense_id
    )
    assert updated["fund"]["balance_vnd"] == 5_000
    personal = service.save_expense(leader, trip, {**entry, "source": "personal"})
    assert personal["fund"]["balance_vnd"] == 5_000
    assert personal["balance"] != {}
    with session_scope(service.database_url) as session:
        assert group_actual_spend(session, trip) == 45_002
    assert service.delete_expense(leader, trip, expense_id)["fund"]["balance_vnd"] == 30_001
    assert service.delete_expense(member, trip, contribution_id)["fund"]["balance_vnd"] == 0
    history = service.expense_history(member, trip, contribution_id)["items"]
    assert [revision["action"] for revision in history] == ["delete", "create"]


def test_group_demo_contribution_is_explicit_and_self_only(group, monkeypatch):
    service, trip, leader, member, _ = group
    member_id = UUID(
        service.join(member, service.create_invite(leader, trip)["code"], None)["member_id"]
    )
    enabled = "BE.app.modules.trip_groups.service._demo_fund_payment_available"
    contribution = {"amount_vnd": 1_000, "method": "demo"}
    monkeypatch.setattr(enabled, lambda: False)
    assert service.detail(member, trip)["fund"]["demo_payment_available"] is False
    with pytest.raises(IdentityError) as disabled:
        service.save_contribution(member, trip, contribution, "fund-demo-1")
    assert disabled.value.code == "GROUP_DEMO_PAYMENT_UNAVAILABLE"
    monkeypatch.setattr(enabled, lambda: True)
    with pytest.raises(IdentityError):
        service.save_contribution(
            leader, trip, {**contribution, "member_id": member_id}, "fund-demo-2"
        )
    simulated = service.save_contribution(member, trip, contribution, "fund-demo-3")
    assert simulated["fund"]["demo_payment_available"] is True
    assert simulated["fund"]["contributions"][0]["method"] == "demo"
    assert simulated["fund"]["balance_vnd"] == 1_000


def test_chat_cursor_is_scoped_and_system_event_is_idempotent(group):
    service, trip, leader, member, outsider = group
    service.join(member, service.create_invite(leader, trip)["code"], None)
    first = service.post_message(member, trip, "Mình đến rồi", None)
    with session_scope(service.database_url) as session:
        post_plan_event(session, trip, "Có lịch mới", "plan:example")
    with session_scope(service.database_url) as session:
        post_plan_event(session, trip, "Có lịch mới", "plan:example")
    latest = service.chat(member, trip, None, 1)
    assert latest["has_more"]
    assert len(latest["items"]) == 1
    assert latest["items"][0]["kind"] == "system"
    assert service.chat(member, trip, UUID(latest["items"][0]["id"]), 1)["items"] == [
        first
    ]
    with pytest.raises(IdentityError):
        service.chat(outsider, trip, None, 50)


def test_chat_reply_and_pinned_meeting_permissions(group, monkeypatch):
    service, trip, leader, member, outsider = group
    service.join(member, service.create_invite(leader, trip)["code"], None)
    monkeypatch.setattr(
        "BE.app.modules.trip_groups.service._catalog_place",
        lambda poi_id: {"name": "Cầu Rồng"},
    )
    meeting = service.post_message(member, trip, "Gặp nhau ở đây", "dragon")
    meeting_id = UUID(meeting["id"])
    answer = service.post_message(leader, trip, "Đồng ý", None, meeting_id)
    assert answer["reply"] == {"id": meeting["id"], "text": "Gặp nhau ở đây"}
    assert service.chat(member, trip, None, 50)["items"][-1] == answer
    with pytest.raises(IdentityError) as error:
        service.pin_meeting(member, trip, meeting_id)
    assert error.value.status == 403
    with pytest.raises(IdentityError):
        service.pin_meeting(leader, trip, UUID(answer["id"]))
    assert service.pin_meeting(leader, trip, meeting_id)["pinned_meeting"][
        "poi_id"
    ] == "dragon"
    assert service.detail(member, trip)["pinned_meeting"]["id"] == meeting["id"]
    assert service.pin_meeting(leader, trip, None)["pinned_meeting"] is None
    with session_scope(service.database_url) as session:
        original = session.get(TripModel, trip)
        another = TripModel(
            account_id=outsider,
            title="Chuyến khác",
            traveler_count=1,
            start_date=original.start_date,
            end_date=original.end_date,
            day_start=original.day_start,
            day_end=original.day_end,
            profile_version=1,
            profile_snapshot={},
        )
        session.add(another)
        session.flush()
        outsider_second_trip = another.trip_id
    service.enable(outsider, outsider_second_trip)
    with pytest.raises(IdentityError):
        service.post_message(outsider, outsider_second_trip, "Thử", None, meeting_id)


def test_member_idea_parsing_does_not_edit_the_group(group, monkeypatch):
    service, trip, leader, member, outsider = group
    service.join(member, service.create_invite(leader, trip)["code"], None)
    settings = Settings(app_mode=AppMode.test, database_url=service.database_url)
    monkeypatch.setattr(group_api, "get_settings", lambda: settings)
    monkeypatch.setattr(
        group_api, "load_catalog",
        lambda: {"pois": [{"poi_id": "museum", "name": "Bảo tàng Chăm"}]},
    )
    seen = []

    def interpret(_service, text, *, catalog, trip_context):
        assert trip_context == {}
        seen.append(text)
        return {
            "hard_constraints": {"must_visit": ["museum"]},
            "soft_preferences": {"food_preferences": ["Mì Quảng"]},
        }

    monkeypatch.setattr(group_api.AiAssistanceService, "interpret", interpret)
    text = group_api.SuggestionTextBody(text="Ghé Bảo tàng Chăm và ăn mì Quảng")
    with pytest.raises(IdentityError):
        group_api.interpret_suggestions(
            trip, text, Principal(outsider, uuid4(), frozenset(), "test"),
        )
    assert not seen
    proposal = group_api.interpret_suggestions(
        trip, text, Principal(member, uuid4(), frozenset(), "test"),
    )
    assert seen == [text.text]
    assert proposal["items"] == [
        {"kind": "place", "poi_id": "museum", "title": "Bảo tàng Chăm"},
        {"kind": "food", "title": "Mì Quảng"},
    ]
    assert not service.detail(member, trip)["suggestions"]
