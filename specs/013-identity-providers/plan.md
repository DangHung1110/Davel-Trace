# Implementation Plan

Follow the repository Spec Kit sequence using its checked-in templates/workflow;
the agent command skills are not installed in this checkout. Existing Task 012
checkpoint was clean and already pushed at `6817315` before this work.

## Architecture

- Keep the identity module, opaque Davel credentials and existing PostgreSQL.
- Add typed optional SMTP/Google env settings. SMTP uses Python stdlib smtplib,
  EmailMessage and default TLS trust; delivery selection preserves explicit demo.
- Add Google subject/account associations and short-lived OAuth transaction rows
  in additive Alembic migration `013_001` after `010_001`.
- Authorize one additional backend dependency in this plan: `google-auth[requests]`
  (2.x) for Google's maintained signature/issuer/audience/expiry verification.
  Authorization-code exchange uses TLS and stdlib urllib; PKCE/state/nonce checks
  remain explicit application responsibilities. No frontend dependency is added.
- Allow at most 30 seconds of ID-token clock skew (including expiry) while keeping
  signature/audience/issuer mandatory. A no-cache Google HTTP Date probe found
  the local clock approximately 0.6 seconds behind; future-issued tokens beyond
  this small tolerance and expired tokens remain rejected by signed-token tests.
- Web flow: open popup to `/v1/auth/google/start` with configured application
  origin and accepted terms; set HttpOnly SameSite=Lax browser cookie; store only
  state/browser/nonce hashes. Browser secret doubles as PKCE verifier. Callback
  atomically consumes state before exchanging code, verifies signed ID token and
  nonce, resolves stable subject, then creates a 60-second one-time handoff.
- Callback sends only the handoff through postMessage to the validated origin.
  Flutter validates popup source and API origin and exchanges the handoff via POST
  for an ordinary session. Tokens are never returned through navigation URLs.
- Google email collisions fail closed instead of silently linking existing users.
- Redact OAuth callback query strings in application and Uvicorn access logs.
- Failed SMTP actions are unusable; a resend issues a fresh action. A successful
  send means SMTP accepted the message, not guaranteed inbox arrival. SMTP and DB
  are not a distributed transaction; an exceptional DB commit failure after SMTP
  acceptance requires a resend and is documented, not reported as guaranteed delivery.

## Validation

Unit tests use stub SMTP and Google HTTP/token verification. PostgreSQL contract
tests exercise state/cookie binding, nonce/audience rejection, handoff replay,
subject resolution, account collision/state, refresh and password recovery.
No automated test sends real mail or contacts Google unless invoked explicitly.
Flutter tests cover Google-result handling and existing auth/mobile layout.
Real smoke checks are limited to the user's configured email/client and local DB.

## Constitution check

Spec precedes implementation; dependency is explicitly included in this plan;
PostgreSQL remains authoritative; deterministic planning is untouched. No main/dev
push or remote deletion. User retains PR creation as previously requested.
