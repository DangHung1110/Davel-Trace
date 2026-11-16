# Personalized Travel Agent Constitution

## Core Principles

### I. Feasibility-First (NON-NEGOTIABLE)
Deterministic optimization decides itineraries; LLM MUST NOT generate routes
directly. Every itinerary MUST pass the feasibility gate (entity truthfulness,
opening hours, spatio-temporal reachability, budget, headcount) before any
quality scoring. A plan that fails the gate MUST NOT reach the user.
Rationale: benchmarks show end-to-end LLM routing degrades to 55%+ gap and
infeasible plans at scale, while OR-Tools CP-SAT holds 100% feasibility.

### II. Spec-Driven Development
No implementation without spec → plan → tasks → analyze-green. Every
non-trivial feature MUST have `specs/<nnn-name>/spec.md` (WHAT/WHY only),
`plan.md` (HOW + stack), `tasks.md` (dependency-ordered). `/speckit.analyze`
MUST report no blocking issues before `/speckit.implement` runs.

### III. Test-First
Validator and evaluator code MUST exist before optimizer tuning. Minimum bars:
PATM pairwise accuracy ≥70%, feasibility 90%+ on feasible tasks, opening-hours
violations = 0 on complete data, budget violations = 0 when budget is hard.
Gold references follow TravelEval Approach B (filter → cluster → TSP/OR-Tools).

### IV. Data Provenance & Honesty
Every POI MUST trace to the versioned Da Nang snapshot (100–200 POIs, TravelEval
schema). Unverified data MUST carry uncertainty labels and MUST NOT enter the
main itinerary. Assumptions MUST NOT be presented as facts. No secrets or API
keys in code (`.env` only, never committed).

### V. Simplicity & Tier Discipline
Build in tiers (nấc 1 rule → nấc 2 trained → nấc 3 scale) and stop at demo-adequate.
BANNED in MVP: RL/GRPO training, GPU-dependent models, generative next-POI,
multi-city, voice, booking/payment, receipt OCR. ALLOWED since rev 2026-09-28:
small CPU-only fine-tune (e.g. PhoBERT intent classifier S3, ≤500 labels) as
baseline/offline role only — parser stays LLM-primary. New dependencies require plan
approval. Scope is Da Nang only until explicitly expanded.

### VI. Mobile Contract
Flutter is the primary frontend; FastAPI (in `BE/`) serves all intelligence.
Inference server-side (PATM <5ms). Map works offline (PMTiles); new itineraries
need network (cached last itinerary + data timestamp shown). Budgets: parser
<10s, full itinerary <30s, replan <15s on 4G.

## Technology Constraints

Python 3.11; FastAPI backend; Flutter frontend (`index.html` stays demo/test
only); OR-Tools CP-SAT optimizer; LightGBM PATM (pairwise RankNet loss);
Pydantic validation; pytest; OSRM snapshot route matrix (no VietMap — free,
deterministic, offline-capable); POI data via Google Places API (legal, reliable,
~$3.40 for 200 POIs); local LLM via Ollama on demo machine (Qwen3-14B primary,
Sailor2-8B fallback), API (GPT-4o-mini/Gemini Flash, <5 USD total) only for
demo polish and edge-case judge; PostgreSQL is the authoritative operational
store for accounts, profiles, trips, expenses, itinerary versions, acceptance
evidence and audit records; SQLAlchemy 2 models and reviewed Alembic migrations
govern schema changes; versioned JSON/PMTiles remain authoritative planning
snapshots; SQLite MAY be used only for isolated tests or explicitly labeled
demo/offline caches and MUST NOT be the production source of truth; Open-Meteo
provides weather (free, no key); secrets remain outside Git; Vietnamese-first,
English later.

## Development Workflow

Branches `feat/*`, `fix/*`, `chore/*`, `task/*`, and `release/*` merge through
reviewed PRs into `dev`; `main` is stable. Product-scale work MUST be divided
into independently testable Spec Kit increments and MUST NOT use a big-bang
rewrite. Direct pushes to `main`/`dev` and force-pushes are FORBIDDEN.

Remote branch deletion is forbidden by default. It MAY occur only after an
explicit repository-owner request, exact remote-ref verification, confirmation
that all required commits are reachable from another named branch or tag, and
closure or retargeting of the associated PR. The deletion and surviving ref
MUST be reported. Checkpoint (`wip: checkpoint before agent run` + push) before
large agent runs. Reviews MUST verify constitution compliance. Definition of
Done lives in `AGENTS.md` and MUST all hold before merge.

## Governance

This constitution supersedes all other practices on conflict. Amendments require
a PR, team review, and a version bump (MAJOR: principle removal/redefinition;
MINOR: new principle/section; PATCH: wording). A request to retire a remote
branch is effective only when made by the repository owner and when the
preservation evidence required by Development Workflow has been verified.
Complexity beyond these principles MUST be justified in the PR. Runtime
guidance: `AGENTS.md`.

**Version**: 2.0.0 | **Ratified**: 2026-09-21 | **Last Amended**: 2026-10-29
