# Data Model: Stable Planner and Configurable LLM Integration

No new authoritative database entity is required. This feature adds transient AI-assistance domain objects and reuses existing product entities.

## Confirmed Planning Request

- Existing immutable ownership, trip, idempotency and request identifiers.
- `input_payload`: confirmed structured values only; raw natural-language text is excluded.
- `remaining_context`: completed/skipped/unavailable POIs, remaining time and actual spend.
- `data_version`, status, counts, shortage and failure evidence.

Validation: owned trip; target count 1–5; automated duration 1–2 days; only user-confirmed interpretation values persist.

## Interpretation Proposal

Transient and non-authoritative:

- `proposal_id`, owned `trip_id`, proposed `fields`.
- `hard_constraints`, `soft_preferences`, `assumptions`, `unresolved`.
- Non-secret provider/model labels and `ready|needs_clarification|unavailable` status.

It never mutates a trip or starts planning. Unknown POIs remain unresolved. Confirmation occurs through the existing planning-request contract.

## LLM Capability Status

- Provider: `disabled|local|gemini|compatible`.
- Non-secret model label.
- Interpretation/explanation/shadow flags.
- Configured/available state, last normalized failure, external-processing flag.

## Grounded Explanation

- Owned `alternative_id`, `data_version`, summary and reasons.
- Every reason carries `evidence_keys[]` that must exist in the minimized evidence map.
- Deterministic warnings and `deterministic|ai_grounded` source.
- Unsupported citations cause deterministic fallback; explanation never mutates a plan.

## Planner Alternative

Existing durable entity generated only by the deterministic planner: complete schedule/movement/totals, five-family gate evidence, deterministic rank/score, fingerprint, data version and selectability state. AI cannot trigger state transitions.

## Shadow Observation

Existing durable non-authoritative evidence: trip/candidate identities, provider/model/rubric labels, forward/reverse decisions, consistency, latency and status. `authoritative=false` is invariant.
