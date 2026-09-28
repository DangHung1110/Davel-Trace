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
