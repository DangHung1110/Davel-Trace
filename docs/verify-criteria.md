# Tiêu chí `verified=true` — check được bằng máy vs. cần người

Ngày: 29/10/2026. Lane: `task/full-verify-scale`. Spec gốc: `docs/full-audit.md` B6 + C2.
Tool: `BE/ml/data/spotcheck_v2.py` (`--apply-flag`, mặc định `--dry-run`).
Phạm vi: snapshot `BE/data/snapshots/danang-v1/pois.json` (742 POI, 48 verified).

Tài liệu này trả lời đúng một câu: **một POI được bật `verified=true` khi nào, và
cái gì script quyết được, cái gì bắt buộc con người quyết.** Không có "verify cho
đủ số": cờ `verified` là cổng chống-hallucination của FAR, bật bừa là whitelist
data xấu (`SPOT_CHECK.md` đã bắt được dòng "Sai type/dur").

---

## 1. `verified=true` nghĩa là gì (và không nghĩa là gì)

**Có nghĩa:** bản ghi đủ toàn vẹn cấu trúc để planner được phép dùng — toạ độ
thật và nằm trong Đà Nẵng, có tên, có loại hình khớp `cat`, có giờ mở cửa đọc
được, có nguồn, và không nằm trong một cụm nghi trùng chưa xử lý.

**Không có nghĩa:** type/duration/rating/giá là *đúng ngoài đời*. Các trường đó
vẫn là dữ liệu crawl + suy luận (`dur_source="category_rule"`); `verified=true`
không xác nhận chúng. Vì vậy mọi dòng do máy bật đều mang
`verified_by="auto-verify-v1"` (khác `"spotcheck-v1"` của 48 dòng người duyệt
2026-10-08) để lọc/audit lại được, và không bao giờ hạ cờ dòng người đã duyệt.

Hệ quả vận hành: `verified_by` là provenance, không phải nhãn trang trí.
- `spotcheck-v1` = người đọc và tick `SPOT_CHECK.md` (49 dòng, 48 Dung).
- `auto-verify-v1` = applier bật vì mọi check mục 3 xanh, không có cờ nghi ngờ.
- Dòng còn `verified=false` = chưa ai/không gì xác nhận → đi `needs_verification`.

---

## 2. Check tự động được (script quyết)

Tất cả phải xanh thì mới `auto_pass`. Một check đỏ = không bật cờ (phân loại
`fail` hoặc `queue`, xem mục 4).

| # | Check | Quy tắc máy kiểm | Nguồn field |
|---|-------|------------------|-------------|
| A1 | Toạ độ | `lat`/`lon` là số thực hữu hạn (không bool, không NaN) và nằm trong bbox Đà Nẵng `15.80–16.35 N, 107.75–108.55 E` | `lat`, `lon` |
| A2 | Tên | `name` non-empty sau khi normalize; **tên 1 token** không fail nhưng bị đẩy queue (D8: nghi junk/trùng) | `name` |
| A3 | Loại hình khớp `cat` | `type` non-empty; `canonical_category(type)` phải bằng `cat`, hoặc thuộc bảng refinement mục 3.3. `type` không map được → queue; lệch ngoài bảng → queue | `type`, `cat` |
| A4 | `cat` hợp lệ | `cat` non-empty và thuộc 14 category planner biết (`restaurant, cafe, attraction, landmark, spa, lodging, bar, market, beach, nature, museum, park, viewpoint, transport`) | `cat` |
| A5 | Nguồn | `source` non-empty (hiện có: `serpapi/google-maps`, `osm/overpass`, `manual+web`, `manual+review`) | `source` |
| A6 | Giờ mở cửa | `opening_hours` non-empty; mỗi segment khớp `HH:MM-HH:MM`, giờ trong `00:00–23:59`, `start != end`. **Qua đêm hợp lệ** (`07:30-02:00`, `11:00-00:00`). Thiếu giờ = queue, không phải fail | `opening_hours` |
| A7 | Không trùng | `poi_id` không lặp trong snapshot; không trùng `name` normalized; không nằm trong cụm <100 m có ≥2 token tên chung | `poi_id`, `name`, `lat`, `lon` |

### 2.1 Ghi chú A1 — "số thật"
Kiểm được: là số, hữu hạn, trong bbox. **Không** kiểm được: toạ độ có đúng là
của POI đó hay không (sai lệch vài chục mét hoặc ghim nhầm đường vẫn qua bbox).
Đây là check biên, không phải check định vị.

### 2.2 Ghi chú A6 — "giờ plausible"
Kiểm được: format, khoảng giờ, không rỗng, không zero-length. **Không** kiểm
được: POI có thật sự mở đúng giờ đó không. Vì vậy POI thiếu giờ **không được
auto-bật** (239/694 dòng rơi vào đây) — người phải xác nhận hoặc chấp nhận
"giờ chưa rõ" bằng quyết định có ghi vết, không phải script đoán.

### 2.3 Ghi chú A7 — "địa chỉ"
Snapshot **không có field `address`**. Nên "không trùng địa chỉ" được hiện thực
hoá bằng: trùng `name` normalized, hoặc cặp <100 m có ≥2 token tên chung
(ngưỡng của D1 trong `spotcheck_v2.py`). Không có địa chỉ chuẩn hoá để so khớp
chính xác hơn — đó là giới hạn dữ liệu, ghi nhận tại đây.

---

## 3. Check cần người (script không quyết)

| # | Check | Vì sao máy không quyết | Ai/khi nào |
|---|-------|------------------------|------------|
| H1 | `type` có đúng bản chất POI | type là nhãn Google thô tiếng Việt; "Điểm thu hút khách du lịch" có thể là quán hải sản (SPOT_CHECK dòng "Quán Hải sản Tân Trà Beach") | người đọc tên + web |
| H2 | `visit_min.p50` hợp lý | suy từ category rule; lệch >60% median bị đẩy queue nhưng trong ngưỡng vẫn có thể sai (Ghềnh Bàng 54' quá ngắn) | người |
| H3 | `rating` thật / ảo | không có review count trong snapshot; 5.0 tuyệt đối bị queue | người (hoặc crawl review count) |
| H4 | `fee`/`price_level`/`ticket_vnd` đúng | B5: fee=0 cho cả 742, price_level đồng loạt =2; chỉ 13 dòng có `ticket_vnd` | người + `ingest_money.py` |
| H5 | Giờ mở cửa đúng ngoài đời | A6 chỉ kiểm format | người / nguồn web |
| H6 | Trùng lặp thật hay khác chi nhánh | A7 chỉ phát hiện nghi vấn; quyết định gộp/giữ/loại là của người | người (`REVIEW_V2.md` D1) |
| H7 | POI có phải điểm du lịch | "CỬA HÀNG ĐIỆN NƯỚC HUY HIỀN" từng lọt pool | người (quyết định LOẠI) |
| H8 | `cat` đúng | A3 chỉ kiểm khớp/refinement; cat sai cùng chiều type thì không bắt được | người |

### 3.1 Bảng refinement `type` → `cat` (được coi là nhất quán)
`cat` tuyển chọn được phép **hẹp hơn** nhãn `type` thô. Ngoài bảng này, lệch
`type`/`cat` = nghi vấn, vào queue chứ không tự bật.

| `cat` (curated) | `canonical_category(type)` (thô) được chấp nhận |
|---|---|
| `museum` | `attraction` |
| `beach` | `attraction`, `nature` |
| `viewpoint` | `landmark`, `attraction`, `nature` |
| `landmark` | `museum` (di tích chiến tranh giữ làm landmark) |
| `park` | `attraction`, `nature` |
| `nature` | `attraction` |

Ví dụ đúng: "Bảo tàng Điêu khắc Chăm" type `Điểm thu hút khách du lịch` → canon
`attraction`, cat `museum` → nhất quán. Ví dụ sai: "Cửa hàng trà truyền thống"
→ canon `market`, cat `cafe` → queue (một trong hai field sai, người quyết).

---

## 4. Ba kết cục của applier

| Kết cục | Điều kiện | Hành động |
|---|---|---|
| `auto_pass` | A1–A7 xanh **và** không cờ nghi ngờ nào | bật `verified=true`, ghi `verified_by="auto-verify-v1"`, `verified_at=<ngày chạy>` |
| `queue` | chỉ có điều kiện **không quyết được / nghi ngờ**: `hours_missing`, `name_generic`, `duplicate_name`, `near_duplicate`, `rating_perfect`, `duration_outlier`, `ticket_unverified`, `type_unmapped`, `type_cat_mismatch` | **không bật**, ghi 1 dòng JSONL vào `auto_verify_queue.jsonl` cho người |
| `fail` | vi phạm deterministic: `coords_missing`, `coords_outside_bbox`, `name_missing`, `source_missing`, `type_missing`, `cat_missing`, `cat_unknown`, `duplicate_poi_id`, `hours_format_invalid`, `hours_out_of_range`, `hours_zero_length` | **không bật**, ghi queue JSONL để người sửa/loại |

Thứ tự ưu tiên: có `fail` → `fail`; không fail nhưng có queue reason → `queue`;
sạch hết → `auto_pass`. Dòng đã `verified=true` → `already_verified`, tool không
đọc lại, không hạ cờ, không ghi đè `verified_by`/`verified_at`.

Cờ nghi ngờ (queue) lấy cùng họ D3/D4/D5/D8 của báo cáo spot-check — chúng
không phải tiêu chí pass/fail, mà là "máy thấy đáng ngờ, đừng tự bật".

---

## 5. Quy trình chạy (dry-run là mặc định)

```powershell
# 1. Xem trước: in báo cáo D1–D8 + auto_pass/queue/fail. KHÔNG ghi gì.
python BE/ml/data/spotcheck_v2.py --snapshot BE/data/snapshots/danang-v1

# 2. Bật cờ cho các dòng auto_pass, ghi queue cho phần còn lại.
python BE/ml/data/spotcheck_v2.py --snapshot BE/data/snapshots/danang-v1 --apply-flag

# 3. Người xử lý queue (mỗi dòng 1 JSON: poi_id, decision, hard/queue, siblings).
#    Sửa dữ liệu hoặc duyệt tay rồi chạy lại bước 1 để xem còn bao nhiêu.
```

- `--queue-out <path>` đổi chỗ ghi queue (mặc định `<snapshot>/auto_verify_queue.jsonl`).
  File queue chứa **cả `queue` lẫn `fail`** (mỗi dòng: `poi_id`, `name`, `cat`,
  `decision`, `hard`, `queue`, `siblings`), vì cả hai đều cần người xem.
- `--verified-by <stamp>` đổi provenance (mặc định `auto-verify-v1`; dùng khi
  muốn đánh dấu một đợt riêng, vd `auto-verify-v1-batch2`).
- Apply ghi `pois.json` atomic (temp file cùng thư mục + `os.replace`); nếu
  không có dòng nào được bật thì **không ghi file** → chạy lại không tạo diff.
- Chạy lại nhiều lần là idempotent: dòng đã bật thành `already_verified`, queue
  được ghi đè cùng nội dung (không append trùng).

---

## 6. Số liệu dry-run trên snapshot thật (2026-10-29)

742 POI: 48 `already_verified` (giữ nguyên) + **694 unverified**:

- `auto_pass` **362** (52.2%)
- `queue` **331** (47.7%)
- `fail` **1** (0.1% — "VinWonders Nam Hội An" ngoài bbox Đà Nẵng)

Theo category (`auto_pass/queue/fail`):

| cat | auto | queue | fail |
|---|---|---|---|
| restaurant | 99 | 12 | 0 |
| cafe | 74 | 18 | 0 |
| spa | 48 | 29 | 0 |
| bar | 47 | 22 | 0 |
| attraction | 28 | 56 | 1 |
| market | 22 | 21 | 0 |
| landmark | 19 | 62 | 0 |
| beach | 8 | 5 | 0 |
| museum | 8 | 7 | 0 |
| park | 6 | 8 | 0 |
| nature | 2 | 14 | 0 |
| viewpoint | 1 | 1 | 0 |
| lodging | 0 | 76 | 0 |

Lý do queue (một dòng có thể nhiều lý do, nên tổng > 331):
`hours_missing=239`, `rating_perfect=73`, `near_duplicate=23`,
`duration_outlier=23`, `name_generic=10`, `duplicate_name=8`,
`ticket_unverified=6`, `type_unmapped=3`.
Lý do fail: `coords_outside_bbox=1`.

Đọc số này cho đúng:
- **Lodging = 0 auto** vì 74/76 khách sạn không có `opening_hours` → queue; muốn
  bật thì phải quyết "khách sạn không giờ = nhận phòng 24h" như một quyết định
  dữ liệu có ghi vết, không phải script tự suy.
- **Landmark/nature queue cao** cùng lý do thiếu giờ (đình/chùa/núi).
- **362 dòng auto_pass là trần của máy**, chưa phải số đã bật: lane này chỉ chạy
  dry-run. Bật thật là quyết định của Orchestrator sau khi review số này.
- 9/48 dòng `spotcheck-v1` sẽ **không** qua cổng auto chặt hơn (4 thiếu giờ, 3
  nghi trùng, 2 lệch type/cat, 1 tên 1 token, 1 dur outlier — có chồng lấn).
  Điều này đúng như thiết kế: cổng auto bảo thủ hơn người, và ta **không hạ cờ**
  dòng người đã duyệt.

---

## 7. Còn lại cho người (sau đợt auto)

1. **Queue 331 dòng**: ưu tiên 239 dòng thiếu giờ (quyết định: bổ sung giờ, hay
   chấp nhận "giờ chưa rõ" và vẫn giữ `verified=false`).
2. **Đợt 1 theo C2**: 145 POI có matrix nhưng chưa verified — đây là nhóm mở
   được capacity plan ngay; trong đó museum/park/bar/spa đang 0 verified.
3. **Soát chéo 362 dòng auto**: bắt buộc với các category từng bị SPOT_CHECK bắt
   lỗi type (attraction/landmark) và các dòng `rating_perfect` đã bị loại khỏi
   auto. Auto chỉ chứng minh cấu trúc, không chứng minh bản chất POI.
4. **D5/giá**: 6 dòng `ticket_unverified` + toàn bộ fee=0 (B5) vẫn là nợ dữ
   liệu, không thuộc phạm vi applier này.
