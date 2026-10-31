# Tasks: Product Platform Foundation

**Input**: Design documents from `specs/005-platform-foundation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by Constitution Test-First and the feature success criteria. Test tasks must be written and observed failing before their implementation tasks.

**Organization**: Tasks are grouped by user story and use exact repository paths.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it targets independent files and has no incomplete dependency.
- **[Story]**: User story from `spec.md`.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add approved dependencies and non-behavioral skeletons.

- [X] T001 Add compatible bounded dependencies for `sqlalchemy`, `alembic`, `psycopg[binary]`, and `pydantic-settings` in `BE/requirements.txt`
- [X] T002 [P] Add the PostgreSQL 16 service, healthcheck, named volume, and `docker compose --env-file BE/.env` password wiring in `compose.yaml`
- [X] T003 [P] Expand safe runtime exclusions for database archives, manifests, exports, and generated caches without ignoring tracked PMTiles in `.gitignore`
- [X] T004 [P] Create package skeletons and `__init__.py` files under `BE/app/core/`, `BE/app/db/`, `BE/app/modules/planning_evidence/`, `BE/scripts/`, and `BE/tests/architecture/`
- [X] T005 [P] Create cross-cutting Flutter directories under `FE/lib/core/config/`, `FE/lib/core/errors/`, `FE/lib/core/networking/`, and `FE/lib/core/observability/` without moving behavior yet

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Supply shared test/runtime primitives before user-story implementation.

**Critical**: No user-story implementation starts until these tasks pass.

- [X] T006 Add isolated settings, temporary-environment, correlation-ID, and PostgreSQL integration fixtures in `BE/tests/conftest.py`
- [X] T007 [P] Add SQLAlchemy declarative base and naming conventions in `BE/app/db/base.py`
- [X] T008 [P] Add transaction-scoped engine/session factory interfaces in `BE/app/db/session.py`
- [X] T009 Configure Alembic metadata loading and environment-only database URL in `BE/alembic.ini`, `BE/migrations/env.py`, and `BE/migrations/script.py.mako`
- [X] T010 Add reusable safe test doubles for planning-evidence repositories in `BE/tests/support/planning_evidence.py`

**Checkpoint**: Shared persistence and test scaffolding are available.

---

## Phase 3: User Story 1 — Repeatable Complete Local Startup (Priority: P1) 🎯 MVP

**Goal**: A clean checkout starts predictably, validates configuration, and reports liveness/readiness by component.

**Independent Test**: Configure a clean environment, initialize schema, start backend/mobile, verify health/readiness, then repeat with missing database and invalid secret-bearing settings without leaking values.

### Tests for User Story 1

- [X] T011 [P] [US1] Write failing typed configuration and secret-redaction tests in `BE/tests/unit/test_platform_config.py`
- [X] T012 [P] [US1] Write failing `/v1/health` backward-compatibility and `/v1/ready` component contract tests in `BE/tests/contract/test_platform_health.py`
- [X] T013 [P] [US1] Write failing startup tests for missing database, schema behind/ahead, missing catalog, and optional-provider degradation in `BE/tests/integration/test_platform_startup.py`
- [X] T014 [P] [US1] Write a failing CORS test proving production rejects unlisted origins while local configured origins work in `BE/tests/contract/test_cors.py`

### Implementation for User Story 1

- [X] T015 [US1] Replace the custom settings loader with typed `APP_MODE`, `DATABASE_URL`, `ALLOWED_ORIGINS`, snapshot, and optional-provider validation in `BE/app/core/config.py`, preserving a compatibility export from `BE/app/config.py`
- [X] T016 [US1] Implement database connectivity and Alembic-head inspection without automatic production migration in `BE/app/db/migrations.py`
- [X] T017 [US1] Implement required/optional component readiness models and checks in `BE/app/core/health.py`
- [X] T018 [US1] Wire restricted configuration-driven CORS, `/v1/health`, and `/v1/ready` into the composition root in `BE/app/main.py`
- [X] T019 [US1] Update non-secret example values and PowerShell/Git Bash startup commands in `BE/.env.example`, `README.md`, and `BE/README.md`

**Checkpoint**: Startup and health are independently demonstrable; optional AI/OSRM failure does not block core readiness.

---

## Phase 4: User Story 2 — Durable Authoritative Data (Priority: P1)

**Goal**: PostgreSQL schema, evidence records, migration, import, seed, backup, and restore are durable and repeatable.

**Independent Test**: Initialize empty PostgreSQL, write evidence, restart, upgrade from the prior revision, import a legacy SQLite file twice, then back up/restore and compare IDs/counts.

### Tests for User Story 2

- [X] T020 [P] [US2] Write failing repository contract tests for idempotent acceptance writes, stable ordering, shadow persistence across three consecutive session/process reconnections, and transaction rollback in `BE/tests/contract/test_planning_evidence_repository.py`
- [X] T021 [P] [US2] Write failing model constraint tests for `idempotency_key` length 8–128; positive `schema_version`/rank; correlation in [-1,1]; non-negative veto/latency/counts; shadow status `skipped|completed|failed`; seed mode `demo|test` in `BE/tests/unit/test_platform_models.py`
- [X] T022 [P] [US2] Write failing empty-schema initialization, repeat-upgrade, and failed-migration readiness tests in `BE/tests/integration/test_migrations.py`; add previous-revision coverage only when a later revision exists
- [X] T023 [P] [US2] Write failing legacy import tests for JSON/timestamp validation, SHA-256 idempotency, equivalent conflicts, hard conflicts, and atomic rollback in `BE/tests/integration/test_acceptance_import.py`
- [X] T024 [P] [US2] Write failing demo-seed production rejection and repeatability tests in `BE/tests/integration/test_demo_seed.py`
- [X] T025 [P] [US2] Write failing backup-manifest checksum, revision, count, and representative-read verification tests in `BE/tests/integration/test_backup_restore.py`

### Implementation for User Story 2

- [X] T026 [P] [US2] Define acceptance/shadow domain records and the `PlanningEvidenceRepository` port in `BE/app/modules/planning_evidence/domain.py` and `BE/app/modules/planning_evidence/application.py`
- [X] T027 [P] [US2] Implement SQLAlchemy models with the exact constraints from `data-model.md` for `AcceptanceRecord`, `ShadowObservation`, `ImportRun`, and `SeedRun` in `BE/app/db/models.py`
- [X] T028 [US2] Add and manually review the initial PostgreSQL schema revision in `BE/migrations/versions/005_001_platform_foundation.py`
- [X] T029 [US2] Implement `PostgresPlanningEvidenceRepository` without repository-level commits inside caller-owned transactions in `BE/app/modules/planning_evidence/infrastructure.py`
- [X] T030 [US2] Implement evidence use cases and compatibility-shaped DTO mapping in `BE/app/modules/planning_evidence/application.py`
- [X] T031 [US2] Implement the explicit atomic legacy SQLite importer with fingerprint tracking in `BE/scripts/import_acceptance_sqlite.py`
- [X] T032 [P] [US2] Implement deterministic `demo|test`-only seed execution and scoped reset safeguards in `BE/scripts/seed_demo.py`
- [X] T033 [P] [US2] Implement `pg_dump` archive/manifest creation and restore verification helpers in `BE/scripts/backup_database.py` and `BE/scripts/verify_backup.py`
- [X] T034 [US2] Wire PostgreSQL evidence repository selection into `BE/app/main.py` and `BE/app/routers/planning_evidence.py` without changing public success fields

**Checkpoint**: Planning evidence is authoritative in PostgreSQL; restart, migration, import, seed, backup, and restore tests pass.

---

## Phase 5: User Story 3 — Preserve Existing Product Behavior During Refactor (Priority: P1)

**Goal**: Existing planner, map, route, playback, expense demo, and Flutter navigation remain compatible.

**Independent Test**: Run backend regression, Flutter widgets, PMTiles byte-range check, and the mobile demo before/after the structural move and compare public behavior.

### Tests for User Story 3

- [X] T035 [P] [US3] Extend accepted-plan API regression coverage for list/get/save/readiness response compatibility in `BE/tests/contract/test_acceptance_api.py`
- [X] T036 [P] [US3] Add Flutter regression tests for itinerary, map, expenses, profile navigation and seeded/stale/live labels in `FE/test/platform_foundation_regression_test.dart`
- [X] T037 [P] [US3] Add an automated PMTiles `206 Partial Content` and root-map asset smoke test in `BE/tests/integration/test_root_map_server.py`

### Implementation for User Story 3

- [X] T038 [US3] Implement a temporary legacy `AcceptanceStore` adapter to the repository port with owner/removal annotations in `BE/app/modules/planning_evidence/infrastructure.py`
- [X] T039 [US3] Migrate all planning-evidence endpoint callers to the application contract and remove direct production SQLite construction from `BE/app/routers/planning_evidence.py` and `BE/app/routers/select.py`
- [X] T040 [US3] Preserve byte-range server, PMTiles, search A/B, OSRM/fallback labeling, and vehicle playback while updating only regression documentation in `README.md`

**Checkpoint**: All pre-existing public behavior and demo flows remain green.

---

## Phase 6: User Story 4 — Clear Capability Ownership (Priority: P1)

**Goal**: Backend and Flutter dependency directions are documented and automatically checked.

**Independent Test**: Insert representative forbidden imports and confirm architecture tests fail, then remove them and locate five capability owners from the ownership map.

### Tests for User Story 4

- [X] T041 [P] [US4] Write failing AST import rules for backend domain/application/transport/infrastructure boundaries and cycles in `BE/tests/architecture/test_backend_boundaries.py`
- [X] T042 [P] [US4] Write failing Dart import rules for feature domain/data/presentation/core boundaries in `BE/tests/architecture/test_flutter_boundaries.py`

### Implementation for User Story 4

- [X] T043 [US4] Complete the planning-evidence `api/application/domain/infrastructure` package boundary and composition exports in `BE/app/modules/planning_evidence/`
- [X] T044 [P] [US4] Move Flutter API configuration, exception mapping, and HTTP client into `FE/lib/core/config/`, `FE/lib/core/errors/`, and `FE/lib/core/networking/`, leaving compatibility exports at old paths until callers migrate
- [X] T045 [US4] Update Flutter imports to feature/core boundaries without changing screens in `FE/lib/app_state.dart`, `FE/lib/features/planning/`, and `FE/lib/features/management/`
- [X] T046 [P] [US4] Document capability owners, allowed dependencies, adapters, and removal conditions in `docs/architecture/capability-ownership.md`

**Checkpoint**: Automated checks detect forbidden cycles/imports and ownership is locatable.

---

## Phase 7: User Story 5 — Honest Demo and Production Modes (Priority: P2)

**Goal**: Demo data is explicit/isolated and production writes never silently fall back.

**Independent Test**: Run identical actions in demo and production modes, restart, reset demo, and simulate PostgreSQL failure while confirming distinct labels/IDs/storage behavior.

### Tests for User Story 5

- [X] T047 [P] [US5] Write failing mode-isolation and store-selection tests proving production cannot select SQLite/in-memory fallback in `BE/tests/integration/test_app_modes.py`
- [X] T048 [P] [US5] Write failing Flutter tests proving demo labels remain visible and failed production writes are not reported as persisted in `FE/test/demo_production_mode_test.dart`

### Implementation for User Story 5

- [X] T049 [US5] Implement explicit mode-aware dependency selection and production failure behavior in `BE/app/core/config.py` and `BE/app/main.py`
- [X] T050 [US5] Implement scoped demo metadata/reset behavior in `BE/scripts/seed_demo.py` and expose only safe mode metadata through `BE/app/core/health.py`
- [X] T051 [US5] Propagate explicit demo/live mode and authoritative-write failures through `FE/lib/app_state.dart` and feature presentation labels without local-success fallback

**Checkpoint**: Demo and production records cannot be confused and production failure is honest.

---

## Phase 8: User Story 6 — Diagnose Failures Without Exposing Secrets (Priority: P2)

**Goal**: Every action is correlatable and errors/logs are stable, actionable, and secret-safe.

**Independent Test**: Trigger validation, data, dependency, offline, and unexpected failures; verify one correlation ID across Flutter/backend and zero secrets in responses/logs.

### Tests for User Story 6

- [X] T052 [P] [US6] Write failing correlation-header and standardized error-envelope contract tests in `BE/tests/contract/test_error_correlation.py`
- [X] T053 [P] [US6] Extend secret and personal-data redaction tests for configuration, connection URLs, logs, health, and exceptions in `BE/tests/unit/test_no_secrets.py`
- [X] T054 [P] [US6] Write failing Flutter API error-category and correlation propagation tests in `FE/test/api_diagnostics_test.dart`

### Implementation for User Story 6

- [X] T055 [P] [US6] Implement validated request-local correlation context middleware in `BE/app/core/request_context.py`
- [X] T056 [P] [US6] Implement structured standard-library logging with redaction and correlation binding in `BE/app/core/logging.py`
- [X] T057 [US6] Implement stable safe error mapping and update exception handlers in `BE/app/core/errors.py`, `BE/app/routers/__init__.py`, and `BE/app/main.py`
- [X] T058 [US6] Implement Flutter correlation headers and stable category mapping in `FE/lib/core/networking/api_client.dart` and `FE/lib/core/errors/api_exception.dart`

**Checkpoint**: All tested failures correlate safely without external observability.

---

## Phase 9: Polish & Cross-Cutting Validation

**Purpose**: Complete documentation, security, and end-to-end evidence.

- [X] T059 [P] Update PostgreSQL/DBeaver, migration, seed, import, backup/restore, PowerShell, and Git Bash instructions in `README.md`, `BE/README.md`, and `FE/README.md`
- [X] T060 [P] Add exact canonical setup/test/demo commands and expected outcomes to `specs/005-platform-foundation/quickstart.md`
- [X] T061 Run all backend tests and record only reproducible fixes in `BE/tests/`
- [X] T062 Run Flutter `analyze`, widget tests, release web build, and desktop phone-frame smoke flow against the backend in `FE/`
- [X] T063 Run root PMTiles range, map/search/route/playback smoke validation through `server.py` and `index.html`
- [X] T064 Perform clean PostgreSQL initialization, legacy import twice, three persistence reconnections, backup/restore, and DBeaver inspection using `specs/005-platform-foundation/quickstart.md`
- [X] T065 Scan tracked files and captured normal logs for secrets/runtime databases/backups, then verify `git diff --check` and intended tracked PMTiles in `.gitignore`

---

## Dependencies & Execution Order

### Phase dependencies

```text
Setup → Foundational
               ├─→ US1 Startup
               └─→ US2 Durable Data
US1 + US2 ───────→ US3 Regression Preservation
US2 ─────────────→ US4 Capability Ownership
US1 + US2 ───────→ US5 Demo/Production Honesty
US1 ─────────────→ US6 Diagnostics
US1..US6 ────────→ Polish/End-to-End Validation
```

### Within each story

- Tests are written and observed failing before implementation.
- Models/ports precede repositories and use cases.
- Use cases precede API/composition wiring.
- Story checkpoint must pass before its dependent story begins.

### Parallel opportunities

- T002–T005 can proceed independently after T001 is agreed.
- T011–T014, T020–T025, T035–T037, T041–T042, T047–T048, and T052–T054 are parallel test-writing groups.
- T026/T027 and T032/T033 target independent files.
- US4 and US6 can proceed in parallel after their stated dependencies.
- Documentation tasks T059/T060 can proceed in parallel with final test execution.

## Parallel Examples

### User Story 2

```text
T020 repository contracts
T021 model constraints
T022 migration lifecycle
T023 legacy import
T024 demo seed
T025 backup/restore
```

After those fail as expected, T026 and T027 can be implemented in parallel; T032 and T033 can proceed after their respective tests.

### User Story 6

```text
T052 backend correlation/error contract
T053 redaction tests
T054 Flutter diagnostics tests
```

Then T055 and T056 can run in parallel before T057/T058 integration.

## Implementation Strategy

### MVP checkpoint

1. Complete Setup and Foundational phases.
2. Complete US1 and validate clean startup independently.
3. Continue immediately through US2 because PostgreSQL durability is the production foundation requirement.

### Incremental delivery

1. Startup/readiness first.
2. PostgreSQL evidence persistence and operations second.
3. Regression compatibility before structural ownership moves.
4. Ownership rules, mode honesty, and diagnostics as isolated slices.
5. Full quickstart validation before PR into `feat/product-platform`.

### Branch cleanup

After this task branch is reviewed, merged into `feat/product-platform`, and verified reachable from that branch, delete only `task/005-platform-foundation` locally/remotely. Keep `feat/product-platform` until the complete product is ready for `dev`.

## Notes

- `[P]` means different files and no incomplete dependency.
- Commit after each task or coherent logical group.
- Do not add feature business logic to `core`, `shared`, or compatibility adapters.
- Do not remove legacy entry points until callers and tests use the replacement.

## Phase 10: Convergence

- [X] T066 Add schema behind/ahead and failed-migration readiness coverage in `BE/tests/integration/test_migrations.py` and `BE/tests/integration/test_platform_startup.py` per FR-010, FR-011, SC-004, SC-005 (partial)
- [X] T067 Extend backend architecture checks to cover transport/infrastructure directions and capability dependency cycles in `BE/tests/architecture/test_backend_boundaries.py` per FR-024, SC-008, SC-009 (partial)
- [X] T068 Extend Flutter architecture checks for feature data/presentation/core directions and dependency cycles in `BE/tests/architecture/test_flutter_boundaries.py` per FR-019, FR-020, FR-024 (partial)
- [X] T069 Add shadow reconnection, negative import-count constraint, and invalid legacy timestamp coverage in `BE/tests/contract/test_planning_evidence_repository.py`, `BE/tests/unit/test_platform_models.py`, and `BE/tests/integration/test_acceptance_import.py` per FR-012, FR-013, T020, T021, T023 (partial)
- [X] T070 Include representative relationship evidence in backup manifests and restore comparison in `BE/scripts/backup_database.py`, `BE/scripts/verify_backup.py`, and `BE/tests/integration/test_backup_restore.py` per FR-016, SC-006, T025, T033 (partial)
