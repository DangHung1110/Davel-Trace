# Quickstart Validation: Product Platform Foundation

This is the expected end-to-end validation after implementation, not a substitute for migration review.

## Prerequisites

- Git and Python 3.11
- Docker Desktop with Compose, or accessible PostgreSQL 16
- Bundled `.flutter-sdk` or compatible Flutter SDK
- Chrome; DBeaver Community is optional

## 1. Configure

PowerShell:

```powershell
Copy-Item BE\.env.example BE\.env
```

Git Bash:

```bash
cp BE/.env.example BE/.env
```

Set a local-only PostgreSQL password and matching `DATABASE_URL` in `BE/.env`. Never commit this file.

## 2. Start PostgreSQL

```powershell
docker compose --env-file BE/.env up -d postgres
docker compose --env-file BE/.env ps
```

Expected: `postgres` is healthy. Compose reads the same local `BE/.env` contract as the backend. With external PostgreSQL, skip Compose and set `DATABASE_URL`.

Disk-safe lifecycle:

```powershell
# Stop while preserving the one shared named volume
docker compose --env-file BE/.env down

# Inspect usage; do not run global prune as part of project setup
docker system df
```

The Compose project has a fixed name, an Alpine image, no application build,
and rotated logs (maximum 3 × 10 MB). `down -v` is a manual destructive reset,
never an automatic cleanup step.

## 3. Apply code-first migrations

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r BE\requirements.txt
.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini current
```

Git Bash:

```bash
./.venv/Scripts/python.exe -m pip install -r BE/requirements.txt
./.venv/Scripts/python.exe -m alembic -c BE/alembic.ini upgrade head
./.venv/Scripts/python.exe -m alembic -c BE/alembic.ini current
```

Expected: current revision equals repository head; repeating `upgrade head` is a no-op.

## 4. Optional legacy import

```powershell
.\.venv\Scripts\python.exe -m BE.scripts.import_acceptance_sqlite --source BE\data\accepted_plans.db
```

Run twice. Expected: the second run reports the fingerprint already imported and counts do not grow.

## 5. Start backend and check health

```powershell
.\.venv\Scripts\python.exe -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
curl.exe -i http://127.0.0.1:8000/v1/health
curl.exe -i http://127.0.0.1:8000/v1/ready
```

Expected: both carry `X-Correlation-ID`; health preserves `status` and `snapshot`; readiness reports database, schema, catalog, and optional providers; required failure returns 503 without exposing `DATABASE_URL`.

## 6. DBeaver

Create a PostgreSQL connection using local `BE/.env` values:

```text
Host: localhost
Port: 5432
Database: davel_trace
Username: davel
Password: local BE/.env value
```

Expected tables: `alembic_version`, `acceptance_records`, `shadow_observations`, `import_runs`, and `seed_runs`.

## 7. Backend tests

```powershell
.\.venv\Scripts\python.exe -m pytest BE\tests -q
```

Expected: unit, contract, integration, architecture, migration, and import tests pass. PostgreSQL integration tests do not silently switch to SQLite.

## 8. Flutter validation and laptop demo

```powershell
& '.\.flutter-sdk\bin\flutter.bat' pub get --directory FE
& '.\.flutter-sdk\bin\flutter.bat' analyze FE
Push-Location FE
& '..\.flutter-sdk\bin\flutter.bat' test
Pop-Location
& '.\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Git Bash:

```bash
./.flutter-sdk/bin/flutter.bat run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Expected: phone frame appears; itinerary, map, expenses, and profile navigation work; failed production persistence is not presented as a local success.

## 9. Root PMTiles regression

```powershell
python server.py
curl.exe -I -H "Range: bytes=0-99" http://127.0.0.1:5500/data/danang.pmtiles
```

Expected: `206 Partial Content`; map, search A/B, route fallback, and vehicle play/pause remain functional.

## 10. Backup/restore proof

```powershell
.\.venv\Scripts\python.exe -m BE.scripts.backup_database --output D:\Backups\davel_trace.dump
.\.venv\Scripts\python.exe -m BE.scripts.restore_verify `
  --archive D:\Backups\davel_trace.dump `
  --manifest D:\Backups\davel_trace.dump.json
```

The verifier restores into `davel_trace_restore_check`, compares checksum,
Alembic revision, table counts and representative IDs, then always drops the
temporary database so the Docker volume does not accumulate restore copies.
