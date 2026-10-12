# Implementation Plan: Trip Management MVP

**Branch**: `feat/002-trip-management-mvp` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-trip-management-mvp/spec.md`

## Summary

Deliver a management-first Flutter application backed by a FastAPI modular monolith. Users manage local travel profiles, Da Nang trips, manual itinerary activities and expenses, then view activities and routes on the existing map. SQLAlchemy declarative models are the schema source, Alembic owns migration history, and a file-backed SQLite database satisfies the constitution while remaining directly inspectable in DBeaver. AI branches remain isolated behind a planner port and are not required at runtime.

## Technical Context

**Language/Version**: Python 3.11; Dart SDK `^3.13.3`; Flutter app inherited from `codex/stitch-mobile-ui`

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.x, Alembic, HTTPX; Flutter `http`, `shared_preferences`, existing `flutter_map`, `geolocator`, `latlong2`, `web`

**Storage**: SQLite runtime database at configurable `DATABASE_URL` (default `sqlite:///BE/data/davel_trace.db`) with Alembic migrations; versioned JSON POI snapshot; tracked PMTiles map asset

**Testing**: pytest unit/contract/integration tests; Flutter widget tests and `flutter analyze`; Alembic clean-database migration smoke test; existing root prototype smoke test

**Target Platform**: Flutter web for laptop/mobile viewport and Android/iOS-compatible Flutter UI; FastAPI local server; DBeaver-compatible SQLite file

**Project Type**: Mobile application + REST API + preserved static map prototype

**Performance Goals**: Local management reads/writes visible within 2 seconds; route result or retryable failure within 10 seconds for at most 10 stops; initial trip list under 2 seconds for MVP dataset

**Constraints**: Da Nang only, trips at most two days, one active local profile, VND integer amounts, no authentication/payment/AI runtime, offline PMTiles preserved, route truthfulness preserved, no secrets in code

**Scale/Scope**: Demo-scale single active device; up to 20 profiles, 100 trips, 100 activities per trip, 10,000 expenses and one versioned Da Nang POI snapshot

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **I. Feasibility-First**: PASS — no AI-generated itinerary is exposed. Manual schedules warn on overlap; future planner remains behind an explicit proposal/confirmation seam.
- **II. Spec-Driven Development**: PASS — new `002-trip-management-mvp` artifacts precede implementation and `$speckit.analyze` is required before code changes.
- **III. Test-First**: PASS — contract/integration tests and budget/version tests are tasks before corresponding implementation. Existing AI evaluator rules are not weakened.
- **IV. Data Provenance & Honesty**: PASS — POI remains a versioned catalog; route responses carry source/fallback truth; no API key is committed.
- **V. Simplicity & Tier Discipline**: PASS — modular monolith, SQLite and framework-native state keep MVP demo-adequate; booking, payment, OCR, multi-city and AI are excluded. Every new dependency is listed in this plan.
- **VI. Mobile Contract**: PASS — Flutter remains primary; FastAPI owns persistence/API; PMTiles assets and current route/map behavior remain available.
- **Technology Constraints**: PASS — SQLite/JSON snapshot is retained. PostgreSQL and MySQL are explicitly not introduced in this feature.
- **Post-design re-check**: PASS — data model, contracts and quickstart keep the same boundaries; no constitution exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/002-trip-management-mvp/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api.md
├── checklists/
│   ├── requirements.md
│   └── management-mvp-quality.md
└── tasks.md
```

### Source Code (repository root)

```text
BE/
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   └── routers/
├── data/                   # runtime DB ignored; directory retained
├── tests/
│   ├── contract/
│   ├── integration/
│   └── unit/
├── requirements.txt
└── run.py

FE/
├── lib/
│   ├── api/                # typed HTTP client and error envelope
│   ├── app/                # app state and dependency wiring
│   ├── features/
│   │   ├── profiles/
│   │   ├── trips/
│   │   ├── itinerary/
│   │   ├── expenses/
│   │   └── map/
│   └── shared/
└── test/

data/
├── danang.pmtiles
└── snapshots/danang-v1/    # shared POI catalog, not AI-owned

index.html                  # existing prototype remains untouched except integration-safe fixes
server.py                   # PMTiles byte-range server remains the required map server
```

**Structure Decision**: Extend the repository's documented Mobile + API split. Backend uses feature-neutral repositories/services and one transaction boundary per mutation. Flutter uses feature-first modules with plain domain models and repository interfaces; UI-specific colors/icons stay in presentation code. The root prototype remains a regression target rather than being replaced.

## Complexity Tracking

No constitution violations require justification.
