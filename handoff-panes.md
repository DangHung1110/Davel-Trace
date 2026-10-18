# Handoff — Dieu phoi 3 pane Davel-Trace (w2)

Ngay: 2026-10-18. Repo: `C:\Users\ADMIN\Documents\code\Davel-Trace`. Base: `chore/vibe-setup` -> PR #1 merge vao `dev` truoc lane PRs.

## Topology Herdr (workspace w2, tab w2:t1)
| Pane | Agent | Model | Vai tro | Ghi chu |
|---|---|---|---|---|
| w2:p1 | opencode (orchestrator, session ses_f1d4de8ceffe) | muse-spark-1.3 | Dieu phoi, giu gate, merge PR | Dung focus, khong code truc tiep |
| w2:p2 | opencode `implementer` | opencode-go/deepseek-v4.1-flash | FIXER lane B optimizer | Dang working: Lane B via @fixer subagent |
| w2:p6 | hermes `researcher` | muse-spark-1.3 (reasoning cao) | RESEARCHER + SPEC | Xong task 1: `docs/research_brief_poi_recommender.md` (7186 bytes) |

Tester: KHONG pane co dinh. Luna 6 (`opencode-go/gpt-6-luna` / `openai/gpt-6-luna`) chay on-demand nhu background review: verification-planning + code-review + pytest + scenario S1-S7, gate `travel-mvp-quality.md` + @oracle truoc lane-PR.

## Luat lane (specs/001-travel-agent-mvp/lanes.md)
- A Data&Eval: `feat/lane-a-data-eval` — `data/snapshots/**`, `BE/ml/**`, `BE/eval/**`
- B Optimizer: `feat/lane-b-optimizer` — `BE/app/services/{matrix,gate,optimizer,validator,response,profiles,state}.py`
- C Parser/API/App: `feat/lane-c-parser-api` — routers/schemas/retrieval/rank/explainer + FE
- Chi sua file trong lane minh. Can lane khac -> bao orchestrator. Stub theo `contracts/api.md` khi doi. Commit nho kem task ID (`feat: US3 PATM trainer (T029)`), diff <400 dong/PR, PR phase vao `dev`. Cam push main/dev, cam force-push.
- Implement gate: `/speckit.implement` dung khi `requirements.md` pass; `travel-mvp-quality.md` 0/20 thi STOP hoi "proceed anyway?".

## Model chốt
- Implement: DeepSeek v4.1 Flash (re, nhanh, giu speckit flow trong Opencode).
- Spec cuoi: Luna 6 (reasoning + tieng Viet + JSON schema, quyet dinh N/O).
- Trich paper hang loat: Hermes (re, song song, template D/E/F).
- Searcher code: @explorer + glm-5.3-flash, KHONG dung Hermes de grep.

## Trang thai hien tai
- implementer (p2): working, title "Lane B travel agent optimizer implement…".
- researcher (p6): done task 1, file `docs/research_brief_poi_recommender.md`. Thieu: loss/GNN gate + bang metric chi tiet (can doc full PDF 12 trang).
- Tiep theo: researcher lam brief optimizer + eval + dynamic; implementer xong Lane B thi goi tester Luna 6 review doc lap.

## Lenhl Herdr dung lai
```powershell
herdr pane list --workspace w2
herdr agent list
herdr agent read implementer --source recent-unwrapped --lines 60
herdr agent read researcher --source recent-unwrapped --lines 60
herdr agent prompt implementer "<viec>" --wait --timeout 180000   # text TRUOC flag
herdr agent prompt researcher "<viec>" --wait --timeout 180000
```
