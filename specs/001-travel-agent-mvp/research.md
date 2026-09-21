# Research: Personalized Travel Agent MVP

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
Prior deep research lives in NotebookLM notebook `PBL6-TravelAgent`
(notes `research_brief_*`, 22 papers). This file consolidates decisions.

## R1. Itinerary optimizer: OR-Tools CP-SAT
- **Decision**: Model as OPTW/TOPTW + RCSPP resource vector; solve with OR-Tools CP-SAT (5s timeout MVP).
- **Rationale**: Survey + VRP-LLM papers agree exact solvers hold 100% feasibility at N<100 in 1–15s; end-to-end LLM routing fails (gap 21–55%, infeasible at 500).
- **Alternatives considered**: PyVRP/HGS (kept as baseline, not core — CP-SAT handles time windows + precedence natively); ALNS heuristics (rejected: unnecessary code at MVP scale); LLM-only planning (rejected: evidence).

## R2. Transition scoring: LightGBM pairwise ranker
- **Decision**: RankNet/Bradley-Terry loss, 16 features, server-side FastAPI (<5ms).
- **Rationale**: Convex-like loss converges on CPU in seconds at 500–2000 pairs; tabular data fits GBDT; inference <1ms; output feeds optimizer as `q_ij`.
- **Alternatives considered**: GRPO/RL (rejected: needs A100, unstable on small data — papers); MLP-ONNX (kept as nấc-3 option for on-device); rule weights (nấc-1 bootstrap + fallback).

## R3. Language understanding: local LLM via Ollama
- **Decision**: Qwen3-14B Q4 primary, Sailor2-8B fallback, JSON mode + temp 0.1 + Pydantic validate + ≤2 retries (closed-loop repair); API only as polish fallback.
- **Rationale**: 18–24GB MacBook runs 14B at 30–55 tok/s; Vietnamese verified; full stack runs offline for demo reliability; zero API cost for ~600 judge pairs.
- **Alternatives considered**: API-only (rejected as primary: cost + network dependence at demo); ≤4B local (rejected: drops Vietnamese diacritics); PhoBERT fine-tune for parser (kept as S3 option if offline parser or baseline needed).

## R4. Routing data: OSRM snapshot matrix
- **Decision**: Precompute/cache N≤200 Da Nang matrix once (40k cells); VietMap only if key holds Routing rights, never load-bearing.
- **Rationale**: OSRM public demo rate-limits; cached matrix makes optimizer/evaluator deterministic and offline-capable; prior HTTP 423 on VietMap key.
- **Alternatives considered**: Live VietMap (rejected as primary: 2-month free + ToS limits on bulk caching); haversine-only (rejected: breaks B3 feasibility).

## R5. API + app: FastAPI backend, Flutter frontend
- **Decision**: New Python package under `BE/`; existing Flutter app gains API client replacing in-memory demo data; `index.html` stays demo/test.
- **Rationale**: Matches team direction (BE/ reserved, Flutter shell in progress); mobile-first decision N-Q7/H.
- **Alternatives considered**: New repo (rejected: splits map/routing assets); web-first (rejected: team builds Flutter).

## R6. Evaluation: TravelEval tiers 1→2, cuts documented
- **Decision**: Deterministic metrics first (FAR/VROH/BCS/TCS/HCS/STR/DTU/SSR/CSM/EDI/AQE), LLM-judge Profit/BE second; cut human experts/intercity/seasonal queuing; 30–50 ĐN tests; gold via Approach B.
- **Rationale**: Paper's repo is public and reusable; CN dataset unusable for ĐN so snapshot self-built to TravelEval schema; student-scale effort mapped (tier 1: 1–2 days, tier 2: 1 week).
- **Alternatives considered**: Full TravelEval replication (rejected: needs experts + CN data); no evaluator (rejected: constitution III).

## R7. POI snapshot: self-built Da Nang 100–200
- **Decision**: OSM Overpass skeleton + official-site/Foody crawl for hours/prices + agent normalization + 15% human verify, TravelEval JSON schema.
- **Rationale**: No VN POI dataset exists with hours/prices; Google scraping violates ToS; `DemoTripData` 7 places seed format + first gold test.
- **Alternatives considered**: Google Maps crawl (rejected: key cost + ToS); manual-only (kept as fallback lane per-person 30–40 POIs).
