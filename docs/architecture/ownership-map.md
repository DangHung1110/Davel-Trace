# Product ownership map

This map keeps product domains independent while the AI planner is still experimental.
Each table row names the system of record and the only supported integration direction.

| Domain | Owns | May read | Must not own |
|---|---|---|---|
| Identity | Account, role assignment, session, one-time action, password history, lifecycle and security audit | Product-safe profile identifiers | Trip, budget, POI or AI prompt data |
| Planning | Trip, activity, participant, itinerary state | Account identifier and authorization decision | Passwords, refresh tokens or role storage |
| Budget | Budget, expense, allocation and settlement | Trip membership and account identifier | Authentication or itinerary generation |
| POI and routing | POI catalogue, search result references and route geometry | Trip origin/destination requests | Account credentials or financial records |
| AI planner | Proposal, evidence, model metadata and human decision | Explicit planning context, POI references and constraints | Canonical trip, account or expense records |

## Boundary rules

- API handlers authenticate through `identity.application.AuthorizationPolicy`; product
  modules receive a principal rather than reading identity tables directly.
- Database foreign keys may reference an account ID, but product modules never mutate
  identity-owned rows.
- AI output is always a proposal. A product use case validates and copies accepted values
  into its own canonical model; replacing the AI provider does not migrate identity,
  planning or budget data.
- POI and route data are reference data. A saved trip keeps the stable identifier plus the
  minimum snapshot needed for display, so catalogue refreshes do not rewrite history.
- Export and deletion are orchestrated by Identity. Each product module later contributes
  an explicit export/delete adapter; no module reaches into another module's repository.

## Current implementation locations

| Boundary | Backend | Flutter |
|---|---|---|
| Identity | `BE/app/modules/identity/` | `FE/lib/features/auth/` |
| Planning | `BE/app/modules/planning/` | `FE/lib/features/planning/` |
| Shared transport/config | `BE/app/core/` | `FE/lib/core/` |
| Database schema | `BE/app/db/models.py`, Alembic revisions | API models only; no local source of truth |
