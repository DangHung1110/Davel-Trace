# Flutter Identity Contract

## Root states

```text
initializing -> signed_out | authenticated | demo
signed_out -> registering | signing_in | recovering
registering -> verification_required -> signing_in
recovering -> reset_required -> signing_in
authenticated -> refreshing -> authenticated | signed_out
authenticated -> deletion_pending -> signed_out
```

Every asynchronous state exposes loading, success, stable error category, and retry/cancel behavior. Failed live writes are never presented as persisted success.

## Credential rules

- Access credential is memory-only.
- Refresh credential is read/written only by the secure session store.
- Startup attempts one refresh; failure clears stored credentials and returns to signed-out.
- A 401 triggers at most one refresh/retry for an idempotent request. Refresh failure signs out; no retry loop.
- Sign out clears local credentials even if the backend is unavailable and reports whether remote revocation could not be confirmed.

## Screens

- Welcome/sign-in with registration, recovery, and visibly labeled seeded-demo entry.
- Registration with email, password, password confirmation, and consent.
- Verification and recovery flows with dev-inbox assistance only in explicit demo mode.
- Security/account screen showing safe account status, roles, session list, revoke controls, export, and deletion confirmation.
- Authenticated handoff to the existing management shell; until increment 007, its data source remains explicitly labeled demo/legacy.

## Mobile quality

- Primary flows fit 390×844 with keyboard visible through scrolling and safe-area handling.
- Fields use semantic labels, password visibility controls, and no color-only status.
- Error messages are Vietnamese, actionable, and mapped from stable categories rather than raw server/provider details.
- Text scaling up to 200% keeps primary actions reachable.
