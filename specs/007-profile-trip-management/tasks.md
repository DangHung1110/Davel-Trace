# Tasks: Profile and Trip Management

**Input**: Design documents from `specs/007-profile-trip-management/`

**Organization**: Tasks are dependency ordered and grouped by independently demonstrable user story.

## Phase 1: Setup

- [ ] T001 Add profile/trip module skeletons and ownership READMEs in `BE/app/modules/profiles/` and `BE/app/modules/trips/`
- [ ] T002 [P] Add Flutter feature skeletons in `FE/lib/features/profile_management/` and `FE/lib/features/trip_management/`
- [ ] T003 [P] Add profile/trip owned-data boundaries to `docs/architecture/ownership-map.md`
- [ ] T004 Register `007_001_profile_trip_management` as the next reviewed revision in `BE/migrations/versions/007_001_profile_trip_management.py`
- [ ] T005 [P] Add disposable fixture/cleanup helpers for two-account profile/trip tests in `BE/tests/conftest.py`
- [ ] T006 Record setup and exact no-new-dependency decision in `specs/007-profile-trip-management/validation.md`

## Phase 2: Foundational

**Purpose**: Blocking ownership, persistence, conflict, and composition seams.

- [ ] T007 Extract reusable Bearer principal dependency without credential-table access in `BE/app/modules/identity/dependencies.py` and update `BE/app/modules/identity/api.py`
- [ ] T008 [P] Define framework-free profile/trip domain validation, state enums, conflict results, and snapshots in `BE/app/modules/profiles/domain.py` and `BE/app/modules/trips/domain.py`
- [ ] T009 Add `TravelerProfile`, `Trip`, `TripDay`, `TripActivity`, `ActiveTripSelection`, `MutationReceipt`, and `TripLifecycleEvent` models with constraints from `data-model.md` to `BE/app/db/models.py`
- [ ] T010 Complete upgrade/downgrade operations, indexes, FKs, and isolated scope for revision `007_001` in `BE/migrations/versions/007_001_profile_trip_management.py`
- [ ] T011 [P] Add unit tests for normalization, 1–14 day/1–20 traveler bounds, local times, hard/soft merge, state transitions, and deterministic ordering in `BE/tests/unit/test_profile_trip_domain.py`
- [ ] T012 Add persistence repositories, owned/non-disclosing lookups, row locks, and transaction helpers in `BE/app/modules/profiles/infrastructure.py` and `BE/app/modules/trips/infrastructure.py`
- [ ] T013 Implement persistent account/operation/resource-scoped receipt checks and fingerprint conflicts in `BE/app/modules/trips/infrastructure.py`
- [ ] T014 Add neutral export/purge contributor registry without identity-product import cycles in `BE/app/core/owned_data.py`
- [ ] T015 [P] Define typed Flutter profile/trip/day/activity/lifecycle/conflict models in `FE/lib/features/profile_management/domain/` and `FE/lib/features/trip_management/domain/`
- [ ] T016 [P] Add per-request header support to `FE/lib/core/networking/api_client.dart` while keeping automatic 401 retry limited to idempotent GET
- [ ] T017 Define narrow `ProfileRepository` and `TripRepository` interfaces plus explicit live/demo mode contracts in `FE/lib/features/profile_management/data/` and `FE/lib/features/trip_management/data/`
- [ ] T018 Run migration empty/006-upgrade/downgrade/re-upgrade and architecture gates; record evidence in `specs/007-profile-trip-management/validation.md`

## Phase 3: User Story 1 — Reusable Travel Profile (P1) 🎯 MVP

**Independent Test**: Create/edit/clear/reopen one owned profile; hard constraints remain distinct and another account receives no disclosure.

- [ ] T019 [P] [US1] Add profile domain/service tests for singleton ownership, normalization, reset, version conflict, and hard constraints in `BE/tests/unit/test_profiles.py`
- [ ] T020 [P] [US1] Add PostgreSQL contract tests for `GET/PUT /v1/profile`, reset, two-account isolation, retry, and restart persistence in `BE/tests/contract/test_profiles_api.py`
- [ ] T021 [US1] Implement profile snapshot, create/update/reset, optimistic version, audit, and export contribution use cases in `BE/app/modules/profiles/application.py`
- [ ] T022 [US1] Implement singular profile endpoints and stable errors from `contracts/api.md` in `BE/app/modules/profiles/api.py`
- [ ] T023 [US1] Mount profile router and owned-data contributor in `BE/app/main.py`
- [ ] T024 [P] [US1] Implement HTTP and seeded-demo profile repositories in `FE/lib/features/profile_management/data/`
- [ ] T025 [US1] Implement profile controller states with preserved drafts/conflict recovery in `FE/lib/features/profile_management/application/profile_controller.dart`
- [ ] T026 [US1] Refactor onboarding/profile editor to one account-owned profile with soft/hard sections in `FE/lib/features/profile_management/presentation/`
- [ ] T027 [P] [US1] Add Flutter repository/controller/widget tests including 390×844 and 200% text scale in `FE/test/profile_management_test.dart`
- [ ] T028 [US1] Demonstrate onboarding → edit/reset → sign-out/in persistence and record evidence in `specs/007-profile-trip-management/validation.md`

## Phase 4: User Story 2 — Create and Reopen an Owned Trip (P1)

**Independent Test**: Create a three-day trip with snapshot/override, retry once, restart/sign in, and reopen one identical owned aggregate.

- [ ] T029 [P] [US2] Add trip validation/snapshot/date generation/idempotency tests in `BE/tests/unit/test_trips.py`
- [ ] T030 [P] [US2] Add trip create/list/detail/update, hard-override rejection, conflict, isolation, and persistence contracts in `BE/tests/contract/test_trips_api.py`
- [ ] T031 [US2] Implement effective profile snapshot, trip create/update, date extension, confirmed shortening, and review-state use cases in `BE/app/modules/trips/application.py`
- [ ] T032 [US2] Implement trip list/create/detail/update endpoints and filters from `contracts/api.md` in `BE/app/modules/trips/api.py`
- [ ] T033 [US2] Mount trip router in `BE/app/main.py` and prove only active accounts can mutate records
- [ ] T034 [P] [US2] Implement HTTP and seeded-demo trip repositories with idempotency/version headers in `FE/lib/features/trip_management/data/`
- [ ] T035 [US2] Implement trip workspace controller with list/detail/editor/conflict/date-reduction states in `FE/lib/features/trip_management/application/trip_controller.dart`
- [ ] T036 [P] [US2] Build trip list and search/filter/empty-state UI in `FE/lib/features/trip_management/presentation/trip_list_screen.dart`
- [ ] T037 [P] [US2] Build trip create/edit and effective-profile review UI in `FE/lib/features/trip_management/presentation/trip_editor.dart`
- [ ] T038 [P] [US2] Add trip repository/controller/widget tests for retry, conflict, restart, and hard constraints in `FE/test/trip_management_test.dart`
- [ ] T039 [US2] Demonstrate three-day trip retry/reopen/override and record evidence in `specs/007-profile-trip-management/validation.md`

## Phase 5: User Story 3 — Organize Days and Activities (P1)

**Independent Test**: Manage activities on two days, reorder/status/remove them, reopen, and retain valid contiguous timelines.

- [ ] T040 [P] [US3] Add day-resize, activity validation, overlap warning, CRUD/status, and reorder unit tests in `BE/tests/unit/test_trip_activities.py`
- [ ] T041 [P] [US3] Add day/activity endpoint contracts for retry, versions, ordering, ownership, and atomic failures in `BE/tests/contract/test_trip_activities_api.py`
- [ ] T042 [US3] Implement day generation/resizing and atomic impact confirmation in `BE/app/modules/trips/application.py`
- [ ] T043 [US3] Implement activity create/edit/remove/status/reorder with contiguous positions in `BE/app/modules/trips/application.py`
- [ ] T044 [US3] Add day/activity endpoints and warnings from `contracts/api.md` in `BE/app/modules/trips/api.py`
- [ ] T045 [P] [US3] Build multi-day selector/timeline in `FE/lib/features/trip_management/presentation/trip_detail_screen.dart`
- [ ] T046 [P] [US3] Build scrollable activity editor, status, reorder, overlap, and unresolved-reference states in `FE/lib/features/trip_management/presentation/activity_editor.dart`
- [ ] T047 [US3] Wire day/activity methods and conflict-preserving drafts through `FE/lib/features/trip_management/application/trip_controller.dart`
- [ ] T048 [P] [US3] Add multi-day/activity/reorder/200%-scale widget and controller tests in `FE/test/trip_activity_test.dart`
- [ ] T049 [US3] Demonstrate two-day timeline, retry-safe reorder, completion/skip and record evidence in `specs/007-profile-trip-management/validation.md`

## Phase 6: User Story 4 — Find and Switch Active Trip (P1)

**Independent Test**: Filter 100 owned trips and switch active trip across two sessions while preserving at most one explicit selection.

- [ ] T050 [P] [US4] Add search/sort/filter and concurrent active-selection tests in `BE/tests/contract/test_trip_selection_api.py`
- [ ] T051 [US4] Implement normalized title search, lifecycle filters, deterministic sorting, and bounded cursor pagination in `BE/app/modules/trips/application.py`
- [ ] T052 [US4] Implement versioned set/clear active selection with row locking and no silent fallback in `BE/app/modules/trips/application.py`
- [ ] T053 [US4] Complete list and active-selection contracts in `BE/app/modules/trips/api.py`
- [ ] T054 [US4] Add active marker/switch/clear and lifecycle filters to `FE/lib/features/trip_management/presentation/trip_list_screen.dart`
- [ ] T055 [US4] Persist explicit active context in controller without selecting the first item in `FE/lib/features/trip_management/application/trip_controller.dart`
- [ ] T056 [P] [US4] Add 100-trip filter, two-session selection, empty-state, restart, and mobile tests in `FE/test/trip_selection_test.dart`
- [ ] T057 [US4] Demonstrate one active trip under concurrent sessions and record timing/evidence in `specs/007-profile-trip-management/validation.md`

## Phase 7: User Story 5 — Archive, Restore, and Delete Safely (P2)

**Independent Test**: Archive/restore/delete/recover one trip and purge an expired fixture without changing unrelated records.

- [ ] T058 [P] [US5] Add lifecycle state-machine, exact-scope, audit privacy, and purge idempotency tests in `BE/tests/unit/test_trip_lifecycle.py`
- [ ] T059 [P] [US5] Add archive/restore/delete/recover/active-clear/export contracts in `BE/tests/contract/test_trip_lifecycle_api.py`
- [ ] T060 [US5] Implement atomic lifecycle transitions, 30-day recovery, active clearing, and privacy-safe events in `BE/app/modules/trips/application.py`
- [ ] T061 [US5] Add archive/restore/deletion endpoints to `BE/app/modules/trips/api.py`
- [ ] T062 [US5] Implement scoped repeat-safe purge and minimized evidence in `BE/scripts/purge_trips.py`
- [ ] T063 [US5] Extend identity export/account purge composition and backup relationships in `BE/app/core/owned_data.py`, `BE/app/modules/identity/service.py`, and `BE/scripts/backup_database.py`
- [ ] T064 [US5] Build lifecycle filters, confirmations, recovery, and no-auto-activation UI in `FE/lib/features/trip_management/presentation/`
- [ ] T065 [P] [US5] Add lifecycle controller/widget tests and exact affected-scope assertions in `FE/test/trip_lifecycle_test.dart`
- [ ] T066 [US5] Demonstrate archive/restore/delete/recover/purge and record evidence in `specs/007-profile-trip-management/validation.md`

## Phase 8: Compatibility and Product Validation

- [ ] T067 Implement authenticated HTTP versus explicit demo composition in `FE/lib/app.dart` without network fallback
- [ ] T068 Add temporary selected-trip/day projection for current map/expense/planning consumers in `FE/lib/features/management/data/management_repository_adapter.dart`
- [ ] T069 Preserve shell/navigation keys and evolve itinerary tab into trip workspace in `FE/lib/features/shell/presentation/main_shell.dart`
- [ ] T070 [P] Add compatibility tests for identity, map, route/playback, expense/planning demo, live/demo/stale labels in `FE/test/product_compatibility_test.dart`
- [ ] T071 [P] Extend architecture, migration, backup, export/purge, and no-secret tests in `BE/tests/architecture/`, `BE/tests/integration/`, and `BE/tests/unit/test_no_secrets.py`
- [ ] T072 Update `README.md`, `BE/README.md`, `FE/README.md`, DBeaver/demo/backup guidance, and roadmap status
- [ ] T073 Run proportional backend suite, migration gates, Flutter format/analyze/full tests, release web build, and static map smoke; record exact results in `specs/007-profile-trip-management/validation.md`
- [ ] T074 Run `git diff --check`, secret scan, Docker disk audit without prune/down-v, and account/trip fixture cleanup; record evidence
- [ ] T075 Run `/speckit.converge`, implement every appended gap, and repeat until the feature is converged

## Dependencies and Execution Order

- Setup → Foundation blocks every story.
- US1 provides the profile snapshot used by US2.
- US2 provides trips/days for US3 and trip list for US4.
- US3 and US4 can proceed in parallel after US2.
- US5 depends on trip ownership and active-selection behavior.
- Compatibility/validation follows all selected stories.

## Parallel Opportunities

- Backend domain/contract tests and Flutter domain scaffolding use separate files.
- Within each story, `[P]` tests and presentation files can proceed after contracts stabilize.
- US3 activity work and US4 list/selection work are independent after US2.
- Documentation and selected regression preparation can run while final story validation executes.

## Implementation Strategy

1. Deliver US1 profile onboarding as the smallest independently useful slice.
2. Add durable trip creation/reopen, then days/activities and active selection.
3. Add lifecycle only after ownership/version/idempotency behavior is proven.
4. Keep seeded demo mode and current map/expense/planning consumers via explicit adapters.
5. Commit small logical groups, push only the task branch, and PR into `feat/product-platform`.
