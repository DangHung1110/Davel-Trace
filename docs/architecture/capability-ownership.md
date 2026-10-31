# Capability Ownership and Boundaries

This map prevents the product-platform work from becoming a second monolith
while the existing demo remains available. A capability owns its business
rules and future database tables; integration uses public application APIs.

| Capability | Backend owner | Flutter owner | Current status |
|---|---|---|---|
| Planning evidence | `BE/app/modules/planning_evidence` | `FE/lib/features/planning` | PostgreSQL pilot |
| Profile and account | `BE/app/modules/profiles` | `FE/lib/features/profile` | planned 006/007 |
| Trips and itinerary | `BE/app/modules/trips` | `FE/lib/features/management`, `itinerary` | planned 007/010 |
| Expenses | `BE/app/modules/expenses` | `FE/lib/features/expenses` | planned 008 |
| POI catalog | `BE/app/modules/catalog` | `FE/lib/features/map` | planned 009 |
| Routing | `BE/app/modules/routing` | `FE/lib/features/map` | planned 009 |

## Backend rules

- `domain.py` uses only the Python standard library and domain-owned types.
- `application.py` declares ports and use cases; it does not import FastAPI,
  SQLAlchemy, database models, or private infrastructure.
- `infrastructure.py` implements ports and owns transaction/session details.
- `api.py` is the public composition surface for the capability.
- A module never queries another module's tables directly.
- `BE/app/main.py` remains the HTTP composition root.

## Flutter rules

- Domain models do not import Flutter widgets or HTTP clients.
- A feature exposes public UI through a root barrel such as `map/map.dart`.
- Cross-feature imports target that public barrel, never another feature's
  `data/` or `presentation/` directory.
- `FE/lib/core` contains business-free config, networking, errors, and
  observability only.
- `AppState` is a temporary compatibility coordinator. New calculations belong
  in feature application/domain code.

## Temporary compatibility bridge

`LegacyPlanningEvidenceAdapter` exists only for demo/test compatibility when a
PostgreSQL URL is absent. Its owner is the platform-foundation increment. It is
removed after all runtime planning-evidence callers use PostgreSQL, the explicit
SQLite importer has been verified, and the itinerary lifecycle no longer
depends on the SQLite store. Production mode never selects this adapter.
