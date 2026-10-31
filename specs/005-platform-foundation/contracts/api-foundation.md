# API Foundation Contract

## Compatibility policy

- Existing `/v1/*` requests and successful response fields remain compatible.
- New object fields may be added; existing fields are not renamed or removed in this increment.
- Every response includes `X-Correlation-ID`.
- Invalid caller-provided correlation IDs are replaced by a generated UUID.

## `GET /v1/health`

Process liveness remains available when PostgreSQL or optional providers are unavailable.

```json
{
  "status": "ok",
  "snapshot": "danang-v1",
  "correlation_id": "7eaa723a-d380-4d93-af7e-92a46ca76ef5"
}
```

`status` and `snapshot` preserve the existing contract.

## `GET /v1/ready`

Traffic readiness for production-backed operations.

```json
{
  "status": "ready",
  "mode": "production",
  "components": [
    {"name": "database", "required": true, "status": "ready"},
    {"name": "schema", "required": true, "status": "ready", "revision": "005_001"},
    {"name": "catalog", "required": true, "status": "ready", "version": "danang-v1"},
    {"name": "osrm", "required": false, "status": "degraded"},
    {"name": "ai", "required": false, "status": "degraded"}
  ],
  "correlation_id": "7eaa723a-d380-4d93-af7e-92a46ca76ef5"
}
```

Return 200 when required components are ready. Return 503 with `status: "not_ready"` when a required component is unavailable or schema is not at head. Optional degradation never changes readiness to 503.

## Error envelope

Existing endpoints retain their current `{error, message}` body during this
increment. `X-Correlation-ID` is the authoritative diagnostic metadata for
every response. New endpoints may also include the additive `correlation_id`
field shown below; compatibility endpoints adopt it only when their clients no
longer assert the exact legacy body.

```json
{
  "error": "DATABASE_UNAVAILABLE",
  "message": "Dữ liệu hệ thống đang tạm thời không khả dụng.",
  "correlation_id": "7eaa723a-d380-4d93-af7e-92a46ca76ef5",
  "details": {"field": "optional-safe-detail"}
}
```

`details` is optional and excludes credentials, connection strings, tokens, stack traces, provider bodies, and unnecessary personal data.

## Stable categories

| Category | HTTP | Meaning |
|----------|------|---------|
| `VALIDATION_ERROR` | 422 | Request fields fail validation |
| `AUTHENTICATION_REQUIRED` | 401 | Authentication missing/invalid; later increment |
| `FORBIDDEN` | 403 | Permission denied; later increment |
| `NOT_FOUND` or existing resource code | 404 | Resource absent |
| `CONFLICT` | 409 | Version/idempotency conflict |
| `DEPENDENCY_UNAVAILABLE` | 503 | Provider unavailable for action |
| `DATABASE_UNAVAILABLE` | 503 | Authoritative store unavailable |
| `SCHEMA_NOT_READY` | 503 | Migration revision invalid |
| `INTERNAL_ERROR` | 500 | Safe unexpected failure |

Existing domain-specific codes remain valid and gain correlation metadata.

## Correlation behavior

1. Flutter generates or reuses one ID per user action.
2. `ApiClient` sends `X-Correlation-ID`.
3. Backend middleware validates or generates it and binds request-local context.
4. Logs and all responses include the same ID.
5. Background work carries it explicitly.

Correlation IDs are diagnostic identifiers, not credentials.
