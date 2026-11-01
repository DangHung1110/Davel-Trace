# Tasks: Identity and Access

**Input**: Design documents from `specs/006-identity-access/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Required by the project constitution. Routine validation stays proportional to a student project; heavyweight optimizer benchmarks run only when affected.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can be implemented in parallel because it owns different files and has no incomplete dependency.
- **[Story]**: Maps to the independently demonstrable user story in `spec.md`.

## Phase 1: Setup

**Purpose**: Register approved dependencies, configuration, and module/test structure without changing runtime behavior.

- [ ] T001 Add `pwdlib[argon2]` to `BE/requirements.txt` and `flutter_secure_storage` to `FE/pubspec.yaml` with rationale retained in `specs/006-identity-access/research.md`
- [ ] T002 [P] Add access/refresh/action TTLs, abuse limits, deletion grace period, and production-safe dev-outbox validation to `BE/app/core/config.py` and placeholders to `BE/.env.example`
- [ ] T003 [P] Create identity module exports and package ownership documentation in `BE/app/modules/identity/__init__.py`, `BE/app/modules/identity/README.md`, and `docs/architecture/ownership-map.md`
- [ ] T004 [P] Create Flutter auth feature public barrel and core session-store interfaces in `FE/lib/features/auth/auth.dart` and `FE/lib/core/auth/auth_session_store.dart`
- [ ] T005 Update schema/readiness expectations from `005_001` to `006_001` in the migration test fixtures and backup manifest helpers under `BE/tests/` and `BE/scripts/`

---

## Phase 2: Foundational Identity Infrastructure

**Purpose**: Shared data, crypto, repository, delivery, and error primitives required by every story.

**⚠️ CRITICAL**: User-story implementation starts only after this phase passes its focused tests.

- [ ] T006 [P] Add failing unit tests for normalized case-insensitive email, password policy/Argon2 hash upgrade, opaque token generation/hash comparison, and safe serialization in `BE/tests/unit/test_identity_security.py`
- [ ] T007 [P] Add failing schema tests for account/session/action/lifecycle constraints and `005_001 → 006_001` upgrade/downgrade in `BE/tests/integration/test_identity_migration.py`
- [ ] T008 Implement identity enums, value objects, lifecycle transitions, principal, and safe response models in `BE/app/modules/identity/domain.py`
- [ ] T009 Implement Argon2 password hashing and 256-bit opaque credential/action helpers storing only SHA-256 digests in `BE/app/modules/identity/security.py`
- [ ] T010 Add Account, RoleAssignment, Session, OneTimeAction, PasswordHistory, SecurityRateLimit, AccountLifecycleEvent, SecurityAuditEvent, and ExportRequest models with constraints from `data-model.md` in `BE/app/db/models.py`
- [ ] T011 Create reversible Alembic revision `006_001` for identity tables, indexes, and constraints in `BE/alembic/versions/006_001_identity_access.py`
- [ ] T012 Implement transactional identity repository ports/adapters, row locking, idempotent revocation, and safe aggregate loading in `BE/app/modules/identity/infrastructure.py`
- [ ] T013 [P] Implement delivery port, disabled production adapter, and bounded process-memory demo inbox in `BE/app/modules/identity/delivery.py`
- [ ] T014 Implement shared identity errors, audit creation, rate-limit counter, and current-principal authorization helpers in `BE/app/modules/identity/application.py`
- [ ] T015 Run focused foundation tests and record migration head, downgrade isolation, no plaintext secret persistence, and planning-evidence compatibility evidence in `specs/006-identity-access/validation.md`

**Checkpoint**: Identity schema and security primitives are ready; no public identity endpoint exists yet.

---

## Phase 3: User Story 1 — Register, Verify, and Sign In (Priority: P1) 🎯 MVP

**Goal**: A traveler registers, verifies email ownership, signs in, and reaches the authenticated shell.

**Independent Test**: Register an unused normalized email, consume one dev-delivered verification action once, sign in, restart the client, and prove invalid/unverified credentials cannot enter.

### Tests first

- [ ] T016 [P] [US1] Add failing API contract tests for register, resend, verify, login, non-enumeration, duplicate concurrency, rate limits, dev-inbox gating, correlation headers, and secret-free bodies in `BE/tests/contract/test_identity_registration.py`
- [ ] T017 [P] [US1] Add failing PostgreSQL integration journey for persistence/restart and unique normalized email in `BE/tests/integration/test_identity_registration.py`
- [ ] T018 [P] [US1] Add failing Flutter controller/repository tests for signed-out, registering, verification-required, signing-in, authenticated, and demo states in `FE/test/auth_controller_test.dart`
- [ ] T019 [P] [US1] Add failing 390×844 widget tests for welcome, registration, verification, login, keyboard scroll, errors, and seeded-demo labeling in `FE/test/auth_flow_test.dart`

### Backend implementation

- [ ] T020 [US1] Implement register/resend/verify/login use cases including default traveler role, delivery state, audit, non-enumeration, and atomic duplicate handling in `BE/app/modules/identity/application.py`
- [ ] T021 [US1] Implement request/response schemas, `/v1/auth/register`, verification, login, and gated dev-inbox endpoints from `contracts/api.md` in `BE/app/modules/identity/api.py`
- [ ] T022 [US1] Mount identity routes and preserve foundation error/correlation envelopes in `BE/app/main.py`

### Flutter implementation

- [ ] T023 [P] [US1] Implement account/auth domain models and repository contract in `FE/lib/features/auth/domain/models.dart` and `FE/lib/features/auth/data/auth_repository.dart`
- [ ] T024 [US1] Implement HTTP register/verify/login/dev-inbox adapter with stable error mapping in `FE/lib/features/auth/data/http_auth_repository.dart`
- [ ] T025 [US1] Implement auth controller state machine, access credential memory handling, and explicit demo entry in `FE/lib/features/auth/application/auth_controller.dart`
- [ ] T026 [P] [US1] Build Vietnamese welcome/sign-in and registration screens in `FE/lib/features/auth/presentation/sign_in_screen.dart` and `FE/lib/features/auth/presentation/register_screen.dart`
- [ ] T027 [P] [US1] Build verification screen and visibly development-only inbox helper in `FE/lib/features/auth/presentation/verify_screen.dart`
- [ ] T028 [US1] Add auth gate and authenticated/demo handoff without changing the current management repository in `FE/lib/features/auth/presentation/auth_gate.dart` and `FE/lib/app.dart`
- [ ] T029 [US1] Run US1 backend/Flutter tests and record the registration → verification → login → authenticated shell plus seeded-demo bypass demonstration in `specs/006-identity-access/validation.md`

**Checkpoint**: First useful identity MVP is independently demonstrable.

---

## Phase 4: User Story 2 — Continue and Control Sessions (Priority: P1)

**Goal**: Authentication survives restart, rotates safely, supports two devices, and allows precise or global revocation.

**Independent Test**: Sign in twice, refresh after restart, list both sessions, revoke one, replay its refresh credential, and sign out everywhere.

- [ ] T030 [P] [US2] Add failing API/integration tests for refresh rotation/replay, list/revoke/revoke-others/logout/logout-all, expired status, and concurrent protected access in `BE/tests/contract/test_identity_sessions.py` and `BE/tests/integration/test_identity_sessions.py`
- [ ] T031 [P] [US2] Add failing Flutter secure-store, startup refresh, single retry, and logout-state tests in `FE/test/auth_session_test.dart`
- [ ] T032 [US2] Implement rotate/replay-family revocation, current-principal resolution, session listing, and revocation use cases in `BE/app/modules/identity/application.py`
- [ ] T033 [US2] Add refresh and authenticated session endpoints plus Bearer dependency in `BE/app/modules/identity/api.py`
- [ ] T034 [US2] Implement `flutter_secure_storage` session adapter and keep access credentials memory-only in `FE/lib/core/auth/secure_auth_session_store.dart`
- [ ] T035 [US2] Add authenticated request/retry integration and startup refresh to `FE/lib/features/auth/data/http_auth_repository.dart` and `FE/lib/features/auth/application/auth_controller.dart`
- [ ] T036 [US2] Build session/security screen with current-device label, revoke controls, and honest remote-revocation failure state in `FE/lib/features/auth/presentation/security_screen.dart`
- [ ] T037 [US2] Run the two-browser session demo and record proof that revoked/replayed credentials fail on the next protected request in `specs/006-identity-access/validation.md`

---

## Phase 5: User Story 3 — Recover a Forgotten Password (Priority: P1)

**Goal**: A traveler recovers securely without email enumeration, and all older access is invalidated.

**Independent Test**: Request recovery for known/unknown emails, compare public responses, consume one action, and prove old password, sessions, and actions fail.

- [ ] T038 [P] [US3] Add failing contract/integration tests for non-enumerating request, action expiry/replay/supersession, immediate password reuse rejection, session invalidation, and dev delivery failure in `BE/tests/contract/test_identity_recovery.py` and `BE/tests/integration/test_identity_recovery.py`
- [ ] T039 [P] [US3] Add failing Flutter recovery/reset state and 390×844 widget tests in `FE/test/auth_recovery_test.dart`
- [ ] T040 [US3] Implement recovery request/confirm, bounded password history, action invalidation, and atomic session revocation in `BE/app/modules/identity/application.py`
- [ ] T041 [US3] Add recovery endpoints from `contracts/api.md` in `BE/app/modules/identity/api.py`
- [ ] T042 [US3] Build recovery/reset UI and repository methods in `FE/lib/features/auth/presentation/recovery_screen.dart`, `FE/lib/features/auth/data/http_auth_repository.dart`, and `FE/lib/features/auth/application/auth_controller.dart`
- [ ] T043 [US3] Run recovery demo and secret scanner; record equivalent public known/unknown responses and action-free logs in `specs/006-identity-access/validation.md`

---

## Phase 6: User Story 4 — Enforce Roles and Account Isolation (Priority: P1)

**Goal**: Every protected capability receives a durable current principal, denies by default, and isolates ownership.

**Independent Test**: Exercise the authorization matrix as guest, traveler, curator, administrator, suspended user, and a different traveler.

- [ ] T044 [P] [US4] Add failing authorization-matrix, status/role-change, cross-account non-disclosure, and privileged-denial audit tests in `BE/tests/contract/test_identity_authorization.py`
- [ ] T045 [US4] Complete reusable role/ownership dependencies and deny-by-default capability guards in `BE/app/modules/identity/api.py` and `BE/app/modules/identity/application.py`
- [ ] T046 [US4] Add trusted demo/test role seeding without a public role-escalation endpoint in `BE/scripts/seed_demo.py` and `BE/tests/fixtures/identity.py`
- [ ] T047 [US4] Document the downstream principal integration seam and add an import-boundary test preventing other modules from querying identity persistence internals in `BE/tests/architecture/test_identity_boundaries.py`
- [ ] T048 [US4] Run the published authorization matrix and record immediate role-removal/account-suspension effects in `specs/006-identity-access/validation.md`

---

## Phase 7: User Story 5 — Manage Account Lifecycle (Priority: P2)

**Goal**: Safe account summary, identity export, confirmed deletion, verified cancellation, and idempotent purge.

**Independent Test**: Export identity data, request deletion and observe immediate access loss, cancel within 30 days, then run purge fixtures and inspect minimized evidence.

- [ ] T049 [P] [US5] Add failing contract/integration tests for safe summary, export ownership/checksum/expiry, recent-auth confirmation, deletion, cancellation, purge idempotency, and retained-evidence minimization in `BE/tests/contract/test_identity_lifecycle.py` and `BE/tests/integration/test_identity_lifecycle.py`
- [ ] T050 [P] [US5] Add failing Flutter account summary/export/deletion confirmation tests in `FE/test/account_lifecycle_test.dart`
- [ ] T051 [US5] Implement safe summary, synchronous identity export job, checksum/download, deletion request, cancellation action, and lifecycle audit in `BE/app/modules/identity/application.py`
- [ ] T052 [US5] Add account/export/deletion/deletion-cancel endpoints from `contracts/api.md` in `BE/app/modules/identity/api.py`
- [ ] T053 [US5] Implement idempotent due-account purge and expired rate/action/export cleanup command in `BE/scripts/purge_accounts.py`
- [ ] T054 [US5] Add account/export/deletion controls and confirmation states to `FE/lib/features/auth/presentation/security_screen.dart` and repository/controller files
- [ ] T055 [US5] Run deletion/cancellation/purge demo against disposable fixtures and record proof of exact deletion scope in `specs/006-identity-access/validation.md`

---

## Phase 8: Polish and Cross-Cutting Validation

- [ ] T056 [P] Update `README.md`, `BE/README.md`, and `FE/README.md` with PowerShell/Git Bash demo, DBeaver identity tables, secure dev-outbox use, and stop-without-volume-deletion commands
- [ ] T057 Extend backup manifest/restore verification with identity table counts and relationship evidence while excluding emails, hashes, and secrets in `BE/scripts/backup_database.py`, `BE/scripts/restore_verify.py`, `BE/scripts/verify_backup.py`, and tests
- [ ] T058 Run Alembic empty/upgrade/current/downgrade checks, focused identity suite, normal-action two-second and protected-authorization 100 ms local timing checks, and the proportional student backend regression suite; record exact exclusions and results in `specs/006-identity-access/validation.md`
- [ ] T059 Run Flutter dependency resolution, format, analyze, complete widget/unit tests including 390×844 at 200% text scale, and release web build; record results in `specs/006-identity-access/validation.md`
- [ ] T060 Run PMTiles byte-range and map/search/OSRM/playback static smoke checks plus AI-disabled identity demo; record results in `specs/006-identity-access/validation.md`
- [ ] T061 Run secret scan, `git diff --check`, configuration safety checks, and Docker disk audit without global prune or `down -v`; record results in `specs/006-identity-access/validation.md`
- [ ] T062 Reconcile every FR/SC/API/mobile/authorization contract to code/tests and update `specs/006-identity-access/tasks.md` only from `/speckit.converge`

---

## Dependencies and Execution Order

- Phase 1 → Phase 2 blocks every story.
- US1 establishes Account, RoleAssignment, verification, login, Flutter auth gate, and is the minimum demo.
- US2 depends on US1 session issuance; US3 depends on US1 account/action delivery; they can proceed separately after US1.
- US4 depends on current-principal/session behavior from US2.
- US5 depends on US2 revocation and US3 one-time actions.
- Polish follows all selected stories; the increment is complete only after all five stories and convergence.

## Parallel Opportunities

- Backend unit/migration tests and Flutter interface setup can proceed independently in Phases 1–2.
- For each story, contract/integration tests and Flutter tests use different files and are marked `[P]`.
- Flutter presentation files marked `[P]` can be built after repository/controller contracts stabilize.
- Documentation and selected validation tasks can run independently after code completion.

## Implementation Strategy

1. Deliver US1 as the smallest useful register/verify/login slice.
2. Add session control, then recovery, then role isolation.
3. Complete lifecycle/export only after revocation and one-time actions are proven.
4. Keep the existing shell available through explicit seeded-demo mode throughout.
5. Commit small logical groups with `feat:`, `test:`, `docs:`, or `chore:`; push only the task branch and open a PR into `feat/product-platform`.
