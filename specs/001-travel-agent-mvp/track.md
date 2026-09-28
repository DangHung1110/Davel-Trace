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

## [2026-09-28] T010+T011 — Review matrix cache-first + gate primitives (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-b (feat/lane-b-optimizer, commits 940129e + 540fbc9 + 0dff36f). (1) Vùng file: OK — BE/app/services/{matrix,gate}.py đúng vùng B liệt kê đích danh trong lanes.md + 2 unit tests của lane; không init/skeleton lane C; tasks.md chỉ tick 2 dòng T010/T011. (2) Chạy 2 test file: test_matrix 5/5 OK + test_gate 6/6 OK, exit 0; py_compile 4 file exit 0. (3) Gate KHÔNG duplicate vô lý: worktree lane-b chưa có BE/eval (xác nhận ls) nên gate.py self-contained đúng luật STUB lanes.md; docstring ghi rõ formulas mirror lane-A metrics + converge ở phase-PR; đối chiếu tay: FAR/VROH/BCS khớp T049 (kể cả edge empty-plan: FAR fail / VROH pass cả 2 phía), B3 = dạng boolean của STR. (4) Miss raise THẬT: verify độc lập trên seed lane-a (read-only) — hit (7, 'cache'), miss ghost-poi raise MatrixMissError kèm message rõ, travel_fit gap hẹp → False; 'haversine' chỉ xuất hiện ở 3 dòng docstring, không có code ước lượng (test_miss_raises_never_guesses assert vắng 6371/radians/asin/math.sin/acos); fetch_osrm là hook raise RuntimeError khi chưa wire coords. (5) Tick xứng đáng: T010 (cache-first + OSRM hook + never-haversine) và T011 (4 booleans cho validator + evaluator) đều là code thuần không đợi data. (6) Secret-scan diff 940129e~1..HEAD: 0 hit. Worktree sạch.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

_(chưa có entry nào)_
