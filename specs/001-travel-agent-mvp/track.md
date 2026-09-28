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

## [2026-09-28] T048 — Review US8 S5 integration + 2 fixes (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 3c53f80 + cb95ca7 + 6bbbd2d). (1) Vùng file: OK — BE/tests/integration/test_us8_replan.py (mới) + fix cùng-lane replan.py/state.py; tasks.md chỉ tick 1 dòng T048. (2) Integration 1/1 OK (S5: v2 giữ hill+beach, drop park, new noodle); full lane-b: 12/12 unit files exit 0 (state/replan/optimizer/validator/response/transition/score_plan/budget/profiles/matrix/gate/schemas_plan) — state.py đổi không hồi quy. py_compile OK. (3) 2 bug fix ĐÚNG + có regression cover: (a) rolling-now — complete() tiến state.now theo done_at (trước đó replan start kẹt ở giờ trip-start); (b) depot legs từ done cuối — (depot,x) lấy travel(last_done,x) thay vì 0 miễn phí. Luận chứng cover: thiếu (a) noodle xếp 07:00 chồng hill → B3 fail; thiếu (b) gap 0 < need 10 → B3 fail; test assert full validate passed nên cả 2 đều load-bearing. (4) version 1→2, completed giữ, changes liệt kê keep/drop (park outdoor thay), full done+new validate sạch. (5) Tick xứng đáng ở tầng service; NOTE (không FIX): chữ 'US8 closed' sớm một chút — T047 (mock GPS feed + timeline demo) còn mở; S5 test dùng stub event 'mock-gps' đúng chỗ. (6) Secret-scan: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T046 — Review rolling replan + mode gate (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits cd1bef6 + 794eb1c). (1) Vùng file: OK — BE/app/services/replan.py (mới, vùng B) + BE/tests/unit/test_replan.py; tasks.md chỉ tick 1 dòng T046 (depends T017/T044/T045 ghi đủ). (2) Chạy test `python BE/tests/unit/test_replan.py -v`: 3/3 OK exit 0 — rain → plan v2 giữ completed [hill,beach]; must_keep∩avoid → clarify kèm question, version giữ nguyên (state untouched); infeasible → no_solution + preserved_completed. py_compile cả 2 file exit 0. (3) Completed BẤT BIẾN: drops trừ completed_ids trước optimize, apply_delta cũng loại completed (hợp đồng T045), test assert preserved + drops không chứa hill. (4) Bug plan-rỗng CÓ regression cover: optimizer skip hết → acts rỗng + cand_ids còn → no_solution 'khong xep duoc remaining nao' (dòng 83-88), test_infeasible_no_solution bao phủ (cand [a] nhưng không xếp được → no_solution, không plan rỗng). NOTE (không FIX): corner event xóa SẠCH remaining (cand_ids rỗng) → rơi qua các guard về plan mode với acts rỗng + version++ — đọc được như 'không còn gì để xếp' trung thực, nhưng orchestrator/T047 có thể muốn no_solution; để quyết ở tích hợp. (5) Tick xứng đáng: rolling replan + 3 mode + version++ đủ. (6) Secret-scan diff cd1bef6~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T045 — Review state store + delta + preservation (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 7ca9ba5 + 3d892e2). (1) Vùng file: OK — BE/app/services/state.py (mới, vùng B) + BE/tests/unit/test_state.py; tasks.md chỉ tick 1 dòng T045. (2) Chạy test `python BE/tests/unit/test_state.py -v`: 5/5 OK exit 0 — complete() chuyển remaining→completed không bump version; delta đổi remaining giữ completed (drop noodle→cancelled, add museum, version 1→2); drop completed bị bỏ qua + ghi ignored_completed, completed nguyên vẹn; version++ mỗi delta + history đủ; load.unknown → KeyError. py_compile cả 2 file exit 0. (3) Copy-on-write verify ĐỘC LẬP: apply_delta không mutate input (so deep snapshot), mutate output trả về không ảnh hưởng store (load lại sạch), version đúng. (4) Tick xứng đáng: T045 đòi state store + delta + preservation contract — giao đủ (state shape trip_id/version/now/location/completed/cancelled/remaining/history + FR-047 version++/delta-record). (5) Secret-scan diff 7ca9ba5~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T036b — Review replan budget feed tighten-to-actuals (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 87db837 + 2797754). (1) Vùng file: OK — BE/app/services/budget.py (mới, vùng B) + BE/tests/unit/test_budget.py; tasks.md chỉ tick 1 dòng T036. (2) Chạy test `python BE/tests/unit/test_budget.py -v`: 4/4 OK exit 0 — sáng nặng (2.5M>1.5M) siết đúng cơ cấu (allowed 500000, caps cộng đủ 500000, food 300000=500000×1.5/2.5); âm (-200000) → 0 + caps toàn 0 + reason hết ngân sách; nhẹ (200000) không siết chia đều. py_compile cả 2 file exit 0. (3) Output đủ 6 field cho T046 (trip_id/allowed_total/allowed_remaining/per_kind_cap/tightened/reason — test assert đủ); input khớp shape replan_budget() lane-C (trip_id/budget/spent/left/by_kind/alert) — hợp đồng cross-lane nhất quán. (4) T036 tick đủ 2 nửa: '[T036a replan_budget lane C + T036b feed lane B DONE]' [X] — nửa C đã verify ở review T036a lane-c; NOTE merge phase-PR (không FIX, đúng luật lanes). (5) Secret-scan diff 87db837~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T032s — Review plan scorer profit/utility + gate (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 511b3da + 85f4953). (1) Vùng file: OK — thêm score_plan vào BE/app/services/profiles.py (vùng B) + BE/tests/unit/test_score_plan.py mới; tasks.md chỉ thêm note 1 dòng T033. (2) Chạy test `python BE/tests/unit/test_score_plan.py -v`: 4/4 OK exit 0 — utility exp 0.942 > sav 0.828 (preference-heavy → experience top utility); profit sav 4.2 > exp 3.2 (tight budget → savings top profit); gate-fail (VROH 0) → excluded + scores 0.0; pool thật run_profiles → profit winner là savings. py_compile cả 2 file exit 0. (3) T033 GIỮ NGUYÊN [ ] đúng: note '[T032s DONE 2026-09-28 lane B: score_plan in profiles.py; select endpoint = T033e lane C]' — scorer thuộc B xong, select endpoint để C, đúng split lanes.md. (4) Secret-scan diff 511b3da~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T032 — Review multi-profile runs + solution pool (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits be579df + b789f5d). (1) Vùng file: OK — BE/app/services/profiles.py (mới, vùng B) + BE/tests/unit/test_profiles.py; tasks.md chỉ tick 1 dòng T032. (2) Chạy test `python BE/tests/unit/test_profiles.py -v`: 2/2 OK exit 0; verify độc lập in composition: savings [beach,hill] cost 0 pref 4.65 / balanced [beach,hill,fancy,noodle] cost 550000 pref 4.7 / experience [beach,hill,noodle,fancy] cost 550000 pref 4.7 — ≥2 plans, khác cả composition + cost + reasons (savings rẻ nhất ✓). py_compile cả 2 file exit 0. (3) Mỗi plan qua gate: cả 3 constraint_status 4 cổng 1, dropped rỗng, selected None (select endpoint là lane C T033e — để dành đúng). (4) Tick xứng đáng: T032 đòi multi-profile runs + solution pool — giao đủ 3 weight configs (savings phạt fee / balanced rating / experience rating+intensity) qua optimizer T017 + validate T018; commit ghi 'US4 opened' (mở, không nhận vơ đóng). (5) Secret-scan diff be579df~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T030 — Review q_ij scorer + precedence wiring (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 57719f3 + c76fb40). (1) Vùng file: OK — BE/app/services/scorer.py (mới, vùng B) + BE/tests/unit/test_transition.py + sửa cùng-lane BE/app/services/optimizer.py (thêm 2 params optional q_ij/precedence, không đụng lane khác); tasks.md chỉ tick 1 dòng T030. (2) Chạy test `python BE/tests/unit/test_transition.py -v`: 5/5 OK exit 0 — score float + describe backend rule/16 features; rule mean ~0.000ms (<5ms); model path micro-LGBM (train TEMP in-test) trả float; precedence hill→beach thắng khi khả thi (order hill,beach,noodle) + đảo precedence đảo thứ tự. py_compile 3 file exit 0. Hồi quy: optimizer 3/3 + validator 6/6 + response 4/4 vẫn xanh sau sửa optimizer.py. (3) Fallback rule RÕ: file model vắng → backend 'rule' (test assert), describe() khai báo backend công khai; STUB mirror lane-A (16 feature names + rule weights) ghi thay-bằng-import ở phase-PR. (4) Precedence tôn trọng order user: W_A+s_A≤W_B chỉ khi cả 2 visited + q_ij bonus trên arc dùng — cả 2 chiều đều thắng khi khả thi. (5) Tick xứng đáng + NOTE: wiring q_ij/precedence xong (code), model-path test bằng micro-model; tích hợp live với model.txt T029 thật chờ phase-PR (đúng tiền lệ mock-now/live-later như T050; describe() báo backend nên không lẫn). (6) Secret-scan diff 57719f3~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

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
