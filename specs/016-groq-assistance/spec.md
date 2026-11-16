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
