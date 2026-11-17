# Plan — 017

Branch: fix/llm-extraction-catalog; baseline main 384f575. Lane C owns parser/API/app.
Checkpoint deb3dc6 preserves the prior uncommitted quota/error/time fixes without
modifying the user's fix/ui workspace. All implementation stays in this worktree.

Spec Kit command wrappers are not installed in this checkout. Execute the equivalent
specify → clarify → plan → checklist → tasks → analyze → implement → converge artifacts
here. Clarification resolved from user intent: unresolved places require a local choice
or explicit removal, and AI never receives catalog context, even a shortlist.

Reuse InterpretationDraft for extraction and the stdlib gateway. Remove catalog
context construction from the interpretation prompt; keep allowed trip slots/time
normalization and credential redaction. Resolve names after completion using a public
catalog application function. Normalize đ/diacritics, punctuation and whitespace;
prefer exact normalized names, otherwise whole-word contiguous name matches. Keep all
verified candidates, deduplicate IDs, never choose an arbitrary first result.

Existing hard_constraints retain uniquely resolved IDs. Add place_resolutions for
ambiguous/not-found references: constraint (must_visit|avoid), name, status
(ambiguous|not_found), candidates [{poi_id,name,type,lat,lon,address?}]. No candidate
IDs enter the external prompt. Unknown references also remain in unresolved for older
clients. No proposal persistence or database schema change.

Flutter adds backward-compatible typed resolution/candidate models. Review receives
pending resolutions separately from planner overrides, renders local choice fields
with no default, and requires selection/removal for every reference. Only IDs are
returned in must_visit/avoid, deduplicated; contradictory visit/avoid IDs block submit.
AppState blocks bypassing pending review without explicit corrected place lists.
The planning endpoint and deterministic solver contract are unchanged.

Validation: backend unit and authenticated API tests using fake completions and isolated
databases; Flutter model/state/widget tests for choice/removal/cancel/overrides, plus
existing mobile flows and analyzer. Compare prompt character counts without a network
call. Run local range server and Flutter debug, never a release web build. Restart
demo on this task code only after checks; commit/push task branch and open PR to dev.
