# Implementation Plan: Stable Planning Roadmap MVP

**Branch**: `feat/stable-planning-roadmap` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-stable-planning-roadmap/spec.md`

## Summary

Extend the existing deterministic FastAPI planner without replacing its optimizer or detailed gate registry. Add a five-family view over existing checks, produce five diverse feasible alternatives in explicit diverse mode, persist immutable accepted-plan evidence in a local SQLite store, and add opt-in shadow comparison/readiness reporting that never controls feasibility. Restore the existing Flutter mobile shell from the prior feature branch, adapt it to current planner/expense contracts, retain the PMTiles map assets, and provide seeded offline state plus a 390×844 desktop phone frame. No learned weights or accepted-day retrieval is activated in this phase.

## Technical Context

**Language/Version**: Python 3.11; Dart SDK compatible with Flutter 3.35 / Dart 3.9+

**Primary Dependencies**: Existing FastAPI, Pydantic, OR-Tools, pytest/httpx backend; existing Flutter SDK packages `http`, `shared_preferences`, `flutter_map`, `latlong2`, `geolocator`, `pointer_interceptor`, and `web`. No new third-party dependency.

**Storage**: Python stdlib SQLite for immutable acceptance and shadow-observation rows; existing in-memory planner registry for transient candidate lookup; browser preferences/cache for the mobile demo; versioned JSON/PMTiles snapshot remains authoritative.

**Testing**: pytest backend contract/unit/integration suites; `flutter analyze`, Flutter widget tests, and Flutter web build; root byte-range/map smoke check.

**Target Platform**: FastAPI on Windows/Linux localhost; Flutter Web in Chrome/Edge on Windows laptop with responsive mobile layout; generated Android/iOS projects retained for later device use.

**Project Type**: Mobile application + web service + preserved static map prototype.

**Performance Goals**: Existing full itinerary target under 30 seconds; selection/acceptance local write under 300 ms; readiness reads under 300 ms; shadow judge best-effort and bounded without delaying deterministic response when disabled/unavailable; interactive mobile UI at normal 60 Hz.

**Constraints**: Feasibility-first; no LLM route generation; no secret in source; local map remains usable without provider key; no new package; only verified POIs in selectable plans; root behavior remains backward-compatible; SQLite file is runtime data and not committed.

**Scale/Scope**: Da Nang, one- or two-day request schema, up to five alternatives per request, local demo/audit data volume, four principal mobile tabs plus planning/alternative flow.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Feasibility-First — PASS**: Family reports wrap the existing deterministic registry. Selection re-runs the gate. Shadow output cannot reorder or select.
- **II. Spec-Driven Development — PASS**: Feature has spec, plan/design artifacts, checklist, tasks, analyze, implement, and converge stages.
- **III. Test-First — PASS**: Contract and unit tests are tasks before services and endpoints. Promotion thresholds remain explicit and unachieved stages stay disabled.
- **IV. Data Provenance & Honesty — PASS**: Acceptance rows include snapshot/version and full evidence. Seed/demo state is labeled. No unverified POI is promoted to selectable fact.
- **V. Simplicity & Tier Discipline — PASS**: SQLite and existing packages only. Learned weights, inverse optimization, and RAG are gated rather than implemented prematurely.
- **VI. Mobile Contract — PASS**: Flutter is the primary frontend; FastAPI owns intelligence; PMTiles stays local; cached/seeded state shows timestamp/status.
- **Technology Constraints — PASS**: Uses the existing stack and no new provider or dependency.
- **Workflow/DoD — PASS**: Work is on `feat/stable-planning-roadmap`, checkpoint is pushed, and test/push/PR tasks are planned.

### Post-Design Re-check

The API contract keeps deterministic authority explicit, the data model makes acceptance rows immutable and versioned, and the mobile contract labels all offline/seeded behavior. No constitution violation or complexity exception remains.

## Project Structure

### Documentation (this feature)

```text
specs/003-stable-planning-roadmap/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   └── mobile-demo.md
├── checklists/
│   ├── requirements.md
│   └── delivery.md
└── tasks.md
```

### Source Code (repository root)

```text
BE/
├── app/
│   ├── config.py
│   ├── main.py
│   ├── routers/
│   │   ├── itinerary.py
│   │   ├── select.py
│   │   └── planning_evidence.py
│   └── services/
│       ├── acceptance_store.py
│       ├── gate.py
│       ├── planning_readiness.py
│       ├── pool.py
│       └── shadow_rank.py
└── tests/
    ├── contract/
    ├── integration/
    └── unit/

FE/
├── lib/
│   ├── api/
│   ├── features/
│   │   ├── expenses/
│   │   ├── itinerary/
│   │   ├── map/
│   │   ├── planning/
│   │   ├── profile/
│   │   └── shell/
│   ├── app.dart
│   ├── app_state.dart
│   └── main.dart
├── test/
├── web/
│   ├── data/danang.pmtiles
│   └── map_embed.html
├── onboard.html
├── test_harness.html
└── pubspec.yaml

index.html
server.py
data/danang.pmtiles
```

**Structure Decision**: Keep the repository's established `BE/` FastAPI and `FE/` Flutter split plus the root static map prototype. Import only the tracked Flutter shell/assets from `origin/feat/002-trip-management-mvp`, preserve the newer planner harness/onboarding HTML files, and adapt the mobile state/repository to current planner contracts instead of merging the older backend.

## Complexity Tracking

No constitution violations require justification.
