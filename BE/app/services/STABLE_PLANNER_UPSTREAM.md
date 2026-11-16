# Stable planner upstream manifest

- Source ref: `feat/stable-p1-p4`. `feat/product-platform` was merged into it on 2026-11-16, and
  every planner file here is that branch's own file, unchanged.
- Planner commit: `35872c2` (`PLANNER_SOURCE` in the product boundary). The product platform first
  ported this planner selectively (diff base `origin/feat/stable-planning-roadmap`); the merge replaced
  that port with the stable files.

## Planner files (identical to `feat/stable-p1-p4`)

- Planner algorithms in `BE/app/services/`: gate, matrix, multiday, optimizer, pool, profile filtering/objectives, rank/ranker, repair/replan, response/retrieval, route ordering, scoring, soft rules, state, templates, trip context, validation and weather.
- Shared deterministic helpers in `BE/common.py`.
- Orchestration in `BE/app/routers/itinerary.py` (including `DIVERSE_K = 3`); it returns every plan, empty or failing ones included.
- Versioned `BE/data/snapshots/danang-v1/` POI/matrix/calibration artifacts and PATM artifacts.
- The stable regression tests plus `BE/tools/audit_plans.py` and `BE/tools/bench_latency.py`.
- Evaluation/gold artifacts, matrix build/calibration tools, the LF-normalized OSRM profile and provenance review tooling.

## Product boundary (outside the planner)

- `BE/app/modules/planning_lifecycle/stable_planner.py`: after the planner answers, derives the five gate families from the canonical gate report (`select.evaluate_plan`), a deterministic rank and score, the data version and the planner provenance. Empty and gate-failing plans do not become product alternatives.
- `BE/app/routers/select.py`: the planner's gate decision and plan store, plus the acceptance record written to the planning-evidence store before a plan becomes active (503 when that write fails).
- `BE/app/services/llm.py`: the provider-neutral gateway (disabled/local/groq/gemini/compatible). The planner does not call it; `/v1/parse`, `/v1/review` and the shadow ranker do.
- Kept product compatibility services: `acceptance_store.py`, `planning_readiness.py`, `shadow_rank.py`.
- `BE/app/main.py` mounts the product capabilities next to the planner routers and keeps the planner's production rules (`APP_MODE=production` closes `/v1/review`, `/v1/repair`, `/v1/accept` and the any-localhost CORS rule).

The current `PlanningLifecycleService` remains the only authoritative write path for planning requests, alternatives and immutable versions. The planner is a calculation boundary only.

Product adaptations in the lifecycle: confirmed hard must-visit/avoid constraints are rechecked before persistence; unsupported trips beyond two days fail explicitly; the lifecycle timeout guard is 90 s pending the open deployment latency task. See `specs/012-planning-llm-integration/validation.md` for unfulfilled acceptance criteria.
