# Data Model: Trip Management MVP

Store: SQLite runtime database managed by SQLAlchemy 2 models and Alembic migrations. POI catalog remains versioned JSON under `data/snapshots/`.

## UserProfile

- Fields: `id` UUID string, `display_name` 1–80 chars, `language` (`vi` default), `party_type`, `trip_purpose`, `spending_level` 1–3, `pace` 1–3, `fitness` 1–3, `food_preferences[]`, `must_avoid[]`, `version` integer ≥1, `created_at`, `updated_at`.
- Relationships: one profile owns many trips.
- Validation: trimmed display name required; enum/range constraints applied by API and database checks where portable.
- Delete: explicit confirmation required; deletion cascades to trips and their management data in one transaction.

## DeviceState

- Fields: singleton `id=1`, nullable `active_profile_id`, `updated_at`.
- Relationships: active profile reference uses `SET NULL` on profile deletion.
- Invariant: at most one active profile for this local-device MVP.

## Trip

- Fields: `id` UUID string, `profile_id`, `title` 1–120 chars, `city="da-nang"`, `start_date`, `end_date`, `day_start`, `day_end`, `travelers` ≥1, `budget_vnd` ≥0 integer, `transport`, `status` (`draft|planned|active|done|cancelled`), `version` integer ≥1, timestamps.
- Relationships: belongs to UserProfile; owns one mutable confirmed Itinerary, many Expenses and RouteSegments.
- Validation: range is at most two calendar days; end is not before start; same-day end time is after start time.
- Delete: cascades to itinerary, activities, route cache and expenses after user confirmation.

## Itinerary

- Fields: `id` UUID string, `trip_id` unique, `version` integer ≥1, `source` (`manual|ai`), `status` (`draft|active|archived`), timestamps.
- Relationships: belongs to one Trip and owns ordered Activities.
- Transition: manual add/update/delete/reorder increments `version`; future AI proposal does not change it until confirmation.

## Activity

- Fields: `id` UUID string, `itinerary_id`, `position` integer ≥0, nullable `poi_id`, `title` 1–160 chars, optional `notes`, `latitude` [-90,90], `longitude` [-180,180], `start_at`, `end_at`, `category`, `estimated_cost_vnd` ≥0, `source` (`manual|ai`), `version` integer ≥1, timestamps.
- Relationships: belongs to Itinerary; adjacent activities may have RouteSegments.
- Invariants: `(itinerary_id, position)` is unique; end is after start; coordinates remain as the historical display snapshot even when `poi_id` exists.
- Conflict behavior: overlap is returned as a warning, not automatically modified.

## Expense

- Fields: `id` UUID string, `trip_id`, `label` 1–120 chars, `amount_vnd` integer ≥0, `category` (`food|ticket|transport|other`), `spent_at`, optional `notes`, `version` integer ≥1, timestamps.
- Relationships: belongs directly to Trip, never Itinerary.
- Derived summary: `spent`, `remaining=budget-spent`, totals by category, alert `none|80|100`.
- Delete/update: summary is recomputed from current rows in the same response flow.

## RouteSegment

- Fields: `id`, `trip_id`, `from_activity_id`, `to_activity_id`, `source` (`osrm|cache|fallback`), `is_real_route`, `distance_m`, `duration_s`, `geometry` JSON coordinate list, `fetched_at`.
- Validation: `is_real_route=false` for fallback geometry; a fallback must never be labeled `osrm`.
- Lifecycle: invalidated when activity order or coordinates change.

## POI Catalog Record

- External to runtime relational tables for this feature.
- Fields: stable `poi_id`, name, type, coordinates, provenance, `fetched_at`, `verified`, optional hours/duration/price/tags.
- API behavior: verified-only by default; unverified records carry an explicit label.
- Activity link: `poi_id` is informational and may become unresolved; saved title/coordinates remain authoritative for historical display.

## PlannerProposal (future boundary)

- Not persisted or executed in this MVP.
- Shape: `proposal_id`, `trip_id`, base itinerary version, proposed activities, explanation, created time and expiry.
- Rule: proposal application requires explicit confirmation and a matching base version.

## Relationship Summary

```text
UserProfile 1 ── N Trip 1 ── 1 Itinerary 1 ── N Activity
                     │
                     ├── N Expense
                     └── N RouteSegment

DeviceState ── 0..1 active UserProfile
Activity ── 0..1 POI catalog reference + immutable display snapshot
```

## Transaction and Migration Rules

- SQLite foreign keys are enabled for every connection.
- One API mutation equals one database transaction.
- Schema is created/upgraded only with committed Alembic revisions.
- IDs are generated server-side as UUID strings.
- Timestamps are stored in UTC ISO-compatible database timestamps and rendered in the client timezone.
- Runtime DB files and SQLite WAL/journal files are never committed.
