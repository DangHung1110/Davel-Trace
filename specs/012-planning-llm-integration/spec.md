# Feature Specification: Stable Planner and Configurable LLM Integration

**Feature Branch**: `task/012-planning-llm-integration`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Replace the former Increment 012 administration work with integration of the stable planning algorithms from `feat/stable-p1-p4`, and support a configurable external LLM, initially expected to be a free-tier Gemini model."

## Scope Decisions

This increment connects the proven stable-planning capability to the durable product platform delivered through Increment 011. The source branch is treated as a capability and evidence source, not as a branch that can replace the current product tree wholesale. Planner behavior, verified data, route-matrix assets, regression fixtures, and measurable quality evidence are carried forward behind the current product contracts while account ownership, persisted trips, itinerary versions, acceptance history, expenses, and offline behavior remain intact.

The deterministic planner remains authoritative. A hosted LLM may help interpret Vietnamese natural-language requests, produce evidence-grounded explanations, and run non-authoritative shadow comparisons. The initial deployment candidate is a Gemini free-tier model, but no product record or workflow is coupled to one provider or model name.

### In Scope

- Integrate the stable Da Nang planner, its verified POI snapshot, route matrix, weather-aware scheduling behavior, profile preferences, multi-option generation, and replanning rules into the current planning lifecycle.
- Preserve the current durable request, alternative, selection, versioning, acceptance, authorization, and offline-read contracts.
- Let a traveler submit either structured trip fields or Vietnamese natural language, review the normalized interpretation, and correct it before planning.
- Configure an external LLM provider without committing credentials or requiring a data migration when provider, endpoint, or model changes.
- Use LLM output only as an untrusted proposal for parsing, grounded explanation, or shadow comparison.
- Keep deterministic planning usable when the LLM is disabled, unavailable, rate-limited, malformed, or out of free-tier quota.
- Revalidate the imported planner against its original regression evidence and the current product regression suites.
- Support automated planning for one- and two-day Da Nang requests in this increment while preserving manual management for longer trips.

### Out of Scope

- Directly merging the entire historical source branch over the current product tree.
- Allowing an LLM to invent POIs, opening hours, prices, travel times, routes, or accepted itinerary records.
- Letting an LLM bypass deterministic entity, schedule, movement, budget, safety, accessibility, or opening-hour gates.
- Automatically promoting shadow ranking into the user-visible order.
- Training or fine-tuning a foundation model.
- Guaranteeing the continued availability, price, quota, or privacy terms of a particular free-tier provider.
- Administration, account suspension, catalog-authoring UI, backup/restore operations, and audit-console work formerly planned as `012-admin-data-ops`; that capability is deferred to a later increment.
- Automated planning beyond two days, multi-city planning, booking, payment, receipt OCR, or voice interaction.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plan From Durable Trip Data (Priority: P1)

A signed-in traveler requests a plan for an owned Da Nang trip and receives distinct, feasible alternatives produced from the stable planner while the current product retains ownership, versioning, and acceptance evidence.

**Why this priority**: The scheduling algorithm only becomes product value when it operates through durable trips and accepted-plan history rather than a separate demonstration API.

**Independent Test**: Create an owned one- or two-day trip with profile preferences, request planning, select one alternative, restart the backend, and verify the selected immutable version and its data evidence remain readable.

**Acceptance Scenarios**:

1. **Given** a valid owned trip and a compatible verified data version, **When** planning is requested, **Then** every displayed alternative passes all deterministic gates and is stored through the current itinerary lifecycle.
2. **Given** the planner finds fewer than the target number of distinct feasible alternatives, **When** results are returned, **Then** only valid alternatives appear and the shortage reason is explicit.
3. **Given** a traveler selects an alternative, **When** the request is retried, **Then** exactly one immutable acceptance record exists and prior accepted versions remain unchanged.
4. **Given** a trip longer than two days, **When** automated planning is requested in this increment, **Then** the product explains the supported planning window and keeps manual trip management available.

---

### User Story 2 - Review an AI-Assisted Request Interpretation (Priority: P1)

A traveler writes a Vietnamese request in natural language, sees the proposed dates, time bounds, budget, party, preferences, hard constraints, and assumptions, then confirms or corrects them before any plan is generated.

**Why this priority**: Natural-language convenience is useful only when the traveler remains in control and model guesses cannot silently become authoritative constraints.

**Independent Test**: Submit a fixture containing a must-visit place, soft food preference, budget, and accessibility constraint; inspect the proposal, correct one value, and confirm the corrected structured request is the one sent to planning.

**Acceptance Scenarios**:

1. **Given** a valid natural-language request, **When** interpretation succeeds, **Then** the traveler sees a structured proposal that distinguishes hard constraints, soft preferences, assumptions, and missing fields.
2. **Given** an incorrect or incomplete proposal, **When** the traveler edits it, **Then** only the confirmed values become the planning request.
3. **Given** the model names an unknown place or unsupported value, **When** the proposal is validated, **Then** the value is rejected or marked unresolved rather than converted into catalog truth.
4. **Given** the traveler does not consent to an external model call, **When** planning is started, **Then** the structured form remains fully usable without sending the natural-language text externally.

---

### User Story 3 - Continue When the LLM Is Unavailable (Priority: P1)

A traveler can continue managing trips and generating deterministic plans when the configured LLM is disabled, times out, returns malformed output, is rate-limited, or exhausts its quota.

**Why this priority**: A free or external provider has no product availability guarantee and cannot become a single point of failure.

**Independent Test**: Run the same structured planning fixture with a healthy provider, provider disabled, timeout, malformed response, and quota error; confirm deterministic alternatives and stored records remain correct in every case.

**Acceptance Scenarios**:

1. **Given** the provider is disabled or unconfigured, **When** a structured request is submitted, **Then** deterministic planning completes without an AI dependency.
2. **Given** natural-language parsing cannot complete, **When** the failure is returned, **Then** the traveler receives an actionable message and can continue with the structured form.
3. **Given** explanation or shadow comparison fails after feasible plans exist, **When** results are shown, **Then** the plans remain available in deterministic order with an honest unavailable status.
4. **Given** a provider failure occurs, **When** the request ends, **Then** no partial model output corrupts trips, alternatives, accepted versions, or synchronization data.

---

### User Story 4 - Understand Why a Plan Fits (Priority: P2)

A traveler reads concise reasons for selected places and ordering, with facts traceable to verified data and preferences while uncertain or model-generated language remains visibly distinct.

**Why this priority**: Explanation increases trust only when it is grounded in the exact feasible plan rather than invented by a fluent model.

**Independent Test**: Generate an explanation for a fixture with verified hours, rain exposure, budget, and food preference, then verify every factual statement maps to request or catalog evidence and no new POI or route fact appears.

**Acceptance Scenarios**:

1. **Given** a feasible plan and its evidence, **When** an explanation is requested, **Then** every factual claim can be traced to that plan, request, or verified data version.
2. **Given** the LLM adds an unsupported claim, **When** output validation runs, **Then** the claim is removed or the deterministic explanation is used instead.
3. **Given** no LLM is available, **When** the plan is displayed, **Then** deterministic reasons and warnings remain available.

---

### User Story 5 - Replace the External Provider Safely (Priority: P2)

An operator can enable, disable, or replace the hosted provider and model through deployment configuration without changing source code, exposing credentials, or migrating product records.

**Why this priority**: Free-tier models and quotas change; provider replacement must be an operational choice rather than a rewrite.

**Independent Test**: Exercise disabled, Gemini-compatible test, and mock-compatible configurations; verify readiness identifies the active non-secret configuration, provider-specific failures are normalized, and stored product records are unchanged.

**Acceptance Scenarios**:

1. **Given** a valid provider configuration, **When** readiness is inspected, **Then** it reports capability, provider label, model label, and availability without revealing credentials.
2. **Given** the provider or model changes, **When** the service restarts, **Then** existing accounts, trips, plans, expenses, and acceptance history remain compatible.
3. **Given** a credential is missing or invalid, **When** the capability is invoked, **Then** it fails closed with a normalized status and does not log the credential.
4. **Given** a hosted free-tier provider may process submitted content under its own data policy, **When** the capability is enabled, **Then** the product discloses external processing and sends only the minimum planning context required.

### Edge Cases

- The source planner and current platform represent the same request, POI, or alternative with different identifiers or field names.
- The imported snapshot version differs from the catalog version attached to a persisted trip or accepted itinerary.
- A natural-language request contains prompt injection, credentials, contact details, or unrelated private content.
- A provider returns valid JSON with semantically invalid dates, money, categories, coordinates, POIs, or constraints.
- The free-tier provider returns quota, safety-filter, region, model-retirement, or transient availability errors.
- A provider response arrives after the request was cancelled, timed out, or the account signed out.
- The LLM explanation contradicts deterministic warnings or omits a material hard constraint.
- A stable-planner regression fixture passes in the historical branch but fails after adaptation to current contracts.
- Weather or online-route data is unavailable while the local snapshot and route matrix remain available.
- Planning is retried concurrently and must not duplicate alternatives, versions, or acceptance records.

## Requirements *(mandatory)*

### Functional Requirements

#### Stable Planner Integration

- **FR-001**: The product MUST integrate the stable planner behind the current authenticated planning and itinerary-lifecycle contracts rather than expose a second independent source of product truth.
- **FR-002**: The integration MUST preserve account and trip ownership, authorization, durable request records, immutable accepted versions, parent-version links, data-version evidence, and idempotent selection.
- **FR-003**: Every selectable alternative MUST pass deterministic checks for entity validity, time, opening information, movement, budget, traveler safety/accessibility constraints, and request ownership.
- **FR-004**: AI output MUST NOT create, approve, or modify a selectable alternative after deterministic validation.
- **FR-005**: The planner MUST return only genuinely distinct feasible alternatives and MUST explain shortages without padding results.
- **FR-006**: Planning MUST preserve the stable behavior for verified POI tiers, real travel matrix, weather-aware placement, all-day places, meal/rest rules, profile preferences, route ordering, one- and two-day plans, and remaining-day replanning where applicable.
- **FR-007**: The integration MUST retain the current product behavior for manual itinerary editing, map/route playback, expenses, offline reading, and version history.
- **FR-008**: Source-branch code, data, and tests MUST be adapted selectively; removed or superseded product modules MUST NOT be restored merely to reproduce the historical branch tree.
- **FR-009**: Automated planning in this increment MUST support one- and two-day Da Nang requests; unsupported longer requests MUST degrade to explicit manual or scoped planning rather than silently truncate a trip.

#### Natural-Language Interpretation

- **FR-010**: A traveler MUST be able to submit a Vietnamese natural-language planning request or bypass AI and enter the same request through structured fields.
- **FR-011**: AI-assisted interpretation MUST produce a reviewable proposal that distinguishes confirmed values, hard constraints, soft preferences, assumptions, and unresolved fields.
- **FR-012**: No interpreted value MAY become authoritative until it passes schema, range, catalog, ownership, and policy validation and the traveler confirms it.
- **FR-013**: Unknown POIs, unsupported categories, fabricated coordinates, and inconsistent dates or money MUST be rejected or marked unresolved.
- **FR-014**: Prompt content MUST be treated as untrusted input and MUST NOT override system policy, validation rules, provider configuration, or deterministic gates.

#### Configurable LLM Capability

- **FR-015**: The LLM capability MUST be replaceable and configurable by provider, endpoint, model, credential reference, timeout, retry limit, and enabled capabilities without changing product records.
- **FR-016**: Credentials MUST remain outside source control, responses, ordinary logs, persisted prompts, and readiness output.
- **FR-017**: Missing configuration, invalid credentials, timeout, malformed output, quota exhaustion, safety refusal, and provider unavailability MUST map to explicit non-secret failure categories.
- **FR-018**: Provider retries MUST be bounded and MUST NOT duplicate product mutations.
- **FR-019**: Disabling or losing the LLM MUST NOT block structured deterministic planning, trip management, accepted-plan access, expenses, map use, or offline reading.
- **FR-020**: Readiness MUST expose whether parsing, explanation, and shadow comparison are enabled and available, plus non-secret provider/model labels and last failure category.
- **FR-021**: Replacing a provider or model MUST NOT require destructive migration of accounts, trips, expenses, POIs, itinerary requests, alternatives, versions, or acceptance history.

#### Privacy, Explanation, and Shadow Use

- **FR-022**: Hosted-model calls MUST minimize submitted data and MUST exclude credentials, authentication tokens, account-security data, raw audit records, and unrelated private content.
- **FR-023**: The product MUST disclose when natural-language content is sent to an external provider and MUST offer a non-AI structured path.
- **FR-024**: Stored invocation metadata MUST be limited to operational evidence such as capability, provider/model label, status, latency, schema version, and correlation identifier; raw prompts and outputs MUST NOT be retained by default.
- **FR-025**: AI-assisted explanations MUST be grounded only in the confirmed request, feasible plan, deterministic warnings, and named data version.
- **FR-026**: Unsupported explanation claims MUST be rejected, removed, or replaced by deterministic template text.
- **FR-027**: Shadow comparison MAY evaluate only alternatives that already passed deterministic gates and MUST NOT change user-visible ordering or acceptance.
- **FR-028**: Shadow evidence MUST identify presentation-order checks, consistency, latency, provider/model label, and non-authoritative status without storing credentials.

#### Verification and Compatibility

- **FR-029**: The integration MUST preserve or improve the source planner's published hard-feasibility, reproducibility, preference, weather, and latency evidence on equivalent fixtures.
- **FR-030**: The current backend, mobile, authorization, persistence, migration, offline, map, expense, and itinerary-lifecycle regressions MUST continue to pass.
- **FR-031**: Historical accepted plans MUST remain readable with their original data and schema evidence after planner integration.
- **FR-032**: Runtime secrets, provider responses, generated audit data, model caches, and mutable planning data MUST remain outside source control.

### Key Entities

- **Confirmed Planning Request**: The traveler-approved structured dates, time bounds, budget, party, transport, preferences, hard constraints, and assumptions used by deterministic planning.
- **Interpretation Proposal**: A non-authoritative model response with proposed fields, confidence/uncertainty, unresolved values, schema version, and validation status.
- **Planner Alternative**: A complete deterministic candidate with activities, movement, cost, warnings, gate evidence, rank, diversity evidence, and data version.
- **Planner Integration Evidence**: Regression and compatibility results linking imported source behavior to the current product contract.
- **LLM Capability Configuration**: Non-secret provider, endpoint class, model label, enabled capabilities, timeout, retry, and privacy mode; the credential itself remains external.
- **LLM Invocation Evidence**: Minimal operational metadata for one parse, explanation, or shadow attempt, excluding credentials and raw content by default.
- **Grounded Explanation**: User-facing language whose factual statements are traceable to confirmed input, deterministic output, and versioned data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of displayed alternatives pass the deterministic entity, temporal, movement, financial, opening/data, and traveler-constraint gates on the recorded request and data version.
- **SC-002**: 100% of selection retries with the same idempotency identity produce exactly one immutable accepted version.
- **SC-003**: At least 95% of the agreed Vietnamese interpretation fixtures produce a valid reviewable proposal, and 100% of invalid proposals are blocked before planning.
- **SC-004**: Structured deterministic planning succeeds in 100% of equivalent regression runs when the LLM is disabled, unavailable, malformed, rate-limited, or out of quota.
- **SC-005**: No provider failure scenario corrupts or duplicates a trip, planning request, alternative, itinerary version, acceptance record, expense, or offline cache.
- **SC-006**: 100% of factual statements in the explanation verification set trace to confirmed input, deterministic plan evidence, or the recorded data version.
- **SC-007**: Replacing the configured provider/model in compatibility tests requires no product-data migration and leaves historical accepted plans byte-for-byte equivalent at the contract boundary.
- **SC-008**: The imported planner passes all applicable historical hard-feasibility regression fixtures and all current product planning-lifecycle regression fixtures.
- **SC-009**: On the agreed reference laptop, one-day planning completes within 15 seconds at the 95th percentile and two-day planning completes within 25 seconds at the 95th percentile, excluding optional shadow work.
- **SC-010**: The full supported mobile flow has zero horizontal overflow at 390×844 and exposes planning, failure, AI-assisted, and deterministic states without ambiguous success labels.
- **SC-011**: Secret scanning finds zero live provider keys, tokens, credentials, or private connection strings in committed files and ordinary runtime logs.
- **SC-012**: In 100% of shadow tests, model preference cannot reorder, approve, or persist an itinerary before explicit future promotion criteria are satisfied.

## Assumptions

- `origin/feat/stable-p1-p4` is the source of stable planner algorithms, verified snapshot/matrix assets, tests, and measured evidence; it is not a replacement for the current product-platform history.
- The current authenticated product modules and durable itinerary lifecycle remain authoritative for ownership and persistence.
- Gemini Developer API free tier is the initial hosted-provider candidate, but model availability, quota, pricing, region support, and data-use terms may change; the exact model remains deployment configuration.
- Free-tier hosted requests may be processed under provider improvement policies, so only minimized planning context is sent and the structured non-AI path remains available.
- The verified Da Nang snapshot and calibrated local route matrix remain the planning data baseline until a later catalog-publication increment supersedes them.
- Administration/data-operations work already present on a separate local branch or worktree is preserved but is not part of this increment and must not be merged accidentally.

## Dependencies

- Increment 011 and its offline-cache lifecycle fixes merged into the product integration branch.
- The stable planner source branch and its historical evaluation artifacts.
- Current profile, trip, catalog, itinerary-lifecycle, expense, map, routing, and offline contracts.
- A provider credential supplied outside source control for hosted-model smoke tests; mock/disabled modes cover ordinary automated tests.
- Product approval of the external-processing disclosure before enabling hosted natural-language parsing for real traveler content.
