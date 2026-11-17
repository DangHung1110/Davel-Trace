# 016 — Groq AI assistance

The user requests replacing the failing Gemini configuration with the provider shown
in their screenshot: GroqCloud (console.groq.com), distinct from xAI Grok.
Travelers can optionally interpret Vietnamese wishes and receive grounded explanations
through Groq, while all scheduling, feasibility, ownership and confirmation rules stay
in the deterministic backend. AI failure must not block ordinary planning.

Acceptance: Groq uses its own secret/model settings and official REST endpoint, validates
model JSON locally, normalizes auth/quota/config/transport failures, and redacts its key
from errors/logs/prompts. No key enters Flutter, tracked templates or readiness responses.
UI wording must remain accurate after provider changes. A live smoke with synthetic
travel text is performed only after a key is available locally; readiness configuration
alone is not proof of connectivity. No new dependency or migration.

## Rate-limit regression
The bounded-shortlist requirement below is superseded by
`../017-extraction-local-resolution/spec.md`: no catalog context is sent to AI;
place names are resolved locally after extraction, with explicit ambiguity review.

The real app recorded quota failures. Sending the full 750-place catalog consumes
over 5000 input tokens per attempt and schema retries can exceed the provider budget.
Interpretation must send only a bounded relevant shortlist; the full catalog remains
authoritative for resolution. A place not explicitly requested must never become a
hard must-visit constraint. Missing values use null/empty lists; trip context times
must use the same HH:MM representation as the output schema. Quota errors must be
distinguishable from authentication/config/schema errors in the user-facing response.
