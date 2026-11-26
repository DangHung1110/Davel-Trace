"""Transactional use cases for durable itinerary planning and version history."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
from typing import Callable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from BE.app.core.config import Settings, get_settings
from BE.app.core.request_context import get_correlation_id
from BE.app.db.models import (
    AcceptanceRecordModel,
    ActiveItineraryVersionModel,
    ExpenseEntryModel,
    ItineraryAlternativeModel,
    ItineraryVersionModel,
    ItineraryVersionTransitionModel,
    PlanningRequestModel,
)
from BE.app.db.session import session_scope
from BE.app.modules.catalog.application import resolve_place
from BE.app.modules.catalog.domain import CatalogUnavailable
from BE.app.modules.catalog.infrastructure import load_catalog
from BE.app.modules.identity.service import IdentityError
from BE.app.modules.planning_lifecycle.application import (
    alternative_fingerprint,
    canonical_fingerprint,
    internal_acceptance_key,
)
from BE.app.modules.planning_lifecycle.group_plans import (
    apply_group_inputs,
    group_conditions_match,
    group_hard_inputs,
    latest_group_round,
    ranked_group_plans,
    stop_order,
    trip_stops,
)
from BE.app.modules.planning_lifecycle.infrastructure import (
    acceptance_public,
    active_for_trip,
    owned_alternative,
    owned_request,
    owned_trip,
    owned_version,
    request_public,
    transition_public,
    version_detail,
    version_summary,
)
from BE.app.modules.planning_lifecycle.stable_planner import with_product_evidence
from BE.app.modules.trips.service import trip_public
from BE.app.modules.trip_groups.service import (
    group_actual_spend,
    group_exists,
    group_planning_inputs,
    post_plan_event,
)
from BE.app.routers.itinerary import ItineraryIn, plan_itinerary as legacy_itinerary
from BE.app.schemas.trip import AREA_CODES, TripRequest
from BE.app.services import matrix


Planner = Callable[[dict, int, str], dict]

# Every trip of the product is in Đà Nẵng: its clock says which day of the trip "now"
# is and what time it is there (Vietnam keeps no daylight saving time).
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
# A day with less than this left before `day_end` has no stop left to plan in it: a
# replan goes on to the next day of the trip, and on the last day there is nothing left.
MIN_DAY_LEFT_MIN = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_key(value: str) -> str:
    value = str(value or "").strip()
    if not 8 <= len(value) <= 128:
        raise IdentityError(
            "VALIDATION_ERROR", "Idempotency-Key phải dài 8-128 ký tự.", 422
        )
    return value


def _legacy_payload(result) -> dict:
    if isinstance(result, JSONResponse):
        payload = json.loads(result.body.decode("utf-8"))
        code = payload.get("error")
        if isinstance(code, dict):
            code = code.get("code")
        raise IdentityError(
            str(code or "PLANNING_FAILED"),
            str(payload.get("message") or "Không thể lập lịch."),
            result.status_code,
        )
    if not isinstance(result, dict):
        raise RuntimeError("planner returned an invalid payload")
    return result


# The profile API stores these spending styles (profiles/api.py); "economy" and
# "premium" are the names an older client used. Anything else is the middle level.
SPENDING_LEVEL = {"saver": 1, "economy": 1, "balanced": 2, "comfort": 3, "premium": 3}
# What a trip may change of the profile it was created with. Hard fields (allergies,
# must_avoid, accessibility) are refused by trips/domain.py and never come from here.
SOFT_OVERRIDES = (
    "party_type", "trip_purpose", "pace", "fitness", "spending_style",
    "spending_level", "outdoor_bias", "food_preferences", "preferred_activities",
    "usual_transport",
)


def _level(value) -> int | None:
    """A 1-3 answer (pace, fitness, spending), or None when it is not one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if value in (1, 2, 3) else None


def _bias(value) -> float:
    """outdoor_bias in [-1, 1]; a missing or unreadable answer is neutral."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(-1.0, min(1.0, float(value)))


def _effective_profile(snapshot: dict) -> dict:
    """The trip's profile: the snapshot taken when the trip was created, then the
    trip's own soft `preference_overrides` (e.g. {"outdoor_bias": 0.5})."""
    profile = dict(snapshot.get("profile_snapshot") or {})
    for key, value in (snapshot.get("preference_overrides") or {}).items():
        if key in SOFT_OVERRIDES:
            profile[key] = value
    return profile


def _profile(snapshot: dict) -> dict:
    """Product profile -> the planner's onboarding profile (`TripProfile` keys).

    An answer out of range falls back to the neutral value instead of failing the plan.
    """
    spending = _level(snapshot.get("spending_level"))
    if spending is None:
        spending = SPENDING_LEVEL.get(snapshot.get("spending_style"), 2)
    return {
        "party_type": snapshot.get("party_type", "solo"),
        "trip_purpose": snapshot.get("trip_purpose", "leisure"),
        "spending_level": spending,
        "pace": _level(snapshot.get("pace")) or 2,
        "fitness": _level(snapshot.get("fitness")) or 2,
        "outdoor_bias": _bias(snapshot.get("outdoor_bias")),
        "food_prefs": snapshot.get("food_preferences", []),
        "allergy": snapshot.get("allergies", []),
        "activities": snapshot.get("preferred_activities", []),
        "accessibility": snapshot.get("accessibility_needs", []),
        "must_avoid": snapshot.get("must_avoid", []),
        "transport": snapshot.get("usual_transport", []),
    }


def _current_stop(completed: list[str], known: dict) -> dict | None:
    """Where a replan resumes: the latest finished stop that has a place (by day, then
    by position in the day), as {"poi_id", "date"}. None before any such stop is done:
    the day starts at the base."""
    done = [known[key] for key in completed if (known.get(key) or {}).get("poi_id")]
    if not done:
        return None
    latest = max(done, key=lambda item: item["order"])
    return {"poi_id": latest["poi_id"], "date": latest.get("date")}


def _actual_spend(session, trip_id, grouped=False):
    if grouped:
        return float(group_actual_spend(session, trip_id))
    personal = session.scalar(select(func.coalesce(func.sum(
        ExpenseEntryModel.amount
    ), Decimal("0"))).where(ExpenseEntryModel.trip_id == trip_id))
    return float(personal or 0)


def _require_routable_start(poi_id, snapshot_dir):
    try:
        point = resolve_place(load_catalog(), poi_id)
        routable = point is not None and matrix.has_row(matrix.load_cells(snapshot_dir), poi_id)
    except (OSError, CatalogUnavailable, ValueError):
        raise IdentityError("STARTING_PLACE_UNAVAILABLE", "Chưa thể kiểm tra điểm xuất phát.", 503) from None
    if not routable:
        raise IdentityError(
            "STARTING_PLACE_UNAVAILABLE",
            "Chưa có đường đi từ địa điểm này. Hãy chọn điểm xuất phát khác.",
            422,
        )


def _check_group_acceptance(session, trip, request, data_version):
    latest = latest_group_round(session, trip, data_version)
    if latest is None or latest.request_id != request.request_id:
        raise IdentityError(
            "ALTERNATIVE_STALE", "Các phương án đã thay đổi. Hãy mở lại lịch của nhóm.", 409,
        )
    if not group_conditions_match(request, group_planning_inputs(session, trip.trip_id)):
        raise IdentityError(
            "GROUP_INPUTS_CHANGED", "Điều kiện của nhóm đã đổi. Hãy tạo phương án mới.", 409,
        )
    if request.request_kind == "replan" and _actual_spend(
        session, trip.trip_id, grouped=True
    ) != request.remaining_context.get("actual_spend"):
        raise IdentityError(
            "GROUP_EXPENSES_CHANGED", "Chi phí đã đổi. Hãy tạo phương án mới.", 409,
        )


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _clock(value, default: str) -> int:
    """"08:00:00" or "08:00" -> minutes after midnight; `default` when unreadable."""
    try:
        return _minutes(time.fromisoformat(str(value or default)))
    except ValueError:
        return _minutes(time.fromisoformat(default))


def _trip_dates(snapshot: dict, count: int) -> list[str]:
    """The trip's days as ISO dates, from `start_date` ("" when it is unreadable)."""
    try:
        first = date.fromisoformat(str(snapshot.get("start_date") or ""))
    except ValueError:
        return [""] * count
    return [(first + timedelta(days=offset)).isoformat() for offset in range(count)]


def _moment(value) -> tuple[date | None, time | None]:
    """`remaining_from` -> (its day or None, its time of day), on Đà Nẵng's clock.

    A full ISO 8601 moment ("2026-11-24T14:05:00+07:00") names its day; one with an
    offset ("Z", "+07:00") is read in Đà Nẵng, one without is already Đà Nẵng time.
    "HH:MM[:SS]" is a time of day on no particular day. Empty -> (None, None).
    """
    text = str(value or "").strip()
    if not text:
        return None, None
    try:
        clock = time.fromisoformat(text)
    except ValueError:
        clock = None
    if clock is not None:
        if clock.tzinfo is not None:
            clock = datetime.combine(date(2000, 1, 1), clock).astimezone(LOCAL_TZ).time()
        return None, clock.replace(tzinfo=None)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise IdentityError(
            "VALIDATION_ERROR",
            "remaining_from phải là giờ HH:MM hoặc thời điểm ISO 8601.",
            422,
        ) from None
    if moment.tzinfo is not None:
        moment = moment.astimezone(LOCAL_TZ)
    return moment.date(), moment.time()


def _window(snapshot: dict, remaining_from=None, now: datetime | None = None) -> dict:
    """The part of the trip a plan covers: {"day", "date", "days", "start_time"}.

    `day` counts from 1, `date` is that day's ISO date, `days` how many days are left
    from it (itself included) and `start_time` when that first day starts. Without a
    moment the whole trip is planned from `day_start`, as a fresh plan always is.

    A replan resumes at `remaining_from` (the device's time) or, when the app sends
    none, at `now` (the server's clock); both are read on Đà Nẵng's clock:
    - on a day of the trip, that day from then on (never before `day_start`);
    - with less than MIN_DAY_LEFT_MIN minutes left before `day_end`, the next day from
      `day_start`, and nothing at all after the last day (REPLAN_WINDOW_CLOSED);
    - before the trip, or after it, the whole trip: there is no "now" inside it.
    A bare "HH:MM" is on today's date when there is a clock, else on the first day.
    """
    day_start = _clock(snapshot.get("day_start"), "07:00")
    day_end = _clock(snapshot.get("day_end"), "18:00")
    count = max(1, min(2, len(snapshot.get("days") or []) or 1))
    dates = _trip_dates(snapshot, count)
    whole = {"day": 1, "date": dates[0] or str(snapshot.get("start_date") or ""),
             "days": count, "start_time": _hhmm(day_start)}
    on_day, at = _moment(remaining_from)
    if now is not None:
        local = now.astimezone(LOCAL_TZ)
        if at is None:
            on_day, at = local.date(), local.time()
        elif on_day is None:
            on_day = local.date()
    if at is None:
        return whole
    if on_day is None:
        index = 0
    elif on_day.isoformat() in dates:
        index = dates.index(on_day.isoformat())
    else:
        return whole
    start = max(_minutes(at), day_start)
    if day_end - start < MIN_DAY_LEFT_MIN:
        index, start = index + 1, day_start
        if index >= count:
            raise IdentityError(
                "REPLAN_WINDOW_CLOSED",
                "Chuyến đi đã tới cuối giờ của ngày cuối, không còn phần nào để lập lại.",
                409,
            )
    return {"day": index + 1, "date": dates[index] or whole["date"],
            "days": count - index, "start_time": _hhmm(start)}


def _replan_overrides(source_request: dict | None, changes: dict) -> dict:
    """The constraints a replan plans with: those of the planning request that made the
    source version (copied onto the version when it was accepted), with the client's
    `changed_constraints` on top, key by key. A key it sends replaces the original
    value ([] empties a list, null drops an optional override such as `areas` or
    `base_poi_id`); a key it leaves out keeps what the traveller confirmed before."""
    original = (source_request or {}).get("constraint_overrides")
    return {**(original if isinstance(original, dict) else {}), **changes}


def _areas(snapshot: dict) -> list[str]:
    """The zones a plan stays in: the request's own, else the ones saved on the trip
    (`preference_overrides.areas`, so a replan keeps them), else anywhere.

    The trip API refuses saved values that are not zone codes; any that are
    there anyway are skipped rather than failing the plan."""
    if snapshot.get("areas"):
        return list(snapshot["areas"])
    saved = (snapshot.get("preference_overrides") or {}).get("areas")
    if not isinstance(saved, list):
        return []
    return [code for code in saved if code in AREA_CODES]


def _trip_request(snapshot: dict, remaining: dict) -> dict:
    """The planner's TripRequest: the trip with its confirmed overrides (`snapshot`)
    and, on a replan, what is already behind the traveller (`remaining`).

    `remaining["window"]` is the part of the trip still to plan, resolved by the
    service on its clock (`_window`); without it the window is read without a clock.
    """
    window = remaining.get("window") or _window(snapshot, remaining.get("remaining_from"))
    day_start = _hhmm(_clock(snapshot.get("day_start"), "07:00"))
    end = snapshot.get("day_end") or "18:00:00"
    budget = snapshot.get("indicative_budget")
    actual = float(remaining.get("actual_spend") or 0)
    # What is done, skipped or closed is not planned again, and is no longer a must.
    gone = list(dict.fromkeys([
        *(remaining.get("unavailable_poi_ids") or []),
        *(remaining.get("completed_poi_ids") or []),
        *(remaining.get("skipped_poi_ids") or []),
    ]))
    avoid = list(dict.fromkeys([*(snapshot.get("avoid") or []), *gone]))
    must_visit = [poi for poi in snapshot.get("must_visit") or [] if poi not in gone]
    if remaining.get("include_current_stop") and remaining.get("current_poi_id") not in gone:
        point = remaining["current_poi_id"]
        if point in avoid:
            raise IdentityError(
                "GROUP_CONSTRAINT_CONFLICT",
                "Điểm xuất phát đang nằm trong danh sách cần tránh.",
                422,
            )
        must_visit = [point, *(poi for poi in must_visit if poi != point)]
    # A day starts at the base the traveller chose. A replan resumes its first day where
    # they last finished a stop that day; a stop of an earlier day is behind a night at
    # the base. The planner uses a place only when the matrix can route it.
    saved_base = (snapshot.get("preference_overrides") or {}).get("base_poi_id")
    base = snapshot.get("base_poi_id") or (saved_base if isinstance(saved_base, str) else None)
    here = remaining.get("current_poi_id")
    if here and remaining.get("current_poi_date") not in (None, window["date"]):
        here = None
    first_origin = here or base
    start_time, origin, resume = window["start_time"], first_origin, None
    if window["days"] > 1 and (start_time != day_start or first_origin != base):
        # Only the first day resumes; the days after it start at the base at day_start.
        resume = {"start_time": start_time,
                  "origin": {"poi_id": first_origin} if first_origin else None}
        start_time, origin = day_start, base
    data = TripRequest(
        trip_id=snapshot["id"],
        user_id=snapshot.get("account_id", "owned-user"),
        origin={"poi_id": origin} if origin else None,
        resume=resume,
        city="da-nang",
        date=window["date"],
        start_time=start_time,
        end_time=str(end)[:5],
        days=window["days"],
        travelers=snapshot.get("traveler_count", 1),
        budget=max(0, int(float(budget or 0) - actual)),
        transport=[snapshot.get("preferred_transport") or "mixed"],
        must_visit=must_visit,
        avoid=avoid,
        soft_poi_weights=snapshot.get("soft_poi_weights") or {},
        activities=list(snapshot.get("activities") or []),
        food_prefs=list(snapshot.get("food_preferences") or []),
        areas=_areas(snapshot),
        profile=_profile(_effective_profile(snapshot)),
    ).model_dump()
    if not data["soft_poi_weights"]:
        data.pop("soft_poi_weights")
    return data


class PlanningLifecycleService:
    def __init__(
        self,
        settings: Settings | None = None,
        planner: Planner | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._planner = planner or self._run_legacy_planner
        # What "now" is for a replan the app sends without `remaining_from`.
        self._clock = clock or _now

    def _run_legacy_planner(self, trip_input: dict, target: int, kind: str) -> dict:
        # The interactive search still goes through validation and the hard gate.
        # The request timeout is a final guard for pathological inputs.
        timeout = 90
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="planner")
        future = executor.submit(
            legacy_itinerary,
            ItineraryIn(trip=TripRequest(**trip_input)),
            False,
            interactive=(kind == "plan"),
        )
        try:
            result = future.result(timeout=timeout)
        except FutureTimeout as exc:
            future.cancel()
            raise IdentityError(
                "PLANNING_TIMEOUT" if kind == "plan" else "REPLAN_TIMEOUT",
                "Lập lịch quá thời gian cho phép, bạn có thể thử lại an toàn.",
                504,
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return with_product_evidence(_legacy_payload(result),
                                     self.settings.snapshot_name)

    def create_planning_request(
        self,
        principal,
        trip_id: UUID,
        idempotency_key: str,
        *,
        target_count: int = 5,
        constraint_overrides: dict | None = None,
        request_kind: str = "plan",
        source_version_id: UUID | None = None,
        remaining_context: dict | None = None,
    ) -> dict:
        key = _require_key(idempotency_key)
        if not 1 <= target_count <= 5:
            raise IdentityError("VALIDATION_ERROR", "Số phương án phải từ 1 đến 5.", 422)
        overrides = dict(constraint_overrides or {})
        from BE.app.modules.planning_lifecycle.api import ConstraintOverrides
        overrides = ConstraintOverrides.model_validate(overrides).model_dump(
            exclude_none=True, exclude_unset=True
        )
        remaining = dict(remaining_context or {})

        with session_scope(self.settings.database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id, lock=True)
            grouped = group_exists(session, trip_id)
            group_inputs = group_planning_inputs(session, trip_id) if grouped else {}
            snapshot = trip_public(session, trip)
            snapshot["account_id"] = str(principal.account_id)
            if len(snapshot.get("days") or []) > 2:
                raise IdentityError(
                    "PLANNING_WINDOW_UNSUPPORTED",
                    "Tự động lập lịch hiện hỗ trợ chuyến đi 1-2 ngày; bạn vẫn có thể quản lý thủ công các ngày còn lại.",
                    422,
                )
            effective_snapshot = dict(snapshot)
            for field in (
                "indicative_budget", "preferred_transport", "day_start",
                "day_end", "traveler_count", "preference_overrides",
                "must_visit", "avoid", "activities", "food_preferences",
                "base_poi_id", "areas",
            ):
                if field in overrides:
                    effective_snapshot[field] = overrides[field]
            if "accessibility" in overrides:
                profile_snapshot = dict(effective_snapshot.get("profile_snapshot") or {})
                profile_snapshot["accessibility_needs"] = overrides["accessibility"]
                effective_snapshot["profile_snapshot"] = profile_snapshot
            if grouped:
                apply_group_inputs(effective_snapshot, group_inputs)
            input_payload = {
                "trip": effective_snapshot,
                "constraint_overrides": overrides,
                "request_kind": request_kind,
            }
            if grouped:
                input_payload["group_collaboration"] = True
                input_payload["group_hard_inputs"] = group_hard_inputs(group_inputs)
            fingerprint = canonical_fingerprint({
                "trip_id": str(trip_id),
                "trip_version": trip.version,
                "target_count": target_count,
                "overrides": overrides,
                "source_version_id": str(source_version_id) if source_version_id else None,
                "remaining_context": remaining,
                **({"group_inputs": group_inputs} if grouped else {}),
            })
            existing = session.scalar(select(PlanningRequestModel).where(
                PlanningRequestModel.account_id == principal.account_id,
                PlanningRequestModel.request_kind == request_kind,
                PlanningRequestModel.idempotency_key == key,
            ))
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise IdentityError(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key đã được dùng cho nội dung khác.",
                        409,
                    )
                return request_public(session, existing)
            if request_kind == "replan":
                active = active_for_trip(session, trip_id)
                if source_version_id and (active is None or active.version_id != source_version_id):
                    raise IdentityError(
                        "SOURCE_VERSION_STALE", "Lịch đang dùng đã thay đổi. Hãy mở lại lịch.", 409,
                    )
                # Which part of the trip is left: resolved once, after the replay check
                # (a retry gets the plan it asked for even when that time has passed),
                # outside the fingerprint (the clock is not part of what was sent),
                # and kept with the request so its answer says what it planned.
                remaining["window"] = _window(
                    effective_snapshot, remaining.get("remaining_from"), self._clock()
                )
                if (
                    remaining.get("include_current_stop")
                    and remaining.get("current_poi_date") not in (
                        None, remaining["window"]["date"]
                    )
                ):
                    raise IdentityError(
                        "REPLAN_WINDOW_CLOSED",
                        "Ngày đã chọn không còn đủ thời gian để thêm điểm dừng.",
                        409,
                    )
            row = PlanningRequestModel(
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                request_kind=request_kind,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                source_version_id=source_version_id,
                trip_version=trip.version,
                data_version=self.settings.snapshot_name,
                input_payload=input_payload,
                remaining_context=remaining,
                status="running",
                target_count=target_count,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(select(PlanningRequestModel).where(
                    PlanningRequestModel.account_id == principal.account_id,
                    PlanningRequestModel.request_kind == request_kind,
                    PlanningRequestModel.idempotency_key == key,
                ))
                if existing is None:
                    raise
                if existing.request_fingerprint != fingerprint:
                    raise IdentityError(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key đã được dùng cho nội dung khác.",
                        409,
                    )
                return request_public(session, existing)
            request_id = row.request_id
            planner_input = _trip_request(effective_snapshot, remaining)

        try:
            planned = self._planner(planner_input, target_count, request_kind)
            plans = list(planned.get("plans") or [])[:target_count]
            if grouped:
                plans = ranked_group_plans(plans, group_inputs)
        except IdentityError as exc:
            with session_scope(self.settings.database_url) as session:
                row = session.get(PlanningRequestModel, request_id, with_for_update=True)
                row.status = "failed"
                row.failure_code = exc.code
                row.completed_at = _now()
                session.flush()
                return request_public(session, row)
        except Exception:
            with session_scope(self.settings.database_url) as session:
                row = session.get(PlanningRequestModel, request_id, with_for_update=True)
                row.status = "failed"
                row.failure_code = "PLANNING_FAILED"
                row.completed_at = _now()
                session.flush()
                return request_public(session, row)

        with session_scope(self.settings.database_url) as session:
            # Serialize publication with voting and leader acceptance for this trip.
            trip = owned_trip(session, principal.account_id, trip_id, lock=True) if grouped else None
            row = session.get(PlanningRequestModel, request_id, with_for_update=True)
            if grouped and not group_conditions_match(
                row, group_planning_inputs(session, trip_id)
            ):
                row.status = "failed"
                row.failure_code = "GROUP_INPUTS_CHANGED"
                row.completed_at = _now()
                session.flush()
                return request_public(session, row)
            seen: set[str] = set()
            rank = 0
            for plan in plans:
                poi_ids = {item.get("poi_id") for item in plan.get("activities") or []}
                if (not set(planner_input.get("must_visit") or []).issubset(poi_ids)
                        or set(planner_input.get("avoid") or []).intersection(poi_ids)):
                    continue
                gate = dict(plan.get("gate") or {})
                fingerprint = alternative_fingerprint(plan)
                families = gate.get("families") or {}
                complete_gate = (
                    len(families) == 5
                    and all(bool(item.get("passed")) for item in families.values())
                )
                if (
                    not plan.get("activities")
                    or not gate.get("passed")
                    or not complete_gate
                    or fingerprint in seen
                ):
                    continue
                seen.add(fingerprint)
                rank += 1
                public_plan = dict(plan)
                public_plan["preserved_completed"] = remaining.get(
                    "completed_activity_ids", []
                )
                if remaining.get("window"):
                    # The trip day, date and time this replan starts at.
                    public_plan["window"] = remaining["window"]
                if remaining.get("group_retained_stops"):
                    public_plan["group_retained_stops"] = remaining["group_retained_stops"]
                if grouped:
                    suggested = group_inputs.get("priority_poi_ids") or []
                    public_plan["group_priority_matches"] = [pid for pid in suggested if pid in poi_ids]
                    public_plan["group_priority_unmatched"] = [pid for pid in suggested if pid not in poi_ids]
                    public_plan["group_plan_date"] = planner_input["date"]
                    window = remaining.get("window")
                    resume = planner_input.get("resume") or {}
                    origin = resume.get("origin") if resume else planner_input.get("origin")
                    if window and origin and origin.get("poi_id"):
                        public_plan["group_departure"] = {
                            "poi_id": origin["poi_id"],
                            "day": window["day"],
                            "time": window["start_time"],
                        }
                session.add(ItineraryAlternativeModel(
                    request_id=row.request_id,
                    trip_id=row.trip_id,
                    account_id=row.account_id,
                    fingerprint=fingerprint,
                    profile=str(plan.get("profile") or "balanced"),
                    plan_payload=public_plan,
                    gate_payload=gate,
                    deterministic_rank=rank,
                    deterministic_score=plan.get("deterministic_score"),
                    data_version=row.data_version,
                ))
            row.returned_count = rank
            row.shortage_reason = None if rank >= row.target_count else str(
                (planned.get("solution_pool") or {}).get("shortage_reason")
                or "insufficient_feasible_supply"
            )
            row.status = "completed"
            row.completed_at = _now()
            session.flush()
            if rank and trip is not None:
                latest = latest_group_round(session, trip, row.data_version)
                if latest is not None and latest.request_id == row.request_id:
                    label = "lịch mới cho phần còn lại" if request_kind == "replan" else "lịch cho chuyến đi"
                    post_plan_event(
                        session, trip_id, f"Có {rank} phương án {label}. Mở Lịch nhóm để cùng xem và bình chọn.",
                        f"plans-ready:{request_id}",
                    )
            return request_public(session, row)

    def get_request(self, principal, request_id: UUID) -> dict:
        with session_scope(self.settings.database_url) as session:
            return request_public(
                session, owned_request(session, principal.account_id, request_id)
            )

    def accept(self, principal, alternative_id: UUID, idempotency_key: str) -> dict:
        key = _require_key(idempotency_key)
        with session_scope(self.settings.database_url) as session:
            alternative = owned_alternative(
                session, principal.account_id, alternative_id, lock=True
            )
            request = session.get(PlanningRequestModel, alternative.request_id)
            reason = "replan_accept" if request.request_kind == "replan" else "accept"
            replay = session.scalar(select(ItineraryVersionTransitionModel).where(
                ItineraryVersionTransitionModel.account_id == principal.account_id,
                ItineraryVersionTransitionModel.reason == reason,
                ItineraryVersionTransitionModel.idempotency_key == key,
            ))
            if replay is not None:
                version = session.get(ItineraryVersionModel, replay.to_version_id)
                if version.alternative_id != alternative.alternative_id:
                    raise IdentityError(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency-Key đã chọn một phương án khác.", 409,
                    )
                acceptance = session.scalar(select(AcceptanceRecordModel).where(
                    AcceptanceRecordModel.itinerary_version_id == version.version_id
                ))
                active = active_for_trip(session, version.trip_id)
                return {
                    "acceptance": acceptance_public(acceptance),
                    "version": version_detail(version, active.version_id if active else None),
                    "transition": transition_public(replay),
                }
            trip = owned_trip(session, principal.account_id, alternative.trip_id, lock=True)
            if request.status != "completed" or alternative.selectability_state != "current":
                raise IdentityError("ALTERNATIVE_STALE", "Phương án không còn có thể chọn.", 409)
            if trip.version != request.trip_version or request.data_version != self.settings.snapshot_name:
                alternative.selectability_state = "invalidated"
                trip.review_state = "needs_review"
                raise IdentityError("ALTERNATIVE_STALE", "Dữ liệu chuyến đi đã thay đổi.", 409)
            grouped = group_exists(session, trip.trip_id)
            if grouped:
                _check_group_acceptance(session, trip, request, self.settings.snapshot_name)
            families = alternative.gate_payload.get("families") or {}
            if (
                not alternative.gate_payload.get("passed")
                or len(families) != 5
                or not all(bool(item.get("passed")) for item in families.values())
            ):
                alternative.selectability_state = "invalidated"
                raise IdentityError("GATE_FAILED", "Phương án không còn đạt cổng khả thi.", 422)

            active = active_for_trip(session, trip.trip_id, lock=True)
            ordinal = int(session.scalar(select(func.count()).select_from(
                ItineraryVersionModel
            ).where(ItineraryVersionModel.trip_id == trip.trip_id)) or 0) + 1
            version = ItineraryVersionModel(
                version_id=uuid4(),
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                alternative_id=alternative.alternative_id,
                parent_version_id=request.source_version_id,
                ordinal=ordinal,
                plan_payload=alternative.plan_payload,
                gate_payload=alternative.gate_payload,
                request_payload=request.input_payload,
                data_version=alternative.data_version,
                deterministic_rank=alternative.deterministic_rank,
                deterministic_score=alternative.deterministic_score,
            )
            session.add(version)
            session.flush()
            parent_acceptance = None
            if request.source_version_id:
                parent_acceptance = session.scalar(select(AcceptanceRecordModel).where(
                    AcceptanceRecordModel.itinerary_version_id == request.source_version_id
                ))
            acceptance = AcceptanceRecordModel(
                idempotency_key=internal_acceptance_key(
                    str(principal.account_id), reason, key
                ),
                itinerary_id=str(alternative.alternative_id),
                trip_id=str(trip.trip_id),
                parent_acceptance_id=(
                    parent_acceptance.acceptance_id if parent_acceptance else None
                ),
                data_version=alternative.data_version,
                request_payload=request.input_payload,
                plan_payload=alternative.plan_payload,
                gate_payload=alternative.gate_payload,
                deterministic_rank=alternative.deterministic_rank,
                deterministic_score=alternative.deterministic_score,
                account_id=principal.account_id,
                request_id=request.request_id,
                alternative_id=alternative.alternative_id,
                itinerary_version_id=version.version_id,
            )
            session.add(acceptance)
            transition = ItineraryVersionTransitionModel(
                transition_id=uuid4(),
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                from_version_id=active.version_id if active else None,
                to_version_id=version.version_id,
                reason=reason,
                idempotency_key=key,
                correlation_id=get_correlation_id(),
            )
            session.add(transition)
            if active is None:
                active = ActiveItineraryVersionModel(
                    trip_id=trip.trip_id,
                    account_id=principal.account_id,
                    version_id=version.version_id,
                )
                session.add(active)
            else:
                active.version_id = version.version_id
                active.revision += 1
                active.updated_at = _now()
            alternative.selectability_state = "selected"
            session.execute(update(ItineraryAlternativeModel).where(
                ItineraryAlternativeModel.request_id == request.request_id,
                ItineraryAlternativeModel.alternative_id != alternative.alternative_id,
                ItineraryAlternativeModel.selectability_state == "current",
            ).values(selectability_state="superseded"))
            trip.review_state = "current"
            if grouped:
                post_plan_event(
                    session, trip.trip_id, "Trưởng nhóm đã chốt lịch. Mở Lịch nhóm để xem.",
                    f"plan-published:{version.version_id}",
                )
            session.flush()
            return {
                "acceptance": acceptance_public(acceptance),
                "version": version_detail(version, version.version_id),
                "transition": transition_public(transition),
            }

    def list_versions(self, principal, trip_id: UUID, limit=50, offset=0) -> dict:
        with session_scope(self.settings.database_url) as session:
            owned_trip(session, principal.account_id, trip_id)
            active = active_for_trip(session, trip_id)
            rows = list(session.scalars(select(ItineraryVersionModel).where(
                ItineraryVersionModel.trip_id == trip_id,
                ItineraryVersionModel.account_id == principal.account_id,
            ).order_by(
                ItineraryVersionModel.created_at.desc(),
                ItineraryVersionModel.ordinal.desc(),
            ).offset(max(0, offset)).limit(max(1, min(100, limit)))))
            items = []
            for row in rows:
                item = version_summary(row, active.version_id if active else None)
                transition = session.scalar(select(ItineraryVersionTransitionModel).where(
                    ItineraryVersionTransitionModel.to_version_id == row.version_id
                ).order_by(ItineraryVersionTransitionModel.occurred_at.desc()))
                item["reason"] = transition.reason if transition else "accept"
                items.append(item)
            return {"items": items, "active_version_id": str(active.version_id) if active else None}

    def get_version(self, principal, version_id: UUID) -> dict:
        with session_scope(self.settings.database_url) as session:
            row = owned_version(session, principal.account_id, version_id)
            active = active_for_trip(session, row.trip_id)
            result = version_detail(row, active.version_id if active else None)
            acceptance = session.scalar(select(AcceptanceRecordModel).where(
                AcceptanceRecordModel.itinerary_version_id == row.version_id
            ))
            result["acceptance"] = acceptance_public(acceptance) if acceptance else None
            return result

    def activate(self, principal, version_id: UUID, idempotency_key: str) -> dict:
        key = _require_key(idempotency_key)
        with session_scope(self.settings.database_url) as session:
            version = owned_version(session, principal.account_id, version_id)
            trip = owned_trip(session, principal.account_id, version.trip_id, lock=True)
            replay = session.scalar(select(ItineraryVersionTransitionModel).where(
                ItineraryVersionTransitionModel.account_id == principal.account_id,
                ItineraryVersionTransitionModel.reason == "reactivate",
                ItineraryVersionTransitionModel.idempotency_key == key,
            ))
            if replay:
                if replay.to_version_id != version.version_id:
                    raise IdentityError("IDEMPOTENCY_CONFLICT", "Khóa đã kích hoạt phiên bản khác.", 409)
                current = active_for_trip(session, trip.trip_id)
                return {
                    "version": version_detail(
                        version, current.version_id if current else None
                    ),
                    "transition": transition_public(replay),
                }
            active = active_for_trip(session, trip.trip_id, lock=True)
            if active is None:
                raise IdentityError("STATE_CONFLICT", "Chuyến đi chưa có lịch đang dùng.", 409)
            transition = ItineraryVersionTransitionModel(
                account_id=principal.account_id,
                trip_id=trip.trip_id,
                from_version_id=active.version_id,
                to_version_id=version.version_id,
                reason="reactivate",
                transition_id=uuid4(),
                idempotency_key=key,
                correlation_id=get_correlation_id(),
            )
            session.add(transition)
            active.version_id = version.version_id
            active.revision += 1
            active.updated_at = _now()
            trip.review_state = "current"
            if group_exists(session, trip.trip_id):
                post_plan_event(
                    session, trip.trip_id, "Trưởng nhóm đã dùng lại một lịch đã lưu.",
                    f"plan-published:{transition.transition_id}",
                )
            session.flush()
            return {"version": version_detail(version, version.version_id),
                    "transition": transition_public(transition)}

    def replan(
        self,
        principal,
        trip_id: UUID,
        idempotency_key: str,
        payload: dict,
    ) -> dict:
        """Plan what is left of the trip from the active version (`source_version_id`).

        What is done, skipped or unavailable is excluded, the budget is what is left
        after the expenses, the first day resumes where the traveller last finished a
        stop that day, and the window starts at `remaining_from` or now (`_window`).
        The constraints are those the source version was planned with, with
        `changed_constraints` on top (`_replan_overrides`).
        """
        source_id = UUID(str(payload.get("source_version_id")))
        with session_scope(self.settings.database_url) as session:
            trip = owned_trip(session, principal.account_id, trip_id, lock=True)
            source = owned_version(session, principal.account_id, source_id)
            if source.trip_id != trip_id:
                raise IdentityError("NOT_FOUND", "Không tìm thấy phiên bản lịch trình.", 404)
            active = active_for_trip(session, trip_id)
            if active is None or active.version_id != source.version_id:
                raise IdentityError("SOURCE_VERSION_STALE", "Phiên bản nguồn không còn đang dùng.", 409)
            grouped = group_exists(session, trip_id)
            shared_stops = trip_stops(session, trip, source if grouped else None)
            known = {
                item["id"]: {**item, "order": (
                    stop_order(item) if grouped else (item["date"], item["position"])
                )}
                for item in shared_stops
            }
            changes = dict(payload.get("changed_constraints") or {})
            overrides = _replan_overrides(source.request_payload, changes)
            completed = list(dict.fromkeys([
                *(key for key, item in known.items() if item["status"] == "completed"),
                *(payload.get("completed_activity_ids") or []),
            ]))
            skipped = list(dict.fromkeys([
                *(key for key, item in known.items() if item["status"] == "skipped"),
                *(payload.get("skipped_activity_ids") or []),
            ]))
            if any(item not in known for item in completed + skipped):
                raise IdentityError("VALIDATION_ERROR", "Hoạt động không thuộc lịch của chuyến đi.", 422)
            if set(completed) & set(skipped):
                raise IdentityError(
                    "VALIDATION_ERROR", "Mỗi điểm chỉ có thể đánh dấu đã đi hoặc bỏ qua.", 422,
                )
            here = _current_stop(completed, known) or {}
            current_poi = payload.get("current_poi_id")
            include_current_stop = bool(payload.get("include_current_stop"))
            if include_current_stop and not current_poi:
                raise IdentityError(
                    "VALIDATION_ERROR", "Hãy chọn địa điểm để thêm vào lịch.", 422,
                )
            if current_poi:
                _require_routable_start(current_poi, self.settings.snapshot_dir)
                current_date, _ = _moment(payload.get("remaining_from"))
                here = {"poi_id": current_poi,
                        "date": current_date.isoformat() if current_date else None}
            remaining = {
                "completed_activity_ids": completed,
                "skipped_activity_ids": skipped,
                "completed_poi_ids": [
                    known[item]["poi_id"] for item in completed
                    if known[item]["poi_id"]
                ],
                "skipped_poi_ids": [
                    known[item]["poi_id"] for item in skipped
                    if known[item]["poi_id"]
                ],
                "remaining_from": payload.get("remaining_from"),
                "unavailable_poi_ids": list(payload.get("unavailable_poi_ids") or []),
                "changed_constraints": changes,
                "actual_spend": _actual_spend(session, trip_id, grouped=grouped),
                "current_poi_id": here.get("poi_id"),
                "current_poi_date": here.get("date"),
            }
            if include_current_stop:
                gone = (remaining["completed_poi_ids"] + remaining["skipped_poi_ids"]
                        + remaining["unavailable_poi_ids"])
                if current_poi in gone:
                    raise IdentityError(
                        "VALIDATION_ERROR",
                        "Điểm này đã đi, đã bỏ qua hoặc đang đóng. Bạn vẫn có thể chọn làm điểm xuất phát.",
                        422,
                    )
                remaining["include_current_stop"] = True
            if grouped:
                retained = [
                    {key: value for key, value in known[item].items() if key != "order"}
                    | {"status": status}
                    for items, status in ((completed, "completed"), (skipped, "skipped"))
                    for item in items
                ]
                remaining["group_retained_stops"] = sorted(retained, key=stop_order)
        return self.create_planning_request(
            principal,
            trip_id,
            idempotency_key,
            target_count=int(payload.get("target_count") or 5),
            constraint_overrides=overrides,
            request_kind="replan",
            source_version_id=source_id,
            remaining_context=remaining,
        )
