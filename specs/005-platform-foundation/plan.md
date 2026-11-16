# Implementation Plan: Product Platform Foundation

**Branch**: `task/005-platform-foundation` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-platform-foundation/spec.md`

## Summary

Establish a production-capable foundation without rewriting the working planner, static map, or Flutter demo. PostgreSQL 16 becomes the authoritative operational store, SQLAlchemy 2 models define the code-first schema, and reviewed Alembic migrations control upgrades. The backend is migrated incrementally toward a capability-based modular monolith, beginning with configuration, persistence, health, errors, correlation context, and the accepted-plan evidence store. Flutter retains the current UI and dependencies while feature ownership and core boundaries are made explicit. Compatibility adapters preserve existing API behavior until later increments migrate each capability.

## Technical Context

**Language/Version**: Python 3.11; Dart SDK 3.13 / Flutter project currently pinned by `FE/pubspec.yaml`; HTML/JavaScript root map remains framework-free

**Primary Dependencies**: FastAPI, Pydantic 2, pydantic-settings 2, SQLAlchemy 2, Alembic 1.x, psycopg 3, Uvicorn; existing Flutter packages only

**Storage**: PostgreSQL 16 for authoritative operational records; versioned JSON and PMTiles for planning/map snapshots; legacy SQLite accepted-plan database supported only as an explicit import source and isolated test adapter

**Testing**: pytest unit/contract/integration tests, PostgreSQL migration tests, static architecture checks, Flutter analyze/widget tests, root PMTiles range and map smoke checks

**Target Platform**: Windows 10/11 local development and laptop demo; Linux-compatible backend/container deployment; Flutter Web on Chrome plus existing Android/iOS targets

**Project Type**: Mobile application + FastAPI backend + static PMTiles map/demo

**Performance Goals**: local liveness and readiness complete within one second during the demo; preserve parser <10 s, itinerary <30 s, and replan <15 s budgets; load/stress benchmarks are outside this student-project increment

**Constraints**: Da Nang only; no secret in Git/logs/health; deterministic feasibility remains authoritative; PMTiles range serving remains intact; production writes never fall back to demo/local persistence; setup reaches healthy demo within 20 minutes excluding downloads

**Scale/Scope**: single deployable modular monolith, one Flutter app, one PostgreSQL database, 100–200 curated POIs, MVP-scale user/trip/expense records, and incremental migration of existing APIs

## Constitution Check

*GATE: Passed before research and re-checked after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| Feasibility-first | PASS | No optimizer or hard-gate authority moves to AI; planning behavior is regression-protected. |
| Spec-driven development | PASS | Spec and requirements checklist exist; this plan precedes tasks, analyze, and implementation. |
| Test-first | PASS | Migration, repository contract, health/error, architecture, Flutter, and map regression tests are planned before structural moves. |
| Data provenance and honesty | PASS | JSON/PMTiles snapshot authority is unchanged; production and demo persistence are explicitly separated. |
| Simplicity and tier discipline | PASS | One modular monolith and one database are used; no broker, microservices, new AI model, or Flutter state package is added. |
| Mobile contract | PASS | Flutter remains primary; API compatibility and current performance budgets are preserved. |
| Technology constraints | PASS | PostgreSQL, SQLAlchemy 2, Alembic, FastAPI, Flutter, OSRM, and versioned snapshots match Constitution 2.0.0. |
| Development workflow | PASS | Work occurs on `task/005-platform-foundation`, then reviewed PR into `feat/product-platform`. |

**Post-design re-check**: PASS. The contracts keep optional providers out of core readiness, the data model limits this increment to foundation/evidence records, and the module design avoids a big-bang rewrite.

## Project Structure

### Documentation (this feature)

```text
specs/005-platform-foundation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api-foundation.md
│   ├── module-boundaries.md
│   └── persistence.md
├── checklists/requirements.md
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
│   ├── core/
│   │   ├── config.py
│   │   ├── errors.py
│   │   ├── health.py
│   │   ├── logging.py
│   │   └── request_context.py
│   ├── db/
│   │   ├── base.py
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations.py
│   ├── modules/
│   │   └── planning_evidence/
│   │       ├── api.py
│   │       ├── application.py
│   │       ├── domain.py
│   │       └── infrastructure.py
│   ├── routers/                 # legacy-compatible transport during migration
│   ├── schemas/                 # legacy-compatible public schemas
│   ├── services/                # legacy services migrated incrementally
│   └── main.py                  # composition root
├── scripts/
│   ├── import_acceptance_sqlite.py
│   ├── seed_demo.py
│   └── verify_backup.py
└── tests/
    ├── architecture/
    ├── contract/
    ├── integration/
    └── unit/

FE/lib/
├── core/
│   ├── config/
│   ├── errors/
│   ├── networking/
│   └── observability/
├── features/
│   ├── expenses/
│   ├── itinerary/
│   ├── management/
│   ├── map/
│   ├── planning/
│   ├── profile/
│   └── shell/
├── shared/widgets/              # business-free shared presentation only
├── app.dart
└── main.dart

compose.yaml
server.py                        # byte-range static map server, unchanged contract
```

**Structure Decision**: Retain the existing `BE/`, `FE/`, and root static-map surfaces. Introduce backend `core`, `db`, and capability `modules` beside legacy folders, then move one tested capability at a time through adapters. On Flutter, normalize existing feature-first folders and move only cross-cutting API/config/error concerns into `core`; do not rewrite screens or replace `ChangeNotifier` in this increment.

## Delivery Slices

1. Add regression baselines and architecture rules before moves.
2. Add typed configuration, correlation context, safe errors, liveness/readiness, and restricted CORS.
3. Add PostgreSQL Compose service, SQLAlchemy base/session, Alembic environment, and initial schema.
4. Port accepted-plan and shadow evidence behind a repository contract while preserving current endpoints.
5. Add idempotent legacy SQLite import, deterministic demo seed, backup/restore verification, and DBeaver documentation.
6. Establish BE/FE ownership skeletons and migrate cross-cutting code without changing visible behavior.
7. Run full backend, Flutter, PMTiles, map/search/route, and mobile demo regression.

## Complexity Tracking

No Constitution violations require justification. Repository ports and compatibility adapters are temporary migration mechanisms with explicit removal conditions in [module-boundaries.md](./contracts/module-boundaries.md).
