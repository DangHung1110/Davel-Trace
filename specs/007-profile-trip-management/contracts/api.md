# Profile and Trip HTTP API Contract

All endpoints use `/v1`, Bearer authentication, `X-Correlation-ID`, Vietnamese actionable messages, and the existing error envelope:

```json
{"error": "STABLE_CODE", "message": "Mô tả có thể xử lý."}
```

Another account's private identifier returns `404 NOT_FOUND`. Capability denial returns `403 FORBIDDEN`. Mutable responses include a positive `version`.

## Request guards

- Retriable mutations require `Idempotency-Key` of 8–128 characters.
- Updates include `expected_version`; active selection includes `expected_selection_version`.
- Same idempotency key/fingerprint returns the original result without another version increment.
- Reusing a key with different intent returns `409 IDEMPOTENCY_CONFLICT`.
- Stale expected version returns `409 VERSION_CONFLICT`; the client refetches instead of receiving private state inside the error.

## Profile

| Method/path | Purpose | Success |
|---|---|---|
| `GET /v1/profile` | Current profile or onboarding absence | `200 {profile: null|object}` |
| `PUT /v1/profile` | Create/update current profile | `200` profile |
| `POST /v1/profile/reset` | Reset soft optional values while preserving hard constraints | `200` profile |

The save body contains profile fields and nullable `expected_version` (`null` for first creation). Collections are normalized, de-duplicated, bounded, and deterministically returned. The response groups `soft_preferences` and `hard_constraints` and includes onboarding state/timestamps.

## Trips

| Method/path | Purpose | Success |
|---|---|---|
| `GET /v1/trips` | Search/filter/sort owned trips | `200` items, cursor, `active_trip_id`, selection version |
| `POST /v1/trips` | Create owned trip and days | `201` trip detail |
| `GET /v1/trips/{trip_id}` | Read owned trip/day/activity aggregate | `200` detail |
| `PATCH /v1/trips/{trip_id}` | Versioned edit/date resize | `200` detail |
| `PUT /v1/trips/active` | Set/clear active trip | `200` active selection |
| `POST /v1/trips/{trip_id}/archive` | Archive and clear selection if needed | `200` detail |
| `POST /v1/trips/{trip_id}/restore` | Restore archived or recoverable deleted trip | `200` non-active detail |
| `POST /v1/trips/{trip_id}/deletion` | Confirm recoverable deletion | `204` |

List query supports bounded `q`, lifecycle/state filter, deterministic sort, cursor, and limit. Default excludes archived/deleted. There is no public permanent-purge endpoint.

Trip creation includes title, dates, travelers, daily bounds, optional budget/notes, transport, and allow-listed overrides. Response includes immutable profile snapshot/effective values, days, warnings, and lifecycle/review/progress states.

When date reduction would remove populated days, the first request returns `409 DATE_REDUCTION_CONFIRMATION_REQUIRED`. A repeat with `confirm_removed_days=true`, a new idempotency key, and the current version applies the atomic change.

## Days and activities

Days are derived from the inclusive trip range; clients do not create/delete them directly.

| Method/path | Purpose | Success |
|---|---|---|
| `GET /v1/trips/{trip_id}/days` | Ordered day aggregates/warnings | `200` list |
| `POST /v1/trips/{trip_id}/days/{day_id}/activities` | Add manual activity | `201` updated day |
| `PATCH /v1/activities/{activity_id}` | Edit content/schedule/progress | `200` updated day |
| `DELETE /v1/activities/{activity_id}?expected_version=N` | Remove manual activity | `200` updated day |
| `PUT /v1/trips/{trip_id}/days/{day_id}/activities/order` | Atomic full-list reorder | `200` updated day |

Reorder includes every current owned activity ID exactly once plus `expected_day_version`. Positions returned are contiguous. Invalid bounds return `422`; valid overlap returns a warning rather than silent repair.

## Validation

- Da Nang dates; inclusive duration 1–14 days; travelers 1–20.
- Trimmed bounded title; duplicate titles allowed because UUID is identity.
- VND default/fixed for this increment; budget/cost non-negative.
- Daily and activity start strictly precede end; activity belongs to its day.
- Custom activity requires title; POI reference is honestly unresolved until catalog integration.
- Soft override keys are allow-listed; hard constraint weakening is `422 HARD_CONSTRAINT_VIOLATION`.

## Stable errors

`VALIDATION_ERROR` (422), `HARD_CONSTRAINT_VIOLATION` (422), `AUTHENTICATION_REQUIRED` (401), `FORBIDDEN` (403), `NOT_FOUND` (404), `VERSION_CONFLICT` (409), `IDEMPOTENCY_CONFLICT` (409), `STATE_CONFLICT` (409), `DATE_REDUCTION_CONFIRMATION_REQUIRED` (409), `ACTIVE_SELECTION_CONFLICT` (409), `DATABASE_UNAVAILABLE` (503), and `INTERNAL_ERROR` (500).

## Identity lifecycle contribution

Account export gains `profile` and `trips` sections. Account purge invokes registered profile/trip contributors or reviewed account cascades; identity does not import product repositories. Audit and backup evidence contain IDs, versions, counts, relationships, categories, outcomes, and correlations only—not preference content, allergies, titles, or notes.
