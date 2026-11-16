# Implementation Plan: Stable Planner and Configurable LLM Integration

**Branch**: `task/012-planning-llm-integration` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-planning-llm-integration/spec.md`

## Summary

Upgrade the planner already embedded in the product platform with the measured behavior from `origin/feat/stable-p1-p4` at `35872c2`, adapting files selectively instead of merging the historical tree. The durable authenticated planning lifecycle remains the only product write path. Add an optional AI-assistance module for Vietnamese request interpretation, evidence-grounded explanations, readiness, and non-authoritative shadow comparison. Gemini is the initial hosted provider and is called through its OpenAI-compatible REST surface using an external `GEMINI_API_KEY`; structured deterministic planning remains fully functional with AI disabled.

## Technical Context

**Language/Version**: Python 3.11 backend; Dart/Flutter 3.35-compatible frontend

**Primary Dependencies**: Existing FastAPI, Pydantic v2, SQLAlchemy 2, OR-Tools CP-SAT, LightGBM, NumPy, psycopg, Flutter Material and project HTTP abstractions; no new runtime dependency

**Storage**: Existing PostgreSQL product store for requests, alternatives, itinerary versions, acceptances and shadow observations; versioned JSON/LightGBM/route-matrix planning assets; device cache remains read-only/offline support

**Testing**: pytest unit/contract/integration suites; Flutter analyzer, widget tests and web release build; planner audit and latency tools imported from the stable branch

**Target Platform**: Windows/macOS/Linux backend, Flutter web laptop demo and supported mobile targets; hosted Gemini Developer API is optional

**Project Type**: Mobile client plus authenticated web API with deterministic optimization service

**Performance Goals**: One-day planning p95 ≤15 seconds; two-day planning p95 ≤25 seconds; parsing target ≤10 seconds when the provider responds; optional explanation/shadow calls never extend the authoritative planning timeout

**Constraints**: Da Nang only; automated one- and two-day planning; no secret in Git/logs/responses; AI output is untrusted; every selectable plan passes deterministic gates; provider failures cannot block structured planning; no whole-tree merge from the historical branch

**Scale/Scope**: Existing account/trip platform, up to five alternatives per request, 750-POI stable snapshot at source commit `35872c2` and calibrated local matrix, 390×844 primary mobile viewport

## Constitution Check

*GATE: Passed before research and re-checked after design.*

- **I. Feasibility-First**: PASS. OR-Tools and the five gate families remain authoritative. AI cannot create, mutate, approve or persist alternatives.
- **II. Spec-Driven Development**: PASS. Specification exists; this plan produces research, data model, contracts and quickstart before tasks/analyze/implementation.
- **III. Test-First**: PASS. Tasks will port stable regression fixtures and add failing provider/adapter contracts before implementation changes.
- **IV. Data Provenance & Honesty**: PASS WITH DOCUMENTED SCALE EXCEPTION. Planner assets are pinned to the stable source commit and named snapshot; external AI receives minimized evidence; unknown POIs remain unresolved. The imported stable snapshot contains 750 records rather than the constitution's original 100–200-record baseline; only records admitted by the stable verification tiers may enter selectable plans.
- **V. Simplicity & Tier Discipline**: PASS. Existing REST transport and dependencies are reused; no model training, GPU dependency or generative routing is added.
- **VI. Mobile Contract**: PASS. Flutter remains primary; server inference is optional; cached plans/map remain available while new planning requires the backend.
- **Secret and durable-data rules**: PASS. Gemini key is environment-only; PostgreSQL remains authoritative; no new SQLite product source is introduced.

## Phase 0 Research Decisions

Research decisions and rejected alternatives are recorded in [research.md](./research.md). All technical unknowns are resolved; no `NEEDS CLARIFICATION` markers remain.

## Phase 1 Design

### Planner port boundary

Create an upstream manifest pinned to `35872c2`. Apply only the stable planner services, required router adapter behavior, runtime planning assets, audit tools, and their regression fixtures that changed after `origin/feat/stable-planning-roadmap`. Preserve `BE/app/core`, product modules, migrations, authentication, PostgreSQL lifecycle, offline cache, and current Flutter management boundaries. Where a source file is shared, adapt the stable behavior manually behind the existing public contract.

The authenticated `PlanningLifecycleService` continues to construct the authoritative `TripRequest`, invoke the legacy/stable planner as a pure calculation, reject incomplete gates/duplicates, and persist product-owned alternatives. Source-branch in-memory selection and SQLite evidence paths are not allowed to become product write paths.

### AI-assistance boundary

Add `BE/app/modules/ai_assistance/` with domain schemas, provider-neutral service logic, and authenticated endpoints. Refactor `BE/app/services/llm.py` into a typed gateway that supports `disabled`, `local`, `gemini`, and explicit `compatible` modes. Gemini mode uses `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` by default, bearer authorization from `GEMINI_API_KEY`, and a model supplied through environment configuration. The gateway normalizes configuration, authentication, quota/rate-limit, safety/refusal, timeout, transport, malformed-JSON and schema failures.

Natural-language interpretation returns a proposal only; it never writes a trip or starts planning. Confirmation is represented by the client sending the reviewed values as `constraint_overrides` to the existing planning-request endpoint. Explanations operate on one owned persisted alternative and must cite evidence keys supplied in the minimized prompt. Unsupported citations fail closed to deterministic explanation text. Shadow comparison uses only owned, already-feasible alternatives and stores metadata through the existing durable planning-evidence service; it never changes ranks.

### Mobile flow

Extend the planning repository and itinerary screen with an optional Vietnamese prompt. The user explicitly requests interpretation, reviews the returned proposal, edits or confirms it, and then creates a planning request. The same screen can skip AI and plan directly from structured trip/profile data. AI readiness and failure state are labeled independently from planner availability. Explanation is fetched on demand, never during initial planning.

### Persistence and migrations

No schema migration is required. Existing `planning_requests.input_payload` stores only confirmed structured values. Existing `shadow_observations` stores non-authoritative comparison metadata. Interpretation prompts/outputs and explanation prompts/outputs are not persisted by default. Structured logs record only capability, provider/model label, status, latency, correlation identifier and sanitized failure category.

### Post-design constitution re-check

PASS. The design preserves deterministic authority, test-first sequencing, data provenance, secret isolation, replaceable providers, offline honesty and existing product persistence. No constitution exception requires Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/012-planning-llm-integration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ai-assistance.md
│   ├── mobile.md
│   └── planner-adapter.md
├── checklists/
│   ├── requirements.md
│   └── integration.md
└── tasks.md
```

### Source Code (repository root)

```text
BE/
├── .env.example
├── app/
│   ├── core/config.py
│   ├── main.py
│   ├── modules/
│   │   ├── ai_assistance/
│   │   │   ├── __init__.py
│   │   │   ├── api.py
│   │   │   ├── domain.py
│   │   │   └── service.py
│   │   ├── planning_evidence/
│   │   └── planning_lifecycle/
│   ├── routers/itinerary.py
│   └── services/
│       ├── llm.py
│       ├── optimizer.py
│       ├── multiday.py
│       ├── route_order.py
│       ├── ranker.py
│       └── [stable planner services]
├── data/snapshots/danang-v1/
├── tests/
│   ├── contract/
│   ├── integration/
│   └── unit/
└── tools/

FE/
├── lib/
│   ├── app_state.dart
│   └── features/
│       ├── itinerary/presentation/itinerary_screen.dart
│       └── planning/
│           ├── data/planning_repository.dart
│           └── domain/models.dart
└── test/
```

**Structure Decision**: Reuse the existing mobile/API monorepo and current module boundaries. Planner algorithms remain under the established `BE/app/services` compatibility area; new provider-facing behavior is isolated in `modules/ai_assistance`, and all durable writes remain in existing product modules.

## Complexity Tracking

| Exception | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Reuse the pinned 750-record stable Da Nang snapshot instead of reducing it to the constitution's original 100–200-record baseline | The user's requested stable planner, calibrated route matrix, regression fixtures and feasibility evidence are coupled to this exact versioned snapshot at `35872c2`. Provenance and verification-tier gates remain mandatory. | Trimming the snapshot would invalidate matrix indexes and published regression evidence, creating a new unmeasured dataset instead of integrating the already validated planner. |
