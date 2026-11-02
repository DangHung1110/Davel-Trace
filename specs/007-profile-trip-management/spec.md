# Feature Specification: Profile and Trip Management

**Feature Branch**: `task/007-profile-trip-management`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Continue the product platform after identity and access with durable traveler profiles, preferences, trip/day/activity management, archive and restore; keep AI, expense accounting, POI catalog work, and planning automation in later increments."

## Product Boundary

This increment turns an authenticated account into a useful non-AI travel manager. A traveler can maintain reusable preferences and hard constraints, create an owned Da Nang trip, organize days and manual activities, select the active trip, and safely archive, restore, or delete a trip. All records are durable, private to their owner, and usable without an AI provider.

Expense ledgers, POI catalog/search, route computation, automated itinerary generation, offline write synchronization, collaboration, and administrator consoles remain owned by later increments. A trip may record an indicative budget and optional POI reference, but this increment does not calculate expense summaries or validate external POI truth.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete a Reusable Travel Profile (Priority: P1)

A signed-in traveler records reusable travel preferences and non-negotiable constraints, reviews what is currently active, and edits or clears those values later.

**Why this priority**: Trips need an explicit, owned source of traveler context before future planning can be relevant and safe.

**Independent Test**: Sign in with a new account, complete profile onboarding, edit one soft preference, clear another, sign out and back in, and verify the latest profile remains available with hard constraints clearly distinguished.

**Acceptance Scenarios**:

1. **Given** a verified traveler without a profile, **When** onboarding is completed with valid values, **Then** one owned current profile is created and its update time is visible.
2. **Given** an existing profile, **When** the traveler edits pace, spending style, food preferences, activities, or usual transport, **Then** the current profile reflects the new values without changing historical trip snapshots.
3. **Given** optional profile values, **When** the traveler clears or resets them, **Then** the product distinguishes an intentionally empty value from an unsaved failure.
4. **Given** allergy, safety, must-avoid, or accessibility information, **When** the profile is reviewed, **Then** those values are visibly labeled as hard constraints rather than ordinary preferences.
5. **Given** a different signed-in traveler, **When** that traveler requests the first account's profile, **Then** no private profile data is disclosed.

---

### User Story 2 - Create and Reopen an Owned Trip (Priority: P1)

A traveler creates a Da Nang trip with dates, travelers, daily bounds, transport, notes, and optional trip-specific preference overrides, then reopens the same trip after a new session.

**Why this priority**: Durable trip ownership is the core management value and the root for days, activities, expenses, routing, and later planning.

**Independent Test**: Create a three-day trip, inherit profile values, override one soft value, close the session, sign in again, and reopen the exact same trip without duplication or data loss.

**Acceptance Scenarios**:

1. **Given** an authenticated traveler, **When** valid trip details are submitted, **Then** the trip appears once in that traveler's list with dates, status, traveler count, and last-update time.
2. **Given** a current profile, **When** a trip is created without overrides, **Then** the trip records which profile values were inherited at creation.
3. **Given** a trip-specific soft preference override, **When** the trip is viewed, **Then** the override is visible, applies only to that trip, and does not mutate the global profile.
4. **Given** an attempted override of an allergy, safety, or accessibility constraint, **When** the trip is saved, **Then** the hard constraint is preserved and the weakening change is rejected.
5. **Given** a successful trip creation followed by a client retry, **When** the same creation intent is repeated, **Then** no duplicate trip is created.

---

### User Story 3 - Organize Days and Manual Activities (Priority: P1)

A traveler manages ordered trip days and manually adds, edits, reorders, completes, skips, or removes activities within each day.

**Why this priority**: Day and activity management makes the product useful even when automated planning and POI services are unavailable.

**Independent Test**: Open a multi-day trip, add custom activities to two days, edit times and notes, reorder activities, mark one completed and another skipped, remove one, and verify the timeline remains valid after reopening.

**Acceptance Scenarios**:

1. **Given** a valid trip date range, **When** the trip is created or its dates change, **Then** the trip has exactly one ordered day for each local calendar date in the range.
2. **Given** an owned trip day, **When** a valid manual activity is added, **Then** it appears in the requested position with its label, time, duration, cost estimate, status, and notes.
3. **Given** several activities in one day, **When** the traveler reorders them, **Then** every activity has one deterministic position and repeated retries do not duplicate or corrupt the order.
4. **Given** an activity, **When** it is completed or skipped, **Then** its progress state changes without deleting its schedule or history.
5. **Given** an activity time outside the trip day or an end before a start, **When** saving is attempted, **Then** the change is rejected with a clear correction message.
6. **Given** a future POI reference or a custom activity, **When** the activity is displayed, **Then** custom entries are clearly labeled and unresolved references do not break the day timeline.

---

### User Story 4 - Find and Switch the Active Trip (Priority: P1)

A traveler searches and filters their trips, sees one active trip, and switches the active trip without changing or duplicating any trip content.

**Why this priority**: Mobile navigation and later expenses, maps, and planning need one unambiguous current-trip context.

**Independent Test**: Create upcoming and completed trips, search by title, filter by status, switch the active trip twice, and verify the correct trip remains active after a new session.

**Acceptance Scenarios**:

1. **Given** several owned trips, **When** the traveler searches by normalized title text, **Then** only matching owned trips are shown.
2. **Given** active, upcoming, completed, archived, and deleted trips, **When** a status filter is selected, **Then** only the requested state is returned in a deterministic order.
3. **Given** one active trip, **When** another eligible trip becomes active, **Then** the previous trip remains intact but is no longer active.
4. **Given** two devices switching the active trip close together, **When** both operations settle, **Then** the account has at most one active trip and the later accepted change is visible.
5. **Given** no eligible active trip, **When** the traveler opens the management shell, **Then** the empty state explains how to create or restore a trip.

---

### User Story 5 - Archive, Restore, and Delete Safely (Priority: P2)

A traveler removes finished trips from the normal workspace by archiving them, restores them without duplication, and uses a separate recoverable deletion flow for unwanted trips.

**Why this priority**: Lifecycle controls keep the trip list manageable while protecting owned history from accidental permanent loss.

**Independent Test**: Archive an active trip, restore it, soft-delete it, recover it during the recovery window, then purge a separate disposable fixture and verify unrelated records remain unchanged.

**Acceptance Scenarios**:

1. **Given** an active or completed trip, **When** it is archived, **Then** it leaves the normal trip list, cannot remain active, and keeps all days and activities.
2. **Given** an archived trip, **When** it is restored, **Then** its days, activities, ordering, profile snapshot, and history return without duplication.
3. **Given** an owned trip, **When** deletion is explicitly confirmed, **Then** it enters a recoverable deleted state and is unavailable to normal trip actions.
4. **Given** a deleted trip inside the recovery window, **When** the owner restores it, **Then** the trip returns to a non-active eligible state with the same stable identity.
5. **Given** a deletion whose recovery window has ended, **When** purge runs, **Then** owned trip content is removed or minimized according to retention rules without affecting another trip or account.

### Edge Cases

- A trip starts or ends on a leap day, crosses midnight, or is edited around local midnight; Da Nang local dates remain authoritative.
- The start date is after the end date, the duration exceeds 14 days, or traveler count falls outside 1–20.
- Daily start is not before daily end, activity time is outside its day, or activities overlap; invalid bounds are rejected while overlaps are visibly warned rather than silently reordered.
- A date edit shortens the trip while removed days contain activities; the traveler must confirm the affected scope before saving.
- A trip title contains only whitespace, Vietnamese diacritics, emoji, or duplicate text; identity remains stable and search remains normalized.
- A request is retried after a timeout during trip creation, activity creation, reorder, archive, restore, or active-trip switch.
- Two authorized sessions edit the same profile or trip from stale versions; the later writer is not allowed to silently overwrite unseen changes.
- The current active trip is archived, deleted, or becomes ineligible; the account transitions to no active trip rather than selecting another silently.
- A referenced POI is unavailable or not yet synchronized; the activity remains readable with an honest unavailable-reference state.
- The identity account becomes suspended or deletion-pending during a write; access fails closed and no partial trip change is committed.

## Requirements *(mandatory)*

### Functional Requirements

#### Ownership and Profile

- **FR-001**: Every profile, trip, day, activity, override, lifecycle event, and active-trip selection MUST have a stable identity and an owning account.
- **FR-002**: Every read and write MUST verify the current authenticated account owns the requested private record.
- **FR-003**: The system MUST maintain at most one current traveler profile per active account and expose its creation and last-update times.
- **FR-004**: The profile MUST support party type, trip purpose, pace, fitness, spending style, food preferences, preferred activities, usual transport, must-avoid items, allergies, and accessibility needs.
- **FR-005**: Profile editing MUST distinguish hard constraints from soft preferences in labels, review summaries, and downstream snapshots.
- **FR-006**: A traveler MUST be able to review, edit, clear, and reset optional profile values.
- **FR-007**: Profile writes MUST reject unsupported values, excessive text, malformed collections, and attempts to modify another account's data.
- **FR-008**: Profile changes MUST use conflict detection so stale clients cannot silently overwrite a newer profile.
- **FR-009**: A profile change MUST affect future trip inheritance but MUST NOT rewrite existing trip snapshots or historical accepted plans.

#### Trips and Overrides

- **FR-010**: A traveler MUST be able to create, list, view, and edit owned Da Nang trips without any AI or planning provider.
- **FR-011**: A trip MUST include title, destination, start and end dates, traveler count, lifecycle status, optional indicative budget, currency, preferred transport, daily time bounds, notes, ownership, creation time, and update time.
- **FR-012**: Trip dates MUST be interpreted in Da Nang local time and support a duration from 1 through 14 calendar days.
- **FR-013**: Traveler count MUST be an integer from 1 through 20, and monetary values MUST be non-negative in the trip currency.
- **FR-014**: A trip MAY override soft profile values without changing the global profile.
- **FR-015**: A trip override MUST NOT remove or weaken allergy, safety, must-avoid, or accessibility constraints.
- **FR-016**: Before a trip is saved or later sent to planning, the traveler MUST be able to review the effective inherited values, overrides, and hard constraints.
- **FR-017**: Trip creation MUST be idempotent under a repeated client intent and MUST return the originally created trip for the same owner and intent.
- **FR-018**: Trip edits MUST use conflict detection and expose a recoverable stale-version outcome rather than silently overwriting newer data.
- **FR-019**: A change that would invalidate an accepted itinerary MUST preserve that itinerary and mark the trip as needing review; it MUST NOT recalculate a plan in this increment.

#### Days and Activities

- **FR-020**: Each trip MUST contain one ordered trip day for every local date in its inclusive date range.
- **FR-021**: Extending a trip MUST add only missing dates; shortening a trip with non-empty removed days MUST require explicit confirmation of the affected scope.
- **FR-022**: A traveler MUST be able to add, view, edit, reorder, complete, skip, and remove a manual activity within an owned trip day.
- **FR-023**: An activity MUST support a custom label or optional external POI reference, local start and end, duration, optional cost estimate, progress status, notes, stable order, and timestamps.
- **FR-024**: Custom activities MUST be visibly distinguishable from verified or unresolved external-place references.
- **FR-025**: Activity time bounds MUST be valid for their trip day; overlaps MUST be reported honestly and MUST NOT be silently repaired.
- **FR-026**: Activity creation and reorder operations MUST be idempotent and MUST preserve a contiguous deterministic order under retry.
- **FR-027**: Removing an activity MUST preserve any immutable itinerary or acceptance evidence owned by later planning increments.
- **FR-028**: Day and activity edits MUST be atomic so a failed request cannot leave missing days, duplicate order positions, or partially updated activities.

#### Active Trip, Search, and Lifecycle

- **FR-029**: An account MUST have at most one active trip.
- **FR-030**: A traveler MUST be able to activate any eligible owned trip and explicitly clear the active trip.
- **FR-031**: Archived, deleted, or otherwise ineligible trips MUST NOT remain active, and the system MUST NOT silently choose a replacement.
- **FR-032**: Trip lists MUST support search by normalized title, filters for active/upcoming/completed/archived/deleted states, and deterministic sorting.
- **FR-033**: The default list MUST exclude archived and deleted trips while making those states reachable through explicit filters.
- **FR-034**: A traveler MUST be able to archive and restore an owned eligible trip without changing its stable identity or duplicating nested content.
- **FR-035**: Archiving an active trip MUST atomically clear its active selection.
- **FR-036**: Trip deletion MUST require explicit confirmation and MUST first enter a recoverable deleted state.
- **FR-037**: A deleted trip MUST be restorable by its owner during a 30-day recovery window and MUST return as non-active.
- **FR-038**: Purge after the recovery window MUST be idempotent, scoped to eligible deleted trips, and preserve only the minimum lifecycle evidence required for accountability.

#### Continuity, Contracts, and Evidence

- **FR-039**: Profile, trip, day, activity, ordering, lifecycle, and active-trip records MUST survive application, service, and deployment restarts.
- **FR-040**: The authenticated mobile experience MUST provide connected profile onboarding, profile review/editing, trip list/detail/editing, day timeline, activity editing, active-trip switching, archive, restore, and deletion flows.
- **FR-041**: The mobile experience MUST clearly distinguish authenticated persistent records from seeded demo records.
- **FR-042**: Every mutation MUST produce a stable success or failure result with a correlation reference suitable for support and diagnostics.
- **FR-043**: Lifecycle changes, ownership denials, conflict rejections, and destructive confirmations MUST create privacy-safe audit evidence without storing profile text or trip notes in audit metadata.
- **FR-044**: Account export and account purge MUST expand to include or remove profile and trip records according to the identity lifecycle defined by the previous increment.
- **FR-045**: Backup and restore evidence MUST cover profile/trip relationship integrity without exposing personal preference text or private trip notes.
- **FR-046**: The feature MUST preserve existing map, search, route, playback, planning-demo, expense-demo, and identity behavior while moving management data to durable owned records.
- **FR-047**: Core profile and trip management MUST remain usable when AI, automated planning, POI providers, routing providers, and expense services are disabled.

### Key Entities *(include if feature involves data)*

- **Traveler Profile**: One current owned set of reusable soft preferences, hard constraints, onboarding state, version, and timestamps.
- **Trip**: Owned Da Nang journey with dates, travelers, lifecycle and review state, indicative budget, currency, transport, daily bounds, notes, active eligibility, version, and timestamps.
- **Trip Preference Snapshot**: The effective profile values inherited when a trip is created, retained so later profile edits do not rewrite trip history.
- **Trip Preference Override**: Trip-scoped changes to permitted soft preferences with an explanation of what differs from the profile.
- **Trip Day**: Ordered local calendar-date container belonging to exactly one trip.
- **Activity**: Ordered manual stop or task belonging to one day, with schedule, optional reference/cost, progress, notes, and version.
- **Active Trip Selection**: The account-level reference to at most one eligible current trip.
- **Trip Lifecycle Event**: Privacy-safe evidence of creation, archive, restore, deletion, recovery, purge, or state transition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of first-time testers complete profile onboarding in under three minutes without facilitator intervention.
- **SC-002**: At least 95% of testers create a three-day trip, add and reorder an activity, and reopen the same data after a new sign-in session without assistance.
- **SC-003**: 100% of defined ownership tests prevent one traveler from reading or modifying another traveler's profile, trip, day, or activity.
- **SC-004**: Profile, trip, day, activity, order, lifecycle, and active-trip data survive 100% of defined application and service restart tests.
- **SC-005**: Duplicate profiles, trips, activities, days, and order positions occur in 0% of defined retry tests.
- **SC-006**: All defined stale-edit tests report a conflict and preserve both the accepted server state and the user's unsaved input for correction.
- **SC-007**: 100% of hard-constraint override tests reject silent weakening of allergy, safety, must-avoid, or accessibility constraints.
- **SC-008**: A traveler can find any owned trip by title or lifecycle state in under ten seconds in a fixture containing at least 100 trips.
- **SC-009**: Archive, restore, soft-delete, recover, and purge tests affect exactly the selected trip in 100% of lifecycle fixtures.
- **SC-010**: Every primary profile and trip action remains reachable without clipping at 390×844 and 200% text scale.
- **SC-011**: Profile and trip CRUD remains demonstrable with AI and automated planning disabled.
- **SC-012**: Existing identity, map, route, playback, planning-demo, and expense-demo regression scenarios retain their previous passing behavior.

## Assumptions

- Identity, authenticated principal resolution, account lifecycle, and session control from increment 006 are available and authoritative.
- The MVP is Vietnamese-first, Da Nang-only, uses VND by default, and treats Asia/Ho_Chi_Minh local time as authoritative.
- One account owns each trip; shared editing, invitations, and collaborative ownership are deferred.
- Supported trip duration is 1–14 days and traveler count is 1–20.
- Trip budget in this increment is an indicative planning field; budget revision history, expenses, accounting summaries, and financial export belong to increment 008.
- Activities may retain an optional external POI identifier, but catalog validation, search, map integration, and routing belong to increment 009.
- Overlapping activities are allowed only with a visible warning because travelers may intentionally model parallel or flexible tasks; invalid time bounds are rejected.
- Deleted trips remain recoverable for 30 days before becoming purge-eligible.
- Offline reading and queued offline writes are deferred to increment 011; network failures must still preserve the user's entered form values for retry.

## Out of Scope

- Expense entries, budget accounting, alerts, category summaries, receipts, or expense export.
- POI catalog ingestion, place search/details, geolocation, route computation, and map stop rendering.
- Automated itinerary generation, alternative ranking, replanning, or AI-based parsing/explanation.
- Multi-owner trips, invitations, messaging, social feeds, public sharing, and booking/payment.
- General-purpose destinations outside Da Nang.
