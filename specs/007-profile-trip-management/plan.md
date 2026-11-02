# Implementation Plan: Profile and Trip Management

**Branch**: `task/007-profile-trip-management` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-profile-trip-management/spec.md`

## Summary

Replace the authenticated shell's seeded profile/trip data with durable, account-owned profile, trip, day, and manual-activity capabilities. Add separate backend `profiles` and `trips` modules, reviewed PostgreSQL migration `007_001`, version/idempotency guards, lifecycle and active-trip state, then introduce narrow Flutter repositories/controllers behind a compatibility facade so map, expense, and planning demos keep working. No AI, POI, routing, or expense implementation is added.

## Technical Context

**Language/Version**: Python 3.11 backend; Dart 3.13 / Flutter 3.47 client

**Primary Dependencies**: Existing FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3; existing Flutter `http`, `flutter_secure_storage`, and current UI packages. No new dependency.

**Storage**: PostgreSQL 16 is authoritative. JSONB-compatible fields store bounded preference collections and immutable snapshots; local trip dates/times remain local calendar values.

**Testing**: pytest unit/contract/integration/architecture tests against PostgreSQL; Flutter analyze plus controller/repository/widget tests; existing identity, static map, planner, and demo-management regressions.

**Target Platform**: FastAPI service on Windows/Linux and Flutter web laptop demo at 390×844, with Android/iOS-compatible code paths.

**Project Type**: Mobile/web Flutter client plus modular-monolith HTTP API.

**Performance Goals**: Normal profile/trip actions visibly complete within two seconds locally; a 100-trip owned list filters within one second; ownership/version decisions add less than 100 ms locally.

**Constraints**: Da Nang-only; one profile and at most one active trip per account; 1–14 days; 1–20 travelers; no silent seeded fallback for authenticated data; no AI/expense/POI/routing dependency; no destructive planner rewrite; no new stateful service or Docker image.

**Scale/Scope**: Student MVP for thousands of accounts, hundreds of trips per account, 14 days per trip, and dozens of activities per day.

## Constitution Check

*GATE: Passed before research and re-checked after design.*

| Gate | Result | Evidence |
|---|---|---|
| Feasibility-first | PASS | No itinerary generation/ranking; accepted evidence is preserved and invalidating edits only mark review required. |
| Spec-driven | PASS | Spec/checklist precede plan; tasks, analyze, implement, and converge remain mandatory. |
| Test-first | PASS | Ownership, conflict, lifecycle, migration, and regression contracts precede implementation. |
| Provenance and honesty | PASS | Custom/unresolved POIs are labeled; audit/backup omit private content. |
| Simplicity/tier discipline | PASS | Existing monolith/dependencies reused; no broker, cache service, AI, or microservice. |
| Mobile contract | PASS | Flutter stays primary; live errors never become demo data; PMTiles behavior is preserved. |
| Technology constraints | PASS | PostgreSQL, SQLAlchemy/Alembic, FastAPI and Flutter remain authoritative. |
| Git governance | PASS | Task branch targets `feat/product-platform`; protected branches remain untouched. |

## Architecture Decisions

### Capability ownership

- `profiles` owns the singleton profile and framework-free snapshot reader.
- `trips` owns trips, snapshots, overrides, days, activities, active selection, lifecycle events, and mutation receipts.
- Direction is `trips → profiles → identity`; modules receive `Principal` and never query credentials.
- Identity export/purge uses neutral owned-data contributors registered at composition time, avoiding an import cycle.

### Persistence and concurrency

- Migration `007_001_profile_trip_management` extends `006_001` only.
- Mutable aggregates expose versions; mismatch returns `409 VERSION_CONFLICT`.
- Retriable writes use persisted account/operation/resource-scoped receipts plus request fingerprints.
- Date resize, reorder, active switch, archive/delete/restore, and purge lock affected rows and commit atomically.
- An account-to-active-trip row enforces at most one selection.

### Flutter migration

- Add narrow profile/trip repositories/controllers; do not expand `AppState` or the broad legacy repository.
- Authenticated mode composes token-aware HTTP repositories; demo mode stays seeded and visibly labeled.
- A compatibility facade projects the selected trip into current map/expense/planning consumers.
- Keep current shell/navigation keys while evolving the itinerary area into a trip workspace.

## Project Structure

```text
specs/007-profile-trip-management/
├── {spec,plan,research,data-model,quickstart,tasks}.md
├── contracts/{api,mobile}.md
└── checklists/

BE/app/
├── core/owned_data.py
├── db/models.py
└── modules/
    ├── identity/dependencies.py
    ├── profiles/{domain,application,infrastructure,api}.py
    └── trips/{domain,application,infrastructure,api}.py
BE/migrations/versions/007_001_profile_trip_management.py
BE/scripts/purge_trips.py
BE/tests/{unit,contract,integration,architecture}/

FE/lib/features/
├── profile_management/{domain,data,application,presentation}/
├── trip_management/{domain,data,application,presentation}/
└── management/data/management_repository_adapter.dart
FE/test/{profile_management,trip_management,management_contract,product_compatibility}_test.dart
```

**Structure Decision**: Extend the modular monolith and Flutter feature-first layout with separate profile/trip ownership. Retain legacy consumers through a temporary adapter rather than a big-bang rewrite.

## Migration and Compatibility

1. Add schema/backend contracts without removing demo/legacy code.
2. Prove ownership, conflicts, idempotency, lifecycle, restart persistence, and migration isolation.
3. Add Flutter repositories/controllers and explicit authenticated/demo composition.
4. Feed map/expense/planning through a projection; custom activities without coordinates remain honestly unavailable on map.
5. Extend identity export/purge and backup evidence via neutral contributors.
6. Remove no legacy API in 007; later increments retire adapters after equivalent tests.

## Validation Strategy

- Unit: validation, normalization, hard/soft merge, snapshots, date resize, ordering, state transitions.
- Contract/PostgreSQL: isolation, singleton profile, conflict, retries, day resize, active uniqueness, lifecycle, export/purge.
- Migration: empty upgrade, `006_001 → 007_001`, downgrade/re-upgrade, untouched identity/planning evidence.
- Flutter: controllers/repositories, preserved drafts, multi-day timeline, lifecycle, explicit modes, 390×844 at 200%.
- Regression: identity, PMTiles, map/search/OSRM/playback, planning and expense demo; heavy optimizer benchmarks excluded unless touched.

## Complexity Tracking

No constitution violation requires justification.
