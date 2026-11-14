# Quickstart: Stable Planner and Gemini Validation

## Prerequisites

- Python 3.11 with `BE/requirements.txt`.
- Flutter SDK.
- PostgreSQL and `DATABASE_URL` for lifecycle integration tests.
- Optional Gemini Developer API key from Google AI Studio; a Gemini consumer subscription does not replace this key.

## Current local checkout and database

The active Task 012 checkout is now `D:\Project\PBL6`, branch
`task/012-planning-llm-integration`. Backend settings load **this checkout's**
`BE/.env`. The older worktree is detached at `2877e5e` and is no longer the
running application's working directory. Do not copy an older worktree env
over the current credentials.

The existing local demo uses `COMPOSE_PROJECT_NAME=davel-trace-task012-demo`,
`POSTGRES_PORT=5437`, database `davel_trace`, user `davel`, and the password
in the ignored env. `DATABASE_URL` must use the same port and password.
The example file uses placeholders and is only for a new setup.

From the checkout root:

```powershell
docker compose --env-file BE/.env up -d postgres
docker compose --env-file BE/.env ps
```

`COMPOSE_PROJECT_NAME` selects the existing project/volume even though the
Compose file has a default name. Changing a password in env does not change
the password already initialized in a volume. Preserve existing volumes.

For DBeaver use PostgreSQL, host `127.0.0.1`, port `5437`, database
`davel_trace`, username `davel`, password from `POSTGRES_PASSWORD` in env.
The local schema head is `010_001`.

## Deterministic validation without AI

```powershell
if (!(Test-Path BE\.env)) { Copy-Item BE\.env.example BE\.env }
# Set DATABASE_URL and keep LLM_PROVIDER=disabled.
python -m pytest BE/tests/unit BE/tests/contract -q
python -m uvicorn BE.app.main:app --port 8000
```

Structured planning/selection/history must work, and `/v1/ai/readiness` must expose no secret.

## Gemini configuration

Put only in ignored `BE/.env`:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=replace-with-your-key
LLM_MODEL=gemini-3.1-flash-lite
LLM_API_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_TIMEOUT_SECONDS=20
LLM_MAX_RETRIES=1
LLM_PARSE_ENABLED=true
LLM_EXPLANATION_ENABLED=true
LLM_SHADOW_ENABLED=false
```

Restart backend. Interpretation should return a reviewable proposal. Removing the key should produce an AI-specific error while structured planning remains functional.

## Validation

```powershell
python -m pytest BE/tests -q
python BE/tools/audit_plans.py --out "$env:TEMP/davel-task012-audit.json" --plans "$env:TEMP/davel-task012-plans.txt"
python BE/tools/bench_latency.py --snapshot BE/data/snapshots/danang-v1
Set-Location FE
flutter analyze
flutter test
flutter build web --release --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Use provider mocks in automated tests; a real key is only for explicit smoke testing. Validate prompt disclosure/review, structured fallback, explanation labels, map/route/expenses/offline regression and 390×844 layout.

Before commit:

```powershell
git diff --check
python -m pytest BE/tests/unit/test_no_secrets.py -q
```

Never commit `.env`, keys, runtime databases, raw provider responses, audit outputs or model caches.
