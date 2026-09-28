---
description: "Task list for Personalized Travel Agent MVP"
---

# Tasks: Personalized Travel Agent MVP

**Input**: Design documents from `/specs/001-travel-agent-mvp/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: Included per constitution III (Test-First, NON-NEGOTIABLE).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1..US9)
- Paths per plan.md (`BE/` backend, `FE/` Flutter, `data/` snapshots)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create BE package skeleton per plan.md (`BE/app/main.py`, `routers/`, `services/`, `schemas/`, `BE/requirements.txt` with fastapi, uvicorn, ortools, lightgbm, pydantic, pytest, httpx)
- [ ] T002 [P] Configure pytest layout (`BE/tests/contract/`, `BE/tests/integration/`, `BE/tests/unit/`)
- [X] T003 [P] Seed snapshot dir `data/snapshots/danang-v1/` with 7 POIs (from Flutter `DemoTripData`) + 7×7 route matrix
- [X] T003b [P] Build full Da Nang snapshot 100–200 POIs via Apify one-shot (free $5, test 10 trước, ≤2 ngày; tắc >2 ngày → fallback Overpass + tay): normalize to TravelEval JSON schema, 15% human spot-check (`BE/data/snapshots/danang-v1/pois.json`) [SerpApi DONE 2026-09-28: 329 POIs (core 327), quota 50/240; human 15% + nac-2 pending]
- [X] T003c [P] Duration estimator nấc 1+2 (`BE/ml/patm/estimate_duration.py`): category defaults × modifiers → LLM batch (Qwen, input name+category+rating+tags+reviews, swap-check) → `visit_min{p25,p50,p75}` + `dur_source`/`dur_confidence` per POI; human verify 15% + outliers (depends on T003b; see R8) [nac-1 DONE 2026-09-28 seed 7/7; bulk N1-FILL 2026-09-28: 329 POIs p50>0 (VI aliases+attraction200/park120/cafe45, seed-locked 7 keys untouched, seed re-check 7/7; medians attraction200/museum90/park144/beach120/cafe54, restaurant72-seed-locked; Ba Na missing entirely + 9 office-junk types for human 15% pass); nac-2 LLM batch doi Bach]
- [ ] T004 [P] Add `BE/.env.example` + config loader (Ollama URL, snapshot path, Google Places API key, OSRM base URL; no secrets committed)
- [ ] T005 LLM gateway client (`BE/app/services/llm.py`): JSON mode, temp 0.1, Pydantic validate, ≤2 retries
- [ ] T006 [P] FE API client skeleton (`FE/lib/api/client.dart`, base URL config)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

- [ ] T007 [P] Pydantic schemas (`BE/app/schemas/models.py`): User, TripRequest, POI, Restaurant, RouteSegment, Activity, Itinerary, DynamicEvent, Expense, WeatherSnapshot, EvaluationRecord [A: poi.py+eval.py DONE 2026-09-28 (7/7 seed validate); C: trip done; B: plan.py pending]
- [X] T008 [P] Snapshot loader + validation (`BE/app/services/snapshot.py`): verified flag, fetched_at, TravelEval schema check
- [ ] T009 [P] Error envelope + logging middleware (`BE/app/main.py`)
- [ ] T010 Route matrix service (`BE/app/services/matrix.py`): cache lookup first, OSRM fetch hook, never haversine-only for feasibility
- [ ] T011 Gate primitives (`BE/app/services/gate.py`): FAR/VROH/B3/BCS boolean checks used by validator AND evaluator

**Checkpoint**: Foundation ready — schemas load, seed snapshot validates, matrix serves, LLM gateway returns validated JSON

---

## Phase 3: US1 - Tạo itinerary cơ bản (Priority: P1) — MVP

**Goal**: Vietnamese prompt → structured trip → single feasible 1-day itinerary + reasons
**Independent Test**: quickstart S1–S3 on seed data

- [ ] T012 [P] [US1] Contract test `POST /v1/parse` in `BE/tests/contract/test_parse.py` (write FIRST, fail)
- [ ] T013 [P] [US1] Contract test `POST /v1/itinerary` in `BE/tests/contract/test_itinerary.py` (write FIRST, fail)
- [ ] T014 [P] [US1] Parser service (`BE/app/services/parser.py`): NL → TripRequest, clarification list on missing slots
- [ ] T015 [P] [US1] POI retrieval/filter (`BE/app/services/retrieval.py`): hard-constraint filter + candidate list
- [ ] T016 [P] [US1] Rule ranker nấc-1 (`BE/app/services/rank.py`): attribute + context weights
- [ ] T017 [US1] CP-SAT optimizer basic (`BE/app/services/optimizer.py`): OPTW, depot/flow/Tmax/time-window, 5s timeout (depends on T007, T010)
- [ ] T018 [US1] Validator gate (`BE/app/services/validator.py`): FAR/VROH/B3/BCS via gate.py (depends on T011)
- [ ] T019 [US1] Response builder (`BE/app/services/response.py`): itinerary + totals + constraint status
- [ ] T020 [US1] Routers `parse` + `itinerary` (`BE/app/routers/`) per contracts/api.md
- [ ] T021 [US1] Integration test seed end-to-end in `BE/tests/integration/test_us1_flow.py` (S2+S3)

**Checkpoint**: US1 fully functional — fixed Vietnamese prompt yields feasible itinerary on 7-POI seed

---

## Phase 4: US2 - Gợi ý POI phù hợp ngữ cảnh (Priority: P1)

**Goal**: Preference-aware POI/restaurant suggestions with uncertainty labels
**Independent Test**: "quán yên tĩnh hẹn hò gần biển" returns matching POIs with reasons

- [X] T022 [P] [US2] Extend POI schema fields (ambience, crowd, dietary, pros/cons, source, fetched_at)
- [ ] T023 [US2] Context scorer (`BE/app/services/context_score.py`): preference→attribute mapping incl. "yên tĩnh/hẹn hò/sau hiking" rules
- [ ] T024 [US2] Uncertainty labeling in retrieval output (unverified excluded from main plan)
- [ ] T025 [US2] Integration test US2 in `BE/tests/integration/test_us2_recommend.py`

**Checkpoint**: US1 + US2 work independently

---

## Phase 5: US3 - Thứ tự theo sở thích + PATM (Priority: P1)

**Goal**: Transition scoring (rule nấc-1 → LightGBM nấc-2) + precedence constraints
**Independent Test**: hiking→beach outscores beach→hiking; pairwise accuracy ≥70%

- [X] T026 [P] [US3] Transition feature extractor, 16 features (`BE/ml/patm/features.py`)
- [X] T027 [P] [US3] Rule scorer nấc-1 (`BE/ml/patm/rule_score.py`) + unit test
- [ ] T028 [US3] Pair dataset builder: 1,500–2,000 pairs (min viable 500–1,000; protocol 1000-rule/600-judge/200-human, swap-check, 30/40/30 balance) in `BE/ml/patm/make_pairs.py` (depends on T003 seed + T003b snapshot; owner batch LLM: Bách; human-check: bạn, ≤3 ngày sau batch)
- [ ] T029 [US3] LightGBM RankNet trainer (`BE/ml/patm/train.py`): 5-fold + held-out, export model.txt (depends on T028)
- [ ] T030 [US3] FastAPI scorer + precedence wiring into optimizer (`q_ij` edge weights, W_A+s_A≤W_B) (depends on T017, T029)
- [ ] T031 [US3] PATM eval test: pairwise accuracy, flip consistency, leave-POI-out CV (giấu nguyên 20% POI khỏi train — chứng minh tổng quát hóa trên POI chưa từng thấy) in `BE/tests/unit/test_patm.py`

**Checkpoint**: US3 pipeline scores transitions; optimizer prefers preference order when feasible

---

## Phase 6: US4 - Nhiều phương án + chấm điểm (Priority: P1)

**Goal**: 3 profiles (savings/balanced/experience), scored cards, user select
**Independent Test**: one request → ≥2 feasible plans with distinct scores/reasons

- [ ] T032 [US4] Multi-profile optimizer runs + solution pool (`BE/app/services/profiles.py`)
- [ ] T033 [US4] Plan scorer (Profit/Utility + gate) + select endpoint (`POST /v1/itinerary/select`)
- [ ] T034 [US4] Integration test US4 (distinctness + selection persistence)

---

## Phase 7: US5 - Quản lý chi tiêu (Priority: P1)

**Goal**: Budget set at planning, expense log, 80%/100% alerts, remaining feeds replan
**Independent Test**: quickstart S6

- [ ] T035 [P] [US5] Expense store + routers (`POST /v1/expenses`, summary) per contracts/api.md
- [ ] T036 [US5] Budget wiring: trip budget → alerts → remaining into replan constraints (depends on T035 + Phase 10)
- [ ] T037 [US5] FE budget UI (replace in-memory expenses with API) in `FE/lib/features/expenses/`
- [ ] T038 [US5] Integration test US5 (S6 scenario)

---

## Phase 8: US6 - Thời tiết (Priority: P1)

**Goal**: Open-Meteo fetch/cache, context injection, rain>70% proactive suggestion
**Independent Test**: mocked rain 80% afternoon → outdoor swapped + reason cited

- [ ] T039 [P] [US6] Weather service (`BE/app/services/weather.py`): fetch, cache, fetched_at label
- [ ] T040 [US6] Weather→context wiring (weather_id features, explanation lines, rain trigger)
- [ ] T041 [US6] Integration test US6 with mocked forecast

---

## Phase 9: US7 - Giải thích (Priority: P2)

**Goal**: Fact/inference-split explanations with uncertainty flags
**Independent Test**: every decision in sample plan has ≥1 evidenced reason; no unverified claims

- [ ] T042 [US7] Explanation builder (`BE/app/services/explainer.py`): claim+evidence|inference+source per decision
- [ ] T043 [US7] Hallucination sweep test (POI names/hours cross-checked vs snapshot)

---

## Phase 10: US8 - Replan động (Priority: P2)

**Goal**: State/delta, preservation, rolling replan, Plan/Clarify/NoSolution gate
**Independent Test**: quickstart S5 (2 done + rain event → versioned replan)

- [X] T044 [P] [US8] Event classifier S2 (templates + paraphrase + TF-IDF/LightGBM or PhoBERT, ~8 types)
- [ ] T045 [US8] State store + delta + preservation contract (`BE/app/services/state.py`)
- [ ] T046 [US8] Rolling-horizon replan + mode gate + version++ (depends on T017, T044, T045)
- [ ] T047 [US8] Mock GPS feed interface + timeline file for video demo
- [ ] T048 [US8] Integration test US8 (S5 scenario)

---

## Phase 11: US9 - Đánh giá (Priority: P2)

**Goal**: Tier-1 deterministic metrics + LLM-judge + 30–50 ĐN tests + Approach-B gold
**Independent Test**: quickstart S4 (tampered plan fails named gate, no soft scores)

- [X] T049 [P] [US9] Tier-1 metrics (`BE/eval/metrics.py`): FAR/VROH/BCS/TCS/HCS/STR/DTU/SSR/CSM/EDI/AQE
- [X] T050 [US9] LLM-judge Profit/BE (`BE/eval/judge.py`) + cost log [mock-test DONE 2026-09-28; live-run pending pairs full T003b/T028]
- [ ] T051 [US9] Test-suite builder + Approach-B gold generator (`BE/eval/gold/`, 30–50 ĐN queries)
- [ ] T052 [US9] Evaluator endpoint `POST /v1/evaluate` per contracts/api.md (depends on T049)
- [ ] T053 [US9] Full-suite run: baselines (distance-only, LLM-only) vs hybrid; record SC-005→SC-010

**Checkpoint**: All user stories independently functional

---

## Phase 12: Polish & Cross-Cutting

**Purpose**: Demo-ready integration

- [ ] T054 [P] FE API client replaces all in-memory demo data (`FE/lib/api/`, itinerary/map/expenses features)
- [ ] T055 [P] Plan cards UI (3 profiles + scores + select) in `FE/lib/features/itinerary/`
- [ ] T056 [P] Radar-chart comparison script (hybrid vs baselines)
- [ ] T057 Full quickstart.md validation run (S1–S7 green)
- [ ] T058 Docs: README BE run guide + demo video script (mock GPS timeline + rain scenario)
- [ ] T059 Security sweep: no secrets, `.env` excluded, logs redacted

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2** (blocks everything) → **Phases 3–11** in priority order (3–8 P1, 9–11 P2) → **Phase 12**.
- Within story: tests FIRST (fail) → models → services → endpoints → integration.
- Parallel lanes for 3-person team: A = data/eval (T003, T028, T051, Phase 11), B = optimizer/solver (T017, T030, T032, T046), C = parser/API/FE (T014, T020, T037, T054, T055). PATM train (T029) + event clf (T044) run CPU-side anytime after data ready.
- MVP stop line: Phases 1–8 + T054/T057 (static demo). P2 (9–11) follows.

## Backlog (P3 — sau MVP, không chặn demo)

- [ ] T060 Duration nấc 3: mine temporal expressions từ reviews ("đi 2 tiếng", "cả buổi sáng") + update prior `p50` từ actual activity durations (rule-based, không continual learning — constitution V; xem R8)

## Milestone M1 (mobility prior — ngoài MVP line)

- [ ] T062 Foursquare mobility prior P(cat|cat,bucket) + PATM feature (prior.py/crosswalk/transition_prior.json, features #17, eval vs unigram + ablation) [PARTIAL 2026-09-28 lane A: ppl −10.9% MET / acc +6.0% SHORT / ablation +1.0pp SHORT (+5pp); feature wired, tests green; NO tick - see docs/mobility-prior.md]

## Milestone M2 (dwell duration prior — ngoài MVP line)

- [ ] T064 Foursquare-TKY dwell EB-shrinkage duration prior + optimizer/validator hooks (duration_prior.py/json, seed smoke; real eval coverage>=80% + MAE>=10% better PENDING user gold checklist) [WIP 2026-09-28 lane A: n=1136 dwells, posteriors sane, smoke log-MAE 0.546 preliminary; NO tick - see docs/dwell-prior.md]

## Milestone M4 (weather label — ngoài MVP line)

- [ ] T063 OSM tags+geometry + indoor/outdoor labeler + validator/explainer hooks (weather_label/, seed+OSM smoke; real eval macro-F1>=0.95 PENDING user I/O audit) [WIP 2026-09-28 lane A: DN 2978 + HoiAn 1396 elements (TEMP), rules smoke indoor2655/outdoor323, GBDT hook ready; NO tick - see docs/weather-label.md]
