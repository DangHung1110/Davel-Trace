# HANDOFF — Davel-Trace planner core (compact 28/10)

Branch: `feat/profile-templates-onboarding` (từ `c3e86db`) — **~60 file sửa local, CHƯA COMMIT**.
Nhánh chức năng, không worktree. Không push thẳng main/dev. Không commit secret.

## Chạy test thử
- BE: ` $env:LLM_PROVIDER='api'; $env:LLM_API_URL='http://127.0.0.1:1234/v1'; $env:LLM_API_MODEL='qwen3-8b'; $env:SNAPSHOT_DIR='BE/data/snapshots/danang-v1'; python -m uvicorn BE.app.main:app --port 8000`
- Static: `python server.py --port 5500` (map PMTiles + harness)
- LM Studio: bật server 127.0.0.1:1234, model qwen3-8b (parse/review/repair cần nó; tắt vẫn test được phần còn lại)
- Suite: `$env:PYTHONPATH='BE'; python -m unittest discover -s BE/tests -t BE` → **691 passed, 2 skipped** (5-6 phút)
- Harness: http://127.0.0.1:5500/FE/test_harness.html · Onboard: http://127.0.0.1:5500/FE/onboard.html
- Câu test chuẩn: "Toi muon di Da Nang 1 ngay, ngan sach 2 trieu, thich hai san, xuat phat 7h sang" + card B (nhóm bạn) hoặc profile solo tay

## Đã chốt (làm rồi, verify live OK)
- Ống: parse (NL→TripRequest, có /no_think + normalize ""→default, hết 503) → profile 10 mục catalog (onboard UI 3 archetype A/B/C + tùy tay, localStorage) → template khung ngày → CP-SAT + PATM + state động → hard gates → LLM review/repair → evaluate
- Kỷ luật ngày: ăn đúng bữa, nghỉ bám bữa (45/30p theo pace), cafe ≤2 khác buổi, cấm kề quán/kề loại, cap 1/ngày phi-ăn, bữa theo phủ giờ
- Đa dạng: pool MMR + Jaccard + `?diverse=true`; default profiles = cả 3, pairwise Jaccard ≤0.6
- Ma trận 193 POI / 37.249 cell, 48 verified routable; weather live Open-Meteo; CORS allow-all TEST-ONLY (siết trước PR)
- `FE/test_harness.html` + `FE/onboard.html` là công cụ test (chưa commit)

## Thứ tự đã chốt (đừng đảo)
1. Đóng băng rule (không thêm; gộp trùng; giữ ~5 gate cứng) + bật log plan chấp nhận + LLM ranker shadow
2. Thu 50–200 phán xét A/B → học weight (Bradley-Terry), weight tay làm prior
3. Đủ thư viện ngày tốt → RAG khung ngày
4. Lát 2: luật ráp khung V2, verify POI bar/museum, PATM conditioned pilot
- Rank (so N plan chọn hay nhất) KHÁC review (chê 1 plan + veto): giữ cả hai, rank không thay review

## Còn lại
- User test lại → gom 2 PR vào dev: (1) data+matrix+gate/rule (2) planner+FE. Siết CORS + quét secret trước khi đẩy.
- Harness hiện tên POI (thay id) — nhét vào lane PR.
- Nợ biết rõ: quán hải sản chưa thắng quán 4.9 (taste vào node optimizer — lát 2); viewpoint pool thiếu; review LLM nondeterministic ở lỗi nhẹ (bảo đảm bằng gate); parse flake đã giảm chưa hết hẳn (bấm lại là qua).
- Paper related-work: /tmp/llm_itinerary_papers.md, diversity_papers.md, novelty_papers.md, meal_state_papers.md, stable_planning_papers.md
