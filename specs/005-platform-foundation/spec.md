# Feature Specification: Product Platform Foundation

**Feature Branch**: `feat/product-platform`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Refactor the existing backend and frontend into a clean professional structure, establish durable production data and incremental delivery, and preserve all working planner, map and mobile demo behavior."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repeatable Complete Local Startup (Priority: P1)

A developer or presenter can start the product from a documented clean checkout, obtain a healthy backend and mobile interface, and understand every dependency failure without editing source files.

**Why this priority**: A complete product cannot be developed or demonstrated reliably when setup depends on hidden machine state.

**Independent Test**: On a clean development machine, follow one documented sequence to configure the environment, initialize authoritative data, start the backend and mobile web app, and observe healthy status plus the seeded demo.

**Acceptance Scenarios**:

1. **Given** a clean checkout and documented prerequisites, **When** setup is followed, **Then** required services, schema and seed data initialize without manual source edits.
2. **Given** required configuration is missing or invalid, **When** startup occurs, **Then** it fails with an actionable message naming the missing category without revealing a secret.
3. **Given** all required services are available, **When** health is checked, **Then** application, authoritative data, catalog snapshot and migration status are distinguishable.
4. **Given** optional route, weather or AI providers are unavailable, **When** the product starts, **Then** core management and documented local fallbacks remain available.

---

### User Story 2 - Durable Authoritative Data (Priority: P1)

A developer can initialize, upgrade, seed, back up and restore the shared product data while user-owned records survive process and deployment restarts.

**Why this priority**: The current demo repositories and in-memory stores cannot support a complete multi-user product.

**Independent Test**: Initialize an empty environment, write representative records through product contracts, restart every process, upgrade one schema version, back up and restore, and verify identifiers and relationships remain valid.

**Acceptance Scenarios**:

1. **Given** an empty authoritative store, **When** initialization runs, **Then** the expected schema version exists and the operation is repeatable.
2. **Given** records were committed successfully, **When** backend and data services restart, **Then** the same records and relationships remain available.
3. **Given** the immediately previous supported schema, **When** upgrade runs, **Then** data is preserved and the new version is recorded.
4. **Given** an interrupted or failed schema change, **When** the service recovers, **Then** it does not report a partially upgraded state as healthy.
5. **Given** a verified backup, **When** it is restored into an empty environment, **Then** integrity checks and representative product reads succeed.

---

### User Story 3 - Preserve Existing Product Behavior During Refactor (Priority: P1)

A traveler or presenter continues to use itinerary generation, hard-gate selection, review/repair, map/search/route, vehicle playback, expenses demo and mobile navigation while internal code is reorganized incrementally.

**Why this priority**: Architectural cleanup has no value if it breaks the working product or changes its contracts silently.

**Independent Test**: Run the established backend regression suite, Flutter widget suite, root map smoke flow and one end-to-end mobile demo before and after each structural move and compare the public behavior.

**Acceptance Scenarios**:

1. **Given** a currently supported request, **When** the refactored backend handles it, **Then** public fields, status categories and feasibility behavior remain compatible unless an approved contract change says otherwise.
2. **Given** the Da Nang map and route demo, **When** refactored frontend modules load, **Then** PMTiles, search A/B, real/fallback route labels and play/pause remain functional.
3. **Given** an existing cached or seeded mobile state, **When** the app starts, **Then** it remains visibly labeled and does not become fake authoritative data.
4. **Given** a moved capability is not fully migrated, **When** a caller uses it, **Then** an explicit compatibility adapter handles the call rather than duplicate business logic.

---

### User Story 4 - Clear Capability Ownership (Priority: P1)

A contributor can locate the owner of a business rule, data record, API behavior or mobile screen without searching unrelated modules, and can change one capability without creating a circular dependency.

**Why this priority**: Professional structure reduces regressions and allows later increments to be delivered independently.

**Independent Test**: Ask a contributor unfamiliar with the refactor to locate and change one profile rule, expense calculation, planning gate and map widget; verify each change remains inside its capability boundary plus approved shared contracts.

**Acceptance Scenarios**:

1. **Given** a business capability, **When** its code and tests are located, **Then** one documented module owns its domain rules, application behavior, data boundary and presentation/API boundary.
2. **Given** two capabilities must collaborate, **When** one calls the other, **Then** the dependency follows a documented direction and does not access private persistence or transport internals.
3. **Given** code is genuinely cross-cutting, **When** it is placed in a shared area, **Then** it contains no feature-specific business decision.
4. **Given** a legacy file has multiple owners, **When** it is split, **Then** behavior moves with tests and the legacy entry point is removed only after callers migrate.

---

### User Story 5 - Honest Demo and Production Modes (Priority: P2)

A presenter can deliberately choose an isolated seeded demo, while a signed-in production flow always uses authoritative shared data and never silently falls back to local fake persistence.

**Why this priority**: The current demo is useful, but mixing demo and production records would undermine trust and testing.

**Independent Test**: Start in demo mode and production mode, perform the same visible actions, restart, and verify labels, identifiers, storage behavior and reset scope remain different and correct.

**Acceptance Scenarios**:

1. **Given** explicit demo mode, **When** seeded records are changed, **Then** they remain isolated, visibly labeled and safely resettable.
2. **Given** production mode, **When** authoritative data is unavailable, **Then** a write fails honestly instead of being reported as locally persisted success.
3. **Given** a demo reset, **When** it is confirmed, **Then** only designated demo state changes and real records remain untouched.
4. **Given** a production record identifier, **When** it is shown, **Then** it originated from an acknowledged authoritative write.

---

### User Story 6 - Diagnose Failures Without Exposing Secrets (Priority: P2)

A developer or operator can correlate a failing mobile action with backend and dependency status, while travelers receive stable, understandable errors and sensitive configuration remains protected.

**Why this priority**: Incremental refactoring needs observable behavior; raw exceptions and hidden failures are not supportable.

**Independent Test**: Trigger validation, authorization, data, route-provider and unexpected failures; correlate each across client and backend using non-sensitive identifiers and verify user messages remain stable.

**Acceptance Scenarios**:

1. **Given** one user action, **When** it crosses frontend and backend boundaries, **Then** diagnostic records share a correlation identifier.
2. **Given** a known failure category, **When** it reaches a client, **Then** the response uses a stable category and actionable message.
3. **Given** an unexpected failure, **When** it is logged, **Then** operators receive diagnostic context while the traveler sees a safe generic message.
4. **Given** logs, health output or error responses, **When** they are inspected, **Then** credentials, recovery tokens, private connection values and unnecessary personal content are absent.

### Edge Cases

- Initialization is run twice or two startup instances attempt it concurrently.
- The authoritative store is reachable but schema version is older, newer or partially applied.
- Seed data conflicts with an existing stable identifier.
- A backup is incomplete, corrupt, encrypted with unavailable credentials, or from an unsupported version.
- Process termination occurs between validation and commit.
- Optional dependencies are down while required durable data is healthy, and vice versa.
- A compatibility adapter and new implementation are accidentally enabled together.
- A legacy module imports a new module in the opposite direction and creates a cycle.
- Generated/runtime files appear inside source directories after tool execution.
- Demo and production base URLs point to the same environment accidentally.
- A secret contains characters that break naïve configuration parsing.
- Flutter starts before backend readiness, backend restarts while the app is open, or a stale cached response arrives late.
- A refactored error category changes but an older client is still running.
- PMTiles byte ranges work while external font/icon assets fail.

## Requirements *(mandatory)*

### Functional Requirements

#### Startup and Configuration

- **FR-001**: The product MUST have one documented configuration contract for required, optional, secret and environment-specific values.
- **FR-002**: Startup MUST validate required configuration before accepting user traffic.
- **FR-003**: Configuration errors MUST identify the invalid category without printing the secret value.
- **FR-004**: A clean environment MUST be initializable through documented, repeatable actions without editing source code.
- **FR-005**: Required and optional dependencies MUST have distinct readiness states.
- **FR-006**: Health information MUST distinguish application liveness, authoritative-data readiness, schema readiness, catalog readiness and optional-provider degradation.
- **FR-007**: PowerShell and Git Bash startup flows MUST be documented and produce equivalent product behavior.

#### Durable Data Lifecycle

- **FR-008**: Production records MUST use one shared authoritative store and MUST NOT rely on process memory or device-local demo state as the source of truth.
- **FR-009**: The authoritative schema MUST have an explicit version and repeatable initialization path.
- **FR-010**: Every schema change MUST have a forward upgrade path from the immediately previous supported version.
- **FR-011**: Failed schema changes MUST not be reported as successfully applied.
- **FR-012**: Authoritative writes MUST be atomic at product-defined consistency boundaries.
- **FR-013**: Stable identifiers and required relationships MUST remain valid across restart, upgrade, backup and restore.
- **FR-014**: Demo seed data MUST be deterministic, isolated and safe to apply repeatedly in a designated demo environment.
- **FR-015**: Production startup MUST NOT silently seed demonstration users or records.
- **FR-016**: A documented backup and restore flow MUST include integrity verification.
- **FR-017**: Runtime databases, credentials, backups, exports and generated caches MUST remain outside version control.

#### Modular Ownership and Compatibility

- **FR-018**: Each backend business capability MUST have one documented owner for domain rules, application behavior, persistence boundary and public transport boundary.
- **FR-019**: Each frontend feature MUST own its domain state, application actions, data adapters and feature presentation.
- **FR-020**: Shared code MUST contain only cross-cutting behavior and MUST NOT become an alternate home for feature-specific rules.
- **FR-021**: Business rules MUST be callable and testable without requiring a live user interface or HTTP request.
- **FR-022**: Presentation and transport code MUST NOT own authoritative business calculations.
- **FR-023**: One capability MUST NOT access another capability’s private persistence representation directly.
- **FR-024**: Cross-capability dependencies MUST follow documented directions and automated checks MUST detect forbidden cycles.
- **FR-025**: Existing public behavior MUST remain compatible during migration unless a versioned contract change is approved.
- **FR-026**: Temporary compatibility adapters MUST have a named owner, covered behavior and removal condition.
- **FR-027**: Duplicate old/new business implementations MUST NOT remain active after caller migration is complete.

#### Regression and Refactor Safety

- **FR-028**: Existing planner, feasibility gate, selection, review, repair, replan, map, search, route and playback flows MUST have regression evidence before structural code is moved.
- **FR-029**: A refactor step MUST be small enough to review and revert without discarding unrelated feature work.
- **FR-030**: Existing accepted-plan and catalog data versions MUST remain readable through the documented compatibility period.
- **FR-031**: Generated artifacts and runtime data MUST be ignored without ignoring intentionally tracked PMTiles or platform source.
- **FR-032**: A refactor MUST preserve explicit seeded, live, stale, offline and failed product states.
- **FR-033**: Removing a legacy entry point MUST wait until all known callers and tests use the replacement.

#### Error Handling and Observability

- **FR-034**: Every product request MUST have a correlation identifier available to client and backend diagnostics.
- **FR-035**: Expected failures MUST use stable categories and user-actionable messages.
- **FR-036**: Unexpected failures MUST fail safely and provide operators sufficient non-sensitive context for diagnosis.
- **FR-037**: Logs and health output MUST exclude credentials, session values, recovery tokens and unnecessary personal content.
- **FR-038**: A client MUST distinguish validation, authentication, authorization, conflict, unavailable dependency, offline and unexpected failure states.
- **FR-039**: Observability MUST not become a required external dependency for normal local development or demo operation.

#### Demo and Developer Experience

- **FR-040**: Demo mode MUST be activated explicitly and remain visibly labeled in user-facing screens.
- **FR-041**: Production mode MUST fail an authoritative write honestly when the required store is unavailable.
- **FR-042**: Demo reset MUST be scoped to designated demo data and MUST never target production records.
- **FR-043**: The repository MUST document canonical commands for setup, startup, schema upgrade, seed, test, backup, restore and mobile demo.
- **FR-044**: The local mobile demo MUST retain the desktop phone frame and navigation among itinerary, map, expenses and profile.
- **FR-045**: The root static map MUST continue to be served by a byte-range-capable server.

### Key Entities

- **Environment Configuration**: Named required/optional/secret values and their validation state, never their exposed secret content.
- **Schema Version**: Ordered identifier for authoritative data structure and applied upgrade history.
- **Migration Record**: Evidence that a version transition started, completed or failed.
- **Seed Dataset**: Deterministic, explicitly designated demo data with stable identifiers and scope.
- **Backup Manifest**: Backup time, source version, checksum, scope and restore compatibility.
- **Health Component**: Named required or optional dependency with liveness/readiness/degraded state.
- **Correlation Context**: Non-sensitive identifier connecting one client action to backend diagnostics.
- **Error Envelope**: Stable category, safe message, correlation identifier and optional field-level details.
- **Capability Contract**: Public application behavior one module exposes without revealing private persistence or transport details.
- **Compatibility Adapter**: Temporary bridge with owner, covered callers, tests and removal condition.
- **Demo Session**: Isolated seeded state and explicit mode metadata that cannot be confused with authoritative production records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new contributor completes documented local setup and reaches a healthy backend plus mobile demo within 20 minutes, excluding dependency download time.
- **SC-002**: Required configuration mistakes are identified correctly in 100% of configuration fixtures without exposing their values.
- **SC-003**: Representative authoritative records survive 100 consecutive backend restart tests without loss or duplication.
- **SC-004**: An empty environment and the immediately previous supported schema both reach the current schema successfully in automated tests.
- **SC-005**: Failed upgrade tests leave 0 partially healthy schema states.
- **SC-006**: Backup/restore tests reproduce all representative identifiers, relationships and record counts exactly.
- **SC-007**: Existing backend regression, Flutter widget, root map and manual mobile smoke suites pass after every completed refactor slice.
- **SC-008**: No prohibited capability dependency cycle exists in automated architecture checks.
- **SC-009**: At least 90% of sampled business-rule changes touch one owning capability plus approved shared contracts only.
- **SC-010**: Demo and production writes are correctly distinguished in 100% of mode-isolation tests.
- **SC-011**: A failed production authoritative write is never reported as local persisted success.
- **SC-012**: All defined client/backend error scenarios carry a correlation identifier and stable error category.
- **SC-013**: No committed file, health output or captured ordinary log contains a live credential or private connection value.
- **SC-014**: PMTiles range, search A/B, route fallback and vehicle play/pause remain demonstrable after the foundation increment.
- **SC-015**: A contributor unfamiliar with the refactor locates the owner of profile, trip, expense, planning and map behavior correctly in at least 9 of 10 test prompts.

## Assumptions

- The current stable planning, data-quality and Flutter mobile code is the behavioral baseline to preserve.
- The authoritative production store is shared and relational; the implementation plan selects the engine and migration tooling explicitly.
- Existing demo SQLite/in-memory/local repositories may remain temporarily behind compatibility contracts but are not the final production source of truth.
- Identity, complete trip CRUD and expense migration are delivered by later increments; this foundation provides their durable and modular prerequisites.
- Da Nang, Vietnamese-first behavior, existing PMTiles and deterministic feasibility remain product constraints.
- The foundation is delivered by incremental moves, not a repository-wide rename or rewrite in one commit.
- Optional route, weather, email and AI providers may be unavailable locally without making the core backend unhealthy.
- Existing public contracts remain compatible during this increment unless a separately reviewed versioned change is required.

## Dependencies

- The verified behavior and regression tests carried from the stable-planning release.
- Access to a supported shared relational data environment for production-mode verification.
- Existing root byte-range server, PMTiles assets, Flutter SDK project and backend dependency environment.
- Review agreement on capability ownership before legacy files are removed.
