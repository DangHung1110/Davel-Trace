# Pre-implementation analysis

Spec -> plan -> tasks traceability: US1/FR001–003 -> T004/T008/T009;
US2/FR004–007 -> T005–008; US3/FR008–009 -> T008–010.

Checklist: browser-bound state, PKCE, signed token verification, nonce and email
verification, no silent email linking, expiring one-time handoff, restricted
postMessage origin/source, no credentials in URLs/logs, no dev-inbox fallback in
SMTP mode, SMTP TLS/timeouts and preserved account eligibility are all planned.

No blocking inconsistencies found. Native Google login and account linking are
explicitly excluded. Provider acceptance and human consent must not be confused
with local mocked test success. Pre-implementation gate: ready.

Final convergence (2026-11-15): verified against `validation.md`, including real
SMTP delivery, user-confirmed Google login, signed-token rejection cases,
cross-origin browser probe, 29 backend tests, 48 Flutter tests and secret sweep.
No blocking issues remain in increment 013's specified scope.
