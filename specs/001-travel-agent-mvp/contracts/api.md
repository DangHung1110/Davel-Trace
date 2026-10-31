# API Contracts: BE ↔ Flutter (`v1`)

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
Base: `http://<be-host>:8000/v1`. All bodies JSON, Pydantic-validated.
Errors: `{ "error": "<code>", "message": "<vi>" }`.

## POST /parse — NL → TripRequest
- In: `{ "text": "cuối tuần đi Đà Nẵng 2 người 3 triệu thích biển", "user_id": "u1" }`
- Out: `TripRequest` (data-model.md) OR `{ "needs_clarification": ["budget", ...] }`

## POST /itinerary — TripRequest → plans
- In: `{ "trip": {TripRequest}, "profiles": ["savings", "balanced", "experience"] }`
- Out: `{ "plans": [{Itinerary + scores + explanations + activity_match}], "selected": null, "retrieval": {...} }`
- Rule: every plan passed feasibility gate; ≥2 plans when feasible.
- Rule (FR-006, FR-022): `activities` không bao giờ lọc bớt POI. Mỗi hoạt động hiểu được thành ràng buộc "ít nhất 1 điểm thuộc nhóm loại đó" cho bộ giải; không xếp được thì bỏ ràng buộc đó và cảnh báo. Mỗi plan có `activity_match: [{activity, categories, status}]`, `status` ∈ `met` / `unmet` / `no_verified_poi` / `not_understood`.
- Rule (FR-013, FR-024): `retrieval = { candidates, needs_verification_total, needs_verification: [{poi_id, name, cat, must_visit, reasons, uncertainty}] (tối đa 20, must_visit trước), excluded: {lý do: số POI}, unmatched_activities }`.
- Rule: pool rỗng sau bộ lọc cứng → plan rỗng `passed: false`, `infeasible_by.rule = "EMPTY_POOL"`; không bao giờ lấy toàn bộ snapshot thay thế.
- Rule: `constraint_status` có thêm cổng cứng `PROFILE_SAFE` (dị ứng / must_avoid / khả năng đi lại của hồ sơ, kiểm lại trên plan cuối).

- Rule (FR-020): `trip.days = 2` trả một plan cho cả chuyến. Mỗi phần tử `activities` và `segments` có `day` (1, 2); `days = [{day, date, stops, total_cost, total_km, total_min, travel_min, cost_estimated, passed, violations, template, soft_penalties}]`. Không điểm nào lặp giữa các ngày; `total_cost` và `passed` tính cho cả chuyến. Không xếp đủ số ngày → `passed: false` kèm cảnh báo. `days = 1` giữ nguyên dạng cũ (không có `day`, `days`).

## POST /itinerary/select — chốt plan
- In: `{ "itinerary_id": "..." }` → Out: `{ "active_id": "..." }`

## POST /replan — disruption → new version
- In: `{ "itinerary_id": "...", "event": {DynamicEvent}, "completed": [...], "day": 2 }`
- Out: `{ "itinerary": {Itinerary v+1}, "mode": "plan|clarify|no_solution", "changes": [...], "day": 2 }`
- Rule: completed activities preserved; version++.
- Rule (FR-020): plan nhiều ngày chỉ xếp lại một ngày: `day`, mặc định là ngày đầu tiên còn điểm chưa đi. Các ngày khác trả về nguyên vẹn. Ngày không có trong plan → 404 `UNKNOWN_DAY`.

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

## Env: LLM_PROVIDER (local|api)
- `local` (mặc định, demo day): parser/judge/explanation qua Ollama `http://localhost:11434` (Qwen3-14B).
- `api` (test env, BE deploy): qua GPT-4o-mini/Gemini Flash, temp 0.1. Key qua `.env`, không commit.
