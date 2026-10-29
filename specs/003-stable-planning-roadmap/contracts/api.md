# API Contract Addendum: Stable Planning Roadmap MVP

Base: `http://<host>:8000/v1`. JSON. Existing error envelope remains `{"error":"CODE","message":"Vietnamese text"}`.

## POST /itinerary?diverse=true

Request remains the existing `{"trip": TripRequest, "profiles": [...]}` contract.

Response additions:

```json
{
  "plans": [
    {
      "itinerary_id": "uuid",
      "trip_id": "t1",
      "deterministic_rank": 1,
      "gate": {
        "passed": true,
        "failed_families": [],
        "families": {
          "temporal": {"passed": true, "score": 1.0, "checks": []},
          "financial": {"passed": true, "score": 1.0, "checks": []},
          "movement": {"passed": true, "score": 1.0, "checks": []},
          "safety_data": {"passed": true, "score": 1.0, "checks": []},
          "traveler_constraints": {"passed": true, "score": 1.0, "checks": []}
        }
      },
      "data_version": "danang-v1",
      "shadow": {"status": "disabled", "authoritative": false}
    }
  ],
  "selected": null,
  "solution_pool": {
    "target": 5,
    "returned": 5,
    "shortage_reason": null
  },
  "shadow": {"status": "disabled", "authoritative": false}
}
```

Rules: only family-passing plans appear. Target is five in diverse mode. A smaller list is valid only with `shortage_reason`: `insufficient_feasible_supply`, `duplicates_removed`, `time_budget_exhausted`, or `planner_failure`.

## POST /itinerary/select

```json
{
  "itinerary_id": "uuid",
  "idempotency_key": "mobile-generated-key",
  "parent_acceptance_id": null
}
```

Success:

```json
{
  "active_id": "uuid",
  "acceptance": {
    "acceptance_id": "uuid",
    "itinerary_id": "uuid",
    "trip_id": "t1",
    "selected_at": "2026-10-28T12:00:00Z",
    "schema_version": 1,
    "data_version": "danang-v1"
  }
}
```

If `idempotency_key` is omitted, the server generates one, persists the acceptance, and preserves the legacy response shape `{"active_id":"..."}` so existing clients do not break. A supplied key returns the acceptance summary shown above and retries return the same acceptance. Unknown or gate-failing plans return the existing 404/422 envelope and write nothing.

## GET /acceptances/{acceptance_id}

Returns a complete decoded immutable record including `request`, `plan`, `gate`, deterministic evidence, and optional shadow link. Unknown ID: 404 `UNKNOWN_ACCEPTANCE`.

## GET /acceptances?trip_id=t1&limit=50

Returns `{"items": [...], "count": N}`, newest first. `limit` range 1–200.

## POST /shadow/evaluate

Request:

```json
{"trip_id":"t1","itinerary_ids":["uuid-a","uuid-b","uuid-c"]}
```

All IDs must exist and pass the hard gate. Success returns a non-authoritative observation. Unavailable judge returns HTTP 200 with `status: "unavailable"`; it never rewrites plan order.

## GET /planning/readiness

Returns threshold counts and booleans for pairwise learning, full-day learning, accepted-day retrieval, and judge calibration. Missing/insufficient evidence is represented by `enabled: false` and nullable metrics, never fabricated values.

## Backward Compatibility

- Existing clients may keep sending only `itinerary_id` to select.
- Existing response fields remain present.
- Existing expense, weather, parse, evaluate, replan, review, and repair contracts remain unchanged.
