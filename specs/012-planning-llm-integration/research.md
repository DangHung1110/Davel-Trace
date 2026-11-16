# Research: Stable Planner and Configurable LLM Integration

## Decision 1: Selective port, not Git merge

**Decision**: Pin `origin/feat/stable-p1-p4` commit `35872c2` as the upstream behavior source and port only planner runtime, required assets, audit tools, and regression tests into the current product architecture.

**Rationale**: The historical and product branches differ across hundreds of files. A whole-tree merge would reintroduce removed modules and conflict with authentication, PostgreSQL lifecycle, migrations, offline sync and current Flutter work. The current platform already contains an older stable planner, so focused upgrades preserve product contracts.

**Alternatives considered**: Whole-tree merge (too destructive); a second vendored planner (two sources of truth); rewriting behavior from prose (loses measured code and tests).

## Decision 2: Keep deterministic planner authoritative

**Decision**: LLM capabilities are limited to interpretation proposals, grounded explanation and shadow comparison. Only the stable deterministic planner may create alternatives, and the product lifecycle validates/persists them.

**Rationale**: This follows the constitution and guarantees structured planning during provider failure.

**Alternatives considered**: End-to-end LLM itinerary generation and visible LLM reranking were rejected.

## Decision 3: Gemini through the existing REST transport

**Decision**: Add explicit Gemini provider support through Google's OpenAI-compatible REST endpoint and the existing standard-library JSON transport. Do not add `google-genai` or an OpenAI SDK.

**Rationale**: Current capabilities need only chat-completion JSON. Reusing the transport avoids a dependency and keeps provider replacement simple.

**Alternatives considered**: Google Gen AI SDK is unnecessary for current scope; OpenAI SDK is excluded; native `generateContent` is deferred.

## Decision 4: Gemini subscription and API access are separate

**Decision**: Configuration requires a Gemini Developer API key created in Google AI Studio. A consumer Gemini Plus/Google AI subscription is not treated as API billing or API quota.

**Rationale**: Gemini API projects, keys, free tier and paid billing are managed independently. Missing key/configuration must fail honestly.

**Alternatives considered**: Browser login or consumer subscription cookies are unsupported and insecure.

## Decision 5: No new database migration

**Decision**: Persist confirmed requests through existing lifecycle tables and shadows through `shadow_observations`. Do not persist raw prompts or outputs by default.

**Rationale**: Current tables already support ownership, versions, data evidence and shadow metadata; data minimization reduces privacy risk.

## Decision 6: Authenticated AI endpoints

**Decision**: Introduce trip-owned interpretation and alternative-owned explanation endpoints in a dedicated module. Keep `/v1/parse` only for compatibility; Flutter uses authenticated endpoints.

**Rationale**: Natural-language text and itinerary evidence are user-owned content and require ownership checks before external calls.

## Decision 7: Failure normalization and bounded work

**Decision**: Calls use configured timeout and at most two retries. Errors normalize to `LLM_DISABLED`, `LLM_CONFIG`, `LLM_AUTH`, `LLM_QUOTA`, `LLM_SAFETY`, `LLM_TIMEOUT`, `LLM_TRANSPORT`, `LLM_BAD_JSON`, or `LLM_SCHEMA` without secret-bearing detail.

**Rationale**: The UI needs actionable state while provider failures remain isolated from planner failures.

## Decision 8: Revalidate source evidence

**Decision**: Run stable planner fixtures plus current PostgreSQL lifecycle, Flutter, secret, build and latency/audit validation after adaptation.

**Rationale**: Passing in the historical architecture does not prove correctness through current adapters.
