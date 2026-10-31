# Feature Specification: Davel Trace Complete Product MVP

**Feature Branch**: `feat/product-platform`

**Created**: 2026-10-29

**Status**: Portfolio baseline — delivered through incremental feature specs

**Input**: User description: "Deliver a complete, production-oriented Davel Trace application with full management capabilities, durable shared data, a laptop-runnable mobile experience, and clean seams for adding AI itinerary recommendations later."

## Product Vision

Davel Trace is a Vietnamese-first travel companion for planning and managing a Da Nang trip from one place. A traveler can create an account, maintain travel preferences, organize trips and daily activities, compare only feasible itinerary alternatives, use the local Da Nang map and route guidance, track budget and expenses, and recover their data on another authorized device. Operators can curate the POI catalog and inspect operational evidence without editing user-owned records silently.

This feature converts the current demonstrator into a complete product MVP. Demo-only, in-memory, and device-local repositories remain useful for explicit showcase or offline modes, but they are not accepted as the authoritative store for signed-in users.

Implementation is intentionally split into independently reviewable increments. This document remains the product-wide source of scope and success criteria; [increments.md](./increments.md) defines delivery order, and each increment receives its own Spec Kit specification, plan, tasks, tests, and PR.

## Scope

### In Scope

- Account registration, authentication, session management, password recovery, profile editing, account export, and account deletion.
- Persistent traveler preferences, constraints, accessibility needs, food preferences, transport choices, and spending style.
- Complete trip, day, activity, participant-count, note, and status management.
- Manual itinerary editing plus deterministic generation of multiple feasible alternatives, selection, version history, and replanning.
- A curated Da Nang POI catalog with category search, details, verification status, opening-hour evidence, prices, location, and map display.
- Local Da Nang PMTiles display, route preview, real-route/fallback distinction, geolocation state, and play/pause route simulation.
- Trip budgets, categorized expenses, daily and trip summaries, threshold warnings, corrections, and exports.
- Explicit online, offline, seeded-demo, synchronizing, stale, and conflict states.
- Administrative user-status controls, POI curation, data versioning, operational audit, and safe demo reset.
- Stable interfaces and evidence records for adding AI parsing, explanation, ranking, and recommendation after the management MVP is reliable.
- A laptop demo in a mobile-sized frame and deployable mobile/web behavior from the same product flows.

### Out of Scope for This MVP

- Booking, ticket purchasing, payment processing, subscriptions, and refunds.
- Receipt OCR, voice control, public social feeds, messaging, collaborative live trip editing, and marketplace features.
- Multi-city optimization; selectable plans remain limited to Da Nang.
- AI-generated routes or any AI output that can bypass deterministic feasibility checks.
- Automatic learned ranking or accepted-day retrieval before the published evidence thresholds are met.
- Background turn-by-turn navigation comparable to a dedicated navigation provider.

## Actors and Permissions

- **Guest**: Can view onboarding, run an explicitly labeled seeded demo, browse public verified POIs, and register or sign in. Guest changes are not presented as server-persisted records.
- **Traveler**: Owns a profile, trips, itineraries, expenses, exports, and account controls. A traveler cannot access another traveler’s private records.
- **Administrator**: Can suspend/reactivate accounts, inspect audit metadata, manage catalog data, publish data versions, and monitor system readiness. An administrator cannot silently rewrite a traveler’s expense or selected itinerary.
- **Data Curator**: Can propose and verify POI changes but cannot manage user accounts. An administrator may also hold this role.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secure Account and Recovery (Priority: P1)

A traveler creates an account, signs in, remains signed in safely, recovers a forgotten password, signs out, and can request export or deletion of the account.

**Why this priority**: Durable ownership and isolation are prerequisites for every management feature.

**Independent Test**: Register a new traveler, verify the account, sign in on a second browser session, recover the password, confirm private data isolation, and sign out from all sessions.

**Acceptance Scenarios**:

1. **Given** an unused valid email address, **When** the traveler registers with a compliant password and accepts required terms, **Then** the account is created without exposing credentials in logs or responses.
2. **Given** valid credentials, **When** the traveler signs in, **Then** a private session starts and only that traveler’s records are accessible.
3. **Given** an unknown or incorrect credential, **When** sign-in fails repeatedly, **Then** the response remains non-enumerating and abuse protection activates without blocking unrelated accounts.
4. **Given** a traveler has forgotten a password, **When** a valid recovery flow is completed, **Then** the new password works and older sessions are invalidated.
5. **Given** an authenticated traveler, **When** account deletion is confirmed, **Then** access ends immediately and the documented deletion lifecycle begins.

---

### User Story 2 - Personal Travel Profile (Priority: P1)

A traveler records preferences and hard constraints once, reviews what will affect planning, and can override non-safety preferences for a specific trip.

**Why this priority**: The profile makes planning relevant while separating preferences from non-negotiable safety constraints.

**Independent Test**: Create and edit a profile, start a trip with inherited values, override pace for that trip, and verify allergy/accessibility constraints remain clearly identified.

**Acceptance Scenarios**:

1. **Given** a new account, **When** onboarding is completed, **Then** the profile stores party type, pace, fitness, spending style, food preferences, avoidances, accessibility needs, and usual transport.
2. **Given** an existing profile, **When** a preference is edited, **Then** future requests use the new value while existing accepted itinerary history remains unchanged.
3. **Given** a trip-level override, **When** planning starts, **Then** the override is visible and applies only to that trip.
4. **Given** an allergy or accessibility constraint, **When** a conflicting POI is considered, **Then** it is excluded or visibly blocked rather than treated as a soft preference.

---

### User Story 3 - Manage Trips and Daily Activities (Priority: P1)

A traveler creates, edits, archives, restores, and deletes trips; organizes days and activities; and always sees which trip is active.

**Why this priority**: Trip management is the core non-AI value of the product.

**Independent Test**: Create a multi-day Da Nang trip, add and reorder activities, change dates and traveler count, archive and restore it, then reopen it after signing in again.

**Acceptance Scenarios**:

1. **Given** a signed-in traveler, **When** a valid trip is created, **Then** it appears in the traveler’s trip list with dates, status, budget, traveler count, and last-update time.
2. **Given** an active trip, **When** the traveler adds, edits, reorders, or removes an activity, **Then** the day timeline and route-impact state update consistently.
3. **Given** a trip with accepted itinerary history, **When** dates or constraints change, **Then** the existing accepted version remains auditable and the trip is marked as needing review or replanning.
4. **Given** an archived trip, **When** the traveler restores it, **Then** its itinerary, expenses, and history are restored without duplication.
5. **Given** a deletion request, **When** the traveler confirms it, **Then** the product explains the consequence and performs a recoverable soft-delete before final purge.

---

### User Story 4 - Receive and Select Feasible Itineraries (Priority: P1)

A traveler requests alternatives, compares tradeoffs and hard-gate evidence, selects one, and can replan without losing the selected-plan history.

**Why this priority**: Feasible, explainable planning is the product’s principal differentiator.

**Independent Test**: Request a one-day trip plan, receive up to five distinct feasible alternatives, inspect evidence, select one idempotently, change a constraint, and create a linked replan version.

**Acceptance Scenarios**:

1. **Given** a valid trip and available catalog data, **When** alternatives are requested, **Then** every returned alternative passes entity, schedule, movement, budget, and traveler-constraint checks.
2. **Given** fewer than five genuinely different feasible alternatives, **When** results are returned, **Then** the product reports the actual count and reason without padding with duplicate or infeasible plans.
3. **Given** several alternatives, **When** the traveler compares them, **Then** cost, travel distance, schedule, POIs, warnings, data version, and gate status are understandable.
4. **Given** a selectable alternative, **When** selection is submitted twice because of retry, **Then** exactly one accepted-plan record is created.
5. **Given** a previously accepted plan, **When** replanning occurs, **Then** the new plan links to its parent and the earlier version remains immutable.
6. **Given** planning cannot produce a valid result, **When** the request completes, **Then** the traveler receives actionable reasons and can edit constraints or continue manual planning.

---

### User Story 5 - Explore POIs and Use the Map (Priority: P1)

A traveler searches verified Da Nang places, reads details, adds a POI to a trip, views stops on the local map, previews a route, and controls route playback.

**Why this priority**: The map connects itinerary decisions to the real trip and preserves the project’s existing core capability.

**Independent Test**: Search a POI by Vietnamese name/category, inspect its evidence, add it to a day, open the map offline, obtain a route when online, and play/pause the vehicle simulation.

**Acceptance Scenarios**:

1. **Given** a traveler searches by name, address, or category, **When** matches exist, **Then** verified results appear first and uncertain data is visibly labeled.
2. **Given** a POI detail, **When** it is opened, **Then** the traveler sees location, category, opening information, expected price, verification status, source/version, and relevant constraints.
3. **Given** local map data is available but routing is offline, **When** the map opens, **Then** the map and stops still render while route unavailability is distinguished from map failure.
4. **Given** a real route succeeds, **When** it renders, **Then** it is labeled as a real route and route playback can start, pause, resume, and reset.
5. **Given** only an interpolated fallback can be shown, **When** it renders, **Then** it is clearly labeled as not being a real road route.
6. **Given** geolocation is denied or unavailable, **When** locate is requested, **Then** the product explains the state without breaking trip or map use.

---

### User Story 6 - Manage Budget and Expenses (Priority: P1)

A traveler sets a trip budget, records and corrects expenses, sees remaining budget and category summaries, and exports expense history.

**Why this priority**: Expense management is a primary requested capability and must work independently of AI planning.

**Independent Test**: Set a budget, add expenses in four categories across two days, edit and remove entries, trigger threshold warnings, sign out/in, and export the same totals.

**Acceptance Scenarios**:

1. **Given** an active trip, **When** a valid expense is added, **Then** it persists with amount, currency, category, label, time, optional note, and creator.
2. **Given** an existing expense, **When** it is edited or deleted, **Then** totals update and an audit trail records the change.
3. **Given** spending crosses configured warning thresholds, **When** the summary is viewed, **Then** an understandable 80% or 100% warning appears without preventing legitimate entries.
4. **Given** multiple trip days, **When** the traveler filters by day or category, **Then** list and summary totals remain mathematically consistent.
5. **Given** a traveler requests export, **When** export completes, **Then** the file contains the same entries and totals visible in the product.

---

### User Story 7 - Continue Safely Through Connectivity Changes (Priority: P2)

A traveler can reopen the most recent synchronized trip when offline, understand data freshness, queue safe edits, and resolve conflicts after reconnection.

**Why this priority**: Mobile travel conditions are unreliable; silent data loss or fake server success is unacceptable.

**Independent Test**: Load a trip online, disconnect, reopen it, make permitted offline edits, reconnect, and resolve a server conflict without losing either version.

**Acceptance Scenarios**:

1. **Given** synchronized data exists, **When** the app starts offline, **Then** the last valid trip is shown with an offline label and synchronization timestamp.
2. **Given** no synchronized data exists, **When** the app starts offline, **Then** an explicit seeded demo or empty state appears and no fake server identifier is created.
3. **Given** an offline edit is safe to queue, **When** connectivity returns, **Then** the edit synchronizes once and status changes are visible.
4. **Given** local and server versions conflict, **When** synchronization resumes, **Then** the traveler can compare and choose a resolution without silent overwrite.
5. **Given** planning requires the server, **When** offline, **Then** existing plans remain readable but new planning is clearly unavailable.

---

### User Story 8 - Replan During the Trip (Priority: P2)

A traveler marks progress, skips a stop, reports a delay or budget change, and receives a feasible revised remainder while completed history stays fixed.

**Why this priority**: A useful trip manager must adapt during execution, not only before departure.

**Independent Test**: Start a route, complete the first stop, skip the second, reduce the remaining budget, and generate a revised schedule that preserves completed activities.

**Acceptance Scenarios**:

1. **Given** an active itinerary, **When** a stop is completed or skipped, **Then** progress is recorded and completed history cannot be reordered by later replanning.
2. **Given** a delay, closure, weather warning, or budget change, **When** replanning is requested, **Then** only the remaining schedule changes and the new version passes all hard gates.
3. **Given** no feasible remainder exists, **When** replanning finishes, **Then** the product explains which constraints conflict and offers manual adjustment.

---

### User Story 9 - Curate Data and Operate the Product (Priority: P2)

An authorized operator manages POIs, publishes versioned catalog updates, reviews data quality, manages account status, and monitors readiness without seeing unnecessary private content.

**Why this priority**: Reliable plans depend on controlled data and supportable operations.

**Independent Test**: Create a draft POI change, verify required evidence, publish a new version, observe affected planning metadata, suspend a test account, and inspect the audit log.

**Acceptance Scenarios**:

1. **Given** a curator proposes a POI, **When** required evidence is incomplete, **Then** the POI cannot enter selectable itineraries.
2. **Given** a reviewed catalog change, **When** an administrator publishes it, **Then** a new immutable data version is created and existing accepted plans retain their prior version.
3. **Given** an account violates policy, **When** an administrator suspends it with a reason, **Then** new sessions are blocked and the action is audited.
4. **Given** an operator views readiness, **When** evidence thresholds are unmet, **Then** learned or AI-assisted promotion remains disabled.
5. **Given** a support investigation, **When** logs are viewed, **Then** only necessary metadata is shown and secrets/credentials are never present.

---

### User Story 10 - Add AI Later Without Rebuilding Management (Priority: P3)

The product can later add natural-language parsing, explanation, and non-authoritative ranking while accounts, trips, expenses, POIs, itinerary versions, and acceptance evidence remain stable.

**Why this priority**: The management foundation must not be coupled to one model or require a data migration when AI is introduced.

**Independent Test**: Replace an AI adapter with unavailable, local, and hosted test implementations and verify core CRUD, manual planning, deterministic feasibility, and persisted records behave identically.

**Acceptance Scenarios**:

1. **Given** AI is disabled or unavailable, **When** travelers manage trips and request deterministic planning, **Then** the core product remains usable.
2. **Given** AI proposes a parse, explanation, or preference, **When** it conflicts with user data or hard constraints, **Then** authoritative user data and deterministic checks win.
3. **Given** a shadow ranking experiment, **When** results are recorded, **Then** they cannot silently reorder or approve an itinerary before promotion criteria are explicitly met.
4. **Given** a future AI provider changes, **When** the provider is replaced, **Then** stored management records and public product behavior remain compatible.

### Edge Cases

- Duplicate registration, unverified email, expired recovery token, revoked session, and concurrent sign-in attempts.
- A traveler changes email while a recovery request is pending.
- A trip crosses midnight, includes a leap day, or changes timezone while Da Nang local time remains authoritative for activities.
- Start date is after end date, duration exceeds supported scope, traveler count is zero, or budget is negative.
- A POI closes permanently or changes hours after an itinerary was accepted.
- A must-visit POI conflicts with allergy, accessibility, opening hours, movement, or budget constraints.
- The catalog has insufficient verified POIs to produce distinct alternatives.
- Route provider returns an invalid geometry, times out, rate-limits, or disagrees with the local matrix.
- PMTiles loads while CDN fonts/icons fail; map content must remain understandable.
- Geolocation is denied, unsupported, inaccurate, or outside Da Nang.
- Two devices edit the same trip or expense while one is offline.
- A request is retried after timeout and must not duplicate a trip, expense, selection, or replan.
- Currency values exceed normal limits, include decimals, or are entered with Vietnamese separators.
- Deleting an expense after export must not alter the already generated export artifact.
- A suspended or deleted account still has cached data on a device.
- An admin loses permission during a catalog publish operation.
- A published data version fails validation and must not replace the last good version.
- The system restarts during a write, migration, import, export, or synchronization.
- Seeded demo data resembles real data and must remain visibly labeled and isolated.
- AI output is malformed, slow, unavailable, adversarial, or attempts to override system policy.

## Requirements *(mandatory)*

### Functional Requirements

#### Identity, Access, and Privacy

- **FR-001**: The system MUST allow a guest to register with a unique email address and compliant password.
- **FR-002**: The system MUST verify ownership of the registration address before enabling recovery-sensitive account actions.
- **FR-003**: The system MUST allow sign-in, sign-out, sign-out-all-sessions, and password recovery without revealing whether an unrelated account exists.
- **FR-004**: The system MUST isolate every traveler’s private profile, trips, itineraries, expenses, exports, and cached synchronization metadata.
- **FR-005**: The system MUST enforce traveler, administrator, and data-curator permissions on every protected action.
- **FR-006**: The system MUST record security-relevant actions including sign-in failures, password changes, session revocation, suspension, export, and deletion requests.
- **FR-007**: The system MUST allow a traveler to export personal product data in a readable, portable form.
- **FR-008**: The system MUST allow account deletion with immediate access revocation, a documented recovery window, and final purge or anonymization.
- **FR-009**: Secrets, passwords, recovery tokens, and session credentials MUST never appear in product logs, exports, URLs, or ordinary API responses.
- **FR-010**: Privileged operators MUST NOT gain unrestricted access to traveler content merely by holding a catalog-curation role.

#### Traveler Profile and Preferences

- **FR-011**: The system MUST maintain one current traveler profile per account and preserve the change time.
- **FR-012**: The profile MUST support party type, trip purpose, pace, fitness, spending style, food preferences, activities, usual transport, must-avoid items, allergies, and accessibility needs.
- **FR-013**: The product MUST distinguish hard constraints from soft preferences in both editing and planning explanations.
- **FR-014**: A traveler MUST be able to review, edit, clear, and reset profile values.
- **FR-015**: A trip MAY override soft profile preferences without mutating the global profile.
- **FR-016**: A trip override MUST NOT silently weaken an allergy, safety, or accessibility constraint.
- **FR-017**: Profile changes MUST affect future planning requests but MUST NOT rewrite historical accepted plans.
- **FR-018**: The product MUST explain which profile and trip values are active before planning.

#### Trip and Activity Management

- **FR-019**: A traveler MUST be able to create, read, update, archive, restore, soft-delete, and permanently purge owned trips according to the deletion lifecycle.
- **FR-020**: A trip MUST include title, Da Nang destination, start/end dates, traveler count, status, budget, currency, preferred transport, daily time bounds, notes, and ownership metadata.
- **FR-021**: The system MUST validate trip dates, supported duration, traveler count, monetary bounds, and daily time windows before saving.
- **FR-022**: A traveler MUST be able to designate one active trip and switch active trips without data leakage or duplication.
- **FR-023**: A trip MUST contain ordered days and ordered activities within each day.
- **FR-024**: A traveler MUST be able to add, edit, reorder, complete, skip, and remove a manual activity.
- **FR-025**: An activity MUST support a POI reference or a clearly labeled custom activity, time bounds, duration, cost estimate, status, and notes.
- **FR-026**: Schedule edits MUST surface overlaps, out-of-day placement, closed POIs, impossible travel, and budget conflicts before being treated as valid.
- **FR-027**: A change that invalidates an accepted plan MUST preserve that plan and mark the active trip as needing review or replanning.
- **FR-028**: Trip lists MUST support active, upcoming, completed, archived, and deleted states with search and deterministic sorting.
- **FR-029**: Writes MUST be idempotent where network retries can otherwise create duplicate trips or activities.
- **FR-030**: Trip and activity records MUST survive application restarts, backend restarts, and deployment restarts.

#### Itinerary Planning and Versioning

- **FR-031**: Planning MUST use the traveler’s owned trip, active constraints, and a named/versioned data snapshot.
- **FR-032**: Every selectable itinerary MUST pass deterministic entity, temporal, financial, movement, and traveler-constraint gates.
- **FR-033**: The system MUST return up to five genuinely distinct feasible alternatives and MUST never pad a result with a known duplicate or infeasible option.
- **FR-034**: When fewer alternatives are available, the response MUST state target, returned count, and a user-understandable shortage reason.
- **FR-035**: Every alternative MUST include schedule, POIs, expected cost, movement summary, warnings, assumptions, hard-gate evidence, and data version.
- **FR-036**: A traveler MUST be able to compare alternatives and select exactly one current accepted version.
- **FR-037**: Selection MUST be idempotent and MUST persist an immutable acceptance record before reporting success.
- **FR-038**: Acceptance history MUST include the request context, full plan snapshot, gate evidence, timestamp, data version, deterministic rank/score, and parent version when applicable.
- **FR-039**: Unknown, stale, unauthorized, or gate-failing plans MUST NOT become accepted plans.
- **FR-040**: A traveler MUST be able to activate an older accepted version only through an explicit new state transition; historical records remain immutable.
- **FR-041**: Replanning MUST preserve completed activities and link the new version to the prior accepted version.
- **FR-042**: Replanning MUST accept remaining time, actual spend, completed/skipped stops, newly unavailable POIs, and changed constraints.
- **FR-043**: Planning and replanning failure MUST return actionable reason categories without exposing internal secrets or fabricated facts.
- **FR-044**: Manual trip management MUST remain usable when automated planning is disabled.
- **FR-045**: Deterministic feasibility MUST remain authoritative when any later quality ranker or AI component is present.
- **FR-046**: Accepted-plan evidence MUST be queryable by the owning traveler and appropriately summarized for administrators.
- **FR-047**: The product MUST distinguish deterministic, seeded-demo, cached, stale, and AI-assisted metadata in user-visible language.

#### POI Catalog, Search, Map, and Routing

- **FR-048**: The system MUST maintain a versioned Da Nang POI catalog with stable identifiers and provenance.
- **FR-049**: POIs MUST support name, aliases, category, coordinates, address, opening information, price evidence, duration estimate, accessibility, dietary/safety tags, verification state, and source timestamps.
- **FR-050**: Only POIs meeting the published verification policy MAY enter a selectable itinerary.
- **FR-051**: Guests and travelers MUST be able to search and filter POIs by Vietnamese text, category, price, accessibility, dietary needs, and open-time relevance.
- **FR-052**: Search results MUST distinguish verified, incomplete, uncertain, and unavailable records.
- **FR-053**: A traveler MUST be able to add a POI to a trip from search, detail, itinerary, or map context.
- **FR-054**: The local Da Nang map MUST render without a paid provider key and MUST show trip stops in order.
- **FR-055**: The product MUST distinguish local map availability from online route and geolocation availability.
- **FR-056**: A route MUST be labeled as real-provider, local-matrix, fallback, or unavailable.
- **FR-057**: An interpolated line MUST explicitly state that it is not a real road route.
- **FR-058**: Route playback MUST support start, pause, resume, reset, and route-change cancellation.
- **FR-059**: Geolocation MUST be permission-aware and failure MUST NOT block map or trip access.
- **FR-060**: Route/search provider failure MUST degrade to documented fallbacks without presenting fallback data as provider truth.

#### Budgets and Expenses

- **FR-061**: A trip MUST have one currency and a non-negative budget that can be revised with change history.
- **FR-062**: A traveler MUST be able to create, read, edit, and delete an expense owned by a trip.
- **FR-063**: An expense MUST include stable identifier, trip, amount, currency, category, label, occurrence time, creation/update time, creator, and optional note.
- **FR-064**: Supported MVP categories MUST include food, ticket, transport, accommodation, shopping, and other.
- **FR-065**: The product MUST provide trip total, remaining budget, daily total, category total, average expense, and entry count.
- **FR-066**: Summary totals MUST be derived from authoritative entries and remain consistent across list, dashboard, export, and planning context.
- **FR-067**: The product MUST warn at configurable budget thresholds including 80% and 100%.
- **FR-068**: Budget warnings MUST NOT prevent recording a legitimate over-budget expense.
- **FR-069**: Expense writes MUST be idempotent under retry and MUST reject invalid currency, negative amount, unauthorized trip, or malformed time.
- **FR-070**: Expense edits and deletions MUST be auditable without silently altering previously accepted-plan evidence.
- **FR-071**: A traveler MUST be able to filter expenses by day/category and export entries with matching totals.
- **FR-072**: Actual remaining budget MUST be available to replanning without making expense records dependent on an AI component.

#### Offline, Synchronization, and Demo Honesty

- **FR-073**: The product MUST expose online, offline, synchronizing, stale, conflict, seeded-demo, and failed states where relevant.
- **FR-074**: The most recent successfully synchronized trip and itinerary MUST remain readable offline with a visible freshness timestamp.
- **FR-075**: Seeded demo data MUST be isolated, resettable, and visibly labeled on every screen where it can be mistaken for persisted user data.
- **FR-076**: Seeded or offline-only selection MUST NOT create a fake server acceptance identifier.
- **FR-077**: Safe offline edits MAY be queued with stable idempotency identifiers and MUST synchronize at most once.
- **FR-078**: Conflicting versions MUST NOT be silently overwritten; the traveler MUST receive a conflict resolution choice.
- **FR-079**: Server-required features MUST fail with actionable offline messaging while unrelated local reading remains available.
- **FR-080**: Synchronization metadata MUST not expose another traveler’s identifiers or private content.

#### Administration, Data Quality, and Audit

- **FR-081**: Administrators MUST be able to list and filter accounts by status without viewing passwords or credentials.
- **FR-082**: Administrators MUST be able to suspend and reactivate an account with reason, actor, and timestamp.
- **FR-083**: Data curators MUST be able to create draft POIs, edit draft evidence, submit for review, and see validation failures.
- **FR-084**: Only an authorized reviewer MAY verify a POI or publish a catalog version.
- **FR-085**: Publishing MUST produce an immutable catalog version and MUST NOT rewrite the data version of historical accepted plans.
- **FR-086**: A failed catalog validation MUST leave the last good version active.
- **FR-087**: Administrators MUST be able to inspect planning readiness counts and explicit promotion gates.
- **FR-088**: Learned ranking, accepted-day retrieval, or AI promotion MUST remain disabled until its published threshold and review criteria are satisfied.
- **FR-089**: Administrative actions and material data changes MUST create append-only audit events.
- **FR-090**: Audit access MUST be permission-controlled, searchable, and limited to necessary metadata.
- **FR-091**: The system MUST provide health, dependency, data-version, and migration-readiness status without exposing secrets.
- **FR-092**: A safe demo reset MUST affect only designated demo data and MUST never erase real traveler records.

#### Durable Data and Lifecycle

- **FR-093**: Accounts, profiles, trips, days, activities, itinerary versions, acceptances, budgets, expenses, POIs, catalog versions, sessions, and audit events MUST use a shared authoritative data store.
- **FR-094**: Device-local, seeded, file-only, or in-memory data MUST NOT be the authoritative store for signed-in production records.
- **FR-095**: Authoritative writes MUST be atomic so an interrupted operation cannot produce a partially accepted plan, partial expense, or inconsistent trip order.
- **FR-096**: Referential integrity MUST prevent orphaned activities, expenses, accepted plans, and catalog references.
- **FR-097**: Data model changes MUST be versioned, reviewable, repeatable, and safe for existing records.
- **FR-098**: The product MUST provide a documented backup, restore, and demo-seed procedure.
- **FR-099**: Restarting or redeploying the backend MUST NOT erase authoritative user or catalog data.
- **FR-100**: The same authorized traveler MUST see consistent persisted records across supported devices after synchronization.
- **FR-101**: Retention and deletion rules MUST distinguish active, soft-deleted, exported, audit-required, anonymized, and purged data.
- **FR-102**: Runtime data, database credentials, exports, caches, and backups MUST not be committed to source control.

#### AI Extension Boundaries

- **FR-103**: Core identity, management, expense, catalog, map, manual itinerary, feasibility, and persistence flows MUST operate without AI.
- **FR-104**: Future AI integrations MUST use explicit, replaceable capabilities for parsing, explanation, shadow comparison, or non-authoritative recommendation.
- **FR-105**: AI output MUST be treated as untrusted input and validated before it changes authoritative records.
- **FR-106**: AI MUST NOT generate or approve a route that bypasses deterministic feasibility gates.
- **FR-107**: AI unavailability, timeout, malformed output, or provider change MUST NOT corrupt or block core management data.
- **FR-108**: AI experiments MUST record provider/model/version, latency, status, and non-authoritative result without storing secrets.
- **FR-109**: Shadow experiments MUST not reorder user-visible alternatives until explicit promotion criteria and review are complete.
- **FR-110**: Adding or replacing an AI provider MUST NOT require destructive migration of accounts, trips, expenses, POIs, itineraries, or acceptance history.

### Key Entities

- **User Account**: Identity, verification state, account status, privacy lifecycle, and ownership root.
- **Session**: Authorized access instance with issue, expiry, revocation, and device metadata.
- **Role Assignment**: Traveler, administrator, or data-curator permission attached to an account.
- **Traveler Profile**: Current reusable preferences, constraints, accessibility needs, and change time.
- **Trip**: User-owned Da Nang journey with dates, travelers, status, budget, settings, and current versions.
- **Trip Preference Override**: Trip-scoped changes to soft profile values.
- **Trip Day**: Ordered date container within a trip.
- **Activity**: Ordered POI or custom stop with schedule, cost, notes, and progress state.
- **POI**: Stable catalog place with location, evidence, constraints, verification, and provenance.
- **POI Evidence**: Source-specific opening, price, category, accessibility, or safety observation.
- **Catalog Version**: Immutable published set of planning-authoritative POI data.
- **Route Evidence**: Provider/local/fallback route metadata associated with a plan or preview.
- **Itinerary Request**: Normalized trip and traveler constraints used for one planning attempt.
- **Itinerary Alternative**: Complete candidate plan with gate evidence, score, assumptions, and data version.
- **Itinerary Version**: Immutable plan snapshot linked to a trip and optional parent version.
- **Acceptance Record**: Idempotent user decision selecting one feasible itinerary version.
- **Budget Revision**: Historical change to a trip budget.
- **Expense**: User-owned monetary entry assigned to a trip, day, and category.
- **Expense Audit Event**: Append-only record of expense create/edit/delete.
- **Sync Operation**: Idempotent queued mutation and its synchronization/conflict state.
- **Audit Event**: Append-only security, administration, publication, export, or deletion evidence.
- **Shadow Observation**: Non-authoritative comparison/calibration evidence for a future ranker or judge.
- **Export Job**: User-requested portable snapshot with scope, state, expiry, and checksum.

## Non-Functional Product Requirements

- The product MUST be Vietnamese-first and use Da Nang local time and VND consistently in MVP flows.
- The mobile experience MUST remain usable at a 390×844 viewport without horizontal overflow or inaccessible controls.
- Common management actions MUST acknowledge success or actionable failure within two seconds under normal connectivity.
- Planning MAY take longer but MUST show progress, support retry without duplication, and complete or fail explicitly within the published planning budget.
- Accessibility MUST include readable contrast, text scaling, semantic labels, keyboard traversal on web, and no color-only status communication.
- Private records MUST be encrypted in transit and protected at rest according to the deployment environment’s security baseline.
- Logs MUST use correlation identifiers and structured error categories while excluding credentials and unnecessary private content.
- The product MUST support repeatable demo seeding without mixing demo data with real accounts.
- Operational failures MUST fail closed for authorization and itinerary feasibility, and degrade honestly for optional providers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of first-time testers complete registration and profile onboarding in under five minutes without assistance.
- **SC-002**: At least 95% of testers create a trip, add a manual activity, and reopen the same trip after a new sign-in session without data loss.
- **SC-003**: 100% of signed-in trip, itinerary, and expense records survive backend restart and deployment restart tests.
- **SC-004**: Unauthorized cross-account access succeeds in 0% of automated isolation tests.
- **SC-005**: Duplicate trip, activity, expense, selection, and replan records occur in 0% of defined retry tests.
- **SC-006**: 100% of user-visible selectable itineraries pass all five hard-gate families.
- **SC-007**: When fewer than five distinct feasible plans exist, 100% of responses report the actual count and shortage reason rather than padded results.
- **SC-008**: 100% of accepted plans can be traced to request, complete plan, gate evidence, user, timestamp, and catalog version.
- **SC-009**: Expense list, trip total, daily total, category total, and export agree exactly across all golden accounting fixtures.
- **SC-010**: A traveler can record an expense and see updated remaining budget in under 15 seconds end to end.
- **SC-011**: The Da Nang map and cached stops remain viewable in 100% of offline-map test runs.
- **SC-012**: Route provider, fallback route, and unavailable route are correctly distinguished in 100% of route failure scenarios.
- **SC-013**: Start, pause, resume, reset, and route-change cancellation pass all supported browser/device tests.
- **SC-014**: At least 90% of testers complete profile → trip → plan comparison → selection → map → expense without facilitator intervention.
- **SC-015**: Seeded, offline, stale, synchronized, and conflict states are correctly identified by at least 90% of usability-test participants.
- **SC-016**: No seeded or offline-only action creates a false server acceptance in any automated or manual test.
- **SC-017**: A catalog publication failure leaves the prior good catalog active in 100% of failure-injection tests.
- **SC-018**: Account export contains all documented user-owned record types and account deletion prevents new access immediately.
- **SC-019**: Core management and deterministic planning acceptance tests pass with every AI integration disabled.
- **SC-020**: No committed file or ordinary runtime log contains a live credential, password, recovery token, or private connection secret.
- **SC-021**: Full automated regression, mobile widget, migration, authorization, accounting, and smoke suites pass before release approval.

## Assumptions

- MVP is Vietnamese-first, Da Nang-only, uses VND, and treats Asia/Ho_Chi_Minh as the trip timezone.
- Email/password is the initial account method; social sign-in may be added later without changing record ownership.
- One traveler owns a trip in MVP; shared collaborative ownership is deferred.
- Supported trip duration is 1–14 days and traveler count is 1–20 unless later clarified by product policy.
- A shared production-grade relational system of record replaces demo-only SQLite/in-memory persistence for authoritative data. SQLite may remain only for isolated tests or explicitly labeled offline/demo caches.
- Existing verified POI snapshot, deterministic optimizer, hard-gate registry, PMTiles map, route/search fallbacks, and Flutter mobile shell are reusable inputs, not automatically trusted as production-complete.
- The selected database engine, code-first models, migration tooling, connection configuration, and DBeaver setup will be made explicit in the implementation plan, not hidden as an implementation assumption.
- AI itinerary parsing/ranking/explanation is a later capability. The MVP must establish stable data and service boundaries now but does not depend on AI availability.
- Account deletion uses a 30-day recovery window before final purge except records that must be retained or anonymized for audit/security obligations.
- Booking, payments, receipt OCR, voice, multi-city planning, and public social features remain excluded unless a later specification expands scope.
- External route, geolocation, weather, email, and optional AI providers may fail; core data management must remain consistent and errors must be explicit.

## Dependencies

- Existing Davel Trace deterministic planning and hard-gate behavior.
- A curated and versioned Da Nang POI dataset with route matrix and provenance.
- Existing mobile design system, phone-frame behavior, PMTiles data, and map integration.
- A deliverable email verification/recovery mechanism for non-demo environments.
- An operational shared database environment, backup location, and secret configuration managed outside source control.
- Product decisions and review for privacy policy, terms, retention, and administrator assignment.

## Definition of Product Completion

The feature is complete only when every P1 story works against durable shared data, P2 operations and offline honesty are demonstrated, AI-disabled operation passes, migration/backup/restore procedures are verified, all success criteria have evidence, no runtime secret or database is committed, and a reviewed release PR targets `dev` without direct pushes to protected branches.
