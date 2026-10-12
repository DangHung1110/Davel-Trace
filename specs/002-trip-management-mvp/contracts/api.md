# REST Contract: Trip Management MVP

Base path: `/v1`. JSON only. Successful mutation responses return the current resource. Errors use:

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "Resource changed; reload and retry",
    "details": {}
  }
}
```

## Health

- `GET /v1/health` → `{ "status": "ok", "database": "ready", "snapshot": "danang-v1" }`

## Profiles

- `GET /v1/profiles` → `{ "items": [UserProfile], "active_profile_id": "..." | null }`
- `POST /v1/profiles` with profile create fields → `201 UserProfile`
- `GET /v1/profiles/{profile_id}` → `UserProfile`
- `PATCH /v1/profiles/{profile_id}` with changed fields + required `version` → updated `UserProfile`
- `DELETE /v1/profiles/{profile_id}?version=N&confirm=true` → `204`
- `PUT /v1/profiles/{profile_id}/active` → `{ "active_profile_id": "..." }`

## Trips

- `GET /v1/trips?profile_id=...` → `{ "items": [TripSummary] }`
- `POST /v1/trips` with `profile_id`, title, dates/times, travelers, budget and transport → `201 Trip`
- `GET /v1/trips/{trip_id}` → `TripDetail` including current itinerary, ordered activities and expense summary
- `PATCH /v1/trips/{trip_id}` with changed fields + required `version` → updated `Trip`
- `DELETE /v1/trips/{trip_id}?version=N&confirm=true` → `204`

## Manual Itinerary Activities

- `GET /v1/trips/{trip_id}/itinerary` → current `Itinerary` with ordered activities and overlap warnings
- `POST /v1/trips/{trip_id}/activities` with activity fields + `itinerary_version` → `201 Itinerary`
- `PATCH /v1/activities/{activity_id}` with changed fields + `version` + `itinerary_version` → updated `Itinerary`
- `DELETE /v1/activities/{activity_id}?version=N&itinerary_version=N` → updated `Itinerary`
- `PUT /v1/trips/{trip_id}/activities/order` with `{ "activity_ids": [...], "itinerary_version": N }` → updated `Itinerary`

Every activity mutation increments itinerary version exactly once. Overlap warnings have `{activity_ids, message}` and do not reject the manual change.

## Expenses

- `GET /v1/trips/{trip_id}/expenses` → `{ "items": [Expense], "summary": ExpenseSummary }`
- `POST /v1/trips/{trip_id}/expenses` with label, amount, category, spent time and optional notes → `201 { "expense": Expense, "summary": ExpenseSummary }`
- `PATCH /v1/expenses/{expense_id}` with changed fields + required `version` → `{ "expense": Expense, "summary": ExpenseSummary }`
- `DELETE /v1/expenses/{expense_id}?version=N` → `ExpenseSummary`
- Compatibility alias: `GET /v1/expenses/summary?trip_id=...` → `ExpenseSummary`

`ExpenseSummary` contains `budget_vnd`, `spent_vnd`, `remaining_vnd`, `by_category` and `alert` (`none|80|100`).

## POI Catalog

- `GET /v1/pois?q=&limit=20&verified_only=true` → `{ "items": [PoiSummary], "snapshot": "danang-v1", "fetched_at": "..." }`
- `GET /v1/pois/{poi_id}` → full POI record or `404 POI_NOT_FOUND`.

Search is case-insensitive over normalized Vietnamese name/type/tags. Limit range is 1–50.

## Route Preview

- `POST /v1/routes/preview` with `{ "trip_id": "...", "activity_ids": ["..."], "mode": "driving" }`
- Response: `{ "source": "osrm|fallback", "is_real_route": true|false, "distance_m": N, "duration_s": N, "geometry": [[lon,lat], ...], "warning": "..." | null }`

At least two and at most ten ordered activities are required. Timeout/unavailable OSRM may return display-only fallback with `is_real_route=false` and an explicit warning, or a retryable `503`; it must never claim fallback geometry is a real route.

## Status and Error Rules

- `400`: invalid domain command (`INVALID_DATE_RANGE`, `INVALID_EXPENSE`, `ORDER_MISMATCH`).
- `404`: resource not found.
- `409`: stale `version`/`itinerary_version` or uniqueness conflict.
- `422`: request shape validation failure.
- `503`: required external route/catalog resource unavailable.
- Deleting a parent requires `confirm=true`; otherwise `409 CONFIRMATION_REQUIRED` with dependent counts.

## Future Planner Port

No planner endpoint is enabled in this feature. Future `/v1/planner/proposals` responses must remain proposals and require a separate confirmation command with the matching base itinerary version.
