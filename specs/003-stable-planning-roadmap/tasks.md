# Tasks: Stable Planning Roadmap MVP

**Input**: Design documents from `/specs/003-stable-planning-roadmap/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Required by the feature specification, constitution, and Definition of Done. Tests are written before the implementation they pin.

**Organization**: Tasks are grouped by user story so each story remains independently testable. `[P]` means the task touches different files and can be worked independently; this execution remains single-agent per the current request.

## Phase 1: Setup and Repository Hygiene

**Purpose**: Reuse the existing approved mobile kit without merging the older backend, and keep generated/runtime files out of Git.

- [x] T001 Add runtime ignores for `.flutter-sdk/`, `FE/.dart_tool/`, generated build output, Python test scratch directories, and `BE/data/*.db*` in `.gitignore` without ignoring tracked PMTiles or platform source.
- [x] T002 Restore only the tracked Flutter project files (`FE/lib/`, `FE/test/`, `FE/web/`, platform project files, `FE/pubspec.*`, lint/metadata files) from `origin/feat/002-trip-management-mvp`, while preserving current `FE/onboard.html`, `FE/test_harness.html`, and `FE/README.md`.
- [x] T003 Update `FE/README.md` with the current planner/mobile scope and document the reused Sơn Trà Breeze design system.

---

## Phase 2: Foundational Contract Tests

**Purpose**: Pin safety, persistence, readiness, and mobile-state contracts before implementation.

**⚠️ CRITICAL**: These tests must fail for the missing new behavior before implementation begins.

- [x] T004 [P] Add gate-family, five-candidate, shortage-reason, and public-plan evidence tests in `BE/tests/unit/test_gate_families.py` and `BE/tests/contract/test_stable_itinerary.py`.
- [x] T005 [P] Add SQLite schema, immutable acceptance, idempotency, failed-selection-no-write, and acceptance-query tests in `BE/tests/unit/test_acceptance_store.py` and `BE/tests/contract/test_acceptance_api.py`.
- [x] T006 [P] Add anonymization, forward/reverse consensus, unavailable fallback, canary cap, and readiness-threshold tests in `BE/tests/unit/test_shadow_rank.py` and `BE/tests/contract/test_planning_readiness.py`.
- [x] T007 [P] Add Flutter widget tests for desktop phone frame, seeded/offline label, planning alternative selection, bottom navigation, and no fake acceptance in `FE/test/stable_planning_app_test.dart`.

**Checkpoint**: New tests demonstrate the missing behavior and existing tests remain discoverable.

---

## Phase 3: User Story 1 — Receive Safe, Distinct Alternatives (Priority: P1) 🎯 Backend MVP

**Goal**: Return up to five genuinely distinct, complete, hard-gate-passing alternatives with compact family evidence and honest shortage metadata.

**Independent Test**: A deterministic fixture with five feasible solutions returns five unique alternatives; every public plan contains a passing five-family report; smaller pools include a documented shortage reason.

- [x] T008 [US1] Add the derived five-family report and detailed-check traceability to `BE/app/services/gate.py` without changing existing check formulas or soft-check behavior.
- [x] T009 [US1] Raise diverse selection target to five, deduplicate ordered POI sequences, and add target/returned/shortage metadata in `BE/app/services/pool.py` and `BE/app/routers/itinerary.py`.
- [x] T010 [US1] Decorate every public alternative with deterministic rank/score, gate family report, snapshot version, and explicitly non-authoritative shadow status in `BE/app/routers/itinerary.py`; register only selectable plans in `BE/app/routers/select.py`.
- [x] T011 [US1] Run focused gate/pool/itinerary tests and preserve current optimizer, evaluation, review, repair, and replan contracts.

**Checkpoint**: US1 is independently usable with shadow judging disabled and no evidence database.

---

## Phase 4: User Story 2 — Choose and Record an Accepted Plan (Priority: P1)

**Goal**: Persist immutable, idempotent accepted-plan evidence for a feasible registered alternative.

**Independent Test**: Selecting the same plan twice with one idempotency key returns one record; unknown/gate-failing selections write no record; records remain queryable after a new service instance opens the database.

- [x] T012 [US2] Add `acceptance_db_path` environment configuration in `BE/app/config.py` and implement code-first SQLite schema, transaction, insert-or-get idempotency, and read/list operations in `BE/app/services/acceptance_store.py`.
- [x] T013 [US2] Preserve normalized request/private context at plan registration and extend `POST /v1/itinerary/select` with optional `idempotency_key` and `parent_acceptance_id` in `BE/app/routers/select.py`; server-generate the key and persist for legacy calls while retaining their exact response shape.
- [x] T014 [US2] Add acceptance read/list and stable error envelopes in `BE/app/routers/planning_evidence.py`, register the router in `BE/app/main.py`, and ensure runtime databases are never tracked.
- [x] T015 [US2] Run focused acceptance store/API tests and inspect a generated SQLite file with schema queries suitable for DBeaver.

**Checkpoint**: US2 creates trustworthy accepted-plan data without requiring an LLM.

---

## Phase 5: User Story 3 — Measure Shadow Judge and Evidence Readiness (Priority: P2)

**Goal**: Record non-authoritative, order-swapped shadow observations and expose honest promotion/readiness metrics.

**Independent Test**: Injected forward/reverse judge decisions yield win only on agreement, disagreement yields tie, unavailable judge returns a non-failing status, and all later learning/RAG gates remain disabled below their thresholds.

- [x] T016 [US3] Implement identity-blind candidate facts, forward/reverse order mapping, strict decision normalization, consensus/tie rules, stable canary sampling capped at 10%, and optional injected judge gateway in `BE/app/services/shadow_rank.py`.
- [x] T017 [US3] Extend the SQLite service with append/list shadow observations and implement threshold computations in `BE/app/services/planning_readiness.py` without training weights or retrieving accepted days.
- [x] T018 [US3] Add `POST /v1/shadow/evaluate` and `GET /v1/planning/readiness` to `BE/app/routers/planning_evidence.py`; add optional best-effort shadow metadata to planning responses without reordering or blocking them.
- [x] T019 [US3] Update `FE/test_harness.html` to display five-family status, acceptance ID, shadow/calibration status, and readiness counts while preserving existing parse/plan/review/repair flows.
- [x] T020 [US3] Run focused shadow/readiness tests, including order disagreement and zero-evidence cases.

**Checkpoint**: US3 provides measurement seams and evidence gates but no premature learned model or RAG.

---

## Phase 6: User Story 4 — Demo Mobile Experience on a Laptop (Priority: P2)

**Goal**: Deliver a coherent Flutter web mobile demo in a desktop phone frame using live planner/expense APIs when available and honest seeded data otherwise.

**Independent Test**: In Chrome at 1440×900, complete profile → request plan → compare/select → itinerary → map → expense → profile, then repeat startup with backend stopped and observe seeded/offline state without a fake server acceptance.

- [x] T021 [P] [US4] Define planner alternatives, gate evidence, acceptance, readiness, expense, profile, and demo-source models in `FE/lib/features/planning/domain/models.dart` and adapt API base URL/error handling in `FE/lib/api/`.
- [x] T022 [US4] Implement current FastAPI planner/select/acceptance/readiness/expense calls plus bundled seeded fallback in `FE/lib/features/planning/data/planning_repository.dart` and `FE/lib/app_state.dart`; remove dependencies on unavailable legacy management endpoints.
- [x] T023 [P] [US4] Build the planning/alternative comparison flow with live/seeded/stale status, request-plan and accept actions in `FE/lib/features/planning/presentation/` using the existing theme and stable test keys.
- [x] T024 [US4] Adapt itinerary timeline and shell navigation in `FE/lib/features/itinerary/presentation/itinerary_screen.dart` and `FE/lib/features/shell/presentation/main_shell.dart` while retaining the 390×844 desktop frame.
- [x] T025 [P] [US4] Adapt expense entry/summary to the current `/v1/expenses` contract in `FE/lib/features/expenses/presentation/expenses_screen.dart` and expose profile/request settings in `FE/lib/features/profile/presentation/profile_screen.dart`.
- [x] T026 [US4] Preserve PMTiles/route/location behavior in `FE/lib/features/map/`, `FE/web/map_embed.html`, and `FE/web/data/danang.pmtiles`; show distinct local-map, real-route, fallback-route, and geolocation states.
- [x] T027 [US4] Update `FE/lib/app.dart`, `FE/lib/main.dart`, and widget tests so live and offline startup, phone-frame layout, navigation, and selection honesty all pass.
- [x] T028 [US4] Run `flutter pub get`, format, analyze, widget tests, and a release web build using the repository-local Flutter SDK.

**Checkpoint**: US4 is demoable on a laptop with or without the backend.

---

## Phase 7: Documentation, Regression, and Delivery

**Purpose**: Verify the feature against the quickstart and prepare professional Git delivery.

- [x] T029 [P] Update root `README.md`, `BE/README.md`, and `FE/README.md` with current architecture, SQLite/DBeaver connection path, PowerShell and Git Bash commands, live/offline demo flow, and deferred learning/RAG thresholds.
- [x] T030 [P] Update `specs/001-travel-agent-mvp/contracts/api.md` only where backward-compatible endpoint behavior has changed, linking to the 003 addendum rather than duplicating all details.
- [x] T031 Run `python -m pytest BE/tests -q` and resolve regressions without weakening tests.
- [x] T032 Run root `python server.py` smoke checks for HTTP 200 shell and HTTP 206 PMTiles range, then manually verify map/search A-B/route/play-pause availability.
- [x] T033 Execute every command/scenario in `specs/003-stable-planning-roadmap/quickstart.md`, record actual results, scan tracked changes for secrets and runtime artifacts, and review the final diff.
- [x] T034 Run `/speckit.converge`; append and implement any missing tasks until the result is `CONVERGED`.
- [x] T035 Commit in professional English-prefixed logical steps, push `feat/stable-planning-roadmap`, and open a PR to `dev` with spec/change/test evidence and no direct push to protected branches.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 contract tests → US1.
- US2 depends on US1's registered plan context and gate family report.
- US3 depends on US1 feasible alternatives and US2 evidence storage.
- US4 can begin from the restored kit after Phase 2, but live acceptance/readiness wiring depends on US2/US3 contracts.
- Documentation/regression/delivery depends on all desired stories.

## Parallel Opportunities

- T004–T007 affect separate backend/Flutter test files.
- T021, T023, and T025 begin in distinct Flutter feature files after the restored kit exists.
- T029 and T030 affect separate documentation files after contracts stabilize.

## Implementation Strategy

1. Deliver US1 + US2 first: deterministic safe alternatives and durable acceptance are the usable MVP.
2. Add US3 as measurement-only infrastructure, with judge default off and no automatic promotion.
3. Complete US4 from the approved Flutter kit, emphasizing offline honesty and laptop demo reliability.
4. Run the full quickstart and converge loop before commit/push/PR.
