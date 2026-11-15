# Feature Specification: Google sign-in and SMTP identity delivery

**Branch**: `task/012-planning-llm-integration` (authorized follow-up)
**Created**: 2026-11-14
**Status**: Implemented and verified (2026-11-15)

## User Scenarios & Testing

### US1 — Receive real identity email (P1)

A traveler receives verification, password recovery, and deletion cancellation
codes through their configured sender instead of a development inbox.

Acceptance: register, receive a single-use expiring code, verify, log in, request
recovery, reset, and confirm that the previous password and sessions are rejected.
SMTP rejection must record failed delivery and never be reported as sent.
Unknown and known recovery addresses receive the same public response.

### US2 — Sign in with Google (P1)

A traveler uses Google from the local Flutter web interface and receives an
ordinary Davel session, including refresh and revocation. A new account requires
explicit terms acceptance. Existing email/password accounts are not silently
linked by matching email. Google identities are identified by stable subject.

Acceptance: successful consent signs in; cancellation returns a useful error;
tampered, expired, replayed, wrong-browser, wrong-audience, unverified-email and
nonce-mismatched responses cannot establish a session. Suspended/deleted accounts
cannot use Google to bypass their state.

### US3 — Honest setup and regression checks (P1)

Configuration lives in ignored backend env, with placeholder examples only.
Tests distinguish mocked provider contracts from real network checks and human
Google consent. Existing password login, refresh and demo operation continue.

## Requirements

- FR-001: SMTP must use verified TLS, bounded timeouts and explicit delivery status.
- FR-002: Real-delivery mode must not expose codes through the development inbox.
- FR-003: Verification/recovery codes remain single use, hashed at rest and expiring.
- FR-004: OAuth must bind state to a browser, use PKCE and validate Google ID-token
  signature, issuer, audience, expiry, nonce and verified email before account access.
- FR-005: OAuth transactions and one-time handoffs must persist in PostgreSQL and
  enforce expiry and atomic consumption. Google tokens must not be stored.
- FR-006: Access/refresh tokens must not appear in URLs, callback HTML or logs.
- FR-007: Only configured frontend origins may receive popup results. New accounts
  receive only the traveler role; email collisions require ordinary password login.
- FR-008: Refresh rotation, recovery session revocation and local demo must remain.
- FR-009: Google client and SMTP secrets stay out of Git and test output.

## Success Criteria

- SC-001: Automated tests cover success and rejection paths for FR-001–FR-009.
- SC-002: Real SMTP authentication and a message to the user-provided sender are
  verified separately from automated tests; no other real recipients are used.
- SC-003: Google authorization URL and public client configuration are checked;
  end-to-end consent is reported as pending until observed with a real account.
- SC-004: Backend identity regression suite, Flutter tests/analyzer/build and
  migration checks pass before the change is offered for review.

## Assumptions

This increment targets Flutter web on the existing local ports. Native Android/iOS
Google clients and explicit linking of an existing password account are outside
this increment. Users of newly created Google accounts can set a Davel password
through recovery if they need password-confirmed export/deletion operations.
