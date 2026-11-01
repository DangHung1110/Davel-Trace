# Implementation Plan: Identity and Access

**Branch**: `task/006-identity-access` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-identity-access/spec.md`

## Summary

Add a durable identity capability to the existing modular FastAPI/PostgreSQL backend and a Vietnamese-first authentication flow to the Flutter client. Accounts, roles, sessions, one-time verification/recovery actions, lifecycle evidence, and identity exports are authoritative in PostgreSQL. Passwords use a memory-hard one-way hash; access and refresh credentials are opaque random values stored only as hashes. A development-only delivery inbox supports laptop demonstrations without a real email provider. The existing demo management, planner, map, PMTiles, OSRM, and AI-disabled behavior remain compatible and explicitly labeled.

## Technical Context

**Language/Version**: Python 3.11 backend; Dart 3.13 / Flutter 3.47 client

**Primary Dependencies**: FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3; `pwdlib[argon2]` for password hashing; Flutter `http`, `shared_preferences`, and `flutter_secure_storage`

**Storage**: PostgreSQL 16 is authoritative; tokens are stored only as SHA-256 hashes; device credentials use platform secure storage; demo delivery secrets exist only in process memory

**Testing**: pytest with FastAPI/httpx and PostgreSQL integration coverage; Flutter analyze and widget/unit tests; existing static PMTiles smoke checks

**Target Platform**: FastAPI service on local/deployed Linux or Windows; Flutter web laptop demo at 390×844 plus Android/iOS-compatible code paths

**Project Type**: Mobile/web Flutter client plus modular-monolith HTTP API

**Performance Goals**: Normal identity actions acknowledge within two seconds locally; password hashing remains deliberately expensive but below one second on the demo laptop; protected-request authorization adds less than 100 ms locally

**Constraints**: No credential/token in Git or logs; no JWT signing-key lifecycle; private access fails closed; demo outbox disabled in production; no AI dependency; no direct changes to planner feasibility; no Docker image build or extra stateful service

**Scale/Scope**: Student-project MVP and local demonstration, designed for thousands of accounts and sessions without introducing Redis, a message broker, or microservices

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1.*

| Principle | Result | Evidence |
|-----------|--------|----------|
| Feasibility-first | PASS | Identity does not call or alter planning, ranking, routing, or hard gates. |
| Spec-driven development | PASS | `spec.md`, this plan, design artifacts, checklist, tasks, analysis, implementation, and convergence are sequenced. |
| Test-first | PASS | Identity contract, domain, persistence, and Flutter state tests precede endpoint and screen completion. Existing planner tests remain regression gates. |
| Data provenance and honesty | PASS | Demo identities and delivery inbox are explicit; credentials and tokens never enter logs or committed data. |
| Simplicity and tier discipline | PASS | One backend module and existing PostgreSQL are reused; opaque tokens avoid JWT/key infrastructure; no Redis or email vendor is added. |
| Mobile contract | PASS | Flutter remains primary; the auth flow targets 390×844; management demo remains usable after authentication or explicit demo bypass. |
| PostgreSQL authority | PASS | All production identity state is persisted through SQLAlchemy and Alembic revision `006_001`; no in-memory production fallback. |
| Git governance | PASS | Work remains on `task/006-identity-access`, then PRs into `feat/product-platform`; protected branches and remote refs are untouched. |

Post-design re-check: PASS. The contracts preserve foundation error/correlation behavior, the schema uses the existing authoritative database, and development-only delivery is isolated by application mode.

## Architecture Decisions

### Authentication model

- Email/password only for this increment.
- Password hashes use Argon2 through `pwdlib`; parameters are encoded with each hash and can be upgraded on successful authentication.
- Access credentials are random opaque values valid for 15 minutes. Refresh credentials are random opaque values valid for 30 days.
- Email verification actions expire after 24 hours; password-recovery and deletion-cancellation actions expire after 30 minutes. Destructive account actions require authentication within the previous 10 minutes.
- Default fixed-window limits are 5 login attempts per normalized-identity/client pair per 15 minutes, 3 verification-resend or recovery requests per pair per 15 minutes, 10 action-confirm attempts per action, and 10 refresh attempts per session per minute. Configuration may lower these values in production but tests bind the defaults.
- Only SHA-256 credential hashes are stored. Refresh rotates both credentials; reuse of an already-rotated refresh credential revokes that session family.
- Flutter holds access credentials in memory and stores only the refresh credential through secure storage. Demo/test repositories implement the same contract and are visibly labeled.

### Capability boundary

`BE/app/modules/identity` owns domain states, password/token policy, use cases, repositories, delivery interfaces, and API composition. It may import platform configuration, database lifecycle, error/correlation primitives, and clock/identifier helpers. Other business capabilities consume an identity authorization contract and never query identity tables directly.

### Delivery model

Delivery is a port with a development in-memory implementation and a fail-closed production placeholder until a provider is configured. A dev inbox endpoint is mounted only in `demo` or `test` mode and requires an explicit `IDENTITY_DEV_OUTBOX_ENABLED=true`; production startup rejects that flag. Plaintext actions never enter the database or ordinary logs.

### Account lifecycle

Deletion immediately moves the account to `deletion_pending`, revokes all sessions, and schedules purge after 30 days. Cancellation uses a new one-time action. A maintenance command performs due purges idempotently. Identity export is a durable request whose JSON payload initially contains identity-owned data and expands in later increments.

## Project Structure

### Documentation (this feature)

```text
specs/006-identity-access/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   ├── authorization.md
│   └── mobile.md
├── checklists/
│   ├── requirements.md
│   └── security.md
└── tasks.md
```

### Source Code (repository root)

```text
BE/
├── alembic/versions/006_001_identity_access.py
├── app/
│   ├── core/config.py
│   ├── db/models.py
│   ├── main.py
│   └── modules/identity/
│       ├── __init__.py
│       ├── api.py
│       ├── application.py
│       ├── domain.py
│       ├── infrastructure.py
│       ├── security.py
│       └── delivery.py
├── scripts/purge_accounts.py
└── tests/
    ├── contract/test_identity_api.py
    ├── integration/test_identity_postgres.py
    └── unit/test_identity_*.py

FE/
├── lib/
│   ├── app.dart
│   ├── core/auth/
│   │   ├── auth_session_store.dart
│   │   └── secure_auth_session_store.dart
│   └── features/auth/
│       ├── auth.dart
│       ├── application/auth_controller.dart
│       ├── data/auth_repository.dart
│       ├── data/http_auth_repository.dart
│       ├── domain/models.dart
│       └── presentation/
│           ├── auth_gate.dart
│           ├── sign_in_screen.dart
│           ├── register_screen.dart
│           ├── verify_screen.dart
│           ├── recovery_screen.dart
│           └── security_screen.dart
└── test/
    ├── auth_controller_test.dart
    ├── auth_flow_test.dart
    └── auth_mobile_layout_test.dart
```

**Structure Decision**: Extend the capability-based modular monolith and Flutter feature-first structure established by increment 005. Identity receives one backend module and one Flutter feature; legacy management and planner code remain behind existing compatibility boundaries.

## Migration and Compatibility

1. Add revision `006_001` after `005_001`; upgrade and downgrade affect identity tables only.
2. Add configuration with safe defaults for timeouts and an explicit production prohibition on dev outbox.
3. Mount `/v1/auth`, `/v1/account`, and `/v1/dev/identity` routes without changing existing planner routes.
4. Introduce the Flutter auth gate while retaining a clearly labeled seeded-demo entry that reaches the current shell.
5. Preserve foundation error envelopes and `X-Correlation-ID` on every response.
6. Backup/restore manifests gain identity counts and representative relationships without exposing email or hashes.

## Validation Strategy

- Unit: normalization, password policy/hash upgrade, token hashing/rotation, lifecycle transitions, authorization matrix, and safe serialization.
- Contract: all API successes/failures, non-enumeration, correlation headers, no secret fields, idempotency, and dev-outbox mode gates.
- Integration: empty upgrade, `005_001 → 006_001`, persistence across restart, concurrent duplicate registration, session revocation/refresh reuse, backup/restore.
- Flutter: controller transitions, secure persistence adapter, all auth screens, keyboard/text-scale behavior, 390×844 golden-style overflow checks, and seeded-demo labeling.
- Regression: student-scope backend suite, Flutter analyze/tests/release web build, PMTiles 206, search/route/playback smoke, and AI-disabled identity demo.

## Complexity Tracking

No constitution violations require justification. The two new small dependencies directly implement approved password hashing and platform credential storage; no new service, container, or database is introduced.
