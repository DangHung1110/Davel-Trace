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
