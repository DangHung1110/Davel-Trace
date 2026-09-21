# Implementation Plan: Personalized Travel Agent MVP

**Branch**: `001-travel-agent-mvp` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-travel-agent-mvp/spec.md`

## Summary

Vietnamese travel-agent backend + Flutter client for Da Nang: NL parsing →
POI retrieval → preference-aware CP-SAT optimization → feasibility gate →
explanation → dynamic replan, with expense tracking and weather awareness.
LLM acts as Modeler (never route generator); LightGBM PATM scores transitions;
evaluator enforces TravelEval tier-1/2 gates. See `research.md` for decisions.

## Technical Context

**Language/Version**: Python 3.11 (BE), Dart/Flutter (FE, existing app)
**Primary Dependencies**: FastAPI, OR-Tools (CP-SAT), LightGBM, Pydantic, Ollama (Qwen3-14B)
**Storage**: Versioned JSON snapshot (TravelEval schema) + SQLite runtime; OSRM matrix cache
**Testing**: pytest; TravelEval deterministic metrics; 30–50 ĐN tests; gold via Approach B
**Target Platform**: Android/iOS via Flutter; demo BE on MacBook (local, offline-capable)
**Project Type**: Mobile app + Python API backend
**Performance Goals**: parser <10s, itinerary <30s, replan <15s, PATM inference <5ms, CP-SAT timeout 5s
**Constraints**: Da Nang only; 1–2 days; Vietnamese-only; offline map; no booking/payment; no secrets in code
**Scale/Scope**: 100–200 POIs, 30–50 test queries, team 3, deadline 2026-12-15

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Feasibility-First: gate before scoring in evaluator design — PASS.
- II. Spec-Driven: spec → plan → tasks → analyze sequence followed — PASS.
- III. Test-First: validator/evaluator tasks precede optimizer tuning; bars defined — PASS.
- IV. Data Provenance: snapshot schema + uncertainty labels + `.env` secrets — PASS.
- V. Tier Discipline: nấc 1→2→3, no RL/GPU/multi-city/voice/booking — PASS.
- VI. Mobile Contract: Flutter + FastAPI + latency budgets + offline map — PASS.

Post-design re-check: no new violations. Structure extends existing repo (no new projects without need).

## Project Structure

### Documentation (this feature)

```text
specs/001-travel-agent-mvp/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── api.md           # REST contracts BE ↔ Flutter
├── checklists/          # Spec quality (from /speckit.specify)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
BE/
├── app/
│   ├── main.py            # FastAPI wiring
│   ├── routers/           # parse, itinerary, replan, expenses, weather, evaluate
│   ├── services/          # parser, recommender, optimizer, validator, explainer, event_classifier
│   └── schemas/           # Pydantic models (mirrors data-model.md)
├── ml/
│   ├── patm/              # features, train.py, model.txt, onnx/
│   └── event_clf/         # templates, paraphrase, train.py
├── eval/
│   ├── metrics.py         # tier-1 deterministic (FAR/VROH/BCS/TCS/HCS/STR/DTU/SSR/CSM/EDI/AQE)
│   ├── judge.py           # LLM-judge Profit/BE
│   └── gold/              # 30–50 ĐN tests + Approach-B generator
├── data/
│   └── snapshots/danang-v1/  # pois.json, matrix.json, weather_cache.json
└── tests/                 # unit + integration (mirrors quickstart S1–S7)

FE/ (existing Flutter app)
├── lib/api/               # BE client (replaces in-memory demo)
└── lib/features/{itinerary,map,expenses}/  # plan cards, selectors, budget UI
```

**Structure Decision**: Extend the existing Davel-Trace layout (BE/ reserved +
Flutter FE in progress + root web demo untouched). Closest to template Option 3
(Mobile + API): `BE/` = api/, `FE/` = mobile. No new top-level projects.

## Complexity Tracking

> No constitution violations to justify. Table intentionally empty.
