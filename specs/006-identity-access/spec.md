# Feature Specification: Identity and Access

**Feature Branch**: `task/006-identity-access`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Continue the complete product MVP with registration, verification, login, recovery, roles, sessions, and account lifecycle before trip and expense management; keep AI optional and separate."

## Product Boundary

This increment establishes durable account ownership and private access for every later management capability. It covers account identity, authentication, session control, role enforcement, recovery, and self-service account lifecycle. Profile preferences, trip CRUD, expenses, POI curation, planning, AI, and complete administrator consoles remain owned by later increments.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register, Verify, and Sign In (Priority: P1)

A traveler creates an account with email and password, verifies ownership of the email address, signs in, and reaches the authenticated mobile shell without exposing credentials or private records.

**Why this priority**: Every durable profile, trip, expense, and itinerary must have a verified owner before management features can safely use shared data.

**Independent Test**: Register a previously unused email, complete verification using the delivered one-time action, sign in, restart the client, and confirm the same traveler remains authenticated without seeing another account's records.

**Acceptance Scenarios**:

1. **Given** an unused normalized email and a compliant password, **When** registration succeeds, **Then** one unverified traveler account is created and the password is never returned.
2. **Given** an unverified account, **When** the valid verification action is completed once, **Then** the account becomes verified and repeating the action creates no duplicate state.
3. **Given** a verified active account, **When** correct credentials are submitted, **Then** a private session starts and the authenticated shell identifies the current account.
4. **Given** an unknown email or incorrect password, **When** sign-in fails, **Then** the response does not reveal whether the account exists.
5. **Given** an unverified, suspended, deleted, or rate-limited account, **When** sign-in is attempted, **Then** access is denied with an actionable but non-sensitive state.

---

### User Story 2 - Continue and Control Sessions (Priority: P1)

A traveler stays signed in across an ordinary app restart, can sign in on a second browser or device, reviews active sessions, revokes another session, and signs out safely.

**Why this priority**: Multi-device use and revocation are required before private management data can be considered safely owned.

**Independent Test**: Sign in from two isolated browser sessions, list both sessions, revoke the first from the second, verify the revoked session can no longer access private endpoints, then sign out from all sessions.

**Acceptance Scenarios**:

1. **Given** a valid active session, **When** the client restarts, **Then** authentication can continue without asking for the password again until the session expires or is revoked.
2. **Given** two active sessions for one account, **When** the traveler lists sessions, **Then** both are distinguishable by safe device metadata and recent activity without exposing session secrets.
3. **Given** a selected active session, **When** the traveler revokes it, **Then** subsequent private access through that session fails.
4. **Given** a traveler chooses sign out everywhere, **When** the action is confirmed, **Then** all current sessions are invalidated, including the requesting session.
5. **Given** a session is expired, revoked, malformed, or belongs to another account, **When** it is used, **Then** private data is not returned.

---

### User Story 3 - Recover a Forgotten Password (Priority: P1)

A traveler who no longer remembers a password can request recovery, complete a short-lived one-time action, choose a new compliant password, and return to the product securely.

**Why this priority**: Account ownership is incomplete if a legitimate traveler cannot regain access without an administrator changing credentials manually.

**Independent Test**: Request recovery for a registered email and an unknown email, observe indistinguishable public responses, reset the registered account once, verify the old password and old sessions stop working, and sign in with the new password.

**Acceptance Scenarios**:

1. **Given** any syntactically valid email, **When** recovery is requested, **Then** the public response is the same whether or not the account exists.
2. **Given** an active verified account, **When** recovery is requested within allowed limits, **Then** a short-lived one-time recovery action is delivered through the configured channel.
3. **Given** a valid unused recovery action and compliant new password, **When** reset succeeds, **Then** the password changes and all earlier sessions and recovery actions become invalid.
4. **Given** an expired, already-used, malformed, or superseded recovery action, **When** reset is attempted, **Then** no credential or session state changes.

---

### User Story 4 - Enforce Roles and Account Isolation (Priority: P1)

Travelers, data curators, and administrators can access only the capabilities granted to their roles, while every private traveler resource remains isolated by ownership.

**Why this priority**: Later profile, trip, expense, catalog, and administration increments depend on one consistent authorization boundary.

**Independent Test**: Exercise the same protected capability as a guest, traveler, curator, administrator, suspended user, and a different traveler; confirm only explicitly authorized combinations succeed.

**Acceptance Scenarios**:

1. **Given** a guest, **When** a private capability is requested, **Then** authentication is required.
2. **Given** an authenticated traveler, **When** another traveler's resource identifier is supplied, **Then** the resource is not disclosed or changed.
3. **Given** a traveler without an administrative role, **When** an administrative capability is requested, **Then** access is denied and the attempt is auditable.
4. **Given** an account with multiple roles, **When** a permitted capability is requested, **Then** authorization uses the active durable role assignments rather than client claims.
5. **Given** a suspended account, **When** an existing session requests private data, **Then** access is denied even if the session has not otherwise expired.

---

### User Story 5 - Manage the Account Lifecycle (Priority: P2)

A traveler can review basic account status, request a portable account export, request deletion with explicit confirmation, and recover during the documented grace period before final purge.

**Why this priority**: Self-service lifecycle controls establish honest data ownership without coupling deletion behavior to AI or later management interfaces.

**Independent Test**: Request an export, verify its account-owned scope, request deletion, confirm immediate access loss, restore within the grace period through a verified recovery flow, and verify final purge behavior with fixtures whose retention rules are known.

**Acceptance Scenarios**:

1. **Given** an active traveler, **When** account status is viewed, **Then** verification, lifecycle state, roles, and active-session count are understandable without exposing security secrets.
2. **Given** an authenticated traveler, **When** export is requested, **Then** a traceable job is created for documented user-owned record types and cannot be downloaded by another account.
3. **Given** a confirmed deletion request, **When** it is accepted, **Then** sessions are revoked immediately and the account enters a recoverable deletion state.
4. **Given** a deletion-pending account inside the 30-day grace period, **When** the verified owner cancels deletion, **Then** the account returns to an active state without restoring revoked sessions.
5. **Given** the grace period has ended, **When** purge processing completes, **Then** user-owned personal data is removed or anonymized according to documented retention rules while required security evidence remains non-reversible.

### Edge Cases

- Concurrent registrations use the same email with different letter casing or surrounding whitespace.
- Verification or recovery actions are requested repeatedly, delivered out of order, or submitted concurrently.
- A password changes while another device is refreshing or using a session.
- A session is revoked at the same moment it performs a protected write.
- A role is removed or an account is suspended while an older session still exists.
- Client time differs from server time; expiration decisions remain consistent and server-authoritative.
- Email delivery is unavailable; account state remains consistent and retry does not create unlimited active actions.
- Database or delivery failure occurs midway through registration, verification, reset, revocation, export, or deletion.
- A seeded demo user is mistaken for a real registered traveler; every demo identity remains visibly isolated and resettable.

## Requirements *(mandatory)*

### Functional Requirements

#### Registration and Verification

- **FR-001**: The system MUST support email-and-password registration for a traveler using a normalized, case-insensitive unique email identity.
- **FR-002**: Registration MUST validate required consent, email shape, and a documented password policy before creating an account.
- **FR-003**: Credentials, verification actions, recovery actions, and session secrets MUST never be returned in account representations, ordinary logs, health output, or audit metadata.
- **FR-004**: A newly registered account MUST begin unverified and MUST NOT gain authenticated private access until email ownership is verified.
- **FR-005**: Email verification MUST use an expiring, single-use action and MUST be idempotent after successful verification.
- **FR-006**: Resending verification MUST invalidate or supersede older usable actions and MUST be rate-limited without revealing account existence.
- **FR-007**: Duplicate concurrent registrations for one normalized email MUST result in at most one account.

#### Authentication and Sessions

- **FR-008**: Only verified, active, non-deleted accounts with valid credentials MAY start a private session.
- **FR-009**: Failed authentication MUST use non-enumerating responses and MUST apply per-identity and per-client abuse limits.
- **FR-010**: Authentication MUST distinguish public failure categories needed by the client without disclosing stored credential or account-existence details.
- **FR-011**: Every session MUST have a stable identifier, owner, issue time, absolute expiry, revocation state, last-activity time, and privacy-safe device metadata.
- **FR-012**: Session continuation MUST use renewable short-lived access and a revocable session record, without storing a reusable plaintext session secret.
- **FR-013**: A traveler MUST be able to list their own active sessions, revoke one session, revoke all other sessions, or sign out everywhere.
- **FR-014**: Revocation, password reset, account suspension, deletion request, or final purge MUST prevent affected sessions from authorizing subsequent private access.
- **FR-015**: Session creation, renewal, and revocation MUST be atomic and safe under retry so duplicate logical sessions or partially revoked state are not reported as success.

#### Password Recovery

- **FR-016**: Recovery requests MUST return the same public outcome for registered, unknown, inactive, or ineligible email addresses.
- **FR-017**: A recovery action MUST be single-use, short-lived, stored non-reversibly, and superseded by a newer successful recovery flow.
- **FR-018**: Successful password reset MUST invalidate every existing session and outstanding recovery action for the account before reporting success.
- **FR-019**: Password history MUST prevent immediate reuse of the current password during reset without exposing comparison details.

#### Authorization and Roles

- **FR-020**: The system MUST support durable traveler, data-curator, and administrator role assignments independent of client-provided claims.
- **FR-021**: Every protected capability MUST declare its authentication and role requirements and deny by default when no permission is defined.
- **FR-022**: Private account-owned resources MUST be authorized by server-side ownership on every read and write.
- **FR-023**: Cross-account requests MUST NOT reveal whether a private resource identifier belongs to another traveler.
- **FR-024**: Current account status and role assignments MUST be re-evaluated during session authorization so suspension or role removal takes effect without waiting for session expiry.
- **FR-025**: Role assignment changes and denied privileged attempts MUST create privacy-safe audit evidence.

#### Account Lifecycle and Delivery

- **FR-026**: Account lifecycle MUST distinguish unverified, active, suspended, deletion-pending, anonymized, and purged states with valid transitions only.
- **FR-027**: A traveler MUST be able to view their safe account summary and active-session count.
- **FR-028**: Account export and deletion requests MUST require a recently authenticated session plus explicit confirmation.
- **FR-029**: A confirmed deletion request MUST revoke access immediately and begin a 30-day recovery window before final purge.
- **FR-030**: Cancellation during the recovery window MUST require renewed proof of email ownership and MUST NOT reactivate previously revoked sessions.
- **FR-031**: Final purge MUST remove or irreversibly anonymize user-owned personal identity data while retaining only evidence required by documented security and audit rules.
- **FR-032**: Verification and recovery delivery MUST have an explicit sent, delayed, failed, or unavailable state; delivery failure MUST NOT falsely mark the action complete.
- **FR-033**: Local demonstration MUST provide a safe, explicit way to complete verification and recovery without committing a live provider credential or exposing actions in production behavior.
- **FR-034**: Seeded demo identities MUST remain isolated from registered accounts and visibly labeled wherever identity could be mistaken for persisted user data.

#### Integration and Observability

- **FR-035**: Identity records MUST use the authoritative shared store and survive backend or application restarts.
- **FR-036**: Identity operations MUST preserve the platform correlation identifier and stable error envelope.
- **FR-037**: Security events MUST record action category, account or anonymous subject reference where appropriate, outcome, time, and correlation identifier without credentials or reusable secrets.
- **FR-038**: Identity unavailability MUST fail closed for private access while leaving public health and static/demo capabilities honestly distinguishable.
- **FR-039**: Core identity and access behavior MUST operate with every AI integration disabled.
- **FR-040**: Registration, login, verification, recovery, and session controls MUST be usable in the supported 390×844 mobile viewport with loading, empty, success, and actionable failure states.

### Key Entities

- **Account**: Stable ownership root with normalized email identity, password credential state, verification time, lifecycle state, consent evidence, and timestamps.
- **Role Assignment**: Durable association granting traveler, data-curator, or administrator permissions to an account.
- **Session**: Revocable authenticated access instance with stable identity, owner, issue/expiry/revocation times, activity, and safe device description.
- **Verification Action**: Expiring, single-use proof request for email ownership with non-reversible secret evidence and delivery status.
- **Recovery Action**: Expiring, single-use password recovery request that becomes invalid after use, supersession, or account state change.
- **Password History Entry**: Non-reversible evidence used only to reject immediate credential reuse.
- **Account Lifecycle Event**: Append-only transition evidence for verification, suspension, deletion request, recovery cancellation, anonymization, or purge.
- **Security Audit Event**: Privacy-safe evidence for authentication, session, role, abuse-limit, and denied privileged actions.
- **Export Request**: Account-owned request describing scope, status, readiness, expiry, and integrity evidence for a portable data package.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of first-time testers complete registration, verification, and first sign-in in under five minutes without facilitator assistance.
- **SC-002**: Valid sign-in and session continuation show a useful outcome within two seconds under normal local development conditions.
- **SC-003**: Unauthorized cross-account access succeeds in 0% of the defined isolation tests.
- **SC-004**: Replayed, expired, superseded, or already-used verification and recovery actions change account state in 0% of tests.
- **SC-005**: Revoked sessions lose private access on the next protected request in 100% of revocation tests.
- **SC-006**: Password reset invalidates the old password, all old sessions, and all outstanding recovery actions in 100% of recovery tests.
- **SC-007**: Concurrent duplicate registration, verification, recovery, renewal, and revocation attempts create no duplicate durable outcome in the defined retry tests.
- **SC-008**: Guest, traveler, data-curator, administrator, suspended, and deletion-pending access outcomes match the published permission matrix in 100% of authorization tests.
- **SC-009**: Account, role, session, and lifecycle records survive three consecutive backend restarts without loss or duplicate active state.
- **SC-010**: Public login and recovery responses allow testers to infer whether an email exists in 0% of scripted comparison cases.
- **SC-011**: Credential values, reusable session secrets, and verification/recovery actions appear in 0 committed files and 0 ordinary runtime log samples.
- **SC-012**: All registration, sign-in, recovery, session, and account-state screens fit a 390×844 viewport without horizontal overflow or inaccessible primary actions.
- **SC-013**: The complete identity demonstration succeeds with all AI providers disabled.

## Assumptions

- Email/password is the only end-user sign-in method in this increment; social login, passkeys, and multi-factor authentication are deferred.
- Email matching is case-insensitive after normalization; changing an account email is deferred to a later account-settings increment.
- A traveler role is assigned to every newly verified end-user account; curator and administrator roles are provisioned only through trusted development or operations procedures until the administrator increment.
- The local student demonstration may use an explicitly labeled development delivery inbox; production-like behavior never returns verification or recovery secrets in public responses.
- Account deletion uses the product-wide 30-day recovery window, while exact retained audit fields are minimized and documented before purge implementation is accepted.
- Export initially covers identity records available at this increment and expands as profile, trip, expense, and itinerary increments add owned data.
- AI is not a dependency for identity, authorization, recovery, export, or deletion.

## Out of Scope

- Social sign-in, enterprise single sign-on, passkeys, multi-factor authentication, phone-number authentication, and biometric enrollment.
- Full administrator and curator management screens; this increment establishes roles and enforcement contracts only.
- Traveler profile preferences, trips, expenses, POI curation, itinerary generation, offline mutation synchronization, and AI integration.
- Legal-policy authoring, production email-provider procurement, and production deployment certificates.
