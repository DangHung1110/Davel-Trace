# Lanes: 3 người implement không conflict

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
**Base**: `chore/vibe-setup` (chờ PR #1 merge vào `dev` trước khi lane PRs).

## Lane map

| Lane | Người | Branch | Tasks | Agent chạy |
|---|---|---|---|---|
| A Data & Eval | 1 | `feat/lane-a-data-eval` | T003, T008, T028, T029, T031, T044, T049–T053, T056 | @fixer (scope: file lane A) |
| B Optimizer & Solver | 2 | `feat/lane-b-optimizer` | T010, T011, T017–T019, T030, T032+s, T036b, T045, T046, T048 | @fixer (scope: file lane B) |
| C Parser, API & App | 3 | `feat/lane-c-parser-api` | T001, T002, T004, T005, T007*, T009, T014–T016, T020–T025, T033e, T034–T043, T047, T054, T055, T057–T059 | @fixer (scope: file lane C) |

T032 split: scorer → B, select endpoint → C (ghi T032s/T033e lúc làm).
T036 split (theo analyze MINOR-1): T036a alerts (C, Phase 7) + T036b replan feed (B, Phase 10).
T007 split 4 file để khỏi conflict: `schemas/trip.py` (C), `schemas/poi.py` (A),
`schemas/plan.py` (B), `schemas/eval.py` (A); `models.py` chỉ re-export (C).
Đánh `[X]` T007 khi cả 4 xong. (tasks.md giữ nguyên — đây là overlay thực thi.)

## File ownership (vùng cấm lấn)

- **A**: `data/snapshots/**`, `BE/ml/**`, `BE/eval/**`, `BE/tests/unit/test_patm.py`, eval tests.
- **B**: `BE/app/services/{matrix,gate,optimizer,validator,response,profiles,state}.py`.
- **C**: `BE/app/{main.py,routers/**,schemas/**}`, `BE/app/services/{llm,parser,retrieval,rank,context_score,explainer,weather,expenses}.py`, `BE/tests/{contract/**,integration/**}`, `FE/lib/api/**`, `FE/lib/features/**`, `BE/.env.example`.
- **Chung, chỉ sửa theo luật**: `tasks.md` (chỉ dòng task mình), `lanes.md` (bảng status lane mình).

## Thứ tự chạy

1. **Ngày 1 (chung)**: Phase 1+2 theo phân công trên — C dựng skeleton, A seed snapshot, B matrix+gate. Xong mới tách.
2. **MVP line**: Phase 3→8 (P1). Dừng VALIDATE demo static (S1–S3+S6 + T054/T057).
3. **P2**: Phase 9–11 (US7 explain → US8 replan → US9 eval) rồi Phase 12 polish.
4. **Review gates**: @oracle review ở US1-demo và trước mỗi lane-PR; @verifier đối chiếu spec khi cần.

## Git protocol (chống conflict khi fetch)

```powershell
git worktree add ..\Davel-Trace-lane-a feat/lane-a-data-eval   # mỗi người 1 worktree
git worktree add ..\Davel-Trace-lane-b feat/lane-b-optimizer
git worktree add ..\Davel-Trace-lane-c feat/lane-c-parser-api
```

- Mỗi ngày: `git fetch origin` + `git pull` (merge, KHÔNG rebase nhánh share).
- Commit nhỏ, message kèm task ID: `feat: US3 PATM trainer (T029)`.
- Push lane branch hằng ngày; PR vào `dev` theo phase (không PR thẳng vào nhau).
- Conflict: vùng file rời nhau nên auto-merge. Nếu dính (chủ yếu `tasks.md`):
  người sở hữu dòng thắng, bên kia apply lại. Không sửa dòng task của lane khác.
- `tasks.md`: đánh `[X]` ngay khi task xong + test xanh; commit riêng dòng đó.
- PR #1 merge trước, lane PRs sau (rebase không cần — merge commit thường).

## Tracking (update bảng này mỗi PR)

| Lane | Phase xong | Tasks [X]/tổng | PR | Ghi chú |
|---|---|---|---|---|
| A | 1–2 | 0/14 | — | |
| B | 1–2 | 0/12 | — | |
| C | 1–2 | 0/33 | — | |

## Implement gate (đọc trước khi gọi implement)

`/speckit.implement` quét `checklists/`: `requirements.md` ✅ pass, nhưng
`travel-mvp-quality.md` đang 0/20 (reviewer-owned, đúng luật để trống) → lệnh sẽ
**STOP và hỏi "proceed anyway?"**. Reviewer tick `[x]` các mục đã duyệt (10 phút),
hoặc trả lời `yes` ở gate. Lệnh KHÔNG bao giờ tự sửa checklist.
