# Quickstart: Personalized Travel Agent MVP

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
Validation scenarios proving end-to-end behavior. Details: `data-model.md`, `contracts/api.md`.

## Prerequisites
- Python 3.11, `pip install -r BE/requirements.txt` (fastapi, uvicorn, ortools, lightgbm, pydantic, pytest, httpx)
- Ollama with `qwen3:14b` pulled (parser/explanation/judge) — or set `LLM_API_URL` fallback
- Seed snapshot: 7 Da Nang POIs (from Flutter `DemoTripData`) at `data/snapshots/danang-v1/pois.json`
- Cached 7×7 route matrix at `data/snapshots/danang-v1/matrix.json`

## Run
```powershell
uvicorn BE.app.main:app --port 8000
pytest BE/tests -q
```

## Scenarios
- **S1 health**: `GET /v1/health` → `{"status":"ok","snapshot":"danang-v1"}`.
- **S2 parse**: `POST /v1/parse` Vietnamese weekend trip → TripRequest JSON, all required slots filled or `needs_clarification` listed.
- **S3 plan**: `POST /v1/itinerary` with S2 output → ≥2 feasible plans (savings/balanced/experience) each with cost, times, scores, explanations; hiking before beach when preferred.
- **S4 gate**: tamper one plan (closed POI / over budget) → `POST /v1/evaluate` fails gate with named violation, no quality scores.
- **S5 replan**: mark 2 activities done, send "trời mưa" event → `POST /v1/replan` keeps done items, replaces outdoor remainder, bumps version.
- **S6 expense**: set budget 3,000,000 → log 2,500,000 → summary shows 500,000 left + 83% alert.
- **S7 PATM**: `POST /v1/score-transition` hiking→beach vs beach→hiking → first scores higher.

## Expected outcomes
All scenarios green on seed data before scaling snapshot to 100–200 POIs.
Evaluator tier-1 metrics (FAR/VROH/BCS/TCS/HCS) all pass on S3 outputs.
