# Increment 012 validation — 2026-11-14

Status: implementation checkpoint; **not yet converged / not merge-ready**.

## Verified

- Imported deterministic planner and versioned assets from pinned source `35872c2`, selectively; retained current product authentication, PostgreSQL schema/lifecycle and compatibility services.
- Stable solver budget restored to source values: 5 deterministic work units, one worker; distinct re-solve 3 units. Lifecycle final timeout guard is 90 seconds. This deliberately does not claim the performance acceptance criterion passes.
- Backend unit suite excluding the separately run baseline and accuracy suites: **1,026 passed, 2 skipped**.
- Baseline suite: **12 passed** (685.37 seconds).
- Accuracy suite: **63 passed** (18.19 seconds).
- Contract/integration suites excluding PostgreSQL-dependent files and the historical real-snapshot response harness: **109 passed, 1 skipped**.
- New AI API tests: **9 passed**, covering authentication, ownership before provider invocation, disabled/auth/quota/timeout/schema normalization, structured planning after AI failure, explanation fallback and durable shadow in both presentation orders without changing persisted ranks.
- Flutter suite: **43 passed**. Focused planning tests rerun after proposal review/late-response changes: **4 passed**.
- Added state regressions for AI quota fallback and late interpretation after sign-out: **3 AI state tests passed**.
- Additional real-source planner smoke through isolated durable lifecycle: **1 passed** (31.93 seconds), including accept and restart/read evidence equality.
- Flutter web release build succeeded.
- Targeted Dart analysis: no errors/warnings; one existing Material import deprecation info from the installed SDK.
- Secret scan passed in the unit run; only exact known test-password/documentation false positives are exempted.

## Outstanding verification and gaps

- No `DATABASE_URL` is configured in this task worktree. Docker Desktop Linux daemon is unavailable. Six PostgreSQL-dependent test cases (identity, profile/trip, expenses and migrations) failed for this environmental prerequisite; they have not been claimed as passing or changed to hide the failure.
- Gemini credentials have not been supplied; provider behavior is tested with mocks. Hosted accuracy/quota/region/model smoke remains unverified.
- SC-009 latency is **not achieved** on the current Windows environment: a one-profile source-budget smoke took 36.78s cold and 34.75s warm. A temporary shorter search experiment was discarded; production retains the pinned source budget. These are smoke measurements, not a statistically valid p95 benchmark.
- Full audit, supported two-day deployment latency and authenticated manual smoke remain pending.
- Historical `test_real_snapshot_planning.py` expects failed/empty plans in `plans`; product output now correctly removes them. Adapt this harness to assert explicit shortage metadata before using it as a regression gate.
- Interpretation's agreed Vietnamese benchmark set, provider-switch record-equivalence coverage, dedicated AI fallback/explanation widget coverage and full cancellation/account-change race coverage remain incomplete. Enabled-shadow ordering and sign-out interpretation races have focused automated coverage.

## Configuration

Use ignored `BE/.env`, `LLM_PROVIDER=gemini`, `GEMINI_API_KEY` and `LLM_MODEL=gemini-3.1-flash-lite`. Google currently lists a free tier for this model; availability/quota is project-specific. Gemini consumer subscriptions are not backend API credentials.

References checked: [pricing](https://ai.google.dev/gemini-api/docs/pricing), [billing](https://ai.google.dev/gemini-api/docs/billing), [compatible REST](https://ai.google.dev/gemini-api/docs/openai).
