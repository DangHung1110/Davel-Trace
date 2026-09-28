# Track: 001-travel-agent-mvp execution log

**Chủ file: reviewer (w2:p6). Coder KHÔNG sửa file này. Orchestrator đọc để điều phối.**

## Models (2026-09-28, đã verify chạy được trên free usage)

- coder (w2:p2): `Muse Spark 1.3 Free` (Default/OpenCode) · variant `xhigh`
- reviewer (w2:p6): `Muse Spark 1.3 Free` (Default/OpenCode) · variant `xhigh`
- LƯU Ý: account chỉ có free usage qua Ollama Cloud — kimi-k2.7-code, deepseek-v4-pro đều báo `not included in your free usage`. Muốn dùng model trả phí thì nạp credits ollama.com rồi đổi bằng picker (`ctrl+x m`). ĐÃ REVERT: `opencode.json` + preset `opencode-go.orchestrator` về `muse-spark-1.3-contributor` (backup `.pre-kimi-bak`).
- 2026-09-28: preset `fixer` (deepseek-v4.1-flash high) TEST OK qua subagent (reply READY) → đường dispatch @fixer cho implement vẫn sống. Flash hợp vai executor nhanh; pane giữ Free xhigh vì mạnh hơn cho việc khó.
- 2026-09-28: preset `oracle` (qwen3.8-max/high) và `agents.verifier` (kimi-k3/high) SAI VARIANT (không tồn tại) → đã sửa file thành xhigh / max. Nhưng server cache config cũ nên preset vẫn lỗi; workaround: truyền `model` trực tiếp khi gọi subagent (`opencode-go/qwen3.8-max#xhigh`, `opencode-go/kimi-k3#max`) — TEST OK cả 2 (READY). Chưa restart `opencode service` (sợ rớt session orchestrator đang chạy); restart để sau, giữa 2 đợt việc.

## Quy ước ghi log (append-only, mới nhất lên đầu)

Mỗi entry:
```
## [YYYY-MM-DD HH:mm] Txxx — <tên việc> (pane: coder/reviewer)
- Trạng thái: DONE | ISSUE | FIX-REQUEST | NOTE
- Làm gì: ...
- File đổi: ...
- Cần fix / cần orchestrator quyết: ...
```

## Vùng sở hữu

- coder: code theo lanes.md lane được giao + tick `[X]` tasks.md đúng dòng task mình.
- reviewer: file track này + chạy test/validate/check (pytest, validator, đối chiếu spec). KHÔNG sửa code của coder; phát hiện lỗi thì ghi FIX-REQUEST, coder sửa.
- orchestrator (w2:p1): giao việc, đọc track, reconcile, merge/PR.

## Log

## [2026-09-28] T021 — Review US1 S2+S3 e2e + mock-restore fix (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-c (feat/lane-c-parser-api, commits 3327a0a + 0babc64). (1) Vùng file: OK — BE/tests/integration/test_us1_flow.py (mới) + 1 dòng fix trong BE/tests/contract/test_parse.py, toàn vùng C; tasks.md chỉ tick 1 dòng T021. (2) Chạy pytest integration: 3/3 PASSED; full `pytest BE/tests/`: 27/27 passed (24 cũ + 3 mới) exit 0. (3) Bug mock coder tự sửa ĐÚNG và có bao phủ: `self._real` → `TestParseContract._real` trong finally (tránh instance-shadowing khi nhiều test class cùng patch global mock); verify chạy cả 2 thứ tự (integration↔contract) đều 5/5 xanh → không nhiễu chéo, restore sạch. (4) S2+S3 khớp quickstart ở phạm vi stub: S2 parse prompt cố định ra TripRequest đủ slots (city đà-nẵng, budget 3tr); S3 plan ≥2 acts đủ trường (poi_id/start/end/explanation+evidence), không overlap + travel fits, totals + constraint_status 4 cổng 1, clarification khi thiếu city. NOTE (không FIX): quickstart S3 ghi '≥2 plans' thuộc T032 multi-profile — test hiện tại 1 plan stub đã khai báo STUB lane-B trong docstring. (5) Tick xứng đáng: T021 đòi S2+S3 e2e — giao đủ 3 case, US1 khép ở tầng stub. (6) Secret-scan diff 3327a0a~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T020+T012+T013 — Review routers parse+itinerary + contract tests (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-c (feat/lane-c-parser-api, commits 6a52d4f + feacdfe + 82511be). (1) Vùng file: OK — BE/app/routers/{parse,itinerary}.py + main.py (register routers) + BE/tests/contract/{test_parse,test_itinerary}.py, toàn vùng C; tasks.md chỉ tick 3 dòng T020/T012/T013. (2) Chạy pytest contract: 4/4 PASSED exit 0 (parse shape + clarify / itinerary shape + snapshot envelope); full `pytest BE/tests/`: 24 passed exit 0. (3) Shape khớp contracts/api.md: parse In {text,user_id} → Out TripRequest JSON (+assumptions/soft/hard/uncertainties) HOẶC {needs_clarification}; itinerary In {trip,profiles} → Out {plans[0]+totals+status+version, selected None}; lỗi đúng envelope {error,message} (SNAPSHOT_MISSING 503 / NO_FEASIBLE_PLAN 422). NOTE: rule '≥2 plans' thuộc T032 (stub 1 plan đã ghi rõ), không chặn T020. (4) STUB lane-B đánh dấu rõ: khối '# --- STUB (lane B T017/T018/T019) — deleted at phase-PR ---' + docstring 'same plan shape', pipeline dùng real retrieval T015 + rank T016. (5) Tick 3 tasks xứng đáng: T012/T013 contract tests viết theo đúng yêu cầu (shape+envelope, mock LLM/tmp snapshot) + T020 routers chạy xanh qua chúng. (6) Secret-scan diff 6a52d4f~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T016 — Review rule ranker nac-1 attribute+context (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-c (feat/lane-c-parser-api, commits 70d3c83 + 63854b7). (1) Vùng file: OK — BE/app/services/rank.py (vùng C) + BE/tests/unit/test_rank.py; tasks.md chỉ tick 1 dòng T016. (2) Chạy test file `python BE/tests/unit/test_rank.py -v`: 4/4 OK exit 0; full `pytest BE/tests/ -q`: 20 passed exit 0; py_compile cả 2 file exit 0. (3) Ranking ĐÚNG: POI đúng gu (cove 0.95) vượt ngược gu (club 0.5) cách biệt; mưa 0.9 phạt outdoor weather_sensitive (dry > wet); WEIGHTS tổng đúng 1.0, toàn không âm, đủ 6 keys; scores trong [0,1]. (4) Reasons giữ cho explainer: score_poi trả {"score", "reasons"[...]} chuỗi VI đọc được (rating cao/mien phi/vua suc/hop gu/hop buoi toi/mua...), rank() bọc {poi_id, score, reasons} sort desc; docstring chốt format giữ nguyên cho T042 tái dùng. (5) Tick xứng đáng: T016 đòi rule ranker attribute + context weights — giao đủ 6 tín hiệu (rating/price/effort/pref_match/time_fit/weather). (6) Secret-scan diff 70d3c83~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T015 — Review POI retrieval hard-filter + candidates (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-c (feat/lane-c-parser-api, commits ce0b002 + 679bb7a). (1) Vùng file: OK — BE/app/services/retrieval.py (vùng C) + BE/tests/unit/test_retrieval.py; tasks.md chỉ tick 1 dòng T015. (2) Chạy test file `python BE/tests/unit/test_retrieval.py -v`: 6/6 OK exit 0; full `pytest BE/tests/ -q`: 16 passed (llm 6 + parser 4 + retrieval 6) exit 0; py_compile cả 2 file exit 0. (3) Lọc ĐÚNG: must-visit giữ kể cả vi phạm (flag trong reasons, validator FR-031 quyết sau); avoid luôn loại; đóng cửa ngoài window loại (museum out 19:00-22:00, noodle/beach in); vượt budget loại; unverified loại trừ must-visit (FR-013); type-filter qua keyword map VI; mỗi candidate/excluded đều có reasons/reason. (4) Fixture tự chứa GHI RÕ: test docstring 'Fixture-based (no seed in lane C)' + retrieval.py STUB-NOTE 'lane-A snapshot loader T008 wires in at phase-PR' → NOTE tích hợp phase-PR (không FIX, đúng luật STUB lanes.md). (5) Tick xứng đáng: T015 đòi hard-constraint filter + candidate list — giao đủ kèm reasons. (6) Secret-scan diff ce0b002~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T014 — Review NL parser VI hard/soft/clarify (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-c (feat/lane-c-parser-api, commits 5941a33 + 672bb53). (1) Vùng file: OK — BE/app/services/parser.py (vùng C) + BE/tests/unit/test_parser.py; tasks.md chỉ tick 1 dòng T014. (2) Chạy test file `python BE/tests/unit/test_parser.py -v`: 4/4 OK exit 0 toàn mock; full `pytest BE/tests/ -q`: 10 passed (llm 6 + parser 4) exit 0; py_compile cả 2 file exit 0. (3) hard/soft/assumption phân biệt ĐÚNG: must_visit/avoid chỉ từ slots LLM (prompt dặn CHỈ khi user nói bắt buộc/tránh), soft_prefs truyền riêng không bao giờ copy vào hard slots (code không trộn); thiếu city → needs_clarification ['city'] không trip (FR-005); thiếu time → defaults 07:00-18:00/1 ngày GHI vào assumptions không lặng lẽ; test VAGUE khẳng định soft ở yên soft, must_visit/avoid rỗng (FR-006). NOTE (không FIX): bảo đảm FR-006 ở tầng prompt phụ thuộc LLM thật tuân thủ — parser chỉ truyền verbatim; contract test T012 / live-run sẽ kiểm chứng sau. (4) Tick xứng đáng: T014 đòi NL→TripRequest + clarification list — giao đủ 4 case (full/city/time/vague) qua llm gateway T005. (5) Secret-scan diff 5941a33~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T005 — Review LLM gateway JSON mode + validate + retries (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-c (feat/lane-c-parser-api, commits 34fdc9f + ff9c92f). (1) Vùng file: OK — BE/app/services/llm.py (vùng C) + BE/tests/unit/test_llm.py; tasks.md chỉ tick 1 dòng T005. (2) Chạy test `python BE/tests/unit/test_llm.py -v`: 6/6 OK exit 0 toàn mock (valid first-try + temp 0.1 assert / retry-heals-garbage 2 calls / exhausted→LLMError bad_json / transport-retry / schema-mismatch→LLMError schema / api-provider env key + /chat/completions URL); py_compile cả 2 file exit 0. (3) KHÔNG hardcode URL/key: llm.py đọc Settings + env (LLM_API_URL/KEY/MODEL), localhost default nằm ở config.py, key test 'sk-test-fake' chỉ trong test và tự dọn env; grep code không có key thật. (4) Live Ollama vắng mặt GHI NHẬN trung thực: probe localhost:11434 connection-refused (Ollama không chạy) + docstring test ghi 'Live Ollama smoke is manual/optional, not asserted' → không fake pass; retry logic đúng spec (≤2 retries, 3 attempts). (5) Tick xứng đáng: T005 đòi JSON mode + temp 0.1 + Pydantic validate + ≤2 retries — giao đủ cả 4 + machine-readable LLMError reasons. (6) Secret-scan diff 34fdc9f~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T001+T002+T004+T007-foundation — Review BE skeleton + pytest layout + config + trip schemas (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-c (feat/lane-c-parser-api, commits 63f9c18 + 5d230bf + 196d292 + 175ce79). (1) Vùng file: OK — 15 files toàn vùng C (BE/app/**, BE/tests/** inits, BE/.env.example, BE/requirements.txt); không chạm file A/B; tasks.md chỉ tick 4 dòng T001/T002/T004/T007. (2) Tự chạy xanh (fastapi 0.133.1/pydantic 2.13.4): import main/config/schemas OK, settings defaults (local/localhost/danang-v1, key rỗng), User/TripRequest defaults OK, TestClient GET /v1/health → 200 {'status':'ok','snapshot':'danang-v1'} (S1); py_compile 4 file exit 0. (3) models.py KHÔNG import module chưa tồn tại: chỉ re-export trip (User/TripRequest), 3 file pending (poi/eval A + plan B) ghi rõ DO-NOT-import trong docstring — đúng luật STUB/split T007 lanes.md. (4) .env.example không secret thật: GOOGLE_PLACES_KEY/OSRM_BASE_URL để trống, còn lại là localhost/defaults. (5) Tick T007 có note foundation rõ: '[foundation DONE 2026-09-28 lane C: trip (User/TripRequest); poi/eval (A) + plan (B) pending]' — không nhận vơ full T007. (6) Secret-scan diff 63f9c18~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

_(chưa có entry nào)_
