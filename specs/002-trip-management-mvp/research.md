# Research: Trip Management MVP

## R1 — Runtime database and code-first workflow

- **Decision**: Use SQLite with SQLAlchemy 2 annotated declarative models and Alembic migrations. `Base.metadata` is Alembic's `target_metadata`; committed revisions, not ad-hoc `create_all`, are the production schema path.
- **Rationale**: The constitution explicitly requires an SQLite/JSON snapshot store. SQLAlchemy models provide the requested code-first source, Alembic provides reviewable/repeatable schema changes, and DBeaver can open the resulting database file directly.
- **Alternatives considered**: PostgreSQL and MySQL were rejected for this feature because either would require a reviewed constitution amendment and extra infrastructure. Raw `sqlite3` DDL was rejected because it would not provide the requested model-first workflow or migration history.

## R2 — Backend architecture

- **Decision**: Use a FastAPI modular monolith with routers → services → repositories → SQLAlchemy session. Pydantic request/response schemas remain separate from ORM models.
- **Rationale**: It matches the existing plan and Lane C direction, keeps transactional CRUD simple, and leaves the optimizer/AI code outside the management core.
- **Alternatives considered**: Microservices add deployment and consistency cost without MVP value. Direct ORM calls from routers make transaction/error/version handling difficult to test.

## R3 — Flutter state and API access

- **Decision**: Use a typed API client, feature repositories and a small framework-native `ChangeNotifier` application state. Use `shared_preferences` only for active-profile selection and last successful management snapshot metadata.
- **Rationale**: The current UI is a small demo and does not justify adding a state-management framework. Repository boundaries allow a future Riverpod/BLoC change without changing domain types.
- **Alternatives considered**: Keeping screen-local hard-coded `DemoTripData` cannot persist or recover. Adding a large state framework now conflicts with simplicity discipline.

## R4 — Itinerary ownership and future AI seam

- **Decision**: The management core owns trips and the confirmed itinerary. A planner port may return `PlannerProposal` objects; only explicit user confirmation can apply a proposal. Manual activity mutations update itinerary `version` and record `source=manual`.
- **Rationale**: AI can be added later without owning users, expenses or canonical trip state. Proposal confirmation prevents unexpected schedule replacement.
- **Alternatives considered**: Letting AI write directly into itinerary tables creates tight coupling and makes rollback/audit difficult.

## R5 — POI catalog boundary

- **Decision**: Keep POIs in a versioned JSON snapshot and expose them through a catalog repository/API. Activities persist optional `poi_id` plus a name/coordinate snapshot.
- **Rationale**: POIs serve map/manual planning now and AI later. Snapshot fields preserve old trips if catalog records are refreshed or removed.
- **Alternatives considered**: Storing only `poi_id` breaks historical views. Copying the entire POI record into every activity duplicates unstable metadata.

## R6 — Routing and map behavior

- **Decision**: Preserve PMTiles and the root byte-range server. Route previews use OSRM through a backend service with timeout; response always labels `source` and whether geometry is a real route. A straight-line fallback is display-only and never described as a route.
- **Rationale**: This reuses the working map assets, avoids mobile CORS differences and enforces the existing truthfulness rule.
- **Alternatives considered**: Calling OSRM independently from every Flutter platform duplicates policy. Removing the root prototype would violate regression requirements.

## R7 — Concurrency and deletion

- **Decision**: Mutable API resources carry integer `version`; update/delete commands provide the expected version and receive HTTP 409 on mismatch. Database foreign keys are enabled, required relations use cascade delete, and mutations run in one transaction.
- **Rationale**: It prevents silent lost updates and orphaned expenses/activities while remaining simple for a single-device MVP.
- **Alternatives considered**: Last-write-wins conflicts with the specification. Soft delete for every entity adds query complexity without a retention requirement.

## R8 — Database inspection in DBeaver

- **Decision**: Default DB path is `BE/data/davel_trace.db`; quickstart documents the absolute path and SQLite connection steps. Runtime `.db`, journal and WAL files are ignored.
- **Rationale**: Users can inspect tables without running a database server, while Alembic remains the only schema creation/update workflow.
- **Alternatives considered**: Shipping a committed runtime DB causes stale data and merge conflicts.
