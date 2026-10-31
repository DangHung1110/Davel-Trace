# Module Boundary Contract

## Backend dependency direction

```text
api → application → domain
infrastructure ────────┘
composition root wires infrastructure into application ports
```

1. `domain` imports only Python standard library and domain-owned types.
2. `application` imports its domain and ports, never FastAPI, SQLAlchemy models, or another module's infrastructure.
3. `infrastructure` implements ports and may import SQLAlchemy/provider clients.
4. `api` maps HTTP/Pydantic input to application commands and public responses.
5. `core` contains configuration, sessions, safe errors, correlation/logging, and health primitives only.
6. Capabilities collaborate only through public application contracts.
7. A capability never accesses another capability's private tables/models.
8. `main.py` is the composition root and may wire public module APIs.

## Planning-evidence pilot

```text
PlanningEvidenceRepository
├── save_acceptance(...)
├── get_acceptance(id)
├── list_acceptances(trip_id?, limit)
├── count_acceptances()
├── save_shadow(...)
└── list_shadows(limit)
```

Implementations:

- `PostgresPlanningEvidenceRepository`: production/integration.
- `InMemoryPlanningEvidenceRepository`: isolated unit tests.
- Legacy `AcceptanceStore`: compatibility/import input only; never selected in production after cutover.

Compatibility removal requires PostgreSQL tests passing, public endpoints using the port, an independent importer, and no production SQLite selector.

## Frontend dependency direction

```text
presentation → application → domain
data ────────────────────────┘
core networking/config/errors are cross-cutting adapters
```

1. Feature domain models do not import Flutter widgets or HTTP.
2. Feature data adapters implement feature-owned repositories.
3. Widgets call feature actions/controllers, not raw HTTP.
4. `FE/lib/core` contains business-free configuration, networking, errors, and correlation.
5. `FE/lib/shared/widgets` contains reusable visual components only.
6. Features do not import another feature's private `data` or `presentation`.
7. `AppState` remains a compatibility coordinator; no new business calculations are added.

## Automated checks

Tests fail when backend domain/application imports transport/private infrastructure, Flutter domain imports presentation/HTTP/widgets, a generic common area gains business rules, or a capability dependency cycle appears.

## Ownership map

| Capability | Backend owner | Frontend owner | Delivery |
|------------|---------------|----------------|----------|
| Planning/evidence | `modules/planning_evidence` + legacy planner | `features/planning` | Pilot in 005 |
| Profiles | later `modules/profiles` | `features/profile` | 006/007 |
| Trips/itinerary edits | later `modules/trips` | `features/management`, `features/itinerary` | 007/010 |
| Expenses | later `modules/expenses` | `features/expenses` | 008 |
| POI/map/routing | later `modules/catalog`, `modules/routing` | `features/map` | 009 |
| Shell/session | cross-cutting `core` only | `features/shell` | no business calculations |
