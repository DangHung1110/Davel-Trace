# API Contracts: BE ↔ Flutter (`v1`)

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
Base: `http://<be-host>:8000/v1`. All bodies JSON, Pydantic-validated.
Errors: `{ "error": "<code>", "message": "<vi>" }`.

## POST /parse — NL → TripRequest
- In: `{ "text": "cuối tuần đi Đà Nẵng 2 người 3 triệu thích biển", "user_id": "u1" }`
- Out: `TripRequest` (data-model.md) OR `{ "needs_clarification": ["budget", ...] }`

## POST /itinerary — TripRequest → plans
- In: `{ "trip": {TripRequest}, "profiles": ["savings", "balanced", "experience"] }`
- Out: `{ "plans": [{Itinerary + scores + explanations}], "selected": null }`
- Rule: every plan passed feasibility gate; ≥2 plans when feasible.

## POST /itinerary/select — chốt plan
- In: `{ "itinerary_id": "..." }` → Out: `{ "active_id": "..." }`

## POST /replan — disruption → new version
- In: `{ "itinerary_id": "...", "event": {DynamicEvent} }`
- Out: `{ "itinerary": {Itinerary v+1}, "mode": "plan|clarify|no_solution", "changes": [...] }`
- Rule: completed activities preserved; version++.

## GET /itinerary/{id} — đọc lịch (offline cache key)

## POST /expenses + GET /expenses/summary?trip_id=
- In: `{ "trip_id": "...", "label": "Mì Quảng", "amount": 120000, "kind": "food" }`
- Out summary: `{ "budget": 3000000, "spent": 2500000, "left": 500000, "alert": "80%" }`

## GET /weather?lat=&lon= — Open-Meteo snapshot (cached + `fetched_at`)

## POST /evaluate — itinerary → scores
- In: `{ "itinerary": {...}, "trip": {TripRequest} }`
- Out: `{ "gate": {"passed": bool, "violations": [...]}, "soft": {...}, "reward": 0.0 }`
- Rule: gate fail → no quality scores.

## POST /score-transition — PATM (debug/mobile pre-check)
- In: `{ "a": {poi+ctx}, "b": {poi+ctx}, "user": {...} }`
- Out: `{ "score": 0.82 }` (<5ms target)
