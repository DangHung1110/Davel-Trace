# Quickstart: Stable Planner and Gemini Validation

## Prerequisites

- Python 3.11 with `BE/requirements.txt`.
- Flutter SDK.
- PostgreSQL and `DATABASE_URL` for lifecycle integration tests.
- Optional Gemini Developer API key from Google AI Studio; a Gemini consumer subscription does not replace this key.

## Deterministic validation without AI

```powershell
Copy-Item BE\.env.example BE\.env
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
