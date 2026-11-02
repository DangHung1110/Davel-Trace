# Identity HTTP API Contract

All endpoints use `/v1`, foundation error envelopes, and `X-Correlation-ID`. Time values are UTC ISO-8601. Secret response fields appear only on successful credential issuance or the explicitly gated dev inbox.

## Public authentication

| Method/path | Purpose | Success |
|-------------|---------|---------|
| `POST /v1/auth/register` | Create unverified traveler | `202` safe account summary |
| `POST /v1/auth/verification/resend` | Request a new verification action | `202` non-enumerating acknowledgement |
| `POST /v1/auth/verification/confirm` | Consume verification action | `200` verified summary |
| `POST /v1/auth/login` | Start session | `200` account, access credential, refresh credential, expiries |
| `POST /v1/auth/refresh` | Rotate session credentials | `200` new credentials and expiries |
| `POST /v1/auth/recovery/request` | Request recovery | `202` non-enumerating acknowledgement |
| `POST /v1/auth/recovery/confirm` | Change password | `204` and revoke sessions/actions |

Registration body contains email, password, and `terms_accepted=true`. Login contains email, password, and an optional bounded device label. Confirm bodies contain the delivered one-time action and required new password where applicable.

## Authenticated session/account

Bearer access credential required.

| Method/path | Purpose |
|-------------|---------|
| `GET /v1/account/me` | Safe account summary, roles, session count |
| `GET /v1/account/sessions` | Own active sessions |
| `DELETE /v1/account/sessions/{session_id}` | Revoke one owned session |
| `POST /v1/account/sessions/revoke-others` | Revoke all except current |
| `POST /v1/account/logout` | Revoke current session |
| `POST /v1/account/logout-all` | Revoke all sessions |
| `POST /v1/account/exports` | Create identity export request |
| `GET /v1/account/exports/{export_id}` | Read owned request metadata |
| `GET /v1/account/exports/{export_id}/download` | Download ready owned JSON |
| `POST /v1/account/deletion` | Confirm deletion request |

Destructive account actions require `current_password` and `confirmation` with the documented phrase. Session deletion is idempotent for an already-revoked owned session.

## Deletion cancellation

| Method/path | Purpose |
|-------------|---------|
| `POST /v1/auth/deletion-cancel/request` | Non-enumerating delivery request |
| `POST /v1/auth/deletion-cancel/confirm` | Consume one-time action and reactivate account without sessions |

## Development inbox

`GET /v1/dev/identity/outbox?email=...&purpose=...` returns the latest unexpired action only when application mode is demo/test and dev outbox is explicitly enabled. Otherwise the route is absent. The response is marked `development_only: true`; production configuration with the flag is invalid.

## Stable errors

`VALIDATION_ERROR` (422), `AUTHENTICATION_REQUIRED` (401), `INVALID_CREDENTIALS` (401), `ACCOUNT_NOT_ELIGIBLE` (403), `FORBIDDEN` (403), `NOT_FOUND` (404), `CONFLICT` (409), `RATE_LIMITED` (429 with retry metadata), `ACTION_INVALID` (400), `DEPENDENCY_UNAVAILABLE` (503), `DATABASE_UNAVAILABLE` (503), and `INTERNAL_ERROR` (500). Public login/recovery messaging remains non-enumerating even when internal audit categories differ.
