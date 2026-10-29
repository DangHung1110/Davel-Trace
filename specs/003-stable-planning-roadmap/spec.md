# Feature Specification: Stable Planning Roadmap MVP

**Feature Branch**: `003-stable-planning-roadmap`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "Pull and review the latest project and roadmap, complete the frontend and backend that can be demonstrated now, keep the planner stable, and provide a mobile UI runnable on a laptop."

## Scope Decisions

This feature delivers the parts of the stable-planning roadmap that are useful before a large preference dataset exists: a small, explainable feasibility policy; several complete feasible alternatives; shadow ranking with bias measurements; explicit accepted-plan logging; and a laptop-runnable mobile experience. Learned weights and full-day retrieval remain disabled until their evidence thresholds are met.

### In Scope

- Consolidate the planner's blocking decisions into five user-understandable hard-gate families while retaining the detailed reasons needed for diagnosis.
- Return up to five diverse complete alternatives that have passed the hard gates.
- Run a non-authoritative shadow judge over feasible alternatives, including order-swap and length-bias measurements, without allowing the judge to bypass hard gates.
- Allow a user to choose an alternative and persist an immutable acceptance record with the query, complete plan, timestamps, judge observations, and active data version.
- Expose evidence readiness for later learned-ranking and accepted-day retrieval stages.
- Provide a Vietnamese-first mobile UI that runs in a phone-sized frame on a laptop, covers onboarding, alternatives, itinerary, map, expenses, and profile, and remains demonstrable when the planner API is unavailable.
- Preserve the existing local Da Nang map, search/routing prototype, and expense capabilities.

### Out of Scope

- Promoting learned preference weights before at least 150 pairwise judgments and the documented quality gates are met.
- Training from full itineraries before at least 40 accepted complete days exist.
- Retrieving accepted-day skeletons before at least 50 accepted complete days exist.
- Letting an LLM create a route, alter feasibility, or silently replace deterministic scores.
- Multi-city planning, payment, booking, receipt OCR, voice, or production authentication.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive Safe, Distinct Alternatives (Priority: P1)

A traveler submits a Da Nang trip request and receives several complete, meaningfully different alternatives. Every displayed alternative has already passed the same compact hard-feasibility policy, and any shortage is explained instead of padded with invalid plans.

**Why this priority**: The planner is only trustworthy if infeasible plans cannot reach the user and the available choices are genuinely distinct.

**Independent Test**: Submit a deterministic fixture with enough valid POIs and confirm that the response contains no more than five distinct complete alternatives, each with a passed hard-gate summary and traceable detailed evidence.

**Acceptance Scenarios**:

1. **Given** enough verified Da Nang POIs and a feasible trip request, **When** planning completes, **Then** the traveler receives between two and five complete alternatives ordered by the deterministic baseline.
2. **Given** an alternative that violates time, cost, movement, safety/opening, or explicit traveler constraints, **When** candidates are filtered, **Then** that alternative is not shown as selectable.
3. **Given** fewer than five feasible distinct alternatives, **When** planning completes, **Then** only the feasible alternatives are returned and the response states why the target count was not reached.
4. **Given** a valid shadow-judge result, **When** alternatives are returned, **Then** the deterministic order remains authoritative and the shadow recommendation is visibly labeled as experimental.

---

### User Story 2 - Choose and Record an Accepted Plan (Priority: P1)

A traveler selects one feasible alternative as the active itinerary. The system records exactly what the user accepted and the evidence available at that moment so the decision can later support evaluation or learning.

**Why this priority**: The project cannot responsibly learn preferences or retrieve prior day structures without high-quality accepted-plan data.

**Independent Test**: Select a registered feasible alternative, retrieve its acceptance record by identifier, and confirm it contains the original request, immutable plan snapshot, data version, timestamps, gate report, deterministic rank, and optional shadow observations.

**Acceptance Scenarios**:

1. **Given** a registered feasible alternative, **When** the traveler chooses it, **Then** it becomes active and one acceptance record is persisted.
2. **Given** the same selection request is retried with the same idempotency key, **When** it is processed again, **Then** the original acceptance record is returned without creating a duplicate.
3. **Given** an unknown or now-infeasible alternative, **When** selection is attempted, **Then** no acceptance record is written and a clear error is returned.
4. **Given** a prior acceptance record, **When** the active plan is later repaired or replanned, **Then** the prior record remains unchanged and a later selection creates a new linked record.

---

### User Story 3 - Measure a Shadow Judge Without Letting It Control Feasibility (Priority: P2)

A developer or reviewer can inspect how an experimental judge compares complete feasible alternatives, including whether reversing their order changes the result and whether plan length correlates with rank.

**Why this priority**: Ranking can only be promoted after it is shown to be stable and free of obvious position, verbosity, and naming bias.

**Independent Test**: Evaluate a fixed candidate set in normal and reversed order and confirm the stored observation reports both orders, swap consistency, length correlation where measurable, judge availability, and no authoritative reorder.

**Acceptance Scenarios**:

1. **Given** two or more feasible alternatives, **When** shadow evaluation is enabled, **Then** the judge evaluates anonymized facts in both forward and reversed order.
2. **Given** the two orders disagree, **When** the observation is summarized, **Then** the pair is recorded as a tie or inconsistent result rather than a win.
3. **Given** the judge is unavailable, malformed, or times out, **When** planning completes, **Then** feasible alternatives are still returned in deterministic order with an unavailable status.
4. **Given** enough observations, **When** readiness is requested, **Then** the system reports sample count, top-choice agreement, swap consistency, veto regression, length correlation, and whether each promotion threshold is met.

---

### User Story 4 - Demo the Mobile Experience on a Laptop (Priority: P2)

A presenter can launch the app in a browser on a laptop and see it in a realistic phone frame. They can move among the primary screens, inspect seeded itinerary content and the Da Nang map, add expenses, and try live planning when the backend is running.

**Why this priority**: The project needs a coherent end-to-end demo now even though later AI learning stages are intentionally deferred.

**Independent Test**: Start the backend and Flutter web app, open the supplied laptop URL, and complete onboarding → alternatives → itinerary → map → expenses → profile using a 390×844 phone-sized frame.

**Acceptance Scenarios**:

1. **Given** a desktop viewport, **When** the mobile app opens, **Then** the app is centered in a phone-sized frame and all controls remain reachable without horizontal overflow.
2. **Given** the backend is available, **When** the presenter requests a plan and chooses an alternative, **Then** the mobile UI reflects the active plan and acceptance status.
3. **Given** the backend is unavailable, **When** the app opens, **Then** seeded demo data remains navigable and the UI clearly labels offline/demo state without inventing a successful server action.
4. **Given** an itinerary stop, **When** the presenter opens the map, **Then** the existing local Da Nang map data is used and route-related controls remain available.

### Edge Cases

- A request yields zero feasible complete alternatives.
- The planner finds duplicates with different identifiers but the same ordered POI set.
- A selected plan disappears from the in-memory planning cache before persistence.
- The acceptance store is temporarily unavailable or contains an older schema version.
- A shadow judge returns an unknown candidate, extra prose, a partial order, or inconsistent results across order swaps.
- There are too few observations to compute a correlation or promotion metric.
- Browser storage contains older mobile-demo data.
- The API base URL is different on desktop web, Android emulator, and a physical device.
- The map is available locally while routing or geolocation is unavailable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST evaluate every selectable itinerary against five hard-gate families: temporal feasibility, financial feasibility, movement feasibility, safety/opening/data validity, and explicit traveler constraints.
- **FR-002**: Every hard-gate family result MUST retain references to its detailed checks so existing diagnostic and evaluation evidence is not lost by consolidation.
- **FR-003**: The system MUST NOT expose a hard-gate-failing itinerary as selectable, even when a shadow judge prefers it.
- **FR-004**: For a feasible request, the system MUST attempt to produce five diverse complete alternatives and MUST return only the feasible distinct alternatives actually found.
- **FR-005**: Each alternative MUST include an identifier, complete activities, deterministic score/rank, diversity evidence, hard-gate summary, data version, and a user-readable explanation.
- **FR-006**: The system MUST state why fewer than five alternatives were returned, distinguishing insufficient feasible supply, duplicate removal, time budget exhaustion, and planner failure.
- **FR-007**: Shadow evaluation MUST operate only on alternatives that passed all hard gates and MUST be labeled non-authoritative.
- **FR-008**: Shadow evaluation MUST anonymize candidate identity for the first comparison pass, evaluate at least forward and reversed presentation orders, and store both raw decisions.
- **FR-009**: A pair MUST count as a judge win only when both presentation orders agree; otherwise it MUST be recorded as a tie/inconsistent result.
- **FR-010**: Shadow evaluation failure MUST NOT prevent deterministic planning, selection, or mobile demo operation.
- **FR-011**: The system MUST report readiness metrics for judge promotion: sample count, deterministic top-choice agreement, swap consistency, veto regression, length/rank correlation, and canary rate.
- **FR-012**: The system MUST keep shadow judging below a configurable 10% canary rate by default and MUST NOT promote it automatically.
- **FR-013**: A user MUST be able to select a registered feasible alternative and make it the active itinerary.
- **FR-014**: Selection MUST persist an immutable acceptance record containing the normalized request, full accepted plan snapshot, selection timestamp, data version, hard-gate evidence, deterministic rank/score, shadow observation reference if present, and a schema version.
- **FR-015**: Acceptance writes MUST support an idempotency key so retries do not duplicate a user decision.
- **FR-016**: A later repair, replan, or reselection MUST create a new linked record rather than mutating an earlier acceptance record.
- **FR-017**: Acceptance records MUST be queryable for demo/audit without exposing secrets or unverified POIs as facts.
- **FR-018**: The system MUST report data-readiness counts separately for pairwise judgments, accepted complete days, and retrieval-ready accepted days.
- **FR-019**: Learned pairwise weights MUST remain disabled until at least 150 judgments exist, held-out accuracy is at least 70%, and mismatch is below 25%.
- **FR-020**: Full-itinerary learning MUST remain disabled until at least 40 accepted complete days exist.
- **FR-021**: Accepted-day retrieval MUST remain disabled until at least 50 retrieval-ready complete days exist; the readiness report MUST show progress toward the preferred 200-day library.
- **FR-022**: The mobile UI MUST provide connected flows for onboarding/profile, planning request, alternative comparison, active itinerary, map, expenses, and profile management.
- **FR-023**: On desktop viewports the mobile UI MUST be presented in a centered 390×844 logical phone frame; on mobile viewports it MUST fill the available screen without horizontal overflow.
- **FR-024**: The mobile UI MUST preserve the existing Da Nang map data and route/location capabilities and MUST distinguish local-map availability from online routing or geolocation availability.
- **FR-025**: The mobile UI MUST provide seeded fallback data and an explicit demo/offline indicator when the backend is unavailable; offline actions MUST NOT be presented as persisted server actions.
- **FR-026**: The project MUST provide copy-paste commands for installing existing declared dependencies, starting the backend, starting the mobile web demo, and running backend/frontend validation.
- **FR-027**: Existing root map, search A/B, route drawing, and vehicle play/pause behaviors MUST remain operational.
- **FR-028**: No API key or secret MAY be committed; remote providers MUST use environment configuration and local/demo fallbacks.

### Key Entities

- **Plan Alternative**: A complete feasible day option with activities, deterministic evidence, diversity metadata, data version, and optional non-authoritative shadow observation.
- **Hard Gate Report**: Five family outcomes with references to detailed deterministic checks and user-readable failure reasons.
- **Acceptance Record**: An immutable snapshot of a user's plan choice and all request, plan, timing, version, ranking, and evidence fields required for audit and future learning.
- **Shadow Observation**: A non-authoritative record of anonymized forward/reverse judge comparisons, consistency, validity, latency, and optional bias metrics.
- **Readiness Snapshot**: Counts and threshold results that gate learned pairwise ranking, full-itinerary learning, judge promotion, and accepted-day retrieval.
- **Demo Session**: Local mobile state that identifies live versus seeded data, current profile/request, alternatives, active itinerary, expenses, and last data timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of alternatives returned by the planning endpoint pass all five hard-gate families on the same request and data version.
- **SC-002**: On a fixture with at least five distinct feasible solutions, the planner returns five complete alternatives with no duplicate ordered POI set.
- **SC-003**: Repeating a selection with the same idempotency key creates exactly one acceptance record and returns the same record identifier.
- **SC-004**: The complete backend automated suite passes, including regression coverage for root map-related backend contracts and the new planning/acceptance/shadow behavior.
- **SC-005**: A presenter can complete the full laptop mobile demo flow in under five minutes without editing source code or browser storage.
- **SC-006**: The mobile UI has zero horizontal overflow at 390×844 and at a common desktop viewport of 1440×900.
- **SC-007**: When the judge is disabled or unavailable, planning and selection still complete using deterministic behavior and produce an explicit shadow status.
- **SC-008**: The readiness endpoint reports learned ranking and accepted-day retrieval as disabled when evidence counts are below their required thresholds.
- **SC-009**: The root local server still serves the map with byte-range support and the existing search, route, and play/pause smoke flow remains demonstrable.
- **SC-010**: No committed file contains a live API key, password, token, or private connection string.

## Assumptions

- The current Da Nang POI snapshot and route matrix remain the authoritative local planning inputs.
- Existing detailed checks remain valuable diagnostic evidence even after they are grouped into five user-facing hard-gate families.
- SQLite is acceptable for local demo persistence and later export, but the specification does not require a production database migration.
- The Flutter web target is the primary laptop demo target; Android/iOS project files may remain present for later device demos.
- A local seeded demo is acceptable when external routing, geolocation, Ollama, or hosted APIs are unavailable, provided the UI labels the state honestly.
- Current expense management behavior is retained and connected into the mobile shell rather than redesigned as a learned-planning feature.

## Dependencies

- Existing deterministic optimizer, detailed gate registry, Da Nang snapshot, expense API, local PMTiles map, and route/search prototype.
- Existing planner test harness and onboarding catalog as a reference for request fields and review evidence.
- A local Flutter SDK and browser for the laptop mobile demo.
