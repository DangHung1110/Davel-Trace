# Audit dữ liệu TravelAgent — 2026-11-18

## 0. Tóm tắt
- POI chính `BE/data/snapshots/danang-v1/pois.json`: **742** bản ghi (metadata khai 745, lệch -3); trùng nghi ngờ 0 cặp; toạ độ hợp lệ 742/742.
- Quán ăn **128** và quán cà phê **108** (theo `cat`); 153 POI (20.6%) không vào 9 thể loại đích, gồm lưu trú 76 và spa 77 (đếm theo `cat`).
- Giờ mở cửa parse được **483/742** (65.1%); 243 POI rỗng; không có 24/7. Giá VND (`ticket_vnd`) chỉ **13/742** (1.8%).
- Mô tả: **0/742** — THIẾU; văn bản thay thế rất ít. Nguồn chính SerpAPI/Google Maps chiếm 659/742 POI — cần rà soát điều khoản trước khi dùng ML.
- Phân hạng theo luật đề bài: **A 392, B 350, C 0** (biến thể nghiêm ngặt: A 6, B 404, C 332). Code: 99 module, 94 tệp test, 822 hàm test (chưa chạy).

## 1. Kiểm kê project và code

Cây thư mục (tối đa 3 cấp; số tệp tính đệ quy; bỏ `.git`, `node_modules`, `venv`, `__pycache__`, `.pytest_cache`):

```
.opencode/ (15 tệp)
  skills/ (12 tệp)
    design-md/ (3 tệp)
    enhance-prompt/ (3 tệp)
    generate-design/ (4 tệp)
    taste-design/ (2 tệp)
.specify/ (21 tệp)
  integrations/ (2 tệp)
  memory/ (2 tệp)
  scripts/ (6 tệp)
    powershell/ (6 tệp)
  templates/ (5 tệp)
  workflows/ (2 tệp)
    speckit/ (1 tệp)
BE/ (299 tệp)
  app/ (52 tệp)
    routers/ (12 tệp)
    schemas/ (6 tệp)
    services/ (31 tệp)
  data/ (85 tệp)
    raw-round2/ (52 tệp)
    snapshots/ (32 tệp)
  eval/ (8 tệp)
    gold/ (5 tệp)
  ml/ (51 tệp)
    data/ (18 tệp)
    event_clf/ (6 tệp)
    patm/ (23 tệp)
    weather_label/ (4 tệp)
  tests/ (94 tệp)
    contract/ (13 tệp)
    integration/ (9 tệp)
    unit/ (70 tệp)
  tools/ (4 tệp)
data/ (89 tệp)
  gps/ (1 tệp)
  snapshots/ (87 tệp)
    danang-full-tmp/ (84 tệp)
    danang-v1/ (3 tệp)
docs/ (13 tệp)
FE/ (4 tệp)
go-pmtiles_1.31.2_Windows_x86_64/ (3 tệp)
reports/ (4 tệp)
  audit_scripts/ (2 tệp)
scripts/ (1 tệp)
specs/ (12 tệp)
  001-travel-agent-mvp/ (12 tệp)
    checklists/ (2 tệp)
    contracts/ (1 tệp)
.env.lane-a-bak
AGENTS.md
DavelAgentIdea.txt
HANDOFF.md
index.html
README.md
server.py
sh.exe.stackdump
```

Tệp dữ liệu: đường dẫn, định dạng, dung lượng, số dòng, cột:kiểu. Thư mục có ≥5 tệp dữ liệu được gộp một dòng (số tệp, tổng dung lượng, schema giao của 5 tệp đầu). JSON không phải danh sách thì số dòng là số khóa.

| Đường dẫn | Định dạng | Dung lượng | Số dòng | Cột: kiểu |
|---|---|---:|---:|---|
| `.opencode/package-lock.json` | JSON | 14,634 B | object (4 khóa) | name:string, lockfileVersion:number, requires:bool, packages:object |
| `.opencode/package.json` | JSON | 65 B | object (1 khóa) | dependencies:object |
| `.specify/feature.json` | JSON | 56 B | object (1 khóa) | feature_directory:string |
| `.specify/init-options.json` | JSON | 161 B | object (6 khóa) | ai:string, feature_numbering:string, here:bool, integration:string, script:string, speckit_version:string |
| `.specify/integration.json` | JSON | 298 B | object (6 khóa) | version:string, integration_state_schema:number, installed_integrations:array, integration_settings:object, integration:string, default_integration:string |
| `.specify/integrations/opencode.manifest.json` | JSON | 1,283 B | object (4 khóa) | integration:string, version:string, installed_at:string, files:object |
| `.specify/integrations/speckit.manifest.json` | JSON | 1,535 B | object (4 khóa) | integration:string, version:string, installed_at:string, files:object |
| `.specify/memory/.constitution-template.json` | JSON | 103 B | object (2 khóa) | sha256:string, source:string |
| `.specify/workflows/workflow-registry.json` | JSON | 381 B | object (2 khóa) | schema_version:string, workflows:object |
| `BE/data/ranker_shadow.jsonl` | JSONL | 0 B | 0 | — |
| `BE/data/raw-round2/quota.json` | JSON | 76 B | object (3 khóa) | used:number, last:string, cap:number |
| `BE/data/raw-round2/search2/` (51 tệp) | JSON | 1,950,860 B tổng | payload không đồng nhất | search_information, search_metadata, search_parameters |
| `BE/data/snapshots/danang-v1/` (19 tệp) | JSON/JSONL | 28,003,969 B tổng | payload không đồng nhất | schema chung rỗng |
| `BE/eval/gold/t051_scoped_suite.json` | JSON | 29,843 B | 30 | gate:object, infeasible:string, itinerary:object, prefs_text:string, query_id:string, soft:object, trip:object |
| `BE/eval/gold/t053_baselines.json` | JSON | 3,315 B | object (11 khóa) | generated_at:string, suite:string, snapshot:string, coverage:object, feasible:number, infeasible:number, hybrid:object, systems:object (+3 cột) |
| `BE/ml/event_clf/artifacts/labels.json` | JSON | 104 B | 10 | — |
| `BE/ml/event_clf/artifacts/vocab.json` | JSON | 22,681 B | object (2 khóa) | vocab:object, idf:array |
| `BE/ml/patm/` (7 tệp) | JSON | 729,026 B tổng | payload không đồng nhất | schema chung rỗng |
| `data/gps/demo_day.json` | JSON | 391 B | object (2 khóa) | name:string, points:array |
| `data/snapshots/danang-full-tmp/pois_raw.json` | JSON | 234,283 B | 368 | ambience:string, cons:array, dur_confidence:string, dur_source:string, fee:number, fetched_at:string, intensity:number, lat:number (+13 cột) |
| `data/snapshots/danang-full-tmp/pois_raw_before_2026-10.json` | JSON | 211,981 B | 333 | ambience:string, cons:array, dur_confidence:string, dur_source:string, fee:number, fetched_at:string, intensity:number, lat:number (+13 cột) |
| `data/snapshots/danang-full-tmp/quota.json` | JSON | 67 B | object (3 khóa) | used:number, last:string, cap:number |
| `data/snapshots/danang-full-tmp/refresh-2026-10.json` | JSON | 2,301 B | object (7 khóa) | new_place_ids:array, changed_hours:array, changed_ratings:array, changed_coords:array, quota_spent:number, total_pois:number, excluded_outside_bbox:number |
| `data/snapshots/danang-full-tmp/details/` (20 tệp) | JSON | 31,035 B tổng | payload không đồng nhất | error, search_information, search_metadata, search_parameters |
| `data/snapshots/danang-full-tmp/search/` (30 tệp) | JSON | 977,186 B tổng | payload không đồng nhất | search_information, search_metadata, search_parameters |
| `data/snapshots/danang-full-tmp/search/2026-10/` (30 tệp) | JSON | 926,937 B tổng | payload không đồng nhất | search_information, search_metadata, search_parameters |
| `data/snapshots/danang-v1/matrix.json` | JSON | 4,471 B | object (9 khóa) | snapshot:string, ids:array, n:number, mode:string, method:string, source:string, confidence:string, note:string (+1 cột) |
| `data/snapshots/danang-v1/pois.json` | JSON | 4,170 B | 7 | ambience:string, cons:array, cuisine:array, dietary:array, dur_confidence:string, dur_source:string, fee:number, fetched_at:string (+16 cột) |

Code (phân nhóm theo đường dẫn; trạng thái xác định bằng bằng chứng tĩnh: test/import, hàm rỗng, TODO, có `__main__`; **chưa chạy** crawler hay pytest — pytest không cài trong môi trường này (`No module named pytest`)):

| Nhóm | Chức năng | Số module | Trạng thái |
|---|---|---|---|
| crawler | thu thập/làm giàu/ingest POI (BE/ml/data, fetch weather) | 20 | KHÔNG XÁC ĐỊNH 13, chạy được* 7 |
| schema | kiểu dữ liệu API/POI/plan (BE/app/schemas) | 5 | chạy được* 4, bản nháp 1 |
| solver | ma trận, tối ưu lộ trình, benchmark (optimizer, matrix, tools) | 8 | chạy được* 7, KHÔNG XÁC ĐỊNH 1 |
| verifier | kiểm tra điều kiện, gate, đánh giá (validator, gate, judge, metrics) | 4 | chạy được* 4 |
| test | 94 tệp test, 822 hàm test (BE/tests) | 0 | chạy được* (tĩnh) |
| notebook | THIẾU: không có notebook .ipynb nào trong repo | 0 | không có |
| khác | router API, service, ML model, cấu hình, server | 62 | chạy được* 55, KHÔNG XÁC ĐỊNH 7 |

Chi tiết từng module (trạng thái: `chạy được*` = có test/import tĩnh, chưa chạy; `dở dang` = có hàm rỗng/TODO; `bản nháp` = không ai gọi; `KHÔNG XÁC ĐỊNH` = CLI chưa rõ):

| Module | Nhóm | Chức năng (docstring) | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| `BE/ml/data/crawl_targeted.py` | crawler | Targeted SerpApi crawl, round 2 (lane A, stdlib only). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/5; TODO:0; script CLI, không có test/import |
| `BE/ml/data/curate_pool.py` | crawler | Offline LLM-assisted candidate curation (test-local evidence, NOT runtime). | chạy được* | test:1; import:0; hàm rỗng:0/8; TODO:0; có test hoặc import từ code khác |
| `BE/ml/data/enrich_snapshot.py` | crawler | Enrich snapshot weather labels via the audit-safe T063 classifier (stdlib only). | chạy được* | test:2; import:3; hàm rỗng:0/23; TODO:0; có test hoặc import từ code khác |
| `BE/ml/data/enrich_tags.py` | crawler | Smart-tag enrichment v2 (lane A, stdlib only). Taxonomy agreed 2026-10-09. | chạy được* | test:1; import:3; hàm rỗng:0/7; TODO:0; có test hoặc import từ code khác |
| `BE/ml/data/fetch_apify.py` | crawler | Fetch full Da Nang snapshot via Apify one-shot (T003b, CHUAN BI - CHUA CHAY). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/4; TODO:0; script CLI, không có test/import |
| `BE/ml/data/fetch_serpapi.py` | crawler | SerpApi Google Maps fetch (T003b-SCRIPT, lane A). | chạy được* | test:0; import:1; hàm rỗng:0/19; TODO:0; có test hoặc import từ code khác |
| `BE/ml/data/ingest_geo.py` | crawler | Ingest geo_answers.json into snapshot (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/1; TODO:0; script CLI, không có test/import |
| `BE/ml/data/ingest_money.py` | crawler | Ingest money_answers.json into snapshot (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/1; TODO:0; script CLI, không có test/import |
| `BE/ml/data/ingest_review.py` | crawler | Ingest review_answers.json into the snapshot (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/4; TODO:0; script CLI, không có test/import |
| `BE/ml/data/manual_add.py` | crawler | Apply manual_pois.json sidecar into snapshot (lane A, idempotent). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/1; TODO:0; script CLI, không có test/import |
| `BE/ml/data/osm_add.py` | crawler | Add missing OSM POIs into the snapshot (lane A, stdlib only). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/8; TODO:0; script CLI, không có test/import |
| `BE/ml/data/osm_join.py` | crawler | Join OSM tags (fee, opening_hours) into snapshot by proximity (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/5; TODO:0; script CLI, không có test/import |
| `BE/ml/data/price_from_raw.py` | crawler | Fill price_band from SerpApi search-payload prices (lane A, no quota). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/4; TODO:0; script CLI, không có test/import |
| `BE/ml/data/prune_snapshot.py` | crawler | Prune non-tourist POIs + unify categories (lane A, stdlib only). | chạy được* | test:0; import:1; hàm rỗng:0/3; TODO:0; có test hoặc import từ code khác |
| `BE/ml/data/render_geo_review.py` | crawler | Render geo review form for beach/nature/park POIs (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/2; TODO:0; script CLI, không có test/import |
| `BE/ml/data/render_money_review.py` | crawler | Render money review form: expensive-band check + adult venues + must-go adds (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/3; TODO:0; script CLI, không có test/import |
| `BE/ml/data/render_review.py` | crawler | Render REVIEW_V2.md as an offline tick form (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/2; TODO:0; script CLI, không có test/import |
| `BE/ml/data/spotcheck_v2.py` | crawler | Auto spot-check v2 + verified-flag applier (stdlib only). | chạy được* | test:1; import:0; hàm rỗng:0/22; TODO:0; có test hoặc import từ code khác |
| `BE/ml/weather_label/fetch_geometry.py` | crawler | Fetch linked OSM geometry for the T063 weather labeler. | chạy được* | test:1; import:0; hàm rỗng:0/20; TODO:0; có test hoặc import từ code khác |
| `BE/ml/weather_label/fetch_osm.py` | crawler | OSM fetch via Overpass (T063-M4CODE, lane A). Tags+geometry, local cache. | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/3; TODO:0; script CLI, không có test/import |
| `BE/app/schemas/eval.py` | schema | Eval schemas (T007-eval, lane A). EvaluationRecord per data-model.md. | chạy được* | test:1; import:1; hàm rỗng:0/0; TODO:0; có test hoặc import từ code khác |
| `BE/app/schemas/models.py` | schema | Schema re-exports (T007 + T061b). One import seam for all four schema files. | bản nháp | test:0; import:0; hàm rỗng:0/0; TODO:0; không có test, không được import |
| `BE/app/schemas/plan.py` | schema | Plan schemas (T007-plan, lane B). RouteSegment, Activity, Itinerary. | chạy được* | test:1; import:1; hàm rỗng:0/1; TODO:0; có test hoặc import từ code khác |
| `BE/app/schemas/poi.py` | schema | POI schemas (T007-poi, lane A). POI + Restaurant per data-model.md. | chạy được* | test:1; import:1; hàm rỗng:0/1; TODO:0; có test hoặc import từ code khác |
| `BE/app/schemas/trip.py` | schema | Trip schemas (T007-foundation, lane C). User + TripRequest per data-model.md. | chạy được* | test:2; import:3; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/matrix.py` | solver | Route matrix service (T010, lane B). Cache-first, OSRM backfill, no haversine. | chạy được* | test:7; import:1; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/optimizer.py` | solver | CP-SAT optimizer basic, OPTW (T017, lane B). Depot/flow/Tmax/windows. | chạy được* | test:10; import:4; hàm rỗng:0/16; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/osrm_client.py` | solver | OSRM table client (T010b, lane B). Stdlib urllib, batched `/table/v1/driving/`. | chạy được* | test:3; import:3; hàm rỗng:0/7; TODO:0; có test hoặc import từ code khác |
| `BE/eval/baselines.py` | solver | T053 full-suite run: baselines vs hybrid on the T051 gold (lane A). No LLM | chạy được* | test:1; import:0; hàm rỗng:0/14; TODO:0; có test hoặc import từ code khác |
| `BE/tools/benchmark_optimizer.py` | solver | T030 benchmark — gap between CP-SAT (5s budget) and the exact optimum on | chạy được* | test:1; import:0; hàm rỗng:0/4; TODO:0; có test hoặc import từ code khác |
| `BE/tools/build_poi_matrix.py` | solver | Build the OSRM travel-time matrix for the top-N snapshot POIs (T010b, lane B). | chạy được* | test:1; import:0; hàm rỗng:0/6; TODO:0; có test hoặc import từ code khác |
| `BE/tools/build_verify_page.py` | solver | Build a self-contained human-review page for the auto-verify queue. | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/10; TODO:0; script CLI, không có test/import |
| `BE/tools/expand_poi_matrix.py` | solver | Append verified snapshot POIs to the committed OSRM matrix (T010b follow-up). | chạy được* | test:1; import:0; hàm rỗng:0/10; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/gate.py` | verifier | Canonical gate registry (T011 + T061f), shared by validator + evaluator. | chạy được* | test:12; import:8; hàm rỗng:0/23; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/validator.py` | verifier | Validator gate (T018, lane B). Per-gate pass/fail + violations. | chạy được* | test:9; import:3; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/eval/judge.py` | verifier | LLM-judge Profit/BE (T050, lane A). Swap-checked pairwise preference. | chạy được* | test:1; import:0; hàm rỗng:0/9; TODO:0; có test hoặc import từ code khác |
| `BE/eval/metrics.py` | verifier | Tier-1 deterministic metrics (T049, lane A; converged at T061f). No LLM. | chạy được* | test:3; import:3; hàm rỗng:0/13; TODO:0; có test hoặc import từ code khác |
| `BE/app/config.py` | khác | Config loader (T004, lane C). Env + optional BE/.env file, stdlib only. | chạy được* | test:11; import:8; hàm rỗng:0/3; TODO:0; có test hoặc import từ code khác |
| `BE/app/main.py` | khác | FastAPI entry (T001 + T020, lane C). Health + routers. Error envelope | chạy được* | test:21; import:0; hàm rỗng:0/7; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/accept.py` | khác | POST /v1/accept (NOTE(test-local), do NOT PR as-is). "Chốt plan" logging. | chạy được* | test:0; import:1; hàm rỗng:0/4; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/evaluate.py` | khác | POST /v1/evaluate (T052, lane C wiring; contracts/api.md, quickstart S4). | chạy được* | test:2; import:2; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/expenses.py` | khác | Expense routers (T035, lane C). POST /v1/expenses + GET summary. | chạy được* | test:0; import:1; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/itinerary.py` | khác | POST /v1/itinerary (T020, lane C). TripRequest -> profile plans. | chạy được* | test:9; import:1; hàm rỗng:0/12; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/parse.py` | khác | POST /v1/parse (T020, lane C). NL -> TripRequest per contracts/api.md. | chạy được* | test:0; import:1; hàm rỗng:0/1; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/repair.py` | khác | POST /v1/repair (NOTE(test-local), do NOT PR as-is). | chạy được* | test:0; import:1; hàm rỗng:0/4; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/replan.py` | khác | POST /v1/replan (T020 shell + T046 logic, wired at T061e). | chạy được* | test:0; import:1; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/review.py` | khác | POST /v1/review (NOTE(test-local), do NOT PR as-is). LLM layer-3 review. | chạy được* | test:2; import:2; hàm rỗng:0/13; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/scorer.py` | khác | POST /v1/score-transition (S7, contracts/api.md PATM pre-check). | chạy được* | test:0; import:1; hàm rỗng:0/1; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/select.py` | khác | POST /v1/itinerary/select (T033e, lane C — closes US4). Chốt plan. | chạy được* | test:6; import:5; hàm rỗng:0/7; TODO:0; có test hoặc import từ code khác |
| `BE/app/routers/weather.py` | khác | GET /v1/weather (contracts/api.md), backed by the cached forecast service. | chạy được* | test:0; import:1; hàm rỗng:0/1; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/budget.py` | khác | Replan budget feed (T036b, lane B). Tighten spend to actuals. | chạy được* | test:1; import:1; hàm rỗng:0/1; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/common.py` | khác | Lane-B service helper names -> BE/common.py (T061c consolidation). | chạy được* | test:5; import:9; hàm rỗng:0/0; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/context_score.py` | khác | Context scorer (T023, lane C). Preference -> attribute mapping. | chạy được* | test:2; import:0; hàm rỗng:0/3; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/expenses.py` | khác | Expense store (T035, lane C). In-memory; STUB-NOTE: persistent | chạy được* | test:4; import:1; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/explain.py` | khác | Retrieval explanation -> public response lists (B4/FR-013/FR-024). | chạy được* | test:0; import:2; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/explainer.py` | khác | Explanation builder (T042, lane C). Fact/inference-split reasons. | chạy được* | test:2; import:0; hàm rỗng:0/4; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/gps.py` | khác | Mock GPS feed + demo timeline (T047, lane C). | chạy được* | test:1; import:0; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/llm.py` | khác | LLM gateway (T005, lane C). JSON mode + temp 0.1 + Pydantic validate. | chạy được* | test:3; import:6; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/parser.py` | khác | NL parser VI -> TripRequest (T014, lane C) via LLM gateway (T005). | chạy được* | test:4; import:1; hàm rỗng:0/3; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/pool.py` | khác | Solution pool + MMR diverse selection (TASK-4, lane B). | chạy được* | test:2; import:1; hàm rỗng:0/11; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/profile_filter.py` | khác | Hard profile pre-filter (onboarding contract): allergy / must_avoid / accessibility. | chạy được* | test:4; import:6; hàm rỗng:0/18; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/profiles.py` | khác | Multi-profile optimizer runs + solution pool (T032, lane B; US4). | chạy được* | test:10; import:3; hàm rỗng:0/23; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/rank.py` | khác | Rule ranker nac-1 (T016, lane C). Attribute + context weights. | chạy được* | test:6; import:3; hàm rỗng:0/8; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/ranker.py` | khác | Shadow LLM ranker (Hướng 3 + Hướng 6). NEVER on the live response path. | chạy được* | test:1; import:1; hàm rỗng:0/23; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/repair.py` | khác | LLM-guided, gate-checked plan repair (test-local; max 2 rounds). | chạy được* | test:2; import:1; hàm rỗng:0/14; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/replan.py` | khác | Rolling-horizon replan + mode gate + version++ (T046, lane B). | chạy được* | test:2; import:2; hàm rỗng:0/4; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/response.py` | khác | Response builder (T019, lane B). Optimizer output + validator result | chạy được* | test:2; import:0; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/retrieval.py` | khác | POI retrieval/filter (T015 + T024, lane C). Hard filter + uncertainty. | chạy được* | test:9; import:5; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/scorer.py` | khác | Transition scorer: q_ij for the optimizer (T030, lane B). Model or rule. | chạy được* | test:6; import:4; hàm rỗng:0/10; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/snapshot.py` | khác | Snapshot loader + validation (T008, lane A). | chạy được* | test:1; import:2; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/soft_rules.py` | khác | Layer-1 soft/quality rules (test-local data-quality pass), one small module. | chạy được* | test:6; import:11; hàm rỗng:0/21; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/state.py` | khác | Trip state store + delta + preservation contract (T045, lane B). | chạy được* | test:3; import:3; hàm rỗng:0/4; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/templates.py` | khác | Day templates V1 (3 hard archetypes) + profile -> template selection. | chạy được* | test:4; import:1; hàm rỗng:0/11; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/trip_ctx.py` | khác | Trip context + dynamic traveler STATE (planning time, per request). | chạy được* | test:7; import:2; hàm rỗng:0/23; TODO:0; có test hoặc import từ code khác |
| `BE/app/services/weather.py` | khác | Weather service + context wiring (T039+T040, lane C). Open-Meteo, cached. | chạy được* | test:2; import:2; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/common.py` | khác | Shared stdlib glue for BE (one spot for copy-pasted helpers). | chạy được* | test:2; import:20; hàm rỗng:0/13; TODO:0; có test hoặc import từ code khác |
| `BE/eval/gold/approach_b.py` | khác | Approach-B gold generator (T051-BUILDER, lane A). filter -> TSP -> chain. | chạy được* | test:1; import:2; hàm rỗng:0/9; TODO:0; có test hoặc import từ code khác |
| `BE/eval/gold/build.py` | khác | Suite entry (T051-BUILDER, lane A): queries -> Approach-B golds -> T049 gate. | chạy được* | test:1; import:1; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/eval/gold/queries.py` | khác | Test-suite query builder (T051-BUILDER, lane A). Deterministic ĐN queries. | chạy được* | test:1; import:1; hàm rỗng:0/2; TODO:0; có test hoặc import từ code khác |
| `BE/ml/event_clf/paraphrase.py` | khác | Paraphrase: rule-based variants now, Qwen batch frame for later (T044). | chạy được* | test:1; import:1; hàm rỗng:0/6; TODO:0; có test hoặc import từ code khác |
| `BE/ml/event_clf/templates.py` | khác | Event templates S2 (T044, lane A). 10 disruption types, Vietnamese. | chạy được* | test:1; import:2; hàm rỗng:0/0; TODO:0; có test hoặc import từ code khác |
| `BE/ml/event_clf/train.py` | khác | Event classifier trainer S2 (T044, lane A). TF-IDF + LightGBM, CPU-only. | chạy được* | test:1; import:0; hàm rỗng:0/12; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/build_prior.py` | khác | Mobility prior builder (T062 M1, lane A). Foursquare TSMC2014 NYC+TKY. | chạy được* | test:0; import:1; hàm rỗng:0/7; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/duration_prior.py` | khác | Dwell duration prior via Empirical Bayes (T064 M2, lane A). NO TICK (gold pending). | chạy được* | test:1; import:0; hàm rỗng:0/9; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/estimate_duration.py` | khác | Duration estimator nac-1 (T003c): category defaults x modifiers -> p25/p50/p75. | chạy được* | test:2; import:12; hàm rỗng:0/6; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/evaluate.py` | khác | POI-disjoint evaluation for PATM with a human-labeled blind subset. | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/2; TODO:0; script CLI, không có test/import |
| `BE/ml/patm/features.py` | khác | Transition feature extractor, 21 features (T026 + T062 M1 + T063b, lane A). | chạy được* | test:2; import:3; hàm rỗng:0/12; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/gemini_judge.py` | khác | Gemini judge runner for T028 pair batches (lane A, stdlib + REST only). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/3; TODO:0; script CLI, không có test/import |
| `BE/ml/patm/judge_batch_v2.py` | khác | Emit judge batch v2: pairs x synthetic user profiles x contexts (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/1; TODO:0; script CLI, không có test/import |
| `BE/ml/patm/local_judge.py` | khác | Local-LLM judge runner for T028 pair batches (lane A, stdlib + REST). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/2; TODO:0; script CLI, không có test/import |
| `BE/ml/patm/make_pairs.py` | khác | Pair dataset builder (T028-BUILDER, lane A). Protocol T028, stdlib only. | chạy được* | test:4; import:3; hàm rỗng:0/13; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/prior.py` | khác | Mobility prior runtime (T062 M1, lane A). P(next/prev, time-bucket). | chạy được* | test:1; import:1; hàm rỗng:0/5; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/render_verify.py` | khác | Render human-verify set as an offline single-file HTML form (lane A). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/3; TODO:0; script CLI, không có test/import |
| `BE/ml/patm/rule_score.py` | khác | Rule scorer nac-1 (T027, lane A). Deterministic order preference. | chạy được* | test:2; import:1; hàm rỗng:0/6; TODO:0; có test hoặc import từ code khác |
| `BE/ml/patm/sample_verify.py` | khác | Build human-verify set: 200 pairs, disagreement-first (lane A, stdlib). | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/3; TODO:0; script CLI, không có test/import |
| `BE/ml/patm/train.py` | khác | LightGBM pairwise trainer, nac-2 (T029-TRAINER, lane A). Smoke-ready. | chạy được* | test:0; import:1; hàm rỗng:0/4; TODO:0; có test hoặc import từ code khác |
| `BE/ml/weather_label/labeler.py` | khác | Weather labeler indoor/outdoor + rain protection (T063, lane A). | chạy được* | test:3; import:3; hàm rỗng:0/37; TODO:0; có test hoặc import từ code khác |
| `BE/ml/weather_label/render_review.py` | khác | Standalone human-audit review generator for T063 weather labels. | chạy được* | test:1; import:0; hàm rỗng:0/11; TODO:0; có test hoặc import từ code khác |
| `server.py` | khác | (không có docstring) | KHÔNG XÁC ĐỊNH | test:0; import:0; hàm rỗng:0/4; TODO:0; script CLI, không có test/import |

Trạng thái tổng: chạy được* 77, KHÔNG XÁC ĐỊNH 21, bản nháp 1. Không liệt kê `BE/**/__init__.py` (khai báo package) và `reports/` (script audit này).

## 2. Nguồn gốc và giấy phép

- Metadata snapshot: source `serpapi/google-maps`, fetched_at `2026-10-03`, enriched_at `2026-10-26`, pruned_at `2026-10-10`. Mỗi POI có `fetched_at` nhưng chỉ 4 giá trị ngày (lớn nhất 2026-10-03 = 319 POI); `verified_at` có 410/742 POI.
- Nguồn theo POI (cột `source`): `serpapi/google-maps`=659, `osm/overpass`=78, `manual+web`=4, `manual+review`=1.
- **Google Maps qua SerpAPI** (7 tệp .py kể cả test nhắc `serpapi`): `659` POI có nguồn này. Đây là nguồn rủi ro: điều khoản Google/SerpAPI có thể hạn chế lưu, tái sử dụng hoặc dùng để train. **Facebook**: không có POI nào mang nguồn Facebook; 0 tệp code có nhắc `facebook`.
- Hosts trong code thu thập (BE/ml, BE/app, theo số tệp): `127.0.0.1:1234`, `overpass-api.de`, `overpass.kumi.systems`, `localhost:11434`, `127.0.0.1:5500`, `localhost:5500`, `api.openai.com`, `api.open-meteo.com`. OSM: `{osm_n}` POI có `osm_evidence`, nguồn `osm/overpass` = {sum(1 for x in raw if x.get('source') == 'osm/overpass')}.
- Giấy phép: repo có 11 lần nhắc license/điều khoản trong 3 tệp tài liệu; không có văn bản giấy phép dữ liệu nào được gắn vào snapshot. **KHÔNG XÁC ĐỊNH** quyền sử dụng/tái phân phối từ dữ liệu cục bộ.
- Cập nhật: có ngày cập nhật (`verified_at`) cho 410/742 POI; thời điểm lấy `fetched_at` không thay thế ngày xác minh.

## 3. Hồ sơ danh mục POI

- File chính: `BE/data/snapshots/danang-v1/pois.json` (742 POI, khóa `pois`) — app đọc đúng thư mục này (BE/app/config.py). Các ứng viên khác: `data/snapshots/danang-full-tmp/pois_raw.json` (368 bản ghi), `pois_raw_before_2026-10.json` (333), `data/snapshots/danang-v1/pois.json` (7 bản ghi, không dùng).
- Tổng 742; metadata 745; trùng nghi ngờ (< 50 m và tên bỏ dấu ≥ 0.85): **0 cặp**, 0 POI liên quan.

**Số cặp trùng: 0 cặp, không có cặp để in.** Chẩn đoán: có 108 cặp < 50 m (bất kể tên), độ giống tên lớn nhất 0.684 < 0.85.
Ánh xạ 9 thể loại: `cat` là nguồn chính; từ khóa trong `type` (tiếng Việt, đã bỏ dấu) chỉ tinh chỉnh pagoda (chùa), museum_indoor (bảo tàng), night_spot (bar, karaoke, chợ đêm) và day_market (chợ). `cat`→nhóm: beach→beach; viewpoint→viewpoint; park/landmark/nature/attraction→outdoor_landmark; museum→museum_indoor; market→day_market; bar→night_spot; restaurant→restaurant; cafe→cafe; spa, lodging, mã khác→other.

| Thể loại đích | Số POI |
|---|---:|
| beach | 16 |
| viewpoint | 2 |
| outdoor_landmark | 164 |
| pagoda | 35 |
| museum_indoor | 18 |
| day_market | 46 |
| night_spot | 72 |
| restaurant | 128 |
| cafe | 108 |
| other | 153 |

**Quán ăn và quán cà phê có không? Có.** Theo `cat`: restaurant 128, cafe 108. Theo nhóm đích: restaurant 128, cafe 108. Không ánh xạ được (other): 153 POI.

Top 20 `type` gốc trong nhóm `other`:

| type gốc | Số POI |
|---|---:|
| Khách sạn | 58 |
| Spa | 44 |
| Spa mát xa | 17 |
| Khách sạn nghỉ dưỡng | 15 |
| Spa sức khỏe | 10 |
| Spa y tế | 2 |
| Khách sạn lưu trú dài hạn | 1 |
| unknown | 1 |
| Lưu trú nhà dân | 1 |
| Bác sĩ trị liệu xoa bóp | 1 |
| Thẩm mỹ viện | 1 |
| Spa đá nóng | 1 |
| Spa mặt | 1 |

Top 20 `type` gốc toàn bộ:

| type gốc | Số POI |
|---|---:|
| Quán cà phê | 106 |
| Điểm thu hút khách du lịch | 62 |
| Khách sạn | 58 |
| Nhà hàng | 44 |
| Spa | 44 |
| Chùa phật giáo | 34 |
| Quán bar | 34 |
| Nhà hàng hải sản | 26 |
| Cơ sở thờ tự | 19 |
| Spa mát xa | 17 |
| Nhà hàng Việt Nam | 16 |
| Chợ | 16 |
| Khách sạn nghỉ dưỡng | 15 |
| Nhà thờ Công giáo | 14 |
| Lớp học nấu ăn | 14 |
| Quán bar karaoke | 13 |
| Cửa hàng quà lưu niệm | 12 |
| Quán mì | 12 |
| Đỉnh núi | 11 |
| Quán bar cocktail | 11 |

- Toạ độ: thiếu 0; ngoài khung lon 107.2–108.8 / lat 14.9–16.3: 0; nghi đảo lat/lon: 0. Cự ly tới Cầu Rồng (chỉ POI có toạ độ): 0–5 km 439, 5–15 km 254, 15–40 km 49, >40 km 0.
- Phường/xã: **THIẾU** — snapshot không có trường địa chỉ, không có `ward_code`.
- **THAY THẾ**: dùng `crawl_query` (chỉ 340/742 POI có) để đếm theo quận cũ: Hải Châu 19, Thanh Khê 61, Sơn Trà 45, Ngũ Hành Sơn 38, Liên Chiểu 39, Cẩm Lệ 0, Hòa Vang 0, Hoàng Sa 0. Khớp được 202/340; 540 POI không khớp quận nào (có thể chỉ là 'Đà Nẵng' chung hoặc không có `crawl_query`). Đây là vị trí của truy vấn tìm kiếm, không phải địa chỉ thật.

## 4. Độ phủ từng trường

| Trường | Có giá trị | % | Ví dụ | Ghi chú chất lượng |
|---|---:|---:|---|---|
| Tên (có dấu tiếng Việt) | 476/742 | 64.2% | Nhà Hàng Hải Sản - Ơ Kìa | tên có ký tự có dấu; tên là chuỗi lẫn tiếng Việt/Anh |
| Mô tả | 0/742 | 0.0% | — | **THIẾU**: ambience/pros/cons có khóa nhưng rỗng; xem mục 6 |
| Địa chỉ | 0/742 | 0.0% | — | **THIẾU**: không có trường `address` |
| Toạ độ | 742/742 | 100.0% | 16.0801078, 108.2230986 | lat/lon; 0 thiếu |
| Category (cat / type) | 742/742 | 100.0% | restaurant / Nhà hàng hải sản | cat chuẩn hoá và type gốc tiếng Việt |
| Giờ mở cửa (có dữ liệu) | 499/742 | 67.3% | list chuỗi | parse được 483; rỗng 243 |
| Giá VND (`ticket_vnd`) — THAY THẾ cho giá vé | 13/742 | 1.8% | [60000, 100000, 60000] | **THAY THẾ**: không có trường `price`; dùng `ticket_vnd` (VND) và `price_level` (thang Google 1–3, không phải VND) |
| Price_level (Google, THAY THẾ) | 742/742 | 100.0% | 2 | không phải số tiền; phân bố 1:103, 2:579, 3:60 |
| Website/fanpage | 0/742 | 0.0% | — | **THIẾU** trong snapshot; raw payload có khóa website/facebook ở 93/136 tệp |
| SĐT doanh nghiệp | 0/742 | 0.0% | — | **THIẾU** trong snapshot; raw payload có khóa phone ở 94/136 tệp |
| Ảnh | 0/742 | 0.0% | — | **THIẾU** trong snapshot; raw payload có khóa ảnh ở 111/136 tệp (số lần 6157) |
| Giấy phép ảnh | 0/742 | 0.0% | — | **THIẾU** hoàn toàn |
| Rating | 656/742 | 88.4% | — | trường `rating`; số lượt đánh giá (review count) **THIẾU** |
| Ngày cập nhật (`verified_at`) | 410/742 | 55.3% | — | 410 trong 12 tháng; `fetched_at` là ngày snapshot (4 giá trị) |
| Tag | 741/742 | 99.9% | — | `tags` list; trong nhà/ngoài trời (`smart_tags.space`) 742; hợp trẻ em (`party` có family) 448 |
| Wikidata / mã ngoài | 742/742 | 100.0% | — | `poi_id` ChIJ 659, osm: 78, manual 5; `osm_evidence.osm` 223; **Wikidata THIẾU** |

Ghi chú: 'Ngày cập nhật' — `verified_at` là ngày xác minh từng POI; `fetched_at` ở POI chỉ là ngày snapshot.

## 5. Giờ mở cửa và giá

- Kiểu dữ liệu: `opening_hours` là list chuỗi (list 742/742); rỗng `[]` = 243, null = 0. Dạng lưu: `HH:MM-HH:MM` theo khoảng, không có thứ trong tuần.
- Tỉ lệ: parse được **483/742 = 65.1%** (HH:MM-HH:MM 483, 24/7 0); **24/7: 0.0%**; **trống: 243/742 = 32.7%**; không parse: 16.
- Theo từng thứ trong tuần: **THIẾU** — không có khung giờ theo ngày, parser không xác định được tỉ lệ theo thứ. **THAY THẾ** (ghi nhận): áp cùng một khung giờ cho mọi ngày.

10 mẫu không parse (có 16; tất cả có dạng nhiều khoảng giờ trong một chuỗi, ví dụ `11:00-15:00, 17:00-22:30`):

| poi_id | Giá trị thô |
|---|---|
| `ChIJZSsvT9QZQjERf-oLnsT1C3Y` | ['11:00-15:00, 17:00-22:30', '11:00-15:30, 17:00-23:00'] |
| `ChIJ-VaWslgZQjERwaL3uKR9fB4` | ['10:30-14:00, 17:00-02:00'] |
| `ChIJYahwiHIXQjER0CIGd09pgcg` | ['10:00-14:00, 16:00-22:00'] |
| `ChIJ4UuIQXgXQjERz192UgYuxMU` | ['11:00-14:00, 17:00-22:00'] |
| `ChIJ1eef2IsZQjERjy-_tblqzJs` | ['10:00-14:00, 16:00-20:30'] |
| `ChIJ1yFjaOwZQjERO43leJW7YHk` | ['10:00-14:00, 16:00-21:00'] |
| `ChIJo8fznMYZQjERNtNTUT-ZJyk` | ['08:00-12:00, 14:00-16:30'] |
| `ChIJTXOYPFQXQjERGWO0Jf095tw` | ['08:00-11:00, 13:30-16:30'] |
| `ChIJJZ47gFgZQjERvHYpZqPp0lU` | ['00:00-06:30, 14:30-00:00'] |
| `ChIJQ8VFVdgZQjERM6OjWmgGH5A` | ['10:30-13:00, 16:00-20:30'] |

- Giá: đơn vị VND cho `ticket_vnd` (13 POI, khoảng 20000–650000 VND); `price_level` là thang 1–3 (không phải VND); `fee` là trường deprecated, toàn bộ = 0:742.
- Tỉ lệ có giá VND: **13/742 = 1.8%**. Tỉ lệ ghi 'miễn phí' (price_note/ticket_note): **10/742**. `fee=0` không chứng minh miễn phí, nên không suy miễn phí từ trường này.

## 6. Văn bản và ảnh

- Mô tả: **THIẾU** — 0/742 POI có mô tả; độ dài TB và ngôn ngữ không tính được.
- **THAY THẾ** (các ghi chú/bằng chứng có sẵn): `web_evidence` 63 POI, TB 8.6 từ, có dấu Việt 39/63; `price_note` 262 POI, TB 6.0 từ, có dấu Việt 258/262; `ticket_note` 33 POI, TB 12.5 từ, có dấu Việt 33/33; `access_note` 35 POI, TB 18.1 từ, có dấu Việt 35/35. Đây là ghi chú/bằng chứng crawl, không phải mô tả điểm đến.
- Review text: **THIẾU** trong snapshot (0 POI). Raw payload SerpAPI có khóa review ở 111/136 tệp (số lần 3447); không in nội dung. Điều khoản: review là nội dung của Google, cần kiểm tra trước khi lưu hay dùng để embedding.
- Ảnh: snapshot không có ảnh hay URL ảnh. Raw payload có khóa ảnh ở 111/136 tệp; vị trí lưu là các tệp raw trong `BE/data/raw-round2/` và `data/snapshots/danang-full-tmp/`; **giấy phép ảnh THIẾU**.

## 7. Đối chiếu schema đích

| Trường đích | Trạng thái | Căn cứ |
|---|---|---|
| `poi_id` | CÓ SẴN | 742/742; ChIJ 659, osm 78, manual 5 |
| `name.vi` | SUY RA ĐƯỢC | `name` có dấu 476/742; chưa gắn nhãn ngôn ngữ |
| `name.en` | THIẾU | không có tên tiếng Anh |
| `category` | CÓ SẴN | `cat` và `type` 100% |
| `zone` | SUY RA ĐƯỢC | từ `crawl_query` quận cũ (202/742); chưa có ranh giới để tính từ toạ độ |
| `ward_code` | THIẾU | không có mã phường/xã mới |
| `display_point` | CÓ SẴN | lat/lon 100% |
| `access_points` | THIẾU | `access_note` 35 POI là văn bản, không có toạ độ điểm vào |
| `geofence` | THIẾU | không có đa giác |
| `opening_hours` | CÓ SẴN | một phần: parse được 483/742 |
| `price` | SUY RA ĐƯỢC | `ticket_vnd` 13/742; `price_level` (thang Google) là proxy |
| `tags` | CÓ SẴN | 741/742 |
| `effort` | SUY RA ĐƯỢC | từ `intensity` (100%), thang chưa có tài liệu |
| `weather_sensitivity` | CÓ SẴN | `weather_sensitive` 100%; `smart_tags` exposure |
| `time_profile` | CÓ SẴN | `smart_tags.time` 665/742 |
| `dwell_prior` | CÓ SẴN | `visit_min` và `dur_source`/`dur_confidence` 100% |
| `provenance.source` | CÓ SẴN | `source` 742/742 |
| `provenance.verified_at` | CÓ SẴN | 410/742 (chưa đủ cho mọi POI) |
| `provenance.confidence` | SUY RA ĐƯỢC | không có trường chung; có `dur_confidence`, `space_confidence`, `rain_protection_confidence` |
| `valid_from / valid_to` | THIẾU | không có thời hạn hiệu lực |

## 8. Dữ liệu khác

| Hạng mục | Kết quả đếm | Ghi chú |
|---|---|---|
| Log người dùng | 1 tệp tên có log/shadow/accept | `BE/data/ranker_shadow.jsonl` là nhật ký ranker (không phải log người dùng thật); không có log người dùng thật. **THIẾU** |
| GPS/chặng đi | 6 điểm trong `data/gps/demo_day.json` | demo, không xác định nguồn người dùng; tọa độ không in. Code: `BE/app/services/gps.py` |
| Đánh giá/nhãn | 8 tệp (review/human/answers/verify) | review_answers, human_answers, human_verify_200 là nhãn người xem; số dòng ở mục 1 |
| Thời tiết đã lưu | 5 tệp tên có weather | nhãn weather_label, weather_review_200, WEATHER_AUDIT |
| Ma trận khoảng cách/thời gian | `BE/data/snapshots/danang-v1/matrix.json`: 498 ID, phủ 498/742 POI | ma trận hiện có để xếp hạng/solver |
| TripSpec mẫu | 0 tệp tên có trip | **THIẾU** mẫu dữ liệu; chỉ có schema `BE/app/schemas/trip.py` |
| Câu nói/truy vấn mẫu (gold) | 30 truy vấn trong 2 tệp gold | `BE/eval/gold/t051_scoped_suite.json` 30, `BE/eval/gold/t053_baselines.json` 0 |
| Test case | 822 hàm `def test_` trong 94 tệp | chưa chạy (pytest không cài) |
| Bộ benchmark solver | `BE/tools/benchmark_optimizer.py`, `BE/eval/baselines.py`, t053 baseline | có code và test; số kết quả xem `BE/eval/gold/t053_baselines.json` |

## 9. Phân hạng A/B/C

Luật đề bài: **A** = toạ độ hợp lệ + category + giờ parse được + nguồn có giá trị + verified_at trong 12 tháng. **C** = thiếu toạ độ/category, nghi trùng, hoặc chữ đóng cửa/closed/ngừng hoạt động (ranh giới từ, để 'enclosed' không khớp). **B** = phần còn lại.

Bảng chính theo 9 thể loại đích + other:

| Thể loại đích | A | B | C | Tổng |
|---|---:|---:|---:|---:|
| beach | 11 | 5 | 0 | 16 |
| viewpoint | 1 | 1 | 0 | 2 |
| outdoor_landmark | 48 | 116 | 0 | 164 |
| pagoda | 10 | 25 | 0 | 35 |
| museum_indoor | 7 | 11 | 0 | 18 |
| day_market | 24 | 22 | 0 | 46 |
| night_spot | 47 | 25 | 0 | 72 |
| restaurant | 106 | 22 | 0 | 128 |
| cafe | 90 | 18 | 0 | 108 |
| other | 48 | 105 | 0 | 153 |
| **Tổng** | **392** | **350** | **0** | **742** |

Đối chiếu: A 392, B 350, C 0 — khớp với A392/B350/C0 của đối chiếu độc lập. Chữ 'closed/đóng cửa' với ranh giới từ khớp 0 POI; nếu bỏ ranh giới từ, chuỗi thuần khớp 504 POI, toàn bộ là 'enclosed' trong `rain_cover`.

Bảng phụ theo `cat` gốc:

| cat | A | B | C | Tổng |
|---|---:|---:|---:|---:|
| restaurant | 106 | 22 | 0 | 128 |
| cafe | 90 | 18 | 0 | 108 |
| attraction | 30 | 57 | 0 | 87 |
| landmark | 20 | 65 | 0 | 85 |
| spa | 48 | 29 | 0 | 77 |
| lodging | 0 | 76 | 0 | 76 |
| bar | 46 | 23 | 0 | 69 |
| market | 25 | 24 | 0 | 49 |
| beach | 11 | 5 | 0 | 16 |
| nature | 2 | 14 | 0 | 16 |
| museum | 7 | 8 | 0 | 15 |
| park | 6 | 8 | 0 | 14 |
| viewpoint | 1 | 1 | 0 | 2 |

Biến thể nghiêm ngặt (bảng phụ): thêm `verified==true` và giá rõ (ticket_vnd>0, fee>0 hoặc free_entry) vào A; `verified==false` thành C.

| Thể loại đích | A | B | C | Tổng |
|---|---:|---:|---:|---:|
| beach | 0 | 11 | 5 | 16 |
| viewpoint | 0 | 1 | 1 | 2 |
| outdoor_landmark | 1 | 47 | 116 | 164 |
| pagoda | 0 | 10 | 25 | 35 |
| museum_indoor | 5 | 6 | 7 | 18 |
| day_market | 0 | 27 | 19 | 46 |
| night_spot | 0 | 48 | 24 | 72 |
| restaurant | 0 | 116 | 12 | 128 |
| cafe | 0 | 90 | 18 | 108 |
| other | 0 | 48 | 105 | 153 |
| **Tổng** | **6** | **404** | **332** | **742** |

## 10. Vấn đề phát hiện

| Mức độ | Mô tả | Số bản ghi | Ví dụ | Gợi ý xử lý |
|---|---|---:|---|---|
| CAO | Nguồn Google Maps qua SerpAPI: điều khoản chưa rõ cho lưu/tái dùng/train | 659 | source=serpapi/google-maps | Rà soát điều khoản và provenance trước khi dùng ML. |
| CAO | Giá VND gần như không có; price_level là thang Google | 729 | ticket_vnd 13/742 | Thu thập giá vé có nguồn, đơn vị VND và ngày. |
| CAO | Không có mô tả nào để embedding hay phân loại văn bản | 742 | ambience/pros/cons rỗng | Bổ sung mô tả có nguồn và quyền dùng trước khi embedding. |
| TRUNG BÌNH | Giờ mở cửa rỗng hoặc không parse được | 259 | rỗng 243; nhiều khoảng 16 | Thêm parser nhiều khoảng và lịch theo thứ. |
| TRUNG BÌNH | Metadata `count` lệch số POI thực tế | 3 | 745 so với 742 | Đồng bộ count khi xuất snapshot. |
| TRUNG BÌNH | Thiếu verified_at cho POI (không đủ điều kiện A) | 332 | verified_at trống | Ưu tiên xác minh các POI dự kiến dùng. |
| TRUNG BÌNH | Lưu trú/spa/bar lẫn trong danh sách POI du lịch | 222 | spa=77, lodging=76, bar=69 | Tách khỏi activity hoặc gắn cờ suitability. |
| TRUNG BÌNH | Nhóm other chiếm tỉ lệ lớn | 153 | 20.6% POI | Quyết định loại khỏi taxonomy hay thêm nhãn. |
| TRUNG BÌNH | Quận/phường không có trường địa chỉ | 742 | không có address/ward | Thêm địa chỉ có cấu trúc và mã phường/xã mới. |
| THẤP | Regex 'closed' khớp nhầm 'enclosed' trong smart_tags.rain_cover | 504 | rain_cover='enclosed' | Dùng ranh giới từ (đã áp dụng trong phân hạng). |
| THẤP | Trường io_label còn rỗng | 492 | io_label null | Bổ sung nhãn trong nhà/ngoài trời khi có bằng chứng. |

## 11. Những điều KHÔNG XÁC ĐỊNH được

- Quyền sử dụng, tái phân phối và train trên POI, review, ảnh: không có điều khoản/giấy phép trong repo.
- Trạng thái đóng/mở thực tế hôm nay; `verified_at` không bảo đảm địa điểm còn hoạt động.
- Code có chạy được không: crawler gọi mạng và pytest không cài, nên chỉ có bằng chứng tĩnh; các module có `chạy được*` chưa chạy thử.
- Nội dung và nguồn của log/GPS demo, và TripSpec mẫu (không có tệp).
- Ranh giới phường/xã và geofence: không có dữ liệu.

Đối chiếu tuân thủ đề bài (mục đã THIẾU hoặc THAY THẾ):

| Yêu cầu đề bài | Trạng thái | Ghi chú |
|---|---|---|
| Mục 2: điều khoản/giấy phép nguồn Google Maps, Facebook | THIẾU | không có văn bản giấy phép trong repo hoặc snapshot; cần rà soát điều khoản trước khi dùng ML |
| Mục 3: phường/xã (ward_code mới) | THIẾU | không có trường địa chỉ hay mã phường/xã |
| Mục 3: phân bố theo phường/xã hoặc quận cũ | THAY THẾ | đếm theo `crawl_query` (202/742 POI khớp quận cũ); không phải địa chỉ thật |
| Mục 4: giá vé/giá trung bình | THAY THẾ | `ticket_vnd` 13/742 + `price_level` (thang Google, không phải VND) |
| Mục 4: địa chỉ | THIẾU | không có trường địa chỉ |
| Mục 4: website/fanpage, SĐT, ảnh, giấy phép ảnh, số lượt đánh giá, Wikidata | THIẾU | không có trong snapshot; raw payload có khóa nhưng không lưu thành trường POI |
| Mục 5: tỉ lệ parse theo từng thứ trong tuần | THIẾU | không lưu khung giờ theo ngày |
| Mục 5: tỉ lệ miễn phí | THIẾU | không có bằng chứng; fee=0 không đủ, chỉ 10 văn bản ghi 'miễn phí' |
| Mục 6: mô tả (độ dài, ngôn ngữ) | THIẾU | 0 POI có mô tả; THAY THẾ bằng ghi chú/bằng chứng ở trên |
| Mục 6: review text | THIẾU | không có trong snapshot; có khóa trong raw payload |
| Mục 6: ảnh và giấy phép | THIẾU | không có ảnh trong snapshot; giấy phép không có |
| Mục 7: schema `name.en` | THIẾU | không có tên tiếng Anh |
| Mục 7: schema `zone` | THAY THẾ | từ `crawl_query` quận cũ (202/742); chưa có ranh giới để tính từ toạ độ |
| Mục 7: schema `ward_code` | THIẾU | không có mã phường/xã mới |
| Mục 7: schema `access_points` | THIẾU | `access_note` 35 POI là văn bản, không có toạ độ điểm vào |
| Mục 7: schema `geofence` | THIẾU | không có đa giác |
| Mục 7: schema `price` | THAY THẾ | `ticket_vnd` 13/742; `price_level` (thang Google) là proxy |
| Mục 7: schema `valid_from / valid_to` | THIẾU | không có thời hạn hiệu lực |
| Mục 8: log người dùng thật, GPS/chặng thật | THIẾU | chỉ có demo GPS và nhật ký ranker |
| Mục 8: TripSpec mẫu | THIẾU | không có tệp mẫu |

## 12. Phụ lục

10 bản ghi POI ngẫu nhiên (seed = 42, qua `random.Random(42).sample`; trường cá nhân nhạy cảm đã che nếu có):

```json
[
  {
    "poi_id": "ChIJY_iyslwXQjERFoDw4waR2Sg",
    "name": "The Trip 66",
    "type": "Quán bar",
    "lat": 16.0398021,
    "lon": 108.2492857,
    "opening_hours": [
      "08:00-02:00"
    ],
    "visit_min": {
      "p25": 76,
      "p50": 108,
      "p75": 151
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 4.6,
    "tags": [
      "Quán bar",
      "Câu lạc bộ nhạc Blue",
      "Quán cà phê",
      "Quán bar rượu táo",
      "Quán bar cocktail",
      "Quán bar ca nhạc trực tiếp",
      "Câu lạc bộ nhạc Rock"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": false,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-12",
    "verified": true,
    "crawl_query": "quán bar Ngũ Hành Sơn",
    "intensity_source": "canonical_rule",
    "ws_source": "audit",
    "io_label": "I",
    "smart_tags": {
      "ticket": false,
      "price_band": "medium",
      "space": "indoor",
      "party": [
        "couple",
        "group"
      ],
      "time": [
        "night"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.1,
      "sun_exposure": 0.05,
      "wind_exposure": 0.1,
      "rain_cover": "enclosed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "cat": "bar",
    "price_note": "~200.000đ (khoảng 1-400.000 ₫)",
    "space_source": "audit",
    "space_confidence": 1.0,
    "space_evidence": [
      "audit=indoor (human audit wins)"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover",
      "audit indoor does not encode rain protection"
    ],
    "verified_by": "auto-verify-v1",
    "verified_at": "2026-10-29"
  },
  {
    "poi_id": "ChIJo5HJeVg9QjERxLqGaMYHXCw",
    "name": "Mây coffee",
    "type": "Quán cà phê",
    "lat": 16.1083241,
    "lon": 108.25934009999999,
    "opening_hours": [
      "07:00-19:00"
    ],
    "visit_min": {
      "p25": 38,
      "p50": 54,
      "p75": 76
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 1,
    "fee": 0,
    "rating": 5,
    "tags": [
      "Quán cà phê"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": false,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-03",
    "verified": false,
    "intensity_source": "canonical_rule",
    "io_label": null,
    "ws_source": "classifier_name",
    "smart_tags": {
      "ticket": false,
      "price_band": "cheap",
      "space": "indoor",
      "party": [
        "couple",
        "solo"
      ],
      "time": [
        "morning"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.1,
      "sun_exposure": 0.05,
      "wind_exposure": 0.1,
      "rain_cover": "enclosed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "osm_evidence": {
      "osm": "node/13463837701",
      "dist_m": 2.3,
      "fee": null,
      "hours": null,
      "name": null
    },
    "cat": "cafe",
    "price_note": "~50.000đ (khoảng 1-100.000 ₫)",
    "space_source": "name",
    "space_confidence": 0.6,
    "space_evidence": [
      "name indoor keyword(s) coffee"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover"
    ]
  },
  {
    "poi_id": "ChIJO0E1hoYXQjER-ML-N1yAGAU",
    "name": "Phố Nướng Tokyo Đà Nẵng",
    "type": "Nhà hàng",
    "lat": 16.0705931,
    "lon": 108.2429142,
    "opening_hours": [
      "11:00-23:00"
    ],
    "visit_min": {
      "p25": 42,
      "p50": 60,
      "p75": 84
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 4.3,
    "tags": [
      "Nhà hàng",
      "Nhà hàng món nướng"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": false,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-03",
    "verified": true,
    "intensity_source": "canonical_rule",
    "io_label": "I",
    "ws_source": "audit",
    "smart_tags": {
      "ticket": false,
      "price_band": null,
      "space": "indoor",
      "party": [
        "family",
        "couple",
        "group"
      ],
      "time": [
        "morning",
        "night"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.1,
      "sun_exposure": 0.05,
      "wind_exposure": 0.1,
      "rain_cover": "enclosed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "osm_evidence": {
      "osm": "node/4759752150",
      "dist_m": 2.7,
      "fee": null,
      "hours": null,
      "name": "Phố nướng Tokyo"
    },
    "cat": "restaurant",
    "space_source": "audit",
    "space_confidence": 1.0,
    "space_evidence": [
      "audit=indoor (human audit wins)"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover",
      "audit indoor does not encode rain protection"
    ],
    "verified_by": "auto-verify-v1",
    "verified_at": "2026-10-29"
  },
  {
    "poi_id": "ChIJw6DOwZ8QQjERjDMobkQxbF0",
    "name": "Chợ Bình Kỳ",
    "type": "Chợ",
    "lat": 15.9931538,
    "lon": 108.23893249999999,
    "opening_hours": [
      "05:00-16:30"
    ],
    "visit_min": {
      "p25": 52,
      "p50": 75,
      "p75": 105
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 3.8,
    "tags": [
      "Chợ"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": true,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-03",
    "verified": true,
    "intensity_source": "canonical_rule",
    "io_label": null,
    "ws_source": "classifier_name",
    "smart_tags": {
      "ticket": false,
      "price_band": null,
      "space": "both",
      "party": [
        "family",
        "group"
      ],
      "time": [
        "morning"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.6,
      "sun_exposure": 0.48,
      "wind_exposure": 0.48,
      "rain_cover": "mixed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "cat": "market",
    "space_source": "name",
    "space_confidence": 0.6,
    "space_evidence": [
      "name compound keyword(s) cho -> both"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover"
    ],
    "verified_by": "auto-verify-v1",
    "verified_at": "2026-10-29"
  },
  {
    "poi_id": "ChIJ82_sTbkQQjERQ5jmVkoovic",
    "name": "Bảo Tàng Văn Hóa Phật Giáo",
    "type": "Bảo tàng",
    "lat": 15.998929299999999,
    "lon": 108.2547934,
    "opening_hours": [
      "08:00-18:00"
    ],
    "visit_min": {
      "p25": 76,
      "p50": 108,
      "p75": 151
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 4.8,
    "tags": [
      "Bảo tàng",
      "Điểm thu hút khách du lịch"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": false,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-03",
    "verified": true,
    "intensity_source": "canonical_rule",
    "io_label": null,
    "ws_source": "classifier_name",
    "smart_tags": {
      "ticket": false,
      "price_band": null,
      "space": "indoor",
      "party": [
        "family",
        "couple",
        "solo",
        "group"
      ],
      "time": [
        "morning"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.05,
      "sun_exposure": 0.05,
      "wind_exposure": 0.05,
      "rain_cover": "enclosed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1+curated",
    "ticket_note": "Trong chùa Quán Thế Âm, không vé niêm yết, miễn phí/tùy hỷ",
    "osm_evidence": {
      "osm": "[REDACTED: possible personal contact]",
      "dist_m": 60.1,
      "fee": null,
      "hours": "Mo-Su 09:00-17:00",
      "name": "Bảo tàng Phật giáo"
    },
    "cat": "museum",
    "space_source": "name",
    "space_confidence": 0.6,
    "space_evidence": [
      "name indoor keyword(s) bao tang"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover"
    ],
    "verified_by": "auto-verify-v1",
    "verified_at": "2026-10-29"
  },
  {
    "poi_id": "ChIJmUEOJQAfQjERLPIN_eYfU9k",
    "name": "Khu du lịch Nam Ô Heritage",
    "type": "Điểm thu hút khách du lịch",
    "lat": 16.1108107,
    "lon": 108.1324214,
    "opening_hours": [],
    "visit_min": {
      "p25": 140,
      "p50": 200,
      "p75": 280
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 4.2,
    "tags": [
      "Điểm thu hút khách du lịch"
    ],
    "intensity": 2,
    "ambience": "",
    "weather_sensitive": true,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-03",
    "verified": false,
    "intensity_source": "canonical_rule",
    "io_label": "B",
    "ws_source": "audit",
    "smart_tags": {
      "ticket": false,
      "price_band": null,
      "space": "both",
      "party": [
        "family",
        "couple",
        "solo",
        "group"
      ],
      "time": [
        "morning"
      ],
      "budget": [
        "full-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.6,
      "sun_exposure": 0.48,
      "wind_exposure": 0.48,
      "rain_cover": "mixed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "cat": "attraction",
    "space_source": "audit",
    "space_confidence": 1.0,
    "space_evidence": [
      "audit=both (human audit wins)"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover",
      "audit both does not encode rain protection",
      "ambiguous name keyword(s) khu du lich ignored"
    ]
  },
  {
    "poi_id": "ChIJh_2eI0gZQjERROaoM-QEtXY",
    "name": "J Cafe",
    "type": "Quán cà phê",
    "lat": 16.0494293,
    "lon": 108.2398528,
    "opening_hours": [
      "07:00-22:00"
    ],
    "visit_min": {
      "p25": 38,
      "p50": 54,
      "p75": 76
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 1,
    "fee": 0,
    "rating": 4.9,
    "tags": [
      "Quán cà phê"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": false,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-03",
    "verified": true,
    "intensity_source": "canonical_rule",
    "io_label": null,
    "ws_source": "classifier_osm",
    "smart_tags": {
      "ticket": false,
      "price_band": "cheap",
      "space": "indoor",
      "party": [
        "couple",
        "solo"
      ],
      "time": [
        "morning"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.1,
      "sun_exposure": 0.05,
      "wind_exposure": 0.1,
      "rain_cover": "enclosed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "osm_evidence": {
      "osm": "[REDACTED: possible personal contact]",
      "dist_m": 3.4,
      "fee": null,
      "hours": "Mo-Su 07:00-22:00",
      "name": null
    },
    "cat": "cafe",
    "price_note": "~50.000đ (khoảng 1-100.000 ₫)",
    "space_source": "osm",
    "space_confidence": 0.8,
    "space_evidence": [
      "[REDACTED: possible personal contact]",
      "name indoor keyword(s) cafe"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover"
    ],
    "verified_by": "auto-verify-v1",
    "verified_at": "2026-10-29"
  },
  {
    "poi_id": "ChIJQRIRJDIYQjER4JvYKu_Qnak",
    "name": "WONDERLUST - Coffee & Souvenir",
    "type": "Quán cà phê",
    "lat": 16.0691557,
    "lon": 108.22384299999999,
    "opening_hours": [
      "08:00-19:30"
    ],
    "visit_min": {
      "p25": 38,
      "p50": 54,
      "p75": 76
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 4.5,
    "tags": [
      "Quán cà phê",
      "Cửa hàng lưu niệm"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": false,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-03",
    "verified": true,
    "intensity_source": "canonical_rule",
    "io_label": "I",
    "ws_source": "audit",
    "smart_tags": {
      "ticket": false,
      "price_band": "medium",
      "space": "indoor",
      "party": [
        "couple",
        "solo"
      ],
      "time": [
        "morning"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.1,
      "sun_exposure": 0.05,
      "wind_exposure": 0.1,
      "rain_cover": "enclosed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "osm_evidence": {
      "osm": "node/7103226688",
      "dist_m": 9.5,
      "fee": null,
      "hours": null,
      "name": "I Love Bánh Mì"
    },
    "cat": "cafe",
    "verified_at": "2026-10-08",
    "verified_by": "spotcheck-v1",
    "price_note": "~150.000đ (khoảng 100-200 N ₫)",
    "space_source": "audit",
    "space_confidence": 1.0,
    "space_evidence": [
      "audit=indoor (human audit wins)"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover",
      "audit indoor does not encode rain protection"
    ]
  },
  {
    "poi_id": "ChIJnZoMTbkQQjERwzvvHqGlb4E",
    "name": "Chùa Linh Sơn",
    "type": "Chùa phật giáo",
    "lat": 15.998874599999999,
    "lon": 108.2562411,
    "opening_hours": [],
    "visit_min": {
      "p25": 38,
      "p50": 54,
      "p75": 76
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 4.8,
    "tags": [
      "Chùa phật giáo"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": true,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-12",
    "verified": false,
    "crawl_query": "chùa Ngũ Hành Sơn",
    "intensity_source": "canonical_rule",
    "ws_source": "classifier_name",
    "io_label": null,
    "smart_tags": {
      "ticket": false,
      "price_band": null,
      "space": "both",
      "party": [
        "family",
        "couple",
        "solo",
        "group"
      ],
      "time": [
        "morning",
        "sunset"
      ],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.6,
      "sun_exposure": 0.48,
      "wind_exposure": 0.48,
      "rain_cover": "mixed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "cat": "landmark",
    "space_source": "name",
    "space_confidence": 0.6,
    "space_evidence": [
      "name compound keyword(s) chua -> both"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover"
    ]
  },
  {
    "poi_id": "ChIJcUs0-1YXQjERDYZBzXC8l24",
    "name": "Zon Spa",
    "type": "Spa mát xa",
    "lat": 16.0813919,
    "lon": 108.2461933,
    "opening_hours": [
      "08:30-00:00"
    ],
    "visit_min": {
      "p25": 76,
      "p50": 108,
      "p75": 151
    },
    "dur_source": "category_rule",
    "dur_confidence": "low",
    "price_level": 2,
    "fee": 0,
    "rating": 5,
    "tags": [
      "Spa mát xa"
    ],
    "intensity": 1,
    "ambience": "",
    "weather_sensitive": false,
    "pros": [],
    "cons": [],
    "source": "serpapi/google-maps",
    "fetched_at": "2026-10-12",
    "verified": false,
    "crawl_query": "spa Sơn Trà",
    "intensity_source": "canonical_rule",
    "ws_source": "classifier_name",
    "io_label": null,
    "smart_tags": {
      "ticket": false,
      "price_band": null,
      "space": "indoor",
      "party": [
        "couple",
        "solo"
      ],
      "time": [],
      "budget": [
        "half-day"
      ],
      "rain_protection": "unknown",
      "outdoor_exposure": 0.05,
      "sun_exposure": 0.05,
      "wind_exposure": 0.05,
      "rain_cover": "enclosed",
      "exposure_source": "explicit"
    },
    "smart_tag_source": "rule_v1",
    "cat": "spa",
    "space_source": "name",
    "space_confidence": 0.6,
    "space_evidence": [
      "name indoor keyword(s) spa"
    ],
    "space_conflict": [],
    "rain_protection": "unknown",
    "rain_protection_source": "unknown",
    "rain_protection_confidence": 0.4,
    "rain_protection_evidence": [
      "no linked OSM rain-protection evidence -> unknown",
      "abstained: absent evidence is not proof of no cover"
    ]
  }
]
```

Danh sách script: `reports/audit_scripts/data_audit.py` (sinh báo cáo này), `reports/audit_scripts/crosscheck.py` (kiểm chứng độc lập).

```json
{
  "total_poi": 742,
  "has_restaurants": 128,
  "has_cafes": 108,
  "category_counts": {
    "beach": 16,
    "viewpoint": 2,
    "outdoor_landmark": 164,
    "pagoda": 35,
    "museum_indoor": 18,
    "day_market": 46,
    "night_spot": 72,
    "restaurant": 128,
    "cafe": 108,
    "other": 153
  },
  "duplicates_suspected": 0,
  "missing_coords": 0,
  "out_of_bbox": 0,
  "opening_hours_parse_rate": 0.6509,
  "price_coverage": 0.0175,
  "description_coverage": 0.0,
  "tier_counts": {
    "A": 392,
    "B": 350,
    "C": 0
  },
  "sources": [
    "manual+review",
    "manual+web",
    "osm/overpass",
    "serpapi/google-maps"
  ],
  "risky_sources": [
    "serpapi/google-maps"
  ],
  "other_data": {
    "log_nguoi_dung_that": 0,
    "gps_demo_points": 6,
    "review_label_files": 8,
    "weather_files": 5,
    "matrix_ids": 498,
    "matrix_covered_pois": 498,
    "tripspec_sample_files": 0,
    "gold_queries": 30,
    "test_cases": 822,
    "test_files": 94,
    "benchmark_solver": "có code + test; t053_baselines.json"
  },
  "code_status": {
    "crawler": "KHÔNG XÁC ĐỊNH 13, chạy được* 7",
    "schema": "chạy được* 4, bản nháp 1",
    "solver": "chạy được* 7, KHÔNG XÁC ĐỊNH 1",
    "verifier": "chạy được* 4",
    "test": "822 hàm test, chưa chạy (pytest không cài)",
    "notebook": "THIẾU",
    "khác": "chạy được* 55, KHÔNG XÁC ĐỊNH 7"
  },
  "price_coverage_note": "ticket_vnd (VND) 13/742; THAY THẾ: price_level là thang Google 1–3 (không phải VND) phủ 742/742; fee là trường deprecated = 0 cho tất cả, không chứng minh miễn phí",
  "strict_tier_counts": {
    "A": 6,
    "B": 404,
    "C": 332
  }
}
```
