# P0 — `danang-v2.1`: trạng thái cuối (21/11/2026)

Dữ liệu đã chốt để làm kiến trúc. Phần bên dưới mục này là nhật ký P0-c ngày 18–19/11, giữ để truy vết; số liệu trong đó là số lúc ấy.

| Hạng mục | Cuối |
|---|---|
| POI | **1000**: 938 active (862 điểm dừng + 76 lưu trú), 62 excluded (mỗi cái có lý do) |
| Format | 25 khoá cấp cao nhất (danh sách trắng); một bộ 13 khoá `tags` cho mọi POI; luật 1–15 có test (`BE/tests/data/test_snapshot_v2.py`) |
| Giờ (active) | fixed 341 · safe_window 590 (gồm 76 lưu trú 24h quy ước) · by_booking 7 · **unknown 0** |
| Giá (active) | medium 389 · cheap 258 · free 167 · included 33 · expensive 15 · null 76 (lưu trú) |
| Độ nổi tiếng | `prize_prior` 32 mức; 155 POI có cẩm nang nhắc tới, 10 Michelin; không dùng `rating` Google |
| u(t) | 12 dạng, phủ 1000/1000; thử trên CP-SAT: +16% hàm mục tiêu, điểm giờ xấu −59% (`15_ut_sufficiency.md`); khí hậu giảm 62% điểm phơi nắng gắt tháng 6 |
| Thời tiết | mức phơi nắng/mưa 1000/1000 (742 có nhãn, 258 ước lượng theo loại); khí hậu ERA5 6 vùng × 12 tháng × 24 giờ (`16_context_sufficiency.md`) |
| Ma trận | `dense_v1`, 988 id phủ mọi POI active gồm lưu trú, 0 ô thiếu, 7,2 MB; hệ số kẹt xe theo khung giờ (ước lượng) |
| Gold | 30 câu; v2 qua gate 29/30 (v1 27/30); q25 rớt vì 2 điểm bắt buộc cùng nhóm cap cứng — hợp lệ |
| Còn là ước lượng (chỉnh bằng log pilot) | giá theo loại, dwell, u(t), hệ số kẹt xe, mức phơi của 258 POI OSM/nhập tay |
| Để sau (không chặn kiến trúc) | `price.items` (spec 002), gold 30 → 100 |

---

# P0-c — `danang-v2.1` (18–19/11/2026)

Theo `docs/travelagent/PROMPT_P0C_FINALIZE.md`. Q1–Q6 không được trả lời → dùng mặc định của `DATA_FIX_PLAN.md`
(Q1 ngưỡng giá như spec · Q2 ma trận riêng cho v2 · Q3 demo → `cach_ly` sau WP6 · Q4/Q5 giữ nguyên chờ duyệt · Q6 OSRM `car` trước).

## 1. Trước / sau

| | v2.0 (đầu phiên) | v2.1 (bây giờ) |
|---|---|---|
| Khoá cấp cao nhất / POI | 79 (v1 + v2 song song) | **26** = danh sách trắng (luật 11) |
| Giá | 3 hệ: `smart_tags.price_band` 3 mức, `price_level` Google, `price.band` re/vua/kha/cao | **`price.tier`**: medium 326 · cheap 222 · free 167 · included 32 · expensive 18 · null 104 (76 lưu trú) |
| Giờ | `opening_hours` + `hours.spans` + `safe_windows` | **`hours.open` + `kind`**: safe_window 615 · fixed 150 · unknown 104 |
| Google trong `pois.json` | có (policy lúc build) | **không**; chỉ ở `quarantine_google.json`, chọn lúc chạy (`GOOGLE_POLICY`, mặc định `cach_ly`) |
| Cờ `verified` v1 | loại 363 điểm dừng | **bỏ** → luật đủ điều kiện (active, không base, có ma trận, giờ ≠ unknown) |
| Xếp hạng | `rating` Google (200 điểm dừng không có → luôn cuối) | **`popularity.prize_prior`** 0–1 sạch (thể loại + tiêu biểu + Wikidata/Wikipedia khi có) |
| Ma trận | ref ma trận v1, 498 id | **`danang-v2/matrix.json`**: 784 id, 614 656 ô OSRM, 0 ô thiếu |
| Điểm dừng vào được lịch | 406 / 769 | **742 / 769** (Hội An 1 → 114, Bà Nà–Hòa Vang → 32) |
| Liên kết OSM | 223 (theo khoảng cách, nhiều cặp sai) | 315 (≤ 120 m **và** tên khớp) |
| Test | 850 pass / 0 fail (mốc máy thật, gồm `test_baselines.py`) | 862 pass / 0 fail (không gồm `test_baselines.py`) |

## 2. Gói việc

| WP | Trạng thái | Ghi chú |
|---|---|---|
| WP0 | ✅ | commit `5a28ab3`; test mốc `reports/p0/00_baseline_local_20261118.txt` |
| WP1 `poi_view` + schema v2.1 | ✅ | `BE/common.py::poi_view/view_pois`; loader `common.load_pois`, `retrieval.load_pois_json`, `evaluate.load_eval_context`, `snapshot.load_snapshot`; `archive_fields.json` |
| WP2 giá 4 mức | ✅ | `TIER_MIDPOINT` 0/50k/250k/850k, `TIER_UPPER` 0/100k/500k/1,2tr; `effective_fee` đọc `price.tier`; `fee_upper` cho cảnh báo |
| WP3 giờ một trường | ✅ | `parse_windows`; CP-SAT chọn đúng 1 khung; khung qua nửa đêm không còn bị chặn; nhãn "nen kiem tra gio" |
| WP4 bỏ cờ `verified` | ✅ | luật đủ điều kiện trong `poi_view` + `retrieval.retrieve(..., cells)` loại POI thiếu hàng ma trận với lý do |
| WP5 tên, tag | 🟡 | tag đã gom (`good_times`, `time_budget`); **17 tên chờ duyệt**: `reports/p0/12_name_cleanup.csv` |
| WP6 `prize_prior` | 🟡 | đã thay `rating` (legacy `rating` = 3 + 2·prior); Wikidata/Wikipedia chưa có (xem §4) |
| WP7 ma trận | ✅ | OSRM docker local, `expand_poi_matrix.py --select stops --max-table-size 1000 --compact` |
| WP8 xác minh người | 🟡 | bước ingest `human_verify_v2_*.json` xong; hàng đợi v2.1 (chọn tier) `reports/p0/11_verify_queue.html`; chưa có file |
| WP9 dữ liệu mở | 🟡 | OSM: 98/580 điểm gốc Google khớp tên (17% < mục tiêu 50%); 2 điểm lệch > 100 m; popularity bị 429 |
| WP10 duyệt | 🟡 | bước ingest `decisions_*.json` xong; 20 `review`, 6–8 cặp nghi trùng chờ bạn |
| WP11 gold v2 | ✅ | `BE/eval/gold/gold_v2.json`: v1 15/30, v2.1 15/30 qua gate (cùng bộ sinh, `caps=True` cho cả hai) |
| WP12 exports + báo cáo | ✅ | exports thêm `price_tier`, `hours_kind`, `prize_prior`; README snapshot viết lại |

## 3. Luật và cổng

Luật cấu trúc 1–11: **xanh**. Luật 12 (tên sạch) đang chạy như cổng tới khi WP5 được duyệt.

| Cổng | Trạng thái | Còn lại |
|---|---|---|
| G1 mọi điểm dừng có ma trận | ✅ | 0 |
| G2 mỗi khu có attraction + meal + rest | ✅ | 0 |
| G3 điểm tiêu biểu có giờ `fixed` + giá có nguồn | 🔴 | 23 / 32 |
| G4 không còn `review` | 🔴 | 20 |
| G5 gold v2.1 ≥ v1 | ✅ | 0,5 = 0,5 |
| Luật 12 tên sạch | 🔴 | 17 |

## 4. Phát hiện / rủi ro

- **API lập lịch chậm và hay hết giờ CP-SAT (có sẵn từ v1):** ~100 s/request trên máy này, nhiều truy vấn trả lịch rỗng
  `CP_SAT_TIMEOUT_NO_SOLUTION` — giống hệt trên v1, không do dữ liệu. Nên xử lý riêng (P1).
- **Gold Approach-B không áp quota cứng:** với pool dày (742 điểm) chuỗi TSP xếp cà phê/spa liên tiếp → trượt gate. Đã thêm `caps=True`
  (chỉ dùng trong `build_v2.py`, mặc định cũ không đổi).
- **Wikimedia trả 429** cho mọi API khi User-Agent không có liên hệ thật; script đọc `WIKIMEDIA_UA`. WDQS (SPARQL) đang sự cố,
  có đường dự phòng `popularity-api` (geosearch Wikipedia + wbgetentities).
- **Ma trận v2 47 MB** (dưới ngưỡng cảnh báo 50 MB của GitHub). Lần mở rộng sau nên cân nhắc định dạng gọn hơn.
- `replan.py` vẫn dùng một khung giờ (`_win`); chưa đổi trong phiên này.
- Bảng chuyển `cat` cũ: chùa → `landmark` (như v1), điểm ngoài trời → `nature` / `museum` / `attraction` theo nhóm giờ.

## 5. Việc cần bạn

1. Duyệt `reports/p0/12_name_cleanup.csv` (17 tên; 3 đề xuất `excluded`) → chép dòng đồng ý vào `BE/data/sources/decisions_names_YYYYMMDD.json`.
2. Duyệt 20 `review` + cặp nghi trùng (`reports/p0/03_status_review.csv`, `04_duplicate_candidates.csv`) → `decisions_*.json`.
3. Kiểm 30–50 dòng đầu `reports/p0/11_verify_queue.html` (ưu tiên 23 điểm tiêu biểu) → "Xuất JSON" → `BE/data/sources/human_verify_v2_YYYYMMDD.json`.
4. Đặt `$env:WIKIMEDIA_UA = "Davel-TravelAgent/0.2 (<liên hệ của bạn>)"` rồi `python BE/ml/data/fetch_open_data.py popularity`.
5. Sau mỗi bước: `python BE/ml/data/migrate_v2.py` rồi `python -m pytest BE/tests -q`. Đổi `SNAPSHOT_DIR` mặc định sang v2 **chỉ khi** G3/G4 xanh — hỏi trước.

```json
{"wp": "P0-c WP1-WP12", "tests": {"passed": 862, "failed": 0, "not_run": "test_baselines.py (chạy riêng)"},
 "gates": {"G1": "green", "G2": "green", "G3": "red (23)", "G4": "red (20)", "G5": "green", "rule12": "red (17)"},
 "eligible_pois": 742, "stops": 769,
 "todo_for_user": ["duyệt 17 tên (WP5)", "duyệt 20 review + trùng (WP10)", "kiểm giờ/giá 23 điểm tiêu biểu (WP8)",
                   "WIKIMEDIA_UA + fetch popularity (WP9)"]}
```
