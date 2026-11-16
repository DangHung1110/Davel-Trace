# Validation and convergence — identity providers

## Real-provider evidence

- 2026-11-14: SMTP Gmail authentication succeeded and accepted one diagnostic
  message to the user-provided Gmail. Real verification and recovery emails were
  then sent to that same mailbox by a smoke harness using a disposable DB account;
  the harness rerouted only test delivery, never modified the user's password.
- The smoke verified email confirmation, password login, refresh rotation,
  recovery, rejection of the previous password/session, and login with the new
  password. Disposable account and credential rows were removed afterward.
- 2026-11-15: user completed real Google consent and confirmed **Đã đăng nhập được**.
  Backend observed callback 200, handoff exchange 200 and profile GET 200.
  Read-only PostgreSQL inspection confirmed an active account, stable Google
  subject link and consumed handoff. No Google tokens or secrets were recorded.
- A synthetic invalid-code request returned `invalid_grant`; this was only an
  endpoint diagnostic and was not counted as proof of successful sign-in.

## Automated evidence

- Broad regression before the final popup/clock refinements: **1116 passed,
  2 skipped**, three existing SWIG deprecation warnings, 272.79 seconds.
- Final identity/provider/migration run after refinements: **29 passed** in
  11.78 seconds. Includes real RSA signature/audience/expiry tests; bounded
  clock skew; state/browser/nonce binding; expired/replayed handoff; account
  collision/status; SMTP rejection; recovery and refresh-family revocation.
- An earlier rerun during compilation exceeded an existing 100 ms assertion
  (261 ms); the assertion was kept intact. Isolated identity run passed (2 tests),
  and the final combined run above also passed with no relaxed threshold.
- Alembic repeated upgrade/readiness tests passed at head `013_001`.
  `alembic check`: **No new upgrade operations detected**. It reports an existing
  cycle warning involving planner foreign keys; no schema difference was found.
- Release Flutter build passed, including the production JavaScript popup code.
- The Dart/DOM browser probe passed all four checks in an isolated headless Chrome:
  opaque cross-origin frame, accepted correct source, rejected wrong origin and
  rejected wrong source. It imports the actual production predicate.

## Fixes found during validation

1. Dart generic equality touched a cross-origin Window's dispatch property.
   The source check now uses JavaScript `strictEquals` while retaining exact
   origin/source checks; the browser probe covers the user's reported exception.
2. Start/callback host mismatch would split localhost and 127.0.0.1 cookie scopes.
   Backend capabilities supply the callback origin for the popup's start URL.
3. Refresh-family revocation was rolled back by the transaction exception. It is
   now committed before returning the replay error; tests require new credentials.
4. Concurrent unauthorized Flutter GETs now share one refresh rotation.
5. A no-cache Google Date probe measured the machine about 0.6 seconds behind.
   Verification allows only 30 seconds of skew; future tokens beyond the bound,
   expired tokens and invalid signatures/audiences remain rejected.

## Operational notes

PostgreSQL remains the isolated `davel-trace-task012-demo` project on 5437.
Ignored backend env contains the user's current provider credentials, retains
Gemini/DB settings, and disables the development identity inbox. The mobile
release server uses the repository byte-range handler on 5501; PMTiles range
requests were verified as 206. Backend remains on 8000.

Existing password accounts are not silently linked by matching email. Native
Android/iOS Google login and explicit account linking remain outside scope.
The user will create the PR; no PR or protected-branch merge is performed here.

## Final handoff gates (2026-11-15)

- Flutter analyzer: **No issues found**, 16.5 seconds after the final import fix.
- Entire Flutter VM/widget suite: **48 passed**, 63 seconds. Includes Google terms,
  normal session acceptance, shared refresh rotation and existing map/planner UI.
- Git secret sweep: **3 passed**. Exact-value comparison against all 42 staged
  files found **zero files containing the local SMTP/Google/Gemini/DB secrets**.
  Env, provider debug log and local cache junction are all ignored/untracked.
- Backend readiness and served mobile release both returned HTTP 200 after tests.
- User confirmed real Google login success. No manual consent check remains open.

**Convergence**: Converged for increment 013's specified web/SMTP scope. This does
not assert convergence of unrelated planner/evaluation work in increment 012.
