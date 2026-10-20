# Tasks: Trip Management MVP

**Input**: Design documents from `specs/002-trip-management-mvp/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Contract, integration and widget tests are required because the specification requires persistence, exact budget calculations, migration repeatability and regression protection.

**Organization**: Tasks are grouped by independently testable user story. Tests precede implementation inside each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with adjacent tasks because it targets different files and has no incomplete dependency.
- **[Story]**: Maps the task to the corresponding user story in spec.md.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bring the existing Flutter shell into the dev-based feature branch and approve the planned runtime dependencies.

- [x] T001 Integrate the committed `codex/stitch-mobile-ui` Flutter shell into `FE/` while preserving root `index.html`, `server.py`, `data/danang.pmtiles`, and existing prototype behavior
- [x] T002 Configure Python 3.11 dependencies FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.x, Alembic, HTTPX and pytest in `BE/requirements.txt`
- [x] T003 [P] Configure Flutter `http` and `shared_preferences` dependencies plus API base URL environment handling in `FE/pubspec.yaml` and `FE/lib/api/api_config.dart`
- [x] T004 [P] Import the versioned Da Nang POI catalog files into `BE/data/snapshots/danang-v1/` without modifying `data/danang.pmtiles`
- [x] T005 Add Python, Flutter and SQLite runtime ignore patterns while preserving intentionally tracked PMTiles executables/assets in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish migration-driven storage, API error/version semantics and Flutter dependency wiring before story implementation.

**⚠️ CRITICAL**: No user story work begins until this phase passes.

- [x] T006 [P] Write failing API health/error-envelope contract tests in `BE/tests/contract/test_health_errors.py`
- [x] T007 [P] Write failing blank-database Alembic upgrade/downgrade smoke test in `BE/tests/integration/test_migrations.py`
- [x] T008 Implement typed settings and configurable default `sqlite:///BE/data/davel_trace.db` in `BE/app/config.py`
- [x] T009 Implement SQLAlchemy engine/session factory with SQLite foreign keys enabled in `BE/app/database.py`
- [x] T010 Configure Alembic with ORM `Base.metadata` in `BE/alembic.ini`, `BE/migrations/env.py`, and `BE/migrations/script.py.mako`
- [x] T011 Implement structured API errors, validation handlers and CORS middleware in `BE/app/errors.py` and `BE/app/main.py`
- [x] T012 Implement FastAPI/Uvicorn entrypoint and health readiness response in `BE/run.py` and `BE/app/main.py`
- [x] T013 [P] Implement typed API response/error parsing in `FE/lib/api/api_client.dart` and `FE/lib/api/api_exception.dart`
- [x] T014 Implement framework-native app state and dependency injection seam in `FE/lib/app/app_state.dart` and `FE/lib/app/app_scope.dart`
- [x] T015 Run foundational tests and make `BE/tests/contract/test_health_errors.py` plus `BE/tests/integration/test_migrations.py` pass

**Checkpoint**: A blank SQLite database is migration-ready, API error semantics are stable, and Flutter can call the API through one client.

---

## Phase 3: User Story 1 - Manage Local Profiles (Priority: P1) 🎯

**Goal**: Persist CRUD travel profiles and exactly one active profile without remote authentication.

**Independent Test**: Create and edit a profile, select it, restart the API/client, and verify the active profile and edited fields remain.

### Tests for User Story 1

- [x] T016 [P] [US1] Write failing profile CRUD/version/delete-confirmation contract tests in `BE/tests/contract/test_profiles_api.py`
- [x] T017 [P] [US1] Write failing profile persistence/restart integration test in `BE/tests/integration/test_profile_persistence.py`
- [x] T018 [P] [US1] Write failing Flutter profile loading/empty/error/form widget tests in `FE/test/features/profiles/profile_flow_test.dart`

### Implementation for User Story 1

- [x] T019 [US1] Implement `UserProfile` fields (`display_name` 1–80, ranges 1–3, structured preferences, version ≥1) and singleton `DeviceState` ORM models in `BE/app/models/profile.py`
- [x] T020 [US1] Implement profile Pydantic schemas and trimmed/range validation in `BE/app/schemas/profile.py`
- [x] T021 [US1] Implement profile repository/service transactions, optimistic version checks and dependent-count confirmation in `BE/app/repositories/profiles.py` and `BE/app/services/profiles.py`
- [x] T022 [US1] Implement profile CRUD and active-profile endpoints from the contract in `BE/app/routers/profiles.py` and wire them in `BE/app/main.py`
- [x] T023 [US1] Add initial code-first schema migration for `user_profiles` and `device_state` in `BE/migrations/versions/0001_management_schema.py`
- [x] T024 [US1] Implement pure Flutter profile domain models/repository in `FE/lib/features/profiles/domain/profile.dart` and `FE/lib/features/profiles/data/profile_repository.dart`
- [x] T025 [US1] Implement profile picker, empty/loading/error states and create/edit/delete-confirmation forms in `FE/lib/features/profiles/presentation/profile_screen.dart`
- [x] T026 [US1] Wire active-profile restoration into app startup and shell navigation in `FE/lib/app/app_state.dart` and `FE/lib/features/shell/presentation/main_shell.dart`
- [x] T027 [US1] Run and pass profile backend and Flutter widget tests

**Checkpoint**: User Story 1 works independently with durable profile state.

---

## Phase 4: User Story 2 - Manage Trips and Manual Itineraries (Priority: P1)

**Goal**: Persist Da Nang trips up to two days and manual ordered activities with warnings instead of automatic AI changes.

**Independent Test**: Create one trip, add three activities, edit and reorder them, restart, and verify order, snapshots and itinerary version.

### Tests for User Story 2

- [x] T028 [P] [US2] Write failing trip CRUD/date/version/delete contract tests in `BE/tests/contract/test_trips_api.py`
- [x] T029 [P] [US2] Write failing activity add/edit/delete/reorder/overlap contract tests in `BE/tests/contract/test_itinerary_api.py`
- [x] T030 [P] [US2] Write failing trip-itinerary restart/cascade integration test in `BE/tests/integration/test_trip_persistence.py`
- [x] T031 [P] [US2] Write failing Flutter trip and itinerary management widget tests in `FE/test/features/trips/trip_flow_test.dart`

### Implementation for User Story 2

- [x] T032 [US2] Implement Trip (`city=da-nang`, ≤2 days, budget ≥0, travelers ≥1, version ≥1), Itinerary and Activity ORM models with unique order and cascades in `BE/app/models/trip.py`
- [x] T033 [US2] Implement trip/activity schemas, coordinate/date/time validation and overlap warning shape in `BE/app/schemas/trip.py`
- [x] T034 [US2] Implement trip repository/service CRUD and optimistic concurrency in `BE/app/repositories/trips.py` and `BE/app/services/trips.py`
- [x] T035 [US2] Implement manual itinerary service that increments itinerary version exactly once per mutation and invalidates route cache, plus a disabled future proposal port in `BE/app/services/itineraries.py` and `BE/app/services/planner.py`
- [x] T036 [US2] Implement trips and activity/reorder REST endpoints in `BE/app/routers/trips.py` and `BE/app/routers/itineraries.py`
- [x] T037 [US2] Add code-first `0002_trip_itinerary.py` migration with `trips`, `itineraries`, `activities` constraints and indexes in `BE/migrations/versions/`
- [x] T038 [US2] Replace UI-coupled demo domain data with pure Trip/Itinerary/Activity models and presentation mappers in `FE/lib/features/trips/domain/` and `FE/lib/features/itinerary/domain/`
- [x] T039 [US2] Implement typed trip/itinerary repositories in `FE/lib/features/trips/data/trip_repository.dart` and `FE/lib/features/itinerary/data/itinerary_repository.dart`
- [x] T040 [US2] Implement trip list/create/edit/delete-confirmation UI with loading/empty/error/retry states in `FE/lib/features/trips/presentation/`
- [x] T041 [US2] Convert the Stitch itinerary screen from fixed demo data to add/edit/delete/reorder manual activities while preserving visual style in `FE/lib/features/itinerary/presentation/itinerary_screen.dart`
- [x] T042 [US2] Run and pass trip/itinerary backend and Flutter widget tests

**Checkpoint**: User Story 2 provides a useful AI-free manual itinerary manager.

---

## Phase 5: User Story 3 - Track Expenses and Budget (Priority: P1)

**Goal**: Persist expense CRUD and exact derived summaries tied to Trip, with 80%/100% warnings.

**Independent Test**: Add expenses to a 3,000,000 VND trip, reach 2,500,000 VND, edit/delete entries and verify totals/categories after restart.

### Tests for User Story 3

- [x] T043 [P] [US3] Write failing expense CRUD/version/validation contract tests in `BE/tests/contract/test_expenses_api.py`
- [x] T044 [P] [US3] Write failing exact summary/80%/100%/negative-remaining unit tests in `BE/tests/unit/test_expense_summary.py`
- [x] T045 [P] [US3] Write failing expense persistence and trip-cascade integration test in `BE/tests/integration/test_expense_persistence.py`
- [x] T046 [P] [US3] Write failing Flutter expense loading/empty/form/edit/delete/alert widget tests in `FE/test/features/expenses/expense_flow_test.dart`

### Implementation for User Story 3

- [x] T047 [US3] Implement Expense ORM model (`amount_vnd` integer ≥0; category `food|ticket|transport|other`; version ≥1) owned by Trip in `BE/app/models/expense.py`
- [x] T048 [US3] Implement expense schemas and summary response in `BE/app/schemas/expense.py`
- [x] T049 [US3] Implement transactional expense CRUD, optimistic concurrency and exact category/threshold summaries in `BE/app/repositories/expenses.py` and `BE/app/services/expenses.py`
- [x] T050 [US3] Implement nested expense endpoints and compatibility summary alias in `BE/app/routers/expenses.py`
- [x] T051 [US3] Add code-first `0003_expenses.py` migration with expense checks and trip/category/time indexes in `BE/migrations/versions/`
- [x] T052 [US3] Implement Flutter expense models/repository in `FE/lib/features/expenses/domain/expense.dart` and `FE/lib/features/expenses/data/expense_repository.dart`
- [x] T053 [US3] Replace the fixed expense demo with persistent add/edit/delete, category totals and 80%/100% UI states in `FE/lib/features/expenses/presentation/expenses_screen.dart`
- [x] T054 [US3] Run and pass expense backend and Flutter widget tests

**Checkpoint**: User Story 3 delivers durable, exact trip budget management.

---

## Phase 6: User Story 4 - Map, POI Catalog and Route Preview (Priority: P2)

**Goal**: Display saved activities and truthful OSRM/fallback geometry on the existing Da Nang map without requiring AI or location permission.

**Independent Test**: Open a three-activity trip, confirm ordered markers, request a route, then simulate OSRM failure and verify the warning/fallback label.

### Tests for User Story 4

- [x] T055 [P] [US4] Write failing POI query/verified/default/limit contract tests in `BE/tests/contract/test_pois_api.py`
- [x] T056 [P] [US4] Write failing OSRM success/timeout/fallback truthfulness tests in `BE/tests/unit/test_routes.py`
- [x] T057 [P] [US4] Write failing Flutter map model/route-source widget tests in `FE/test/features/map/map_management_test.dart`

### Implementation for User Story 4

- [x] T058 [US4] Implement versioned JSON POI catalog repository with normalized Vietnamese search in `BE/app/repositories/poi_catalog.py`
- [x] T059 [US4] Implement POI search/detail schemas and endpoints in `BE/app/schemas/poi.py` and `BE/app/routers/pois.py`
- [x] T060 [US4] Implement OSRM route service with 10-second timeout and explicit display-only fallback in `BE/app/services/routes.py`
- [x] T061 [US4] Implement RouteSegment ORM/cache and route preview endpoint for 2–10 ordered activities in `BE/app/models/route.py`, `BE/app/schemas/route.py`, and `BE/app/routers/routes.py`
- [x] T062 [US4] Add code-first `0004_route_segments.py` migration with route segment tables/indexes in `BE/migrations/versions/`
- [x] T063 [US4] Connect saved itinerary activities, location-denied behavior and route source/warning to the existing Flutter map in `FE/lib/features/map/`
- [x] T064 [US4] Run and pass POI/route backend and Flutter map tests

**Checkpoint**: User Story 4 reuses PMTiles/OSRM with explicit source truthfulness.

---

## Phase 7: User Story 5 - Recovery and Durable UX (Priority: P2)

**Goal**: Preserve usable state across restarts and failures, with consistent loading/empty/error/retry behavior.

**Independent Test**: Complete the whole management journey, restart services, simulate API failure and verify saved state plus retry behavior.

### Tests for User Story 5

- [x] T065 [P] [US5] Write failing full management restart journey test in `BE/tests/integration/test_management_journey.py`
- [x] T066 [P] [US5] Write failing Flutter app startup/cache/API-retry widget test in `FE/test/app/app_recovery_test.dart`

### Implementation for User Story 5

- [x] T067 [US5] Implement local active-profile and last-success metadata cache in `FE/lib/app/local_preferences.dart`
- [x] T068 [US5] Implement consistent async loading/empty/error/retry surfaces in `FE/lib/shared/widgets/async_state_view.dart` and adopt them across management screens
- [x] T069 [US5] Add API retry/reload handling that preserves already-loaded state in `FE/lib/app/app_state.dart`
- [x] T070 [US5] Run and pass the full restart/recovery backend and Flutter tests

**Checkpoint**: All five stories work together and retain data through restart/failure.

---

## Phase 8: Polish & Cross-Cutting Validation

**Purpose**: Complete documentation, migration, security and regression evidence required for PR.

- [x] T071 [P] Update backend setup, migration, environment and DBeaver guidance in `BE/README.md` and `.env.example`
- [x] T072 [P] Update Flutter laptop/mobile-viewport run instructions and API configuration in `FE/README.md`
- [x] T073 [P] Update root architecture/run commands without replacing the required `python server.py` prototype instructions in `README.md`
- [x] T074 Validate a clean Alembic upgrade, schema visibility and foreign-key cascades against a temporary SQLite database per `specs/002-trip-management-mvp/quickstart.md`
- [x] T075 Run complete `pytest`, `flutter analyze`, `flutter test` and Flutter web build suites
- [x] T076 Run root prototype smoke test for map, A/B search, route and play/pause without severe console errors
- [x] T077 Review secrets, generated database files, dependency scope, error logs and `git diff --check` before commit
- [x] T078 Mark completed tasks, run `$speckit.converge`, and append/complete any remaining convergence tasks in `specs/002-trip-management-mvp/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 Setup → Phase 2 Foundation.
- Phase 2 blocks every user story.
- US1 creates profile ownership and precedes US2.
- US2 creates Trip and precedes US3/US4.
- US3 and US4 can run in parallel after US2.
- US5 depends on US1–US4.
- Polish depends on all selected stories.

### Parallel Opportunities

- T003–T005 can proceed in parallel after T001/T002 context is available.
- Contract/integration/widget test files within each story are parallelizable.
- After US2, expense work (US3) and POI/route work (US4) touch separate backend/Flutter features and may run concurrently.
- README updates T071–T073 are parallelizable.

## Implementation Strategy

1. Establish migration/API/Flutter wiring.
2. Deliver profiles, then trips/manual itinerary as the smallest useful management core.
3. Add expense management as the primary MVP value.
4. Attach POI/map/routing without introducing AI ownership.
5. Close persistence/recovery and run the full quickstart.
6. Converge until no spec/plan/task gap remains, then commit, push and open a PR to `dev`.

## Notes

- Tests are written first and must fail for the intended reason before implementation.
- Runtime `.db`, SQLite journal/WAL, secrets and generated build output must not be committed.
- Do not merge or rewrite AI lane branches; consume only the shared POI snapshot and stable contracts needed by this feature.
- Do not delete or ignore `data/danang.pmtiles` or tracked `pmtiles.exe`.

## Phase 9: Convergence

- [x] T079 Surface a non-blocking API error and retry action while preserving already-loaded management data per FR-026 and US5/AC2 (partial)
- [x] T080 Document management migrations, the default SQLite connection string, and DBeaver setup in `BE/README.md` per plan:T071 (partial)
- [x] T081 Align Flutter laptop-preview documentation with the Sơn Trà Breeze Stitch theme and 390 px frame in `FE/README.md` per plan:T072 (partial)
