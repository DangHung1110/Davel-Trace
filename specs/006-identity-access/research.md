# Research: Identity and Access

## Password hashing

**Decision**: Use Argon2 via `pwdlib[argon2]`, encode parameters with every hash, and opportunistically rehash after a successful login when policy changes.

**Rationale**: Argon2 is memory-hard, has a maintained Python integration, and avoids hand-rolled password cryptography. `pwdlib` exposes a small upgrade-aware interface suitable for the modular identity boundary.

**Alternatives considered**: `hashlib.scrypt` would avoid a dependency but requires more custom encoding and upgrade logic; bcrypt has a mature ecosystem but a less flexible memory-hard profile; plaintext or fast hashes are rejected.

## Session credentials

**Decision**: Use opaque 256-bit random access and refresh credentials, persist only SHA-256 hashes, rotate refresh credentials, and revoke a session family when a rotated credential is replayed.

**Rationale**: Random high-entropy credentials do not need server signing keys and can be revoked immediately from PostgreSQL. Hashing prevents a database reader from directly using stored credentials.

**Alternatives considered**: JWT access tokens reduce database lookups but complicate immediate role/status revocation and signing-key lifecycle; a single 30-day bearer token increases exposure; server cookies alone do not cover the shared mobile client cleanly.

## Flutter credential storage

**Decision**: Keep the short-lived access credential in memory and store the refresh credential with `flutter_secure_storage`; never place either in ordinary preferences or app logs.

**Rationale**: The same repository contract supports web/mobile while native targets use platform-protected storage. The web demo runs only on a trusted localhost secure context and is documented as a demonstration, not a production browser hardening claim.

**Alternatives considered**: `shared_preferences` is inappropriate for reusable credentials; an HttpOnly-cookie-only design is strong for browsers but awkward for native clients and the current HTTP abstraction; memory-only refresh forces login after every restart.

## Verification and recovery delivery

**Decision**: Define a delivery port. Provide a process-memory dev inbox only when explicitly enabled in demo/test mode; production requires a real adapter and rejects dev inbox configuration.

**Rationale**: The local demonstration stays complete without committing provider credentials or leaking actions to logs. The port allows an SMTP or transactional email provider later without changing account state or API contracts.

**Alternatives considered**: Logging tokens violates secret-handling requirements; returning tokens from public registration/recovery responses weakens non-enumeration; selecting an email vendor now expands project scope and cost.

## Abuse limiting

**Decision**: Store bounded fixed-window counters in PostgreSQL keyed by a one-way digest of purpose plus normalized identity and client address. Apply limits to registration resend, login, verification, recovery, and refresh.

**Rationale**: This works across restarts and multiple backend processes without Redis. The scale is small and cleanup can piggyback on the purge maintenance command.

**Alternatives considered**: Process memory loses state on restart and differs between workers; Redis is unnecessary infrastructure for this student MVP; client-only throttling is bypassable.

## Account deletion and audit

**Decision**: Use a 30-day `deletion_pending` state, immediate session revocation, verified cancellation, and an idempotent purge command. Retain only minimized non-reversible security evidence after purge.

**Rationale**: This matches the umbrella product assumption and keeps deletion recoverable without silently preserving credentials or sessions.

**Alternatives considered**: Immediate hard deletion is difficult to recover; indefinite soft deletion violates the stated lifecycle; administrator-only deletion conflicts with self-service ownership.

## Export scope

**Decision**: Persist an export request and produce an integrity-hashed JSON document containing identity-owned records available in this increment. Later capabilities register additional exporters.

**Rationale**: The contract is usable now and avoids redesign when trips and expenses arrive. Persistent request state supports expiry, audit, and retry.

**Alternatives considered**: A synchronous ad-hoc response is harder to audit/extend; a background queue is unnecessary at current scale.
