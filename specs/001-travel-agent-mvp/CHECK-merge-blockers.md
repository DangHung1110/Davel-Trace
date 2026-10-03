# CHECK — Merge-blocker verification (2026-09-29)

Reviewer ngoài: chưa merge PR #2 (lane B) / #3 (lane C). Xác minh độc lập 2 lane:
`@explorer` đối chiếu code thật trên `origin/feat/lane-*` (read-only, `git show`, không checkout).
`@oracle` triage severity + chiến lược fix. Kết quả: **8/8 CONFIRMED, toàn bộ spot-check CONFIRMED**.

## 1. Bảng xác minh 8 lỗi (dòng đã hiệu chỉnh)

| # | Verdict | Vị trí thật @branch | Nội dung |
|---|---|---|---|
| B1 replan lần 2 crash | CONFIRMED | `replan.py:102-106` + `state.py:64-71` @lane-b (reviewer ghi 114-118, lệch offset) | `add` = toàn bộ acts đã optimize, `apply_delta` làm `kept + add` → `['C','D','D','C']`; replan sau `KeyError: 1` (`optimizer.py:64,87`) |
| B2 qua giờ về | CONFIRMED | `optimizer.py:88-89` + `gate.py` CHECKS @lane-b | Chỉ chặn giờ bắt đầu; return leg bị skip (comment line 91); validator không có cổng end-time/TCS |
| B3 missing-travel = 0 | CONFIRMED + hiệu chỉnh | `optimizer.py:96` @lane-b | `.get((a,b), .get((b,a), 0))`, arc depot→first luôn 0. Mâu thuẫn với **luật T010** (`matrix.py:17-19` "miss is loud error"), không phải docstring optimizer như reviewer ghi |
| B4 `verified: True` cứng | CONFIRMED | `profiles.py:71-73` (reviewer ghi 96) + `replan.py:87` @lane-b | FAR không bao giờ fail; snapshot thật 329 POI verified=0 toàn bộ |
| C5 Ollama 500 | CONFIRMED | `llm.py:46-48,81-82` @lane-c vs `BE/eval/judge.py:53-56` @lane-a | Body chỉ có `model` + temperature top-level (Ollama bỏ qua); thiếu `stream:false` (default stream=true → NDJSON → `Extra data` → 500), thiếu `format:json`. File đối chiếu đúng là `BE/eval/judge.py`, không phải `BE/ml/patm/judge.py` (không tồn tại) |
| C6 stub itinerary | CONFIRMED | `itinerary.py:75,84-113` + `select.py:23` + `test_us4_multi.py` @lane-c | Stub `it-stub-1`, `body.profiles` không được đọc → luôn 1 plan; `register()` chỉ được gọi trong chính test; T034 tick `[X] US4 closed` trong khi test assert trên POOL viết tay |
| X7 lệch 17-vs-16 feature | CONFIRMED (latent) | `features.py:13-29` (17 + `assert N_FEATURES==17`) @lane-a vs `scorer.py:19-26,73-74` (16, `_features STUB mirror`) @lane-b | `model.txt` chưa commit trên mọi nhánh → `LightGBMError` chưa nổ, nổ khi model thật đầu tiên load. Không có interface-freeze doc nào ghi thay đổi |
| X8 2 bộ cổng | CONFIRMED | `gate.py` (FAR,VROH,B3,BCS) @lane-b vs `metrics.py:171-177` (FAR,VROH,BCS,TCS,HCS) @lane-a | B3 vắng ở lane A, TCS/HCS vắng ở lane B |

## 2. Spot-check lỗi trung bình: CONFIRMED toàn bộ

Parser budget-missing→0, days=3→500 (`trip.py le=2`, ValidationError không bắt), must_visit/avoid so tên với poi_id (không bao giờ match),
envelope `{detail}` thay `{error,message}` (thiếu exception handler), `DEFAULT_BUDGET=3000000` (`expenses.py:13`),
`rain_at` so giờ-bỏ-ngày (trái docstring), reschedule-mưa thiếu lọc verified (cùng họ B4),
savings chỉ chọn POI free (fee≥~5k điểm âm), `tighten_budget` không được replan gọi (grep 0 ref),
snapshot 329 POI verified=0/fee=0/ws=0 hết, thiếu `matrix.json` (lane C chạy với `cells={}` câm),
2 thư mục `danang-v1` song song (7 POI+có matrix vs 329 POI+không matrix),
matrix seed haversine gắn `source:cache`, flip-consistency phủ định cả feature đối xứng (`train.py:105-110`),
nhãn cặp 100% rule-generated (`make_pairs.py` judge batch mới là scaffold emit-only).

## 3. Severity + fix nhỏ nhất + test tái hiện (mỗi lỗi ≤30 dòng)

1. **B1** — `apply_delta` idempotent (dedupe `add` theo `kept`) + `test_replan_twice_no_duplicates`
2. **X7** — `features.py` (lane A) là source of truth; `scorer.py` xóa copy, import về + `test_scorer_feature_names_match_patm_features`
3. **B2** — thêm `check_etb` vào `gate.py` CHECKS + `test_plan_ending_after_return_time_fails_ETB`
4. **C5** — mở rộng `_endpoint()`: nhánh Ollama mang `stream:false, format:json, options.temperature` (1 seam, không vá từng caller) + test body qua mock transport
5. **B4** — xóa 2 chỗ `verified: True`, luồn flag thật + `test_unverified_poi_fails_FAR_in_replan`
6. **C6** — wire `register()`, loop `body.profiles`, uuid thay id cứng; chưa có B thì 501 envelope chuẩn (fail-loud, không stub câm) + 3 tests
7. **B3** — sentinel/exception thay `.get(...,0)`, origin leg từ matrix + `test_missing_travel_pair_is_infeasible_not_zero`, `test_origin_leg_uses_matrix`
8. **X8** — 1 registry duy nhất `FAR,VROH,B3,BCS,ETB(mới),TCS,HCS` (`gate.py` chủ, evaluator import CHECKS) + `test_validator_and_evaluator_gate_sets_identical`

## 4. Thứ tự merge

spec-PR (`chore/vibe-setup` T061–T064 → `dev`) trước, rồi **C → A → B**.
T061 phải bổ sung task cho B1/B3/B4/C5/X7 (hiện thiếu cả 5) + task xóa `_stub_optimize/_stub_validate` khi B merge.
Reviewer đề xuất "sửa 1–5 + envelope parser pre-merge" là **thiếu** — B3, X7, X8 cũng pre-merge (đều ≤30 dòng, merge rồi sửa đắt hơn).

## 5. Quy trình (theo leverage)

1. Bật branch protection `main`/`dev` (PR + ≥1 review non-author + CI xanh, cấm self-approve/force-push)
2. Reviewer độc lập, luân chuyển chéo (B→C, C→A, A→B); reviewer 0 FIX-REQUEST sau 51 commit không phải review
3. PR ≤400 dòng, tách theo task ID
4. Gỡ tick T007/T003b/T003c/T030/T033/T034/T036/T046/T048 trong spec-PR, gắn bug ID chặn (vd T046 ← B1)
5. Template PR bắt buộc (spec link, contract đổi, test evidence, known stubs)
6. Job CI cross-lane assert mọi hằng số copy (FEATURE_NAMES, CHECKS)

## 6. Data pairwise (không đổi sau review)

`BE/data/snapshots/danang-v1/pois.json` (329) → `BE/ml/patm/make_pairs.py` → `BE/eval/judge.py`
→ train (`model.txt` chưa có) → `scorer.py` serve. Human-blockers: bạn tick `SPOT_CHECK.md` + indoor/outdoor;
Bách Ollama+Qwen3-14B duration nấc-2 + 600 judge overnight; human-check 200 pairs → T028-full→T029→T031-full.
Backup: `AppData\Local\Temp\opencode\serpapi-key-bak.env` + `danang-full-tmp-bak\{details,search}`.

*Gốc khiến test xanh mà lỗi lọt: test assert fixture hình-implementation (mock soi gương mock), không assert contract.
Bộ 8 repro tests mục 3 là hạt giống sửa văn hóa test: mỗi task sau này ship kèm adversarial fixture, không chỉ happy path.*

## 7. Bổ sung từ spot-check Claude-chat (2026-09-29)

Pre-fill 46/49 dòng (rows 4–49) từ review Claude-chat; 3 dòng của user giữ nguyên byte-identical.
10 Sai (rows 9,12,18,21,23,24,34,41,46,48) + 36 Dung. I/O ở dòng Dung là suy luận của orchestrator — joint-check lại.

- **X9 (mới, chặn bật verified): giờ đa-khoảng crash cả 3 lane — VERIFIED bằng đọc code.**
  16 POI có opening_hours dạng `"10:30-14:00, 16:30-22:30"` (1 string, 2 khoảng).
  Lane C `retrieval.py:42` (`o,c = h.split("-")`), lane B `common.py:26` + `parse_hours` (`hours[0].split("-")`),
  lane A `metrics.py:21` — unpack 3 mảnh (hoặc 1 mảnh với giờ lẻ kiểu `"12:03"`) → `ValueError`.
  Hiện ẩn vì verified=false nên POI bị bỏ qua trước bước đọc giờ; bật verified = retrieve() crash trên 329 POI.
  Fix: tách theo dấu phẩy thành nhiều khoảng trước khi split("-") (1 chỗ/lane) + `test_multi_interval_hours_parse`.
- **Backlog data (chưa thành task):** ~25 POI không phải điểm du lịch (tiêm chủng Long Châu, KCN,
  cầu vượt 240', 3 nhà hàng tiệc cưới, thuê xe máy, "Aarohi Media Training"→Bảo tàng,
  VinWonders Nha Trang tọa độ Đà Nẵng); trùng lặp (Mỹ Khê 6 bản/5 bản 240' → optimizer xếp Mỹ Khê 2–3 lần,
  Tân Trà 3, Sơn Thủy, Hòa Liên, Nam Ô, Suối Rạng cách 5m); Chợ Thanh Vinh trùng tên → spot-check cần poi_id;
  tiêu chí outlier 60% vô tác dụng (dur sinh từ 1 luật → 0 outlier thật; lỗi nằm ở cả nhóm "Điểm thu hút" 43 POI
  đều 200–240'); giờ-theo-ngày bị đọc như nhiều khung/ngày (Chợ Thanh Bình).
- **T061 bổ sung:** task fix X9 + task làm sạch theo nhóm (loại/gộp/chuẩn hóa type "Điểm thu hút") + thêm poi_id vào spot-check.
- **Điểm mở cho joint-check:** row1 user "sửa dur 45–60'" vs Claude "loại hẳn khỏi snapshot" (không phải điểm du lịch) —
  QUYẾT 2026-09-29: **LOẠI** (human audit). I/O bổ sung giá trị `B` = cả trong nhà + ngoài trời
  (rows 9,34,41,42,46); rows 11,49 giữ `?` (không rõ chợ có mái hay không).
