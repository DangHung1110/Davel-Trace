# Research: Profile and Trip Management

## Capability split

**Decision**: Separate `profiles` and `trips`; use `trips → profiles → identity`.

**Rationale**: Profiles are reusable account context while trips own snapshots/timelines. This prevents identity, planner, and oversized `AppState` from becoming sources of truth.

**Alternatives considered**: Identity profile fields, one management mega-module, and microservices were rejected for coupling or unnecessary complexity.

## Account-owned singleton profile

**Decision**: One current profile per account; multiple device-local profiles remain demo-only during transition.

**Rationale**: Increment 006 established account ownership and authenticated mode no longer needs ambiguous `active_profile_id` selection.

**Alternatives considered**: Household profiles and trip-only profiles are outside current scope.

## Immutable trip snapshot

**Decision**: Store profile version/effective inherited values when creating a trip, plus allow-listed soft overrides.

**Rationale**: Future profile edits do not rewrite history; hard constraints cannot be silently weakened.

**Alternatives considered**: Live profile lookup causes drift; a second mutable profile confuses ownership.

## Explicit trip days

**Decision**: Persist one day per inclusive local date and scope activities to a day.

**Rationale**: The old flattened itinerary cannot correctly represent empty or multi-day timelines.

**Alternatives considered**: Derived-only days and the flattened itinerary fail empty-day and date-resize behavior.

## Versioning and atomicity

**Decision**: Integer optimistic versions plus row locks for multi-row transitions.

**Rationale**: Stale sessions receive recoverable conflicts while locks preserve order/date/lifecycle invariants.

**Alternatives considered**: Last-write-wins loses data; automatic merge is unsafe for dates/constraints.

## Persisted idempotency receipts

**Decision**: Retriable mutations use account/operation/resource-scoped key hashes, request fingerprints, and result references.

**Rationale**: Guarantees survive restarts without Redis or a workflow engine.

**Alternatives considered**: Memory cache is not durable; unique trip/activity keys alone do not cover reorder/lifecycle.

## Independent states

**Decision**: Separate trip progress, lifecycle, and active selection.

**Rationale**: Archive/delete atomically clears selection; restore never silently activates; one enum would create contradictory combinations.

## Honest Flutter composition

**Decision**: Authenticated sessions use HTTP repositories and demo sessions use seeded repositories, with no error-based fallback.

**Rationale**: The current app always constructs demo management data and could falsely present it as account data.

## Compatibility facade

**Decision**: Project durable trip/day/activity data into existing map/expense/planning interfaces until later increments migrate.

**Rationale**: Preserves verified behavior and avoids a big-bang rewrite.

## Dependencies

**Decision**: Add no dependency; reuse current database, API, Flutter state/network, and test tools.

**Rationale**: Existing tools cover transactions, JSON, concurrency, forms, and validation.
