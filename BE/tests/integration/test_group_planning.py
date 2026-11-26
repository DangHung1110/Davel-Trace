from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from BE.app.core.config import AppMode, Settings
from BE.app.modules.identity.dependencies import current_principal
from BE.app.modules.identity.domain import Principal
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.planning_lifecycle.service import PlanningLifecycleService
from BE.app.modules.trip_groups import planning_api
from BE.tests.integration.test_trip_groups import group  # noqa: F401


def _principal(account_id):
    return Principal(account_id, uuid4(), frozenset({"traveler"}), "test-group-plan")


def _alternative(*poi_ids):
    return {
        "profile": "balanced",
        "activities": [
            {
                "poi_id": poi_id,
                "name": poi_id,
                "start": f"{9 + rank:02d}:00",
                "end": f"{9 + rank:02d}:30",
            }
            for rank, poi_id in enumerate(poi_ids)
        ],
        "gate": {
            "passed": True,
            "families": {str(index): {"passed": True} for index in range(5)},
        },
        "total_cost": 150_000,
        "total_km": 2.5,
        "private_token": "never include planner evidence in shared view",
    }


@pytest.fixture()
def planning_group(group, monkeypatch):  # noqa: F811
    groups, trip_id, leader_id, member_id, outsider_id = group
    groups.join(member_id, groups.create_invite(leader_id, trip_id)["code"], None)
    settings = Settings(app_mode=AppMode.test, database_url=groups.database_url)
    monkeypatch.setattr(planning_api, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "BE.app.modules.trip_groups.service._catalog_place",
        lambda point: {"name": point},
    )
    captures = []

    def planner(trip, _target, kind):
        captures.append((kind, trip))
        if kind == "replan":
            return {"plans": [_alternative("meeting", "market")]}
        return {
            "plans": [_alternative("beach", "cafe"), _alternative("beach", "museum")]
        }

    service = PlanningLifecycleService(
        settings,
        planner=planner,
        clock=lambda: datetime(2027, 1, 8, 6, tzinfo=timezone.utc),
    )
    actors = {
        name: _principal(account)
        for name, account in (
            ("leader", leader_id),
            ("member", member_id),
            ("outsider", outsider_id),
        )
    }

    def actor(subject: str = Header()):
        return actors[subject]

    app = FastAPI()
    app.include_router(planning_api.router)
    app.dependency_overrides[current_principal] = actor
    app.add_exception_handler(
        IdentityError,
        lambda request, exc: JSONResponse({"error": exc.code}, status_code=exc.status),
    )
    app.state.catalog_reader = lambda: {
        "pois": [
            {"poi_id": point, "name": point, "lat": 16.07, "lon": 108.23 + number / 100}
            for number, point in enumerate(
                ("beach", "cafe", "museum", "meeting", "market")
            )
        ],
        "snapshot": "test-catalog",
    }
    app.state.matrix_reader = dict
    app.state.route_provider = lambda _: None
    app.state.matrix_estimator = lambda stops, matrix: None
    with TestClient(app) as client:
        yield groups, trip_id, service, actors, client, captures


def test_shared_round_covers_different_people_votes_and_leader_publishes(
    planning_group,
):
    groups, trip_id, service, actors, client, captures = planning_group
    leader, member = actors["leader"], actors["member"]
    for user, poi in ((leader, "beach"), (member, "museum")):
        groups.suggest(
            user.account_id,
            trip_id,
            {
                "kind": "place",
                "poi_id": poi,
                "priority": True,
                "title": "",
                "notes": "",
                "use_profile": False,
            },
        )

    before = service.create_planning_request(leader, trip_id, "group-round-1")
    newer = service.create_planning_request(leader, trip_id, "group-round-2")
    assert captures[-1][1]["travelers"] == 10
    assert captures[-1][1]["must_visit"] == []
    assert captures[-1][1]["soft_poi_weights"] == {"beach": 1, "museum": 1}
    path = f"/v1/trip-groups/{trip_id}/plans"
    assert client.get(path, headers={"subject": "outsider"}).status_code == 404
    response = client.get(path, headers={"subject": "member"})
    assert response.status_code == 200
    assert "private_token" not in response.text
    plan = response.json()
    assert plan["active"] is None
    first, second = plan["round"]["alternatives"]
    assert first["priority_matches"] == ["beach", "museum"]
    assert second["priority_unmatched"] == ["museum"]
    assert "request" not in first
    assert first["activities"][0]["lat"] == 16.07
    vote_path = f"{path}/{newer['request_id']}/vote"
    for chosen in (first, first, second):
        assert (
            client.put(
                vote_path,
                headers={"subject": "member"},
                json={
                    "alternative_id": chosen["id"],
                },
            ).status_code
            == 200
        )
    vote = client.get(path, headers={"subject": "member"}).json()["round"]
    assert vote["my_vote"] == second["id"]
    assert [alternative["vote_count"] for alternative in vote["alternatives"]] == [0, 1]
    with pytest.raises(IdentityError) as outdated:
        service.accept(
            leader, before["alternatives"][0]["alternative_id"], "outdated-group-plan"
        )
    assert outdated.value.status == 409
    with pytest.raises(IdentityError) as unauthorized:
        service.accept(member, first["id"], "denied-group-plan")
    assert unauthorized.value.status == 404
    confirmed = service.accept(leader, first["id"], "group-plan-chosen")
    confirmed_id = confirmed["version"]["version_id"]
    published = client.get(path, headers={"subject": "member"}).json()
    assert published["active"]["id"] == confirmed_id
    assert published["round"] is None
    route = client.post(
        f"{path}/route",
        headers={"subject": "member"},
        json={
            "plan_id": confirmed_id,
            "day": 1,
        },
    )
    assert route.status_code == 200
    assert route.json()["quality"] == "interpolated"
    assert (
        client.put(
            vote_path,
            headers={"subject": "member"},
            json={
                "alternative_id": second["id"],
            },
        ).status_code
        == 409
    )
    chat = groups.chat(member.account_id, trip_id, None, 30)
    events = [
        message["text"] for message in chat["items"] if message["kind"] == "system"
    ]
    assert len([text for text in events if text.startswith("Có 2 phương án")]) == 2
    assert len([text for text in events if "đã chốt lịch" in text]) == 1


def test_group_replan_resumes_from_confirmed_place_and_keeps_progress(
    planning_group, monkeypatch
):
    groups, trip_id, service, actors, client, captures = planning_group
    leader = actors["leader"]
    detail = groups.detail(leader.account_id, trip_id)
    groups.save_expense(
        leader.account_id,
        trip_id,
        {
            "payer_id": UUID(detail["member_id"]),
            "member_ids": [UUID(member_row["id"]) for member_row in detail["members"]],
            "kind": "expense",
            "label": "Taxi",
            "amount_vnd": 40_000,
        },
    )
    plan = service.create_planning_request(leader, trip_id, "group-start-round")
    accepted = service.accept(
        leader, plan["alternatives"][0]["alternative_id"], "group-first-plan"
    )
    version_id = accepted["version"]["version_id"]
    path = f"/v1/trip-groups/{trip_id}/plans"
    progress = client.get(path, headers={"subject": "member"}).json()["active"][
        "activities"
    ]
    monkeypatch.setattr(
        "BE.app.modules.planning_lifecycle.service._require_routable_start",
        lambda poi, directory: None,
    )
    args = {
        "source_version_id": version_id,
        "target_count": 2,
        "remaining_from": "2027-01-08T13:00:00+07:00",
        "completed_activity_ids": [progress[0]["id"]],
        "skipped_activity_ids": [progress[1]["id"]],
        "current_poi_id": "meeting",
        "include_current_stop": True,
    }
    replanned = service.replan(leader, trip_id, "group-replan-first", args)
    kind, forwarded = captures[-1]
    assert kind == "replan"
    assert forwarded["budget"] == 1_960_000
    assert forwarded["origin"]["poi_id"] == "meeting"
    assert forwarded["start_time"] == "13:00"
    assert forwarded["must_visit"] == ["meeting"]
    assert set(forwarded["avoid"]) >= {"beach", "cafe"}
    assert (
        client.get(path, headers={"subject": "member"}).json()["active"]["id"]
        == version_id
    )
    service.accept(
        leader, replanned["alternatives"][0]["alternative_id"], "group-replan-chosen"
    )
    new = client.get(path, headers={"subject": "member"}).json()["active"]
    states = {activity["name"]: activity["status"] for activity in new["activities"]}
    assert states == {
        "beach": "completed",
        "cafe": "skipped",
        "meeting": "planned",
        "market": "planned",
    }


def test_approved_requirement_closes_old_round_and_cannot_be_dropped(planning_group):
    groups, trip_id, service, actors, client, captures = planning_group
    leader, member = actors["leader"], actors["member"]
    old = service.create_planning_request(leader, trip_id, "group-old-requirements")
    detail = groups.suggest(
        member.account_id,
        trip_id,
        {
            "kind": "place",
            "poi_id": "museum",
            "title": "",
            "notes": "",
            "priority": False,
            "use_profile": False,
        },
    )
    suggestion = next(row for row in detail["suggestions"] if row["poi_id"] == "museum")
    groups.suggestion_action(
        leader.account_id, trip_id, UUID(suggestion["id"]), "approval", True
    )
    path = f"/v1/trip-groups/{trip_id}/plans"
    assert client.get(path, headers={"subject": "member"}).json()["round"] is None
    with pytest.raises(IdentityError, match="Điều kiện"):
        service.accept(
            leader, old["alternatives"][0]["alternative_id"], "broken-hard-inputs"
        )
    refreshed = service.create_planning_request(
        leader, trip_id, "group-new-requirements"
    )
    assert captures[-1][1]["must_visit"] == ["museum"]
    assert refreshed["returned_count"] == 1
    assert "museum" in {
        activity["poi_id"]
        for activity in refreshed["alternatives"][0]["plan"]["activities"]
    }
