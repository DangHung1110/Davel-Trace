# Validation — 2026-11-16

Local ignored BE/.env selects groq with GROQ_MODEL=qwen/qwen3.8-27b. The key was
entered by the user locally and was never copied into source or printed. Database,
SMTP and Google sign-in configuration were preserved. Hosted Groq calls do not use
the user's Codex token balance; no OpenAI API credentials or SDK were introduced.

## Live calls (synthetic content only)
- Official authenticated GET /models: HTTP 200. Initial Llama model returned 404 and
  was replaced by the available Qwen model; this is not treated as a credential failure.
- Minimal JSON completion: success in 0.78s.
- Production complete_json with InterpretationDraft validation: success in 0.74s.
- AiAssistanceService with a synthetic one-place catalog resolved Cầu Rồng to its ID,
  travelers=2 and budget=3000000; proposal status review_required.
- Same service with the actual public 750-place catalog: success in 1.60s, one resolved
  requested place, zero unresolved names, correct travelers/budget.
- Grounded explanation with synthetic evidence: source ai_grounded, four evidence reasons.
- Restarted FastAPI: /v1/ai/readiness reports groq/Qwen, available=true, last_failure=null;
  /v1/ready reports ready. Readiness alone is not used as proof of provider connectivity.

## Automated checks
- Backend provider/config/assistance/ownership/deterministic-lifecycle/secret suite:
  50 passed. Includes JSON schema rejection, non-retry auth/quota/config failures,
  prompt/log/error secret redaction and no secret in settings repr/readiness.
- Flutter analyzer: no issues (6.4s).
- Full Flutter suite: all 71 passed (78s on this machine).
- Final Groq/secret follow-up after staging: 12 passed, including all new tracked files.
- Release web rebuild: passed (103.6s). Served index.html and main.dart.js on port 5501
  return HTTP 200 with SHA-256 digests matching the final build. Backend readiness
  rechecked with provider groq and qwen/qwen3.8-27b after the build.

No personal account/trip content was sent to Groq during these smoke tests. No new
user itinerary was created/accepted, and no database migration/package was added.
Full end-user browser submit is left for the user; lower-level production services
were exercised with real Groq network calls and authenticated API behavior is covered
by the contract suite.

Converged: implementation 5eb59a3 pushed on fix/ui; PR #21 updated with final Groq
scope, model selection and validation: https://github.com/DangHung1110/Davel-Trace/pull/21
Target remains feat/product-platform; no integration-branch merge was performed.

## Actual app failure and fix
The user's next browser submit failed with backend last_failure=quota. A diagnostic
request using the full catalog and app-shaped trip context measured 5339 input tokens;
an initial response needed schema retry and the subsequent call returned Groq 429,
rate_limit_exceeded (31s Retry-After). The earlier smoke did not verify this repeated
app flow and was insufficient evidence of stable end-to-end behavior.

The external prompt now includes at most 24 relevant verified names / 1200 name
characters, selected using accent-insensitive matching. Numeric party/budget tokens
cannot select arbitrary catalog places. Full-catalog resolution remains authoritative.
Context day_start/day_end are normalized from DB HH:MM:SS into schema HH:MM; missing
slots are explicitly null/empty lists. Quota/auth/config/schema errors now have distinct
user-facing messages, with no raw provider body or secret exposed.

Two consecutive real Groq service calls with app-shaped times succeeded in 1.16s and
1.01s, each producing review_required and resolving the two requested places. The
pre-schema prompt was 1497 characters in this scenario.

Verified the actual authenticated release UI in the in-app browser:
selected current trip -> Plan -> AI input -> entered synthetic text for 2 travelers,
3000000 VND, Cầu Rồng/Mỹ Khê and 08:00–18:00 -> Diễn giải -> proposal -> review route.
The screen showed correct budget, travelers, hours and both named places. No plan was
generated/accepted during this check, and the existing trip itinerary was not modified.
Only backend code changed, so no additional Flutter build is required.
Regression suite: 49 backend tests passed (12.45s), including catalog bounds, accent
matching, DB-time normalization, error messages, ownership and deterministic planning
isolation. Runtime readiness after the UI submit: last_failure=null. Existing 71 Flutter
tests remain applicable because this follow-up changes no Flutter source or contracts.
