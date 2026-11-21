# Plan and analysis

Branch: fix/ui, baseline 804bc91, already pushed and clean. This follow-up is included
in the pending product-platform PR #21 so the running mobile UI and provider setup agree.
Spec Kit wrappers remain unavailable; this records specify/plan/tasks/analyze before edits.

Reuse the stdlib REST gateway. Add explicit provider groq, GROQ_API_KEY (repr hidden),
GROQ_MODEL=qwen/qwen3.8-27b. Keep Gemini/local/compatible options functional.
Groq endpoint fixed at https://api.groq.com/openai/v1/chat/completions, Bearer auth,
JSON object response format and bounded completion tokens, with existing Pydantic output
validation. Separate Groq model avoids inheriting a stale Gemini LLM_MODEL in .env.
Remove Gemini from active UI labels; describe optional external AI in neutral language.
Never repurpose Google OAuth credentials: authentication continues independently.

Sources checked 2026-11-16: Groq official docs /docs/models, /docs/openai,
/docs/structured-outputs, /docs/api-reference. JSON mode ensures syntax only; backend
schema and catalog grounding remain authoritative. No SDK/package additions.

Tests: transport body/auth/default model, missing key, normalized failures and key
redaction; existing assistance API/ownership/fallback tests; Flutter regressions/analyzer;
live synthetic JSON and interpretation smoke, then backend restart/readiness and web build.
Gate: PASS — provider-neutral contracts already cover the requested switch.

Live verification found the initially documented llama-3.3-70b-versatile unavailable
(HTTP 404). Authenticated GET /models succeeded and listed qwen/qwen3.8-27b; a real
JSON completion succeeded with that model. Use Qwen with reasoning_effort=none for
these bounded JSON conversion tasks. Model choice is configurable via GROQ_MODEL.
