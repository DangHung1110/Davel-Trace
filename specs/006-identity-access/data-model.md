# Data Model: Identity and Access

## Conventions

- PostgreSQL 16, UUID primary keys, UTC `timestamptz`, lowercase normalized email, snake_case names.
- Credentials and one-time actions store only hashes; plaintext values exist only at creation/delivery or in the client credential store.
- Lifecycle and security audit rows are append-only. Mutable records use explicit transactions and row locking for competing state transitions.
- Revision `006_001` follows `005_001` and does not alter planning-evidence tables.

## Account

| Field | Rules |
|-------|-------|
| `account_id` | UUID primary key |
| `email_normalized` | Required, unique, lowercase, max 320 |
| `password_hash` | Required Argon2 encoded hash; never serialized |
| `status` | `unverified`, `active`, `suspended`, `deletion_pending`, `anonymized`, `purged` |
| `verified_at` | Nullable UTC time; required for active accounts |
| `consented_at` | Required UTC time |
| `deletion_requested_at`, `purge_after` | Nullable; both required in deletion-pending state |
| `created_at`, `updated_at` | Required UTC times |
| `version` | Positive optimistic-concurrency integer |

Valid transitions:

```text
unverified -> active -> suspended -> active
active -> deletion_pending -> active
deletion_pending -> anonymized -> purged
unverified -> deletion_pending
```

## RoleAssignment

Composite uniqueness on `(account_id, role)` where role is `traveler`, `data_curator`, or `administrator`. Includes grant time, optional granting actor, and revocation time. Authorization considers only non-revoked rows.

## Session

| Field | Rules |
|-------|-------|
| `session_id` | UUID primary key |
| `account_id` | Required account reference, cascade on final purge |
| `family_id` | UUID grouping refresh rotations |
| `access_hash`, `refresh_hash` | Unique SHA-256 hex digests; never serialized |
| `access_expires_at`, `refresh_expires_at` | UTC, access earlier than refresh |
| `rotated_at`, `revoked_at`, `revoke_reason` | Nullable transition evidence |
| `device_label`, `client_kind` | Privacy-safe, bounded metadata |
| `last_seen_at`, `created_at` | Required UTC times |

Only the latest non-revoked row in a family is renewable. Replay of a rotated refresh credential revokes every row in that family.

## OneTimeAction

Shared table for `verify_email`, `recover_password`, and `cancel_deletion` actions. Fields include action UUID, account reference, purpose, unique token hash, creation/expiry/used/superseded times, attempt count, delivery state (`pending`, `sent`, `delayed`, `failed`), and correlation identifier. At most one usable action per account/purpose.

## PasswordHistory

Account reference, encoded password hash, and replacement time. The current hash is compared before reset; retention is bounded to the current and most recent prior entry for MVP.

## AccountLifecycleEvent

Append-only row containing event UUID, account reference or anonymized subject reference, event type, actor reference when applicable, UTC time, correlation identifier, and safe metadata. It never stores email, credentials, action values, or provider bodies.

## SecurityAuditEvent

Append-only security outcome with category, outcome, account/anonymous subject reference, session reference where safe, correlation ID, UTC time, and bounded metadata. Email and client addresses are represented only by one-way digests when needed.

## ExportRequest

| Field | Rules |
|-------|-------|
| `export_id` | UUID primary key |
| `account_id` | Required owner reference |
| `status` | `pending`, `ready`, `expired`, `failed` |
| `payload` | Nullable JSON; identity-owned fields only, no hashes/secrets |
| `checksum` | SHA-256 of canonical payload when ready |
| `created_at`, `ready_at`, `expires_at` | UTC lifecycle times |
| `correlation_id`, `error_code` | Safe diagnostics |

## DevelopmentDelivery

Runtime-only entry containing recipient, purpose, plaintext action, and expiry. It exists only in process memory when dev inbox is explicitly enabled and is never backed up, logged, or available in production.

## Relationships and deletion

- Account owns roles, sessions, actions, password history, exports, and lifecycle/security references.
- Deletion request revokes sessions but preserves account ownership during the grace period.
- Purge removes credentials, roles, sessions, actions, password history, and export payloads; the account email is replaced with an irreversible tombstone before the final `purged` state.
- Minimized lifecycle/security events retain an anonymized subject reference and no foreign key requiring personal account data.
