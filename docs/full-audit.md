# FULL AUDIT — Davel-Trace planner + data (chốt trước khi sửa)

Ngày: 29/10/2026. Nhánh: `task/full-verify-scale` (từ `92aeeb5`, cây sạch).
Nguồn: recon explorer (exp-9) + chẩn đoán oracle (ora-2), mọi điểm đã spot-check trên đĩa.
Nguyên tắc user: verify hết, không bypass gate, đa dạng toàn pool, làm nghiêm.

Số liệu nền: snapshot `BE/data/snapshots/danang-v1/pois.json` = **742 POI** (768 là bản cũ),
verified=true **48**, verified=false **694**. Matrix phủ **193 id / 37.249 cells**.
Mọi đường ingest hardcode `verified: False`.

---

## A. CHUỖI NHÂN QUẢ GỐC (hiểu cái này thì mọi bug rời rạc ghép lại thành 1 chuyện)

1. User nói "tắm biển" → trạm TYPE (`retrieval.py:112`) so key Anh (`beach`)
   với chuỗi Việt (`Bãi biển`) → 0 điểm khớp → pool rỗng.
2. Pool rỗng → fallback `profiles.py:463-464` lấy **cả 742 POI**
   (694 unverified, bypass luôn avoid/budget/hours).
3. 742 POI unverified → gate FAR chặn → `passed: false`.
4. 742 POI → scorer O(n²) ~550k cặp + CP-SAT ~552k arcs ×3 profiles
   = "chạy vài phút" mỗi request.

Chữa TYPE + FALLBACK là xong 80% triệu chứng. Còn lại là làm cho đúng và cho đủ.

---

## B. BUG CODE (có dòng chứng cứ, có hướng sửa cụ thể)

### B1. Trạm TYPE so sai ngôn ngữ — BLOCKS PLAN (gốc rễ)
- `BE/app/services/retrieval.py:112`: `if types and p.get("type") not in types`
  (`types` = key Anh từ `ACTIVITY_TYPE_MAP` :25-31; `p.type` = Việt tự do).
- `retrieval.py:77-78`: nhãn "gia chua xac minh" đòi `type == "restaurant"` (Anh)
  → không bao giờ hiện (bug riêng, cùng họ).
- Hướng sửa: match trên `cat` (Anh, qua `soft_rules.poi_category`) thay vì `type`;
  map key Anh → tập chuỗi Việt thực tế đếm từ snapshot (không đoán);
  test regression: "tắm biển"→Bãi biển, "văn hóa"→museum (không restaurant).

### B2. Fallback rỗng → lấy tất cả — BLOCKS PLAN + PERF
- `BE/app/services/profiles.py:461-464`: `if not ids: ids = list(pois_by_id)`.
  `pois_by_id` build sau hard-filter profile nên tránh được allergy/must_avoid
  khi có profile, nhưng gồm 694 unverified và KHÔNG check lại `avoid` bare.
- Hướng sửa: fail-closed — pool verified-only; vẫn rỗng thì trả plan rỗng
  trung thực + `infeasible_by` + cần nới gì (không fallback toàn bộ).

### B3. Substring không word-boundary — SILENT WRONG (5 chỗ)
- `retrieval.py:63` (`if kw in low`): `ăn ⊂ văn hóa`→restaurant,
  `cầu ⊂ yêu cầu yên tĩnh`→landmark.
- Cùng pattern: `templates.py:162`, `soft_rules.py:275-276`,
  `repair.py:101-109`.
- Hướng sửa: regex word-boundary theo mẫu `profile_filter.py:128-147`
  (reuse helper nếu không circular import).

### B4. Explanation tính xong vứt — SPEC VIOLATION (FR-013/FR-024)
- `routers/itinerary.py:176-177` chỉ đọc `["candidates"]`;
  `needs_verification` + `excluded` không tới response nào.
  `routers/repair.py:97` cùng mối. `run_profiles.dropped` chết
  (`profiles.py:362` define, không ai gọi).
- Hướng sửa: trả `needs_verification` + `excluded[] reasons` ra response;
  harness hiện danh sách "cần xác minh" (FR-013), nhãn fact/inference (FR-024).

### B5. Budget chết toàn diện — VACUOUS GUARANTEE
- `fee = 0` ở cả 742 điểm → trạm `retrieval.py:115` không chặn;
  BCS (`gate.py:147-150` qua `common.py:73-83` `total_fee`) luôn pass;
  `response.py:51 total_cost = 0`; `profiles.py:220-235` fee-term chết;
  `repair.py:178` no-op.
- Tệ nhất `rank.py:118-119`: đóng dấu **"mien phi" lên cả 742 POI**
  (fact sai tới user, vi phạm FR-026 `spec.md:127`).
- Data thật ra ĐÃ có: `price_level` 1–3 (cả 742),
  `smart_tags.price_band` cheap/medium/expensive, 13 điểm `ticket_vnd` + `band_verified`
  (enum + ngưỡng ở `price_from_raw.py:56-57`, ingest ở `ingest_money.py`).
  Migration nửa vời: data xong, runtime chưa.
- Hướng sửa: 1 helper `effective_fee(poi)` = `ticket_vnd` → giữa band
  (cheap≈100k/medium≈300k/expensive≈700k theo ngưỡng price_from_raw)
  → `None` = "giá chưa rõ" (nhãn uncertainty, KHÔNG "miễn phí").
  Cắm vào 4 chỗ: retrieval filter, `plan_cost`/BCS, rank price part, repair.
  Giữ `price_level` cho spending-fit (đang sống ở `rank.py:114-117`).
  Spec đòi: FR-017/SC-008 (`spec.md:215,293`), `data-model.md:20`.

### B6. Doc-code gap: `--apply-flag` không tồn tại
- `spotcheck_v2.py:13-16` hứa flag, `main()` :53-57 không có;
  `ingest_review.py` chỉ xóa POI, verdict "fix" in ra rồi bỏ.
  Đây là gốc của "verify rồi mà cờ không lên".
- Hướng sửa: implement applier thật (xem C2).

---

## C. DATA / VERIFIED (trả lời 3 câu tại sao)

### C1. Vì sao chỉ 48 verified
48 = toàn bộ verification từng xảy ra: spot-check tay 49 dòng trên bản crawl
329 POI cũ (`SPOT_CHECK.md`), 48 "Dung" bật cờ tay
(`verified_by="spotcheck-v1"`, `verified_at="2026-10-08"`), 1 dòng LOẠI.
694 còn lại **chưa từng được verify** (không phải "verify nơi khác chưa merge":
`grep verified_by BE/**/*.py` = 0 hit). Snapshot phình 329→742, không đợt nào nữa.
`curate_pool.py` + `pool_curation_seafood.json` là evidence-only (đúng, không phải nguồn verify).
`human_verify_200.jsonl` là label duplicate PATM, không liên quan cờ verified.

### C2. Quy trình verify nghiêm (làm 1 lần, dùng mãi)
1. Viết `docs/verify-criteria.md`: tiêu chí pass/fail check được bằng script
   (tọa độ trong bbox Đà Nẵng + số thật, giờ format plausible, type non-empty
   khớp cat, tên non-empty, không dup poi_id/địa chỉ, có source).
   Ghi rõ check nào auto được, check nào cần người.
2. Implement applier (B6) + test fixture: auto-pass chỉ khi MỌI auto-check xanh
   (ghi `verified_by` + `verified_at`); ngờ → hàng đợi JSONL cho người, không flip.
3. Thứ tự verify (không verify đại trà):
   - Đợt 1: **145 POI có matrix nhưng chưa verified** (chỉ verified∩matrix mới plan được).
     Ưu tiên loại hình đang 0 verified: museum/park/bar/spa
     (family-slow cần park, couple-calm cần museum — hiện 0).
   - Đợt 2: số còn lại, cuốn theo mở rộng matrix (D2).
4. CẤM verify-by-default toàn bộ: giết luận điểm chống-hallucination của FAR;
   SPOT_CHECK đã flag dòng "Sai type/dur" — bật bừa là whitelist data xấu.

### C3. Vì sao đúng 48 này (có coherent không)
Coherent, không ngẫu nhiên: dòng "Dung" của đợt SerpApi crawl
→ nặng quán ăn/cafe: restaurant 17, cafe 16, market 6, landmark 4,
beach 3, attraction 2; museum/park/nature/viewpoint/bar/spa = 0.
Cả 48 tạo clique matrix đầy (48/48) — B3 không chặn trong nội bộ.
48-only + fix B1/B2: plan 6 điểm vừa đủ (4 non-food distinct tối đa dưới
CATEGORY_CAP), plan 8 điểm friends-fast chật, family-slow thiếu park.
Kết luận: 48 đủ cho plan đúng, không đủ cho plan đa dạng → đợt 1 (C2) là fix capacity thật.

---

## D. MATRIX (muốn 742 POI đều lên được plan)

### D1. Hiện trạng + công cụ
- 193 id / 37.249 cells, build bằng `osrm-routed /table` local (motorbike/car),
  cặp không route được bỏ trống (B3 infeasible — đúng).
- Tool `BE/tools/expand_poi_matrix.py`: append rows/columns, merge-only
  (không viết lại cell cũ), tự backup ngoài repo, mặc định `--verified-only`.
- Full 742×742 ≈ 550k cặp; OSRM `--max-table-size 300` → ~9 request 300×300.
  Batch job một lần (phút–giờ), không sửa code.

### D2. Điều kiện mở rộng (không đảo)
1. Lane B (B1+B2+B3) xong trước — pool sai thì matrix đầy cũng vô nghĩa.
2. Verify cuốn theo matrix: verify đợt nào → expand đợt đó
   (`--dry-run` xem selection trước, rồi merge).
3. **Candidate cap trước scorer/optimizer** (vd rank rẻ lấy top ~80 rồi mới
   scorer O(n²) + CP-SAT) + timeout guard — BẮT BUỘC trước khi pool phình,
   nếu không latency phút thành chục phút (N3).
   File chạm: profiles builder/scorer wiring (đi lane riêng sau lane B vì chung file).
4. Rebuild gold suite trên clique mới + suite + E2E live.
5. `matrix.json` phình 37k→~550k cells: commit được (tracked chủ đích) nhưng PR nặng.

---

## E. EVAL + HYGIENE (mù hoặc dơ, phải dọn trước PR)

- **N5 gold stale:** `t051_scoped_suite.json` gold còn 5 POI, 7/30 infeasible;
  `build.py:7` "43 verified lack matrix", `baselines.py:5` "5/764" đã cũ;
  `approach_b.filter_pois` (:77-92) KHÔNG có activities→type filter như runtime
  → eval hiện tại mù với bug B1. Rebuild gold sau D2, align filter eval = runtime.
- **N7 bẫy 2 snapshot:** runtime default root `data/snapshots/danang-v1`
  (7 POI seed), tools/eval default `BE/data/...` (742);
  test pin seed 7 POI (`conftest.py:5-7`) → suite xanh trong khi pool thật hỏng.
  Thêm 1 integration test boot đúng snapshot thật.
- **N6 PR hygiene:** CORS allow-all đã commit (trái note "DO NOT COMMIT as-is"
  của chính nó, `main.py:25-33`); router test-local (review/repair/accept)
  đăng ký vô điều kiện. Siết trước PR.
- **N9 minor:** POI không giờ lọt hours filter + VROH — chấp nhận được hiện tại,
  ghi nhận, xử khi pool rộng.

Đã kiểm KHÔNG bug: must_visit-unverified → optimizer fail trung thực
(`optimizer.py:568-572`); validator FAR ≡ gate FAR; weather degrade graceful
(`trip_ctx.py:406-417`); review grounding có thật (`review.py:10-15`).

---

## F. THỨ TỰ THI CÔNG (không đảo, đo sau mỗi bước)

| Bước | Việc | Gate xong |
|---|---|---|
| 1 | Lane B: B1 (type→cat + :77) + B2 (fallback fail-closed) + B3 (word-boundary 5 chỗ) | pool đúng: "tắm biển" ra biển, pool rỗng fail-closed có lý do, substring regression xanh |
| 2 | C2: criteria + applier + test fixture (dry-run only, chưa flip) | dry-run stats 694 POI: auto-pass/queue/fail theo loại |
| 3 | Verify đợt 1: 145 matrix-covered (ưu tiên museum/park/bar/spa) | pool khả dụng 48→~193 |
| 4 | Candidate cap + timeout (lane riêng, sau bước 1 vì chung file) | latency request về giây trên pool ~193 |
| 5 | Expand matrix đợt 1 + rebuild gold + suite + E2E live | plan 6–8 điểm pass gate, review sạch |
| 6 | B4 explanation (needs_verification ra response + harness) + B5 effective_fee | FR-013/024/017 có bằng chứng trên UI |
| 7 | Verify đợt 2 + expand full 742 + N7 test snapshot thật | diversity toàn pool |
| 8 | N6 siết CORS/router + quét secret → PR vào dev | PR sạch |

Bước 1+2 làm song song được (khác file). Từ bước 3 tuần tự.
File này là spec khóa: lane nào cũng đối chiếu trước khi code.

---

## G. LỘ TRÌNH ĐƯA 742 POI VÀO PLAN (verified + qua gate, không bypass)

Mục tiêu: mọi POI trong snapshot đều **đủ điều kiện** vào plan, và plan nào ra
cũng pass gate trung thực. Không hạ gate, không whitelist bừa.

### G1. Một POI "dùng được" nghĩa là gì (4 điều kiện, thiếu 1 là rớt đúng)
1. `verified = true` (tiêu chí C2) — nếu không: FAR chặn (đúng, giữ nguyên).
2. Có matrix cell tới đủ POI khác (D1) — nếu không: B3 loại (đúng, giữ nguyên).
3. `cat` map đúng (B1) + giờ mở cửa hợp lệ — nếu không: trạm type/hours loại (đúng).
4. Nằm trong candidate sau pre-filter (D2 bước 4) — nếu không: chỉ là chưa đủ điểm,
   không phải bị cấm; vẫn hiện trong explanation (B4).

### G2. Việc phải làm (theo thứ tự, mỗi việc có gate đo)
1. **B1+B2+B3** (F bước 1): pool đúng trước. Gate: E2E "tắm biển" ra biển,
   pool rỗng fail-closed có lý do.
2. **C2 applier + verify đợt 1** (145 matrix-covered, ưu tiên museum/park/bar/spa):
   pool khả dụng 48→~193. Gate: đếm `verified∩matrix` trong snapshot.
3. **Candidate cap** (F bước 4): top-K rank rẻ trước scorer O(n²)/CP-SAT.
   Gate: latency p95 request < X giây (X chốt khi đo baseline bước 1).
4. **Verify đợt 2 + expand matrix full** (D2): verify cuốn theo matrix từng mẻ
   (vd 100 POI/mẻ: verify → expand `--dry-run` → merge → suite nhanh).
   Gate mỗi mẻ: suite xanh + E2E 1 profile pass + latency trong X.
5. **B4 + B5**: explanation + budget thật. Gate: UI hiện "cần xác minh",
   không còn nhãn "miễn phí" sai, BCS chặn được plan vượt ngân sách thật.
6. **Rebuild gold + N7 test snapshot thật + N6 dọn PR** (F bước 5,7,8).

### G3. Trong thời gian chuyển đổi, POI chưa verify đi đâu
Ở đúng vị trí quy trình: `needs_verification` (retrieve đã tách sẵn),
hiện trong response dạng "cần xác minh" (B4), KHÔNG vào plan chính,
KHÔNG bypass FAR. User thấy app trung thực thay vì thấy plan chết khó hiểu.

### G4. Đa dạng toàn pool dưới cap (kỳ vọng đúng)
Cap cứng giữ nguyên (CATEGORY_CAP 1/ngày non-food, CAFE_CAP 1–2, cấm kề loại/quán).
Đa dạng đến từ: pool 742 → pre-filter top-K theo taste/state khác nhau mỗi profile
→ 3 options khác nhau thật (Jaccard đã có). Cap là luật chơi, pool lớn là bài;
đừng nhầm "đa dạng" với "nhét nhiều loại vào 1 ngày".

### G5. Lệnh vận hành từng mẻ (mẫu)
```
# 1. verify mẻ mới (dry-run trước)
python BE/ml/data/spotcheck_v2.py --snapshot BE/data/snapshots/danang-v1 --dry-run
python BE/ml/data/spotcheck_v2.py --snapshot BE/data/snapshots/danang-v1 --apply-flag
# 2. expand matrix cho POI vừa verify
python BE/tools/expand_poi_matrix.py --dry-run
python BE/tools/expand_poi_matrix.py
# 3. kiểm sau mỗi mẻ
$env:PYTHONPATH='BE'; python -m pytest BE/tests -q   # nhanh trước
$env:PYTHONPATH='BE'; python -m unittest discover -s BE/tests -t BE  # đầy đủ trước commit
```
OSRM Đà Nẵng phải chạy ở `:5000` trước bước expand (xem `build_poi_matrix.py`).
`matrix.json` tracked chủ đích — commit data chung lane, ghi số cells vào message.
