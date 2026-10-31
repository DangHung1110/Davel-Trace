# Incremental Delivery Roadmap: Davel Trace Product Platform

**Umbrella specification**: [spec.md](./spec.md)
**Working branch**: `feat/product-platform`
**Rule**: No big-bang rewrite. Each increment preserves verified behavior, has its own Spec Kit artifacts, and is independently demonstrable before the next increment begins.

## Delivery Strategy

1. Introduce professional boundaries and durable infrastructure around the working product.
2. Move one business capability at a time behind stable contracts.
3. Keep compatibility adapters until the replacement passes contract and regression tests.
4. Remove legacy code only after callers have moved and equivalent behavior is proven.
5. Keep map, search, route, planner, review/repair, and play/pause flows working after every increment.

## Increments

| Order | Spec | Deliverable | Independent demo | Status |
|---:|---|---|---|---|
| 1 | `005-platform-foundation` | Durable shared data foundation, migrations, configuration, observability, professional BE/FE module boundaries, compatibility safety | Start the complete local stack, apply schema changes, seed demo data, restart, and verify existing planner/mobile flows still work | Spec ready |
| 2 | `006-identity-access` | Registration, verification, login, recovery, roles, sessions, account lifecycle | Register and sign in on two sessions; revoke and recover securely | Pending specification |
| 3 | `007-profile-trip-management` | Persistent profile, preferences, trip/day/activity CRUD, archive/restore | Create a multi-day trip, reopen after restart, edit activities, archive and restore | Pending specification |
| 4 | `008-expense-budget` | Persistent budgets, expenses, summaries, alerts, audit and export | Add/edit/delete expenses across days; totals survive restart and match export | Pending specification |
| 5 | `009-poi-map-routing` | Versioned POIs, search/details, PMTiles, real/fallback route and geolocation states | Search and add a POI, render local map, preview route, play/pause | Pending specification |
| 6 | `010-itinerary-lifecycle` | Persisted requests, alternatives, hard gates, selection, versions, replan and acceptance evidence | Generate feasible alternatives, select idempotently, change constraints and replan | Pending specification |
| 7 | `011-offline-sync` | Cached reading, queued safe writes, stale/conflict handling, demo isolation | Edit offline, reconnect, synchronize once and resolve a conflict | Pending specification |
| 8 | `012-admin-data-ops` | User status, POI curation, catalog publishing, audit, backup/restore and readiness | Publish a catalog version, suspend a test user, restore a backup | Pending specification |
| 9 | `013-ai-integration` | Replaceable parsing, explanation and shadow ranking adapters after evidence gates | Disable/replace AI provider without breaking management or feasibility | Deferred until evidence gates |

## Refactor Boundaries

### Backend capability ownership

- `identity`: accounts, credentials, sessions and roles.
- `profiles`: traveler preferences and hard constraints.
- `trips`: trips, days, activities and progress.
- `expenses`: budgets, entries, summaries and exports.
- `catalog`: POIs, evidence, verification and data versions.
- `planning`: requests, optimizer orchestration, hard gates, alternatives, versions and acceptance.
- `routing`: route matrices, online route adapters and route evidence.
- `operations`: audit, health, readiness, backup/restore and administrative controls.
- `shared`: configuration, database lifecycle, error envelope, identifiers, clock and cross-cutting observability only.

Business modules must not import router code or reach into another module's persistence internals. Cross-module access uses application-level contracts. Existing planner algorithms remain isolated from account, HTTP and database implementation details.

### Frontend capability ownership

- `core`: application bootstrap, configuration, networking, persistence, routing and shared error handling.
- `features/auth`, `profile`, `trips`, `expenses`, `catalog`, `planning`, `map`, and `admin`.
- Each feature owns its domain models, application state/use cases, data adapters and presentation widgets.
- Shared visual primitives remain in the design system; feature-specific widgets do not move into global shared folders.
- Demo repositories implement the same contracts as live repositories and are injected only by an explicit demo mode.

## Increment Definition of Done

An increment is complete only when:

- Its spec, plan, checklist and tasks are internally consistent.
- New tests first demonstrate missing behavior, then pass with implementation.
- Existing backend and Flutter regression suites remain green.
- Schema changes can be applied to an empty database and upgraded from the previous increment.
- Runtime data and secrets remain outside Git.
- Documentation contains PowerShell and Git Bash demo commands plus DBeaver steps where data changes.
- `/speckit.converge` reports no remaining implementation tasks.
- Commits are small and professional, the branch is pushed, and review targets `dev` without direct protected-branch pushes.

## Branch Model

`feat/product-platform` is the temporary product integration branch requested by the owner. Large increments SHOULD use `task/<increment>-<scope>` branches and merge back only after tests. The final reviewed product branch targets `dev`. The historical release branch receives no further changes.
