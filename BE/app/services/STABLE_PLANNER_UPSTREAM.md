# Stable planner upstream manifest

- Source ref: `origin/feat/stable-p1-p4`
- Pinned commit: `35872c2`
- Diff base used for the selective port: `origin/feat/stable-planning-roadmap`
- Port method: apply only additions/modifications required by the planner, then adapt the authenticated product boundary manually.

## Included

- Planner algorithms in `BE/app/services/`: gate, matrix, multiday, optimizer, pool, profile filtering/objectives, rank/ranker, repair/replan, response/retrieval, route ordering, scoring, soft rules, state, templates, trip context, validation and weather.
- Shared deterministic helpers in `BE/common.py`.
- Stable orchestration behavior in `BE/app/routers/itinerary.py`, adapted to emit the product platform's five gate families and data-version evidence.
- Versioned `BE/data/snapshots/danang-v1/` POI/matrix/calibration artifacts and PATM artifacts required by the pinned source.
- Applicable stable regression tests plus `BE/tools/audit_plans.py` and `BE/tools/bench_latency.py`.
- Evaluation/gold artifacts, matrix build/calibration tools, the exact LF-normalized OSRM profile and provenance review tooling required by those regression fixtures.

## Explicitly excluded or preserved from product platform

- Historical `BE/app/services/llm.py`; Task 012 supplies a provider-neutral Gemini/local/compatible gateway instead.
- Source-branch deletions of `acceptance_store.py`, `planning_readiness.py`, `shadow_rank.py`, `snapshot.py`, `common.py`, `budget.py`, `context_score.py`, `explainer.py`, and `gps.py`; current product/evidence modules still depend on these compatibility services.
- Historical in-memory selection/acceptance and SQLite product write paths.
- Source `BE/app/main.py`, configuration, authentication, migrations, PostgreSQL lifecycle, catalog/routing modules, expenses, offline cache and Flutter product management.
- Historical generated review pages and superseded raw/manual labeling artifacts that are not runtime inputs.

The current `PlanningLifecycleService` remains the only authoritative write path for planning requests, alternatives, immutable versions and acceptance records. The imported planner is a calculation boundary only.

Product adaptations: gate-family evidence is derived from the shared registry; failed/empty public alternatives are removed; confirmed hard must-visit/avoid constraints are rechecked before persistence; unsupported trips beyond two days fail explicitly. The 5-unit source solver budget is preserved; the lifecycle timeout guard is 90s pending the open deployment latency task. See `specs/012-planning-llm-integration/validation.md` for unfulfilled acceptance criteria.
