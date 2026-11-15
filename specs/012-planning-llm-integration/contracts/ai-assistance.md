# Contract: AI Assistance

User-owned endpoints require the existing bearer session and verify ownership before external calls.

## POST `/v1/trips/{trip_id}/ai/interpretations`

Request: `{ "text": "Cuối tuần đi Đà Nẵng 2 người, 3 triệu, phải ghé Cầu Rồng" }`.

Response contains `proposal_id`, `trip_id`, `status`, proposed `fields`, `hard_constraints`, `soft_preferences`, `assumptions`, `unresolved`, and non-secret provider/model labels. It is a proposal only; the client reviews it before submitting confirmed overrides.

Errors: ownership errors before provider invocation; `422 VALIDATION_ERROR`; normalized `503 LLM_DISABLED|LLM_CONFIG|LLM_AUTH|LLM_QUOTA|LLM_SAFETY|LLM_TIMEOUT|LLM_TRANSPORT|LLM_BAD_JSON|LLM_SCHEMA`.

## POST `/v1/itinerary-alternatives/{alternative_id}/ai/explanation`

The server loads one owned persisted alternative and constructs minimized evidence. Response contains `alternative_id`, `data_version`, `source`, `summary`, cited `reasons`, deterministic `warnings`, and non-secret provider/model labels. AI failure or invalid citations returns a deterministic explanation with HTTP 200 and no fabricated provider success.

## GET `/v1/ai/readiness`

Returns provider/model labels, configured/available/external-processing state, per-capability flags and last normalized failure. It never returns keys or raw provider errors.

## Existing planning request extension

`POST /v1/trips/{trip_id}/planning-requests` accepts confirmed `constraint_overrides` for budget, travelers, must-visit, avoidances, activities, food preferences and hard/soft preferences. Raw interpretation text/output is excluded from persistence.
