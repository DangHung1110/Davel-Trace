# Quickstart: Profile and Trip Management Demo

## Prerequisites

- Docker Desktop running.
- Ignored `BE/.env` contains the existing PostgreSQL settings and `IDENTITY_DEV_OUTBOX_ENABLED=true` for local verification.
- Flutter SDK is available at the project-configured path.

## Start the stack (PowerShell)

```powershell
docker compose --env-file BE/.env up -d postgres
& '.\.venv\Scripts\python.exe' -m alembic -c BE\alembic.ini upgrade head
& '.\.venv\Scripts\python.exe' -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
& 'D:\Project\PBL6\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
```

Do not use `docker compose down -v` and do not run global Docker prune.

## Demo sequence

1. Register, verify, and sign in with a disposable account.
2. Complete profile onboarding with a soft preference and a hard allergy/accessibility constraint.
3. Edit and clear soft values; sign out/in and confirm persistence.
4. Create a three-day Da Nang trip; retry the same creation intent and verify one trip.
5. Review inherited values, add a soft override, and prove hard-constraint weakening is rejected.
6. Add activities to two days, reorder, complete/skip, and show a valid overlap warning.
7. Use a second session to edit the trip, then prove a stale first-session save reports a conflict without clearing its form.
8. Create another trip, switch active trip, restart, and prove exactly one selection remains.
9. Archive/restore, soft-delete/recover, and verify stable identity/nested content with no automatic activation.
10. Purge a disposable expired fixture and prove unrelated trips/accounts remain.
11. Sign in as a second account and prove no first-account profile/trip identifier is disclosed.
12. Disable AI/planner/POI/routing/expense providers and repeat profile/trip CRUD.

## DBeaver inspection

Use the connection values from ignored `BE/.env` (default host `127.0.0.1`, port `5432`, database `davel_trace`, user `davel`). Inspect:

- `traveler_profiles`
- `trips`
- `trip_days`
- `trip_activities`
- `active_trip_selections`
- `mutation_receipts`
- `trip_lifecycle_events`

Confirm owner relationships, one profile/account, one active selection/account, contiguous day/activity positions, positive versions, and hashed—not plaintext—idempotency keys.

## Validation commands

```powershell
& '.\.venv\Scripts\python.exe' -m pytest BE/tests/unit BE/tests/contract BE/tests/integration BE/tests/architecture -q
& 'D:\Project\PBL6\.flutter-sdk\bin\flutter.bat' analyze --no-pub
& 'D:\Project\PBL6\.flutter-sdk\bin\flutter.bat' test --no-pub
git diff --check
```

The proportional student gate may exclude the documented heavyweight optimizer/benchmark files when untouched, but must include identity, migration, architecture, PMTiles/static map, management, and Flutter regression coverage.

## Expected outcomes

- Migration head is `007_001` and downgrade to `006_001` does not alter identity/planning data.
- Profile/trip/day/activity data survives backend and client restart.
- Retry fixtures create no duplicates; stale edits never silently overwrite.
- Archive/delete clears active selection; restore keeps identity and returns non-active.
- Authenticated failure never shows seeded records as live account data.
- Existing identity, map, OSRM/playback, planning-demo, and expense-demo behaviors remain usable.
