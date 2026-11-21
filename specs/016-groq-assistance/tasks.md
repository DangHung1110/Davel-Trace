# Tasks

- [x] Inspect current gateway/UI/env and verify Groq official endpoint/model/JSON docs.
- [x] Record spec, plan and analysis gate before implementation.
- [x] Add Groq settings/gateway and secret handling; keep other providers compatible.
- [x] Update ignored local configuration, safe template/docs and provider-neutral UI.
- [x] Run unit/contract/regression checks and a live smoke when local key is available.
- [x] Restart/rebuild preview and document exact results/limits.
- [x] Push and update PR #21.

- [x] Regression: bound catalog context, normalize prompt times and distinguish errors.
- [x] Reproduce authenticated app interpretation with real provider, including consecutive
  requests, and verify the resulting proposal is reviewable on the mobile screen.

Regression analysis gate: PASS. Observed backend last_failure=quota and Groq 429;
diagnostic request measured 5339 input tokens and a 31-second Retry-After. An earlier
response in the same gateway call failed local validation before the retry hit quota.
The minimal API call succeeds. Fix the prompt boundary and errors, not credentials.
