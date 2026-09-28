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

## R3. Language understanding: local LLM primary, API fallback
- **Decision**: Qwen3-14B Q4 primary (Ollama), Sailor2-8B fallback, JSON mode + temp 0.1 + Pydantic validate + ≤2 retries (closed-loop repair). API (GPT-4o-mini/Gemini Flash) used ONLY for: (a) polish explanation text for demo recording, (b) re-judge ambiguous edge-case pairs. Budget: <5 USD total.
- **Rationale**: 18–24GB MacBook runs 14B at 30–55 tok/s; Vietnamese verified; full stack runs offline for demo reliability; zero API cost for ~600 judge pairs. API fallback covers quality ceiling for demo polish without locking into paid dependency.
- **Alternatives considered**: API-only primary (rejected: cost + network dependence at demo); ≤4B local (rejected: drops Vietnamese diacritics); small CPU fine-tune allowed since rev 2026-09-28 (intent classifier S3, PhoBERT-base, 300–500 labels — baseline/offline role only; parser stays LLM-primary).

## R4. Routing data: OSRM snapshot matrix (no VietMap)
- **Decision**: Precompute/cache N≤200 Da Nang matrix once (40k cells) via OSRM. VietMap NOT used at all.
- **Rationale**: OSRM is free, deterministic, offline-capable; VietMap free tier expires + ToS limits on bulk caching + prior HTTP 423 issues. Simplifies stack to zero external routing dependencies.
- **Alternatives considered**: VietMap (rejected: 2-month free, ToS bulk-cache ban, HTTP 423 history); haversine-only (rejected: breaks B3 feasibility); GraphHopper (rejected: more complex than OSRM for same result).

## R5. API + app: FastAPI backend, Flutter frontend, free-tier hosting
- **Decision**: New Python package under `BE/`; existing Flutter app gains API client replacing in-memory demo data; `index.html` stays demo/test. BE deployed on free tier (Render/Fly.io) for mobile to call anytime; local dev on MacBook.
- **Rationale**: Free tier enables real-time mobile demo without local network setup; warm-up 5 min before demo; backup video quay local if venue wifi fails.
- **Alternatives considered**: Local-only (rejected: mobile can't call localhost across network easily); paid hosting (rejected: unnecessary for MVP); new repo (rejected: splits map/routing assets).

## R6. Evaluation: TravelEval tiers 1→2, cuts documented
- **Decision**: Deterministic metrics first (FAR/VROH/BCS/TCS/HCS/STR/DTU/SSR/CSM/EDI/AQE), LLM-judge Profit/BE second; cut human experts/intercity/seasonal queuing; 30–50 ĐN tests; gold via Approach B.
- **Rationale**: Paper's repo is public and reusable; CN dataset unusable for ĐN so snapshot self-built to TravelEval schema; student-scale effort mapped (tier 1: 1–2 days, tier 2: 1 week).
- **Alternatives considered**: Full TravelEval replication (rejected: needs experts + CN data); no evaluator (rejected: constitution III).

## R7. POI snapshot: SerpApi-details + FSQ-OS volume (rev 2026-09-28, grill-locked)
- **Decision**: (1) PRIMARY quality fields: SerpApi Google-Maps (free 250 searches/mo, 50/hr, cached searches free) — ~10 list queries per category/district (hl=vi, gl=vn) + details per place_id for top 200–250 POIs (title, gps, rating, price, operating_hours 7-day, phone). One careful run (no reviews/photos engines); (2) VOLUME: Foursquare OS Places (Apache 2.0, monthly Parquet, unlimited bulk) VN-slice + Overture bbox for 1000-POI base + re-crawls; (3) SUPPORT: Geoapify 3k/day no-card (coords/details, unlimited cache) + OpenTripMap 5k/day (landmarks). Apify $5 demoted to backup-2. FORBIDDEN: multi-account quota evasion, review/photo engines on free quota, Foody scrape, Yelp (VN≈0).
- **Rationale**: SerpApi verified (docs 2026-09-28) to return hours+price+rating; 200 POIs ≈ 210–220 searches fits one month. FSQ-OS covers volume/re-runs legally. Old Apify-first plan kept as fallback only.
- **Alternatives considered**: Apify one-shot (demoted: $5 cap, gray ToS); Google Places API New (deferred: Visa + no-cache rule); OSM Overpass + manual = fallback D (unchanged).

## R8. Visit-duration estimation: 3 nấc (không có nguồn public cho VN)
- **Decision**: Không nguồn nào (Google Places, OSM) cung cấp visit duration cho ĐN → ước tính 3 nấc. **Nấc 1** (P1): category defaults × modifiers (rating ≥4.5 → ×1.2, tag "rộng/lớn" → ×1.3, "check-in/nhẹ" → ×0.7) → `{p25,p50,p75}`, `dur_source=category_rule`, confidence=low. **Nấc 2** (P1): LLM batch (Qwen3-14B qua đêm: name + category + rating + tags + reviews nếu có → JSON `{p25,p50,p75,confidence}`, swap-check hỏi 2 lần, tự loại inconsistent), human verify 15% + toàn bộ outlier (p50 lệch default >50% — moi được POI đặc biệt như Bà Nà 4–6h). **Nấc 3** (P3, sau MVP): mine biểu hiện thời gian trong review ("đi 2 tiếng", "cả buổi sáng") + update prior p50 từ actual activity durations (rule-based, không continual learning — constitution V).
- **Rationale**: Duration sai → vỡ feasibility (SC-006/SC-007 phụ thuộc nó). Optimizer lập lịch bằng p50; gate kiểm p75 buffer (FR-019); UI hiển thị "~90–150 phút (ước tính)" — constitution IV cấm trình bày như fact.
- **Alternatives considered**: 1 số manual duy nhất (rejected: không system, không scale lên 1,000 POI); Google Popular Times (rejected: không expose qua Places API, scrape vi phạm ToS); continual learning từ feedback (rejected cho MVP: constitution V).
