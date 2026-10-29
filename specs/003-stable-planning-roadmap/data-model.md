# Data Model: Stable Planning Roadmap MVP

## Plan Alternative

Transient planner object registered until selection.

| Field | Type | Rules |
|---|---|---|
| itinerary_id | UUID string | Unique per generated alternative |
| trip_id | string | Required |
| profile | enum-like string | Existing deterministic objective label |
| activities | ordered array | Complete schedule; verified POIs only |
| total_cost / total_km / total_min | number | Existing planner totals |
| deterministic_rank | integer | 1-based, authoritative |
| deterministic_score | number | Existing normalized quality/objective evidence |
| diversity | object | MMR rank/quality/similarity and pairwise Jaccard evidence |
| gate | Hard Gate Report | Must pass before public selectability |
| data_version | string | Active snapshot identifier |
| shadow | object or null | Experimental status/reference only |

## Hard Gate Report

| Field | Type | Rules |
|---|---|---|
| passed | boolean | True only if every hard family passes |
| failed_families | array | Empty for selectable plans |
| families | map | Exactly temporal, financial, movement, safety_data, traveler_constraints |
| families.*.passed | boolean | Conjunction of mapped detailed hard checks |
| families.*.score | number 0..1 | Minimum detailed score in the family |
| families.*.checks | array | Detailed check identifiers and results |
| soft_failed | array | Existing non-blocking quality checks |

The existing detailed registry stays canonical. The family view is derived and never becomes a second set of formulas.

## Acceptance Record

Append-only SQLite row with JSON snapshots.

| Field | Type | Rules |
|---|---|---|
| acceptance_id | UUID text primary key | Server generated |
| idempotency_key | text unique | 8–128 chars; client-supplied or server-generated for legacy selection |
| itinerary_id | text | Required |
| trip_id | text | Required, indexed |
| parent_acceptance_id | text nullable | References a prior acceptance conceptually; rows are never updated |
| selected_at | ISO-8601 UTC text | Server generated |
| schema_version | integer | Starts at 1 |
| data_version | text | Required |
| request_json | JSON text | Normalized trip request snapshot |
| plan_json | JSON text | Full public accepted plan snapshot |
| gate_json | JSON text | Selection-time hard gate report |
| deterministic_rank | integer nullable | Rank at display/selection time |
| deterministic_score | real nullable | Score at display/selection time |
| shadow_observation_id | text nullable | Link when a shadow observation exists |

Validation: no write occurs for unknown or gate-failing plan. Duplicate client-supplied idempotency key returns the existing decoded record. Legacy selection receives a server-generated key while retaining its old response shape. Read endpoints never mutate rows.

## Shadow Observation

Append-only SQLite row.

| Field | Type | Rules |
|---|---|---|
| observation_id | UUID text primary key | Server generated |
| trip_id | text | Indexed |
| created_at | ISO-8601 UTC text | Server generated |
| data_version | text | Active snapshot |
| candidate_ids_json | JSON text | Known feasible candidate IDs |
| forward_json | JSON text | Raw normalized forward decision |
| reverse_json | JSON text | Raw normalized reverse decision |
| consensus_json | JSON text | Win/tie/inconsistent result |
| deterministic_top_id | text | Baseline top alternative |
| shadow_top_id | text nullable | Only when both orders agree |
| swap_consistent | boolean | Both order decisions equivalent after remapping |
| length_correlation | real nullable | Null when too few plans/variance |
| veto_count | integer | Shadow veto signals; never blocks |
| status | enum text | completed, unavailable, malformed, skipped |
| latency_ms | integer nullable | Best-effort measurement |

## Readiness Snapshot

Computed object, not stored as an authoritative model.

| Field | Rule |
|---|---|
| pairwise_judgments | Count of eligible comparison/choice evidence |
| pairwise_learning.enabled | True only when count ≥150, held-out accuracy ≥0.70, mismatch <0.25 |
| accepted_complete_days | Count of accepted complete-day records |
| full_day_learning.enabled | True only when count ≥40 |
| retrieval_ready_days | Count of accepted complete days meeting completeness/data-version rules |
| accepted_day_retrieval.enabled | True only when count ≥50 |
| accepted_day_retrieval.preferred_target | 200 |
| judge.sample_count | Completed observations |
| judge.top1_agreement | Agreement ratio or null |
| judge.swap_consistency | Ratio or null |
| judge.length_rank_correlation | Aggregate or null |
| judge.promotion_ready | Never automatic; true only if all documented metrics and ≥200/2-week evidence are present |

## Demo Session (Flutter/local)

| Field | Type | Rules |
|---|---|---|
| mode | live / seeded / stale | Always visible to presenter |
| profile | object | Onboarding fields matching `TripRequest.profile` |
| trip_request | object | Current request |
| alternatives | array | Live API or bundled seed; source labeled |
| active_itinerary | object nullable | Selected/seeded active plan |
| acceptance | object nullable | Present only after confirmed live selection |
| expenses | array | Current session items plus live summary when available |
| data_timestamp | timestamp | Shown when data is cached/seeded |
| api_base_url | URI | Desktop web default localhost; configurable |

### State Transitions

`seeded → live` after health and planning success. `live → stale` after a later network failure while retaining last valid data. Selecting a seeded alternative updates only local demo state and MUST NOT create a fake acceptance identifier.
