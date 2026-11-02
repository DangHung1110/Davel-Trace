# Validation: Identity and Access

**Date**: 2026-11-01
**Branch**: `task/006-identity-access`
**Database revision**: `006_001`

## Backend

- Alembic upgraded the existing local PostgreSQL database from `005_001` to `006_001`; `alembic current` reports `006_001 (head)`.
- Full proportional student regression: **755 passed, 2 skipped, 3 existing SWIG deprecation warnings** in 165.98 seconds.
- Excluded exactly `BE/tests/unit/test_baselines.py` and `BE/tests/unit/test_benchmark_optimizer.py`, the two heavyweight benchmark/exact-optimizer files previously approved for the student-project gate.
- Final identity/security/architecture convergence run: **20 passed in 4.62 seconds**.
- Architecture, secret, backup, migration, identity sweep: **21 passed**.
- Register → verify → login → current account → role refresh → session refresh/replay rejection → export → recovery → old-session rejection → deletion → cancellation is covered against PostgreSQL by `BE/tests/contract/test_identity_api.py`.
- Due-account purge is scoped and idempotent; the disposable fixture is removed after validation.
- The contract suite asserts login completes in under two seconds and a protected
  current-account authorization resolves in under 100 ms on the local demo machine.
  Retried login with the same account-bound idempotency key returns the same session.
- Security audit assertions cover registration, verification, login, refresh, export,
  recovery, deletion request, deletion cancellation, and denied recent-auth evidence.

## Flutter

- Dependency resolution succeeded with `flutter_secure_storage 11.2.0`, which is compatible with existing `geolocator 14.1.1`.
- `flutter analyze --no-pub`: **No issues found**.
- Complete Flutter suite: **20 passed**.
- Mobile auth widget runs at 390×844 and 200% text scale without overflow; every
  primary sign-in, registration, recovery, deletion-cancellation, and demo action is reachable.
- Protected requests perform at most one refresh-and-retry, and never recursively
  retry the refresh endpoint. Account export requires a password and exposes portable,
  selectable JSON with a clipboard action.
- Release web build succeeded in 107 seconds at `FE/build/web`; build output remains ignored.

## Persistence and evidence

- Live evidence collection reports schema `006_001` and includes counts for accounts, roles, identity sessions, actions, and exports without emails or credential hashes.
- Test-created accounts/sessions/actions are cleaned; final identity table counts were zero after the focused run.
- Planning evidence remained present (`acceptance_records`: 10) and the full planner regression stayed green.
- Backup manifest/restore comparison now includes identity counts and representative account/session/role relationships without personal data.

## Docker and disk discipline

- Reused existing `postgres:16-alpine` container and named volume; no application image was built.
- Docker build cache: **0 B**.
- No global prune and no `docker compose down -v` were run.
- PostgreSQL remained healthy on port 5432 for DBeaver/demo use.

## Security scope for learning project

- Argon2 password hashes and SHA-256 opaque-token hashes are authoritative; plaintext password/token values are absent from PostgreSQL evidence and ordinary logs.
- Access tokens are memory-only in Flutter; refresh tokens use secure storage.
- Dev inbox is explicit, process-memory-only, and rejected in production mode.
- Basic single-process rate limiting is included. Shared multi-worker abuse infrastructure, MFA, social login, and a production email provider remain deliberately deferred.

## Static and compatibility smoke

- Full backend regression includes PMTiles byte-range/static server and existing planner/search/route/expense behavior.
- Flutter regression includes desktop phone frame, itinerary, map, expenses, profile, seeded/live/stale labels, and API correlation diagnostics.
- Core identity operates with AI providers disabled; no identity code imports planner or AI services.
