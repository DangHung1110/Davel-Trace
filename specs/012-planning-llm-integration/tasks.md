# Tasks: Stable Planner and Configurable LLM Integration

**Input**: Design documents from `/specs/012-planning-llm-integration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required by the specification, constitution and source-port risk. Test tasks precede implementation tasks.

**Organization**: Tasks are grouped by user story so deterministic planning remains independently testable from every AI capability.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it affects different files and has no incomplete dependency.
- **[Story]**: Maps to the user story in spec.md.
- Every task includes an exact file or directory path.

## Phase 1: Setup and Source Pin

**Purpose**: Establish a reproducible selective-port boundary without changing product behavior.

- [ ] T001 Record upstream commit `35872c2`, included planner/data/test paths and excluded product-platform paths (including historical `BE/app/services/llm.py`) in `BE/app/services/STABLE_PLANNER_UPSTREAM.md`
- [ ] T002 [P] Add Gemini-disabled/local/gemini/compatible configuration examples with no real key in `BE/.env.example`
- [ ] T003 [P] Verify Python/Flutter/runtime secret and generated-artifact patterns remain covered in `.gitignore`

---

## Phase 2: Foundational Provider and Planner Boundaries

**Purpose**: Build shared contracts required by all user stories.

**⚠️ CRITICAL**: No user-story implementation begins until these tests and boundaries exist.

- [ ] T004 [P] Add failing typed-settings tests for provider modes, secret-safe representation, timeout/retry bounds and capability flags in `BE/tests/unit/test_platform_config.py`
- [ ] T005 [P] Add failing gateway tests for Gemini endpoint/auth plus disabled, config, auth, quota, safety, timeout, transport, bad-JSON and schema categories in `BE/tests/unit/test_llm.py`
- [ ] T006 [P] Add failing domain tests for interpretation, grounded citations and secret-free readiness in `BE/tests/unit/test_ai_assistance.py`
- [ ] T007 Create provider-neutral schemas and normalized failure types in `BE/app/modules/ai_assistance/domain.py` and `BE/app/modules/ai_assistance/__init__.py`
- [ ] T008 Extend typed environment settings with `disabled|local|gemini|compatible`, external key/model/URL, timeout/retry and capability flags in `BE/app/core/config.py`
- [ ] T009 Refactor the JSON gateway for explicit Gemini REST compatibility, bounded retries and normalized secret-safe failures in `BE/app/services/llm.py`
- [ ] T010 Implement provider-neutral readiness, minimized prompt construction and evidence-citation validation in `BE/app/modules/ai_assistance/service.py`

**Checkpoint**: Provider configuration and domain behavior are testable without a real API key.

---

## Phase 3: User Story 1 — Plan From Durable Trip Data (Priority: P1) 🎯 MVP

**Goal**: Run the measured stable planner through the authenticated durable lifecycle without restoring historical write paths.

**Independent Test**: Create an owned one/two-day trip, generate feasible alternatives, accept idempotently, restart, and read the immutable selected version with original data evidence.

### Tests for User Story 1

- [ ] T011 [P] [US1] Port applicable stable hard-feasibility, rain, all-day, profile, route-order, multi-day and reproducibility tests into `BE/tests/unit/`
- [ ] T012 [P] [US1] Add lifecycle adapter tests for confirmed overrides, 1–2 day bounds, five complete gates, duplicate rejection and shortage evidence in `BE/tests/contract/test_planning_lifecycle_api.py`
- [ ] T013 [P] [US1] Add authenticated persisted plan/select/restart/replan integration coverage in `BE/tests/integration/test_stable_planner_lifecycle.py`

### Implementation for User Story 1

- [ ] T014 [US1] Port only the non-LLM stable runtime planner services from `35872c2` into `BE/app/services/` while preserving current product imports and removing historical-only write paths
- [ ] T015 [US1] Port required stable `pois.json`, dense route matrix, calibration metadata and PATM artifacts into `BE/data/snapshots/danang-v1/` and `BE/ml/patm/`
- [ ] T016 [US1] Port stable audit and latency tooling required by SC-008/SC-009 into `BE/tools/audit_plans.py` and `BE/tools/bench_latency.py`
- [ ] T017 [US1] Adapt stable itinerary orchestration and five-family evidence in `BE/app/routers/itinerary.py` without replacing product authentication/persistence routers
- [ ] T018 [US1] Extend confirmed override mapping and stable planner adaptation in `BE/app/modules/planning_lifecycle/service.py`
- [ ] T019 [US1] Preserve product-owned alternative identifiers, history and acceptance contracts in `BE/app/modules/planning_lifecycle/infrastructure.py` and `BE/app/modules/planning_lifecycle/application.py`

**Checkpoint**: Structured planning is fully functional with `LLM_PROVIDER=disabled`.

---

## Phase 4: User Story 2 — Review an AI-Assisted Request Interpretation (Priority: P1)

**Goal**: Return a validated, reviewable Vietnamese interpretation proposal without mutating trips or starting planning.

**Independent Test**: Interpret must-visit, soft preference, budget and accessibility fixtures, correct one value, and prove only confirmed structured overrides reach planning.

### Tests for User Story 2

- [ ] T020 [P] [US2] Add authenticated interpretation endpoint ownership, validation and normalized-provider-error contracts in `BE/tests/contract/test_ai_assistance_api.py`
- [ ] T021 [P] [US2] Add parser fixtures for hard/soft separation, unknown POIs, prompt injection and semantic-invalid JSON in `BE/tests/unit/test_ai_interpretation.py`
- [ ] T022 [P] [US2] Add Flutter repository/model tests for proposal parsing and confirmed override submission in `FE/test/planning_ai_repository_test.dart`

### Implementation for User Story 2

- [ ] T023 [US2] Implement owned-trip interpretation and catalog resolution in `BE/app/modules/ai_assistance/service.py`
- [ ] T024 [US2] Add authenticated interpretation and readiness routes in `BE/app/modules/ai_assistance/api.py` and register them in `BE/app/main.py`
- [ ] T025 [US2] Extend planning request validation for confirmed must-visit, avoid, activity, food and hard/soft overrides in `BE/app/modules/planning_lifecycle/api.py` and `BE/app/modules/planning_lifecycle/service.py`
- [ ] T026 [US2] Add interpretation/readiness contracts and proposal models in `FE/lib/features/planning/data/planning_repository.dart` and `FE/lib/features/planning/domain/models.dart`
- [ ] T027 [US2] Add prompt, external-processing disclosure, proposal review/correction and confirm/skip flow in `FE/lib/features/itinerary/presentation/itinerary_screen.dart` and `FE/lib/app_state.dart`

**Checkpoint**: Interpretation is optional and cannot mutate or plan before confirmation.

---

## Phase 5: User Story 3 — Continue When the LLM Is Unavailable (Priority: P1)

**Goal**: Preserve structured deterministic planning and product records across every provider failure mode.

**Independent Test**: Run equivalent planning with provider healthy, disabled, missing key, auth failure, quota, timeout and malformed output; compare deterministic alternatives and durable records.

### Tests for User Story 3

- [ ] T028 [P] [US3] Add provider-failure isolation and late-response/cancellation integration cases in `BE/tests/integration/test_ai_failure_isolation.py`
- [ ] T029 [P] [US3] Add Flutter widget coverage distinguishing AI failure, planner failure, offline and structured fallback at 390×844 in `FE/test/planning_ai_fallback_test.dart`

### Implementation for User Story 3

- [ ] T030 [US3] Normalize AI errors without provider body/key leakage in `BE/app/modules/ai_assistance/api.py` and `BE/app/services/llm.py`
- [ ] T031 [US3] Isolate request-local AI state from deterministic planner state and late responses in `FE/lib/app_state.dart`
- [ ] T032 [US3] Render actionable AI-specific fallback while leaving structured planning controls enabled in `FE/lib/features/itinerary/presentation/itinerary_screen.dart`

**Checkpoint**: All provider failures degrade honestly and do not affect planning persistence.

---

## Phase 6: User Story 4 — Understand Why a Plan Fits (Priority: P2)

**Goal**: Provide on-demand grounded explanation with deterministic fallback.

**Independent Test**: Explain a feasible persisted alternative and verify every AI reason cites supplied evidence; inject an unknown citation and observe deterministic fallback.

### Tests for User Story 4

- [ ] T033 [P] [US4] Add owned-alternative, evidence-citation, unsupported-claim and deterministic-fallback contracts in `BE/tests/contract/test_ai_explanation_api.py`
- [ ] T034 [P] [US4] Add Flutter model/widget coverage for `ai_grounded` versus `deterministic` explanation labels in `FE/test/planning_explanation_test.dart`

### Implementation for User Story 4

- [ ] T035 [US4] Implement minimized alternative evidence and grounded/deterministic explanation generation in `BE/app/modules/ai_assistance/service.py`
- [ ] T036 [US4] Add the owned alternative explanation endpoint in `BE/app/modules/ai_assistance/api.py`
- [ ] T037 [US4] Add on-demand explanation repository/state/UI behavior in `FE/lib/features/planning/data/planning_repository.dart`, `FE/lib/app_state.dart` and `FE/lib/features/itinerary/presentation/itinerary_screen.dart`

**Checkpoint**: Explanation never changes plans and never fabricates grounded success.

---

## Phase 7: User Story 5 — Replace the External Provider Safely (Priority: P2)

**Goal**: Switch disabled/local/Gemini/compatible configurations without source changes, secret exposure or record migration.

**Independent Test**: Run readiness and mocked interpretation under each provider mode, restart after changing model, and verify historical records remain identical.

### Tests for User Story 5

- [ ] T038 [P] [US5] Add provider-switch, secret-safe readiness and unchanged-record compatibility tests in `BE/tests/integration/test_ai_provider_switch.py`
- [ ] T039 [P] [US5] Add durable, non-authoritative shadow ownership and no-reorder tests in `BE/tests/contract/test_ai_shadow_api.py`

### Implementation for User Story 5

- [ ] T040 [US5] Connect optional owned feasible-alternative shadow evaluation to existing PostgreSQL planning evidence in `BE/app/modules/ai_assistance/service.py` and `BE/app/modules/planning_evidence/infrastructure.py`
- [ ] T041 [US5] Expose non-secret capability readiness and optional shadow trigger in `BE/app/modules/ai_assistance/api.py`
- [ ] T042 [US5] Document Gemini API-key creation, free-tier separation from Gemini Plus and provider switching in `BE/README.md` and `README.md`

**Checkpoint**: Provider replacement requires only environment changes and no product-data migration.

---

## Phase 8: Polish and Cross-Cutting Validation

**Purpose**: Prove the integrated result and protect unrelated product capabilities.

- [ ] T043 Run backend unit/contract/integration regression and record results in `specs/012-planning-llm-integration/validation.md`
- [ ] T044 Run Flutter format/analyze/widget regression and 390×844 planning flow tests; record results in `specs/012-planning-llm-integration/validation.md`
- [ ] T045 Run planner audit and one/two-day latency measurements against the agreed reference environment; record results in `specs/012-planning-llm-integration/validation.md`
- [ ] T046 Run secret scan and inspect tracked files for `.env`, keys, provider outputs, runtime databases, caches and audit artifacts; record results in `specs/012-planning-llm-integration/validation.md`
- [ ] T047 Run Flutter web release build plus authenticated manual smoke for structured planning, optional interpretation, selection, history, explanation, map, expenses and offline reading; record results in `specs/012-planning-llm-integration/validation.md`
- [ ] T048 Reconcile quickstart commands and final changed-file boundaries in `specs/012-planning-llm-integration/quickstart.md` and `BE/app/services/STABLE_PLANNER_UPSTREAM.md`

---

## Dependencies and Execution Order

- Phase 1 → Phase 2 → all user stories.
- US1 is the deterministic foundation and precedes US2–US5.
- US2 and US3 complete before UI explanation work.
- US4 and US5 may proceed independently after US1/US2 foundation.
- Phase 8 follows all selected stories.
- Within each story: tests must be added and observed failing before implementation, then rerun green.

## Parallel Opportunities

- T002/T003, T004/T005/T006, and test tasks marked `[P]` affect distinct files.
- Backend contract tests and Flutter model tests for a story can be prepared in parallel.
- Backend, Flutter, latency, secret and manual-smoke validation results are recorded sequentially in the shared `validation.md` artifact.

## Implementation Strategy

1. Complete provider-neutral boundaries with no real key.
2. Deliver US1 and validate deterministic planning with AI disabled.
3. Deliver interpretation and failure isolation.
4. Add grounded explanation and shadow evidence.
5. Run complete regression/performance/security validation.

The minimum viable deliverable is US1: stable deterministic planner through durable lifecycle. The requested Increment 012 includes all five stories before convergence.
