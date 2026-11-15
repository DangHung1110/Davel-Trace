# Contract: Stable Planner Adapter

## Source pin

- Upstream: `origin/feat/stable-p1-p4` at `35872c2`.
- It is a behavior/data/test source, not the integration target.

## Input invariants

Authenticated lifecycle constructs an owned, validated Da Nang `TripRequest`: 1–2 days, non-negative VND budget, named snapshot, confirmed overrides, and completed/skipped/unavailable exclusions for replanning.

## Output invariants

Each selectable plan has complete activities/segments/totals, named data version, deterministic score/rank, diversity identity, warnings/evidence, and exactly five passing gate families. Shortage metadata reports target, actual count and reason.

## Stable behavior carried forward

Verified-pool fail-closed selection, profile safety, calibrated matrix, date-specific hours, meals/rest/all-day places, rain-aware placement, profile preference leaning, route-order timing, reproducible one/two-day alternatives and remaining-day replanning.

## Product boundary

Planner code writes no product record. The lifecycle rejects empty activities, incomplete gates, duplicates and excess results. Product persistence creates authoritative identifiers and retains historical versions. LLM output is never accepted as a planner result.
