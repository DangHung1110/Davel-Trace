# Data Model: Profile and Trip Management

Timestamps are UTC. Trip dates and activity times are Da Nang local values. Mutable aggregates have positive integer `version`.

## TravelerProfile

- `account_id` UUID primary key/account reference
- `display_name`, `party_type`, `trip_purpose`, `pace`, `fitness`, `spending_style`
- normalized collections: `food_preferences`, `preferred_activities`, `usual_transport`
- hard collections: `must_avoid`, `allergies`, `accessibility_needs`
- `onboarding_complete`, `version`, `created_at`, `updated_at`

One row per account. Collections are bounded and de-duplicated. Hard values cannot be weakened by trip overrides.

## Trip

- `trip_id` UUID; `account_id` owner; `title`; fixed `destination=da_nang`
- local `start_date`, `end_date`; `traveler_count`
- progress `draft|planned|in_progress|completed`
- lifecycle `available|archived|deleted|purged`; review `current|needs_review`
- optional `indicative_budget`, `currency=VND`, transport, daily bounds, notes
- `profile_version`, immutable `profile_snapshot`, soft `preference_overrides`
- `version`, timestamps, `archived_at`, `deleted_at`, `purge_after`

Owner/lifecycle/date/update/title indexes support listing. Deleted/archived records are excluded by default.

## TripDay

- `day_id`, `trip_id`, `local_date`, contiguous `position`, `version`, timestamps
- unique `(trip_id, local_date)` and `(trip_id, position)`

Extending creates missing dates. Shortening populated days requires confirmed atomic removal.

## TripActivity

- `activity_id`, `day_id`, kind `custom|poi_reference`, optional `poi_id`
- title, optional local start/end/duration, optional non-negative cost, `currency=VND`
- progress `planned|completed|skipped`, contiguous position, notes, version, timestamps

Custom activities require title. Invalid bounds are rejected; overlap is a warning; unresolved POIs stay labeled.

## ActiveTripSelection

- `account_id` primary key; nullable unique owned eligible `trip_id`; `version`, `updated_at`

Archive/delete clears selection atomically; restore does not select automatically.

## MutationReceipt

- `receipt_id`, `account_id`, operation, optional resource ID
- idempotency-key hash, request fingerprint, result resource ID/status, timestamps/expiry
- unique account/operation/resource/key scope

Same fingerprint returns the result; a changed fingerprint yields `IDEMPOTENCY_CONFLICT`. Private request bodies are not stored.

## TripLifecycleEvent

- `event_id`, nullable trip/account subject, event/outcome, actor/session reference
- correlation ID, privacy-safe metadata, occurrence time

Metadata includes versions/counts/states but excludes preferences, allergies, titles, and notes.

## Relationships

```text
Account 1──0..1 TravelerProfile
Account 1──* Trip 1──* TripDay 1──* TripActivity
Account 1──0..1 ActiveTripSelection ──1 Trip
Account 1──* MutationReceipt
Trip 1──* TripLifecycleEvent
```

## State Transitions

```text
Profile: absent -> current; current -> current(version+1)
Trip progress: draft -> planned -> in_progress -> completed
Trip lifecycle: available <-> archived
                available|archived -> deleted -> available (within 30 days)
                deleted -> purged (after 30 days)
Activity: planned <-> completed; planned <-> skipped
```

Restore preserves stable identity/nested content and returns non-active.

## Migration

`007_001_profile_trip_management` depends on `006_001`, creates only these entities/constraints/indexes, and downgrades without changing identity, acceptance evidence, PMTiles, or planning snapshots.
