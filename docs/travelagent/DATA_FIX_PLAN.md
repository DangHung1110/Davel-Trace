# Kế hoạch hoàn thiện dữ liệu → `danang-v2.1` — 18/11/2026, 22:00

> Đích: `DATA_SPEC_v2_1.md`. Hiện trạng có số liệu: `reports/p0/P0_report.md`.
> Ký hiệu người làm: **CC** = Claude Code trong repo · **BẠN** = người dùng · **MẠNG** = cần máy có internet thường
> (máy ảo của Claude chỉ ra được pypi) · **ROUTING** = cần OSRM/Valhalla chạy trên máy bạn.

## 0. Hiện trạng `danang-v2` (v2.0) lúc viết

| | Số liệu |
|---|---|
| POI | 869 = 742 từ v1 + 127 mới từ OSM (Hội An, Bà Nà, Mỹ Sơn, 2 điểm Đà Nẵng) |
| Trạng thái | active 845 · review 20 · excluded 4 · lưu trú (base) 76 |
| POI có thể là điểm dừng (active, không base) | 789 |
| **Thực sự xếp được vào lịch hôm nay** | **409** (thiếu ma trận 300 · cờ `verified=false` cũ 380 · thiếu giờ 8) |
| Giờ (789 điểm) | Google 403 · ước lượng nhóm 245 · OSM 84 · web 55 · người dùng 2 |
| Giá (789 điểm) | có giá 417 (Google 181, luật "miễn phí" ~150, web 31, người dùng 8…) · ước lượng 343 · chưa có 28 |
| Thời lượng ghé | 751 ước lượng theo bảng · 38 người dùng xác nhận |
| Toạ độ | 580 gốc Google chưa đối chiếu · 204 OSM · 5 thủ công |
| Tín hiệu nổi tiếng sạch | Wikidata 6 điểm · lượt xem Wikipedia 0 |
| Trường cấp cao nhất | ~79 (v1 + v2 song song) → đích ~25 |
| Test | 838 pass / 0 fail (`test_baselines.py` chưa chạy được trên máy ảo) |

## 1. Quyết định bạn cần chốt (trước WP liên quan)

| # | Câu hỏi | Mặc định nếu không trả lời |
|---|---|---|
| Q1 | Ngưỡng 4 mức giá (free / <100k / 100–500k / 500k–1,2tr) | dùng như trên |
| Q2 | Ma trận cho v2: file riêng trong `danang-v2/` (+26 MB) hay thêm hàng vào ma trận v1 | file riêng |
| Q3 | Chính sách Google lúc chạy cho tới khi có `prize_prior`: `demo_phi_thuong_mai` hay `cach_ly` | demo, chuyển cach_ly sau WP6 |
| Q4 | 20 POI `review`, 8 cặp nghi trùng (`reports/p0/03_*.csv`, `04_*.csv`) | giữ nguyên tới khi bạn duyệt |
| Q5 | Danh sách 18 điểm thuộc vé phố cổ Hội An | dùng danh sách hiện có, gắn nhãn cần xác nhận |
| Q6 | Profile ma trận: chạy lại OSRM `car` (nhanh) hay dựng Valhalla `motor_scooter` (đúng kiến trúc) | OSRM trước, Valhalla ở P1 |

## 2. Gói việc (làm theo thứ tự; mỗi gói xong phải xanh test)

### WP0 — Chốt mốc hiện tại · BẠN
- `git checkout -b feat/p0-data-v2`, `git add BE reports docs/travelagent`, commit.
- Chạy đủ test trên máy bạn: `python -m pytest BE/tests -q` (gồm `test_baselines.py`).
- Trả lời Q1–Q6.

### WP1 — Bộ chuyển `poi_view` + schema v2.1 · CC
- **Vì sao:** để `pois.json` sạch mà app không gãy.
- **Làm:** `BE/common.py::poi_view(poi, policy)` trả dict có **cả** trường v2.1 lẫn trường cũ app đang đọc
  (`opening_hours`, `visit_min`, `smart_tags.price_band`, `free_entry`, `rating`, `price_level`, `verified`, `type`, `tags`, `intensity`,
  `weather_sensitive`, `ambience`). Mọi chỗ đọc `pois.json` (`common.load_pois`, `retrieval.load_pois_json`,
  `routers/evaluate.load_eval_context`, `snapshot.load_snapshot`) đi qua `poi_view`.
  `GOOGLE_POLICY` đọc lúc chạy: demo → điền `rating`/`price_level`/giờ Google từ `quarantine_google.json` khi v2.1 không có giá trị sạch.
- `migrate_v2.py` ghi `pois.json` theo mục 2 của spec, dồn trường thừa sang `archive_fields.json`.
- **Nghiệm thu:** luật 11 (danh sách trắng khoá) xanh; toàn bộ test cũ xanh trên v1 **và** khi `SNAPSHOT_DIR=…/danang-v2`.

### WP2 — Giá: một trường `price.tier` · CC
- Ánh xạ: `free_entry`/luật nơi công cộng → free; `requires_ticket_of` + attraction → included; số VND có nguồn → tier theo bảng;
  ước lượng theo thể loại → tier + `provenance.price.verified_by = inferred`; không biết → `null`.
- `BE/common.py`: thay `BAND_MIDPOINT` 3 mức bằng bảng 4 mức (trung điểm 0/50k/250k/850k, cận trên 0/100k/500k/1,2tr);
  `effective_fee()` đọc `price.tier`; tính vé cha 1 lần cho cả cụm.
- `profiles`, `rank`, `scorer`, `ranker`: bỏ `price_level` (Google), dùng thứ hạng tier.
- Bỏ `ticket_vnd`, `fee`, `smart_tags.ticket`, `price_band`, `free_entry` khỏi file (số VND + URL giữ trong `provenance.price.note/evidence_url`).
- Cổng "vé có bằng chứng" đổi thành **G3** (chỉ điểm `signature` + mức `expensive` cần nguồn).
- **Nghiệm thu:** mỗi POI đúng 1 trường giá; test ngân sách (dự kiến = tổng trung điểm, cảnh báo = tổng cận trên); gold không giảm.

### WP3 — Giờ: một trường `hours.open` · CC
- `hours.open` = khung hợp lệ mọi ngày mở; `kind` fixed / safe_window / unknown; giữ `closed_days`, `access_window`.
- **Optimizer:** `BE.common.parse_hours` hiện chỉ lấy khung đầu → nhà hàng mở trưa + tối chỉ được xếp trưa. Cho CP-SAT nhận
  nhiều khung (khoảng tuỳ chọn, chọn đúng 1). Test: POI `11:00-14:00, 17:00-22:00` được xếp 18:00 trong trip 16:00–21:00.
- Điểm `kind = safe_window` mang nhãn "nên kiểm tra giờ" trong response.
- **Nghiệm thu:** không còn `opening_hours`/`spans`/`safe_windows` song song trong file; test optimizer mới xanh.

### WP4 — Bỏ cờ `verified` kiểu cũ · CC
- Thay bằng **luật đủ điều kiện** trong `retrieval`: `status = active`, `role ≠ base`, có hàng ma trận, `hours.kind ≠ unknown`
  (và không rơi vào `closed_days` khi biết ngày đi). Độ tin cậy thấp → nhãn trong response, **không loại**.
- **Nghiệm thu:** 10 điểm tiêu biểu (Bà Nà, Chợ Hàn, Chợ Cồn, VinWonders, Cù Lao Chàm…) vào được ứng viên khi có ma trận.

### WP5 — Tên, tag, thời lượng · CC + BẠN duyệt
- **Tên:** 23 tên bẩn (quảng cáo, địa chỉ, `|`, chữ Hàn/Trung) → `name` sạch, gốc vào `name_raw`. CC đề xuất bảng, BẠN duyệt.
- **Tag:** gom `smart_tags` + các trường lẻ vào `tags`; đổi `budget` → `time_budget`; 76 điểm thiếu `good_times` → luật theo thể loại;
  soát `weather_sensitive` cho điểm trong nhà (lớp nấu ăn, bảo tàng).
- **Thể loại:** soát nhóm dễ sai — `wellness` lẫn tiệm nặn mụn/nail; "quán nhậu" nightlife vs restaurant.
- **Thời lượng:** giữ bảng v2 theo 31 loại; 38 điểm người dùng xác nhận giữ nguyên; chỉnh lại sau từ log pilot (P3).
- **Nghiệm thu:** luật 12 (tên sạch) xanh; không còn khoá `smart_tags`.

### WP6 — Tín hiệu xếp hạng sạch `prize_prior` · CC (+ MẠNG để đầy đủ)
- `prize_prior` ∈ [0,1] = kết hợp có trọng số: `signature` (danh sách must-go đã duyệt), thể loại (prior theo vai trò),
  `wikidata_sitelinks`, `wikipedia_views_90d` (log, chuẩn hoá theo vùng). Thiếu nguồn thì chỉ dùng 2 thành phần đầu, confidence thấp.
- Ranker/profile `balanced` đọc `prize_prior` thay `rating`. 205 POI không có rating Google (127 mới + 78 gốc OSM) hiện luôn bị xếp cuối — đây là lỗi cần sửa.
- Sau WP6 mới chuyển `GOOGLE_POLICY=cach_ly` mặc định (Q3).
- **Nghiệm thu:** gold v1 vẫn qua gate với `cach_ly`; điểm mới Hội An xuất hiện trong lịch Hội An.

### WP7 — Ma trận cho 300 POI · BẠN (ROUTING) + CC
- BẠN: bật OSRM (`127.0.0.1:5000`, extract Việt Nam như lần build 27/10) — hoặc Valhalla `motor_scooter` nếu chọn ở Q6.
- CC: cho `BE/tools/expand_poi_matrix.py` ghi vào ma trận của v2 theo Q2, chia lô ≤ 100 POI, không để ô 0 giả.
- **Nghiệm thu:** cổng **G1** xanh (mọi POI active không base có hàng ma trận).

### WP8 — Xác minh của người · BẠN + CC
- BẠN: mở `reports/p0/11_verify_queue.html`, kiểm 30–50 dòng đầu (ưu tiên **giờ** của điểm tiêu biểu), bấm "Xuất JSON",
  lưu `BE/data/sources/human_verify_v2_YYYYMMDD.json`.
- CC: ingest file này (ưu tiên cao nhất, `verified_by=human` khi có URL, thiếu URL → `user`); dựng lại hàng đợi.
- **Nghiệm thu:** cổng **G3** xanh.

### WP9 — Dữ liệu mở đầy đủ · BẠN (MẠNG) + CC
- BẠN: `python BE/ml/data/fetch_open_data.py all` (OSM khớp tên + Wikidata + lượt xem Wikipedia).
- CC: dùng `osm_match.json` để đối chiếu 580 toạ độ gốc Google (lệch > 100 m → `review`), điền `ext_ids.osm`, `popularity.*`.
- **Nghiệm thu:** ≥ 50% POI gốc Google có liên kết OSM khớp tên; báo cáo POI lệch toạ độ.

### WP10 — Chốt các mục chờ duyệt · BẠN + CC
- BẠN duyệt Q4, Q5. CC áp quyết định qua file nguồn (`BE/data/sources/decisions_*.json`), không sửa tay `pois.json`.
- **Nghiệm thu:** cổng **G4** xanh (không còn `review`).

### WP11 — Gold v2 + chuyển mặc định · CC
- Dựng lại 30 truy vấn gold trên v2.1 (gold cũ dựng trên v1); so sánh v1 ↔ v2.1.
- Đổi `SNAPSHOT_DIR` mặc định sang `danang-v2` **chỉ khi** G5 xanh. Hỏi BẠN trước khi đổi.

### WP12 — Exports + báo cáo chốt · CC
- Dựng lại `BE/data/exports/danang-v2/` theo v2.1 (thêm `price_tier`, `hours_kind`, `prize_prior`).
- `reports/p0/P0_final.md`: bảng trước/sau, trạng thái 12 luật + 5 cổng, việc còn lại.

## 3. Dữ liệu kiến trúc cần thêm (không phải POI) — P1

| Dữ liệu | File đề xuất | Nguồn | Ghi chú |
|---|---|---|---|
| Đường cong `u(t)` cho 13 `time_profile` | `BE/data/priors/time_profiles.json` | thiết kế + log sau này | neo bình minh/hoàng hôn, phủ 24 h, đỉnh = 1 |
| Giờ mặt trời theo ngày | sinh bằng code (công thức thiên văn, không cần mạng) | — | dùng cho `u(t)` |
| Khí hậu bình thường theo tháng × giờ | `BE/data/priors/climate_danang.json` | Open-Meteo historical (MẠNG) | để tính phần lệch thời tiết |
| Tham số trạng thái (năng lượng, độ no, nhiệt) | `BE/data/priors/state_params.json` | thiết kế, hiệu chỉnh từ pilot | mô phỏng, không thu thập |
| Ma trận theo khung giờ × thời tiết, P50/P90 | ma trận v2 | Valhalla `motor_scooter` | |
| Gold 30 → 100 | `BE/eval/gold/` | thủ công + tạo sinh | |

## 4. Điều kiện "chốt dữ liệu" để triển khai kiến trúc

- [ ] 12 luật cấu trúc xanh; G1–G5 xanh.
- [ ] Mỗi POI đúng một trường giá, một trường giờ; không còn khoá ngoài danh sách trắng.
- [ ] Mọi POI active có ma trận; không còn cờ `verified` cũ.
- [ ] Mỗi khu có attraction + meal + rest.
- [ ] ≥ 50 điểm tiêu biểu có giờ do người kiểm.
- [ ] `prize_prior` thay `rating`; chạy được với `GOOGLE_POLICY=cach_ly`.
- [ ] Gold dựng lại trên v2.1, tỉ lệ qua gate ≥ v1.

## 5. Không làm

- Không sửa/xoá `danang-v1`. Không sửa tay `danang-v2/pois.json` — mọi thay đổi qua `migrate_v2.py` + file nguồn.
- Không gọi SerpAPI/API trả phí. Không để LLM viết mô tả hay đoán giờ/giá cụ thể.
- Không thêm > 150 POI mới mà không hỏi. Không đổi hợp đồng API (`specs/.../contracts/`) mà không hỏi.
- Không xoá file: thay vào đó chuyển sang `_to_delete/` và báo.

## 6. Nhật ký tiến độ (handoff)

| Ngày | Việc | Kết quả / chỗ xem |
|---|---|---|
| 18/11 | WP0–WP4, WP7, WP9, WP11–12 | commit `5a28ab3`…`00fb0de`; `reports/p0/P0_final.md` |
| 19/11 | Giá null → nguồn web | 104 → 89 null (76 lưu trú); `reports/p0/13_null_price_research.md` |
| 19/11 | Trang duyệt HTML + ingest JSON | `reports/p0/review_v21.html`, `BE/tools/ingest_review.py` |
| 19/11 | **Duyệt vòng 1** (export người dùng, ảnh #6–#11, vé phố cổ Hội An, tách Sơn Trà/Bạch Đằng/Hải Vân, gộp Linh Ứng) | `reports/p0/14_review_round1.md`; 872 POI, review 1; ma trận 789 |

**Việc mở tiếp theo:**
- VỌC Glamping (review).
- Bãi Đá Đen, Bãi Rạng, Hồ Xanh: thiếu toạ độ.
- Data contract P1 (mục 3):
  - Opening-hours: theo mùa, ngày ngoại lệ, suất diễn.
  - Ticket: vé 80k/120k, số ô, phí bắt buộc.
  - Tổng chi phí phải đếm số khoản "chưa biết", không coi chưa biết là 0.
