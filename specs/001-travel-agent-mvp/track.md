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

_(chưa có entry nào)_
