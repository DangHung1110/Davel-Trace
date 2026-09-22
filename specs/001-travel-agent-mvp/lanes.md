# Lanes: 3 người implement không conflict

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
**Base**: `chore/vibe-setup` (chờ PR #1 merge vào `dev` trước khi lane PRs).

## Lane map

| Lane | Người | Branch | Tasks | Agent chạy |
|---|---|---|---|---|
| A Data & Eval | 1 | `feat/lane-a-data-eval` | T003, T003b, T008, T028, T029, T031, T044, T049–T053, T056 | @fixer (scope: file lane A) |
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

## Thứ tự chạy (3 lanes SONG SONG được)

1. **Ngày 1 (chung, vẫn song song)**: Phase 1+2 đã chia rời file — C dựng skeleton,
   A seed snapshot (7 POIs) + bắt đầu build Google Places snapshot (100–200 POIs), B matrix+gate. Xong mới tách lanes.
2. **MVP line (song song toàn phần)**: Phase 3→8 (P1). Dừng VALIDATE demo static.
3. **P2 (song song)**: Phase 9–11 rồi Phase 12 polish (cần cả 3 xong mới ráp).
4. **Review gates**: @oracle review ở US1-demo và trước mỗi lane-PR; @verifier đối chiếu spec khi cần.

## Luật STUB (để song song không chờ nhau)

- Lane nào cần đồ lane khác chưa xong → **code theo `contracts/api.md` + schemas
  đã đóng băng, dùng stub/mock**, KHÔNG ngồi chờ. Ví dụ: B cần file model PATM
  của A → B code optimizer với hàm `score_transition()` giả trả số cố định;
  A giao file thật ở phase-PR, B thay 1 dòng là chạy.
- CẤM viện cớ "đợi lane kia" quá 1 ngày — quá hạn thì stub + ghi vào lanes.md.
- Tích hợp thật xảy ra ở phase-PR (test S1–S7 bắt stub phải khớp interface thật).

## Git protocol (chống conflict khi fetch)

```powershell
git worktree add ..\Davel-Trace-lane-a feat/lane-a-data-eval   # mỗi người 1 worktree
git worktree add ..\Davel-Trace-lane-b feat/lane-b-optimizer
git worktree add ..\Davel-Trace-lane-c feat/lane-c-parser-api
```

- Mỗi ngày: `git fetch origin` + `git pull` (merge, KHÔNG rebase nhánh share).
- Commit nhỏ, message kèm task ID: `feat: US3 PATM trainer (T029)`.
- **PR NHỎ, PR SỚM (chống phình): mỗi phase xong → PR ngay vào `dev`, không dồn.**
  CẤM ôm 2+ phases mới PR. Diff mục tiêu <400 dòng/PR. Không PR lane thẳng vào nhau.
- **ĐÓNG BĂNG interface sau ngày 1 (chống trôi):** `contracts/api.md` + `schemas/*`
  xong Phase 2 là chốt. Muốn đổi chữ ký hàm/endpoint/schema: ghi vào bảng dưới +
  báo 2 lane kia TRƯỚC khi code, không tự đổi.
- Conflict: vùng file rời nhau nên auto-merge. Nếu dính (chủ yếu `tasks.md`):
  người sở hữu dòng thắng, bên kia apply lại. Không sửa dòng task của lane khác.
- `tasks.md`: đánh `[X]` ngay khi task xong + test xanh; commit riêng dòng đó.
  Mỗi sáng pull để thấy `[X]` của lane khác (khỏi hỏi "xong chưa").
- PR #1 merge trước, lane PRs sau (rebase không cần — merge commit thường).

## Mô hình nhánh: task → lane → dev (stacked)

- Task NHỎ (<nửa ngày, 1 file, trong vùng lane): commit thẳng lên lane branch.
- Task LỚN (>1 ngày, hoặc rủi ro cao, hoặc agent thực hiện): tách nhánh
  `task/T029-patm-train` từ lane → xong → merge vào lane → xóa nhánh task.
- **Cổng task→lane**: test của task xanh + scenario quickstart liên quan pass.
  Lane phải luôn xanh — lane đỏ thì dừng nhận merge, fix trước.
- **Cổng lane→dev** (phase-PR): full test lane xanh + @oracle review + update bảng
  tracking. Diff mục tiêu <400 dòng.

## Interface freeze log (đổi interface ghi vào đây)

| Ngày | Lane | Đổi gì | Ảnh hưởng lane nào | Đã báo chưa |
|---|---|---|---|---|
| | | | | |

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
