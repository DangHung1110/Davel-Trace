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

## [2026-09-28] T019 — Review response builder totals + status + version (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 947d6b2 + d42f564). (1) Vùng file: OK — BE/app/services/response.py đúng vùng B + BE/tests/unit/test_response.py; tasks.md chỉ tick 1 dòng T019. (2) Chạy test `python BE/tests/unit/test_response.py -v`: 4/4 OK exit 0 — totals khớp (60000đ / 3.5km / 220min = visit 210 + travel 10, 1 segment); status phản ánh đúng (pass→4 cổng 1 + violations rỗng; fail VROH→passed False + VROH 0 + violations ['VROH']); version mặc định 1 và giữ version=3 khi replan + created_at. py_compile cả 2 file exit 0. (3) Để dành T032 đúng mực: docstring ghi 'Multi-profile pooling is T032 — this builds ONE plan', signature một optimizer_out + version param cho T046, không lấn multi-profile. (4) Tick xứng đáng: T019 đòi itinerary + totals + constraint status — giao đủ per contracts/api.md. (5) Secret-scan diff 947d6b2~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T018 — Review validator gate + offenders (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 63b8c58 + d754feb). (1) Vùng file: OK — BE/app/services/validator.py đúng vùng B (via gate.py T011) + BE/tests/unit/test_validator.py; tasks.md chỉ tick 1 dòng T018 (depends T011 ghi đủ). (2) Chạy test `python BE/tests/unit/test_validator.py -v`: 6/6 OK exit 0 — good pass 4 checks True; mỗi tamper rớt đúng tên cổng KÈM offender (ghost→FAR['ghost'] / musu 18h→VROH['musu'] / gap 5<10→B3['musu->beach'] / budget 10k→BCS non-empty). py_compile cả 2 file exit 0. (3) Dùng được cho cả optimizer output và evaluator sau: validate() nhận plain dicts không dính optimizer, trả {passed, checks, violations, details} — đúng shape endpoint T052 cần; docstring ghi rõ 2 entry points + STUB-NOTE phase-PR. (4) Bonus CHẠY THẬT: optimize 6 POIs fixture → optimal 6 acts → validate cho passed True, 4 checks True, violations rỗng, details {} (exit 0). (5) Tick xứng đáng: T018 đòi validator gate via gate.py — giao đủ per-gate pass/fail + offender details. (6) Secret-scan diff 63b8c58~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T017 — Review CP-SAT OPTW optimizer (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 32b4957 + cdaa1f3). (1) Vùng file: OK — BE/app/services/optimizer.py đúng vùng B + BE/tests/unit/test_optimizer.py; tasks.md chỉ tick 1 dòng T017 (depends T007/T010 ghi đủ). (2) Chạy test `python BE/tests/unit/test_optimizer.py -v`: 3/3 OK exit 0 — feasible optimal 6 acts score 16.0 (tổng tối đa 3+5+2+4+1+1) trong 0.031s, tôn trọng windows/gaps/durations từng activity; timeout 5s trả best-found (itinerary non-None, wall < 8s); require_all mâu thuẫn → infeasible + reason + itinerary None. py_compile cả 2 file exit 0. (3) STUB schemas đánh dấu rõ: StubPOI/StubTrip gắn '# STUB (T007 ...)' từng class + docstring 'phase-PR swaps them without touching model code', field names khớp trip/poi — đúng luật STUB lanes.md. (4) Bug depot-leg coder tự sửa CÓ test bao phủ: dòng 88 'skip j == 0: return leg must not pin t[0]' — với code cũ, arc cuối →depot ép t[0]>=t[i]+dur+w mâu thuẫn t[0]==start khiến mọi tour phi-rỗng infeasible → test_feasible (assert len>0 + full window/gap check) sẽ FAIL; test xanh hiện tại chính là bao phủ regression. (5) Tick xứng đáng: T017 đòi OPTW + depot/flow/Tmax/time-window + timeout 5s — giao đủ (circuit self-loop=skip, t[i] windows, Tmax, maximize score, 3 status optimal/feasible-timeout/infeasible). (6) Secret-scan diff 32b4957~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T007-plan — Review Activity/Itinerary/RouteSegment schemas (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 1966876 + 1a49860). (1) Vùng file: OK — BE/app/schemas/plan.py đúng phần split T007 của B + BE/tests/unit/test_schemas_plan.py; models.py/trip.py/poi.py/eval.py không chạm (grep diff rỗng); tasks.md chỉ thêm note 1 dòng T007. (2) Chạy test `python BE/tests/unit/test_schemas_plan.py -v`: 5/5 OK exit 0 (valid itinerary / missing activities / segments-count mismatch / bad status / source vocab); py_compile cả 2 file exit 0. (3) Field khớp data-model.md từng mục: RouteSegment đủ 8 fields + source Literal osrm|cache ('guess' bị từ chối); Activity đủ 8 fields + status Literal 4 trạng thái; Itinerary đủ 12 fields + validator segments rỗng-hoặc-n-1 + version≥1 + Explanation {claim, evidence, inference, source}. (4) Note T007 rõ: '[B: plan.py DONE 2026-09-28; A: poi/eval done; C: trip done — cho C wire models.py]', giữ [ ] — không nhận vơ, đúng luật split (plan.py cũng dặn C wire, không import chéo). (5) Secret-scan diff 1966876~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T010+T011 — Review matrix cache-first + gate primitives (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 940129e + 540fbc9 + 0dff36f). (1) Vùng file: OK — BE/app/services/{matrix,gate}.py đúng vùng B liệt kê đích danh trong lanes.md + 2 unit tests của lane; không init/skeleton lane C; tasks.md chỉ tick 2 dòng T010/T011. (2) Chạy 2 test file: test_matrix 5/5 OK + test_gate 6/6 OK, exit 0; py_compile 4 file exit 0. (3) Gate KHÔNG duplicate vô lý: worktree lane-b chưa có BE/eval (xác nhận ls) nên gate.py self-contained đúng luật STUB lanes.md; docstring ghi rõ formulas mirror lane-A metrics + converge ở phase-PR; đối chiếu tay: FAR/VROH/BCS khớp T049 (kể cả edge empty-plan: FAR fail / VROH pass cả 2 phía), B3 = dạng boolean của STR. (4) Miss raise THẬT: verify độc lập trên seed lane-a (read-only) — hit (7, 'cache'), miss ghost-poi raise MatrixMissError kèm message rõ, travel_fit gap hẹp → False; 'haversine' chỉ xuất hiện ở 3 dòng docstring, không có code ước lượng (test_miss_raises_never_guesses assert vắng 6371/radians/asin/math.sin/acos); fetch_osrm là hook raise RuntimeError khi chưa wire coords. (5) Tick xứng đáng: T010 (cache-first + OSRM hook + never-haversine) và T011 (4 booleans cho validator + evaluator) đều là code thuần không đợi data. (6) Secret-scan diff 940129e~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

_(chưa có entry nào)_
