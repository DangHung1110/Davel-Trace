# Quickstart: Identity and Access Demo

## Prerequisites

- Docker Desktop is running.
- Python environment and shared Flutter SDK from increment 005 are available.
- `BE/.env` contains the local PostgreSQL connection and `IDENTITY_DEV_OUTBOX_ENABLED=true`; never commit this file.

## Start and migrate

```powershell
docker compose --env-file BE/.env up -d postgres
\.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini upgrade head
\.\.venv\Scripts\python.exe -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

Expected readiness reports schema revision `006_001` and a ready database.

## Run the mobile-sized web demo

```powershell
& '.\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
```

At the sign-in screen:

1. Register a new email and accept terms.
2. Open the visibly labeled development inbox helper, copy the verification action, and verify.
3. Sign in; open Account security and observe the current session.
4. Sign in through an incognito window, then revoke the first session.
5. Request password recovery, complete it through the dev inbox, and prove old sessions/password fail.
6. Request/download the identity export.
7. Request account deletion and observe immediate sign-out.
8. Cancel deletion through a fresh verified action; sign in again.
9. Use “Tiếp tục với dữ liệu demo” to show that the old map/planner shell still works and is explicitly labeled.

## DBeaver

Use host `127.0.0.1`, port `5432`, database `davel_trace`, user `davel`, and the password from ignored `BE/.env`. Inspect `accounts`, `role_assignments`, `sessions`, `one_time_actions`, `account_lifecycle_events`, and `security_audit_events`. Credential/action columns must contain hashes rather than values used in the browser.

## Validation

```powershell
\.\.venv\Scripts\python.exe -m pytest BE\tests\unit\test_identity_*.py BE\tests\contract\test_identity_api.py BE\tests\integration\test_identity_postgres.py -q
& '.\.flutter-sdk\bin\flutter.bat' analyze FE
& '.\.flutter-sdk\bin\flutter.bat' test FE\test
```

Run the existing student-scope backend suite and PMTiles/map/search/route/playback smoke checks before review. High-cost exact optimizer benchmarks remain outside the routine student demo gate unless their code changes.

## Stop without deleting data

```powershell
docker compose --env-file BE/.env down
```

Do not use `down -v` or global Docker prune for routine cleanup.
