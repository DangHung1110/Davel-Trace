# Kế hoạch hoàn thiện dữ liệu → `danang-v2.1` — 18/11/2026, 22:00

> Đích: `DATA_SPEC_v2_1.md`. Hiện trạng có số liệu: `reports/p0/P0_final.md`.
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
- **Kết quả 20/11:** mở rộng truy vấn OSM (mọi `amenity/tourism/shop/leisure` có tên; trước thiếu khách sạn, spa, karaoke, cửa hàng) + khớp tên chứa nhau ở bước tải → liên kết OSM **107 → 180/627 (29%)**; lệch toạ độ trung vị 14 m. **Không đạt 50%** vì phần lớn quán nhỏ/spa/cà phê chưa có trên OSM — giới hạn của nguồn, không phải thuật toán (khớp tên lõi chỉ thêm 6 cặp, có cặp dễ nhầm nên không dùng). Đề xuất đổi tiêu chí thành "mọi điểm có trên OSM đều được liên kết".

### WP10 — Chốt các mục chờ duyệt · BẠN + CC
- BẠN duyệt Q4, Q5. CC áp quyết định qua file nguồn (`BE/data/sources/decisions_*.json`), không sửa tay `pois.json`.
- **Nghiệm thu:** cổng **G4** xanh (không còn `review`).

### WP11 — Gold v2 + chuyển mặc định · CC
- Dựng lại 30 truy vấn gold trên v2.1 (gold cũ dựng trên v1); so sánh v1 ↔ v2.1.
- Đổi `SNAPSHOT_DIR` mặc định sang `danang-v2` **chỉ khi** G5 xanh. Hỏi BẠN trước khi đổi.
- **Kết quả 24/11:** đã đổi mặc định sang `danang-v2` theo yêu cầu (nhánh `feat/default-snapshot-v2`). Gold chạy lại
  (n=30, seed 7, `cach_ly`): v1 29/30, v2 29/30 qua cổng → G5 vẫn xanh. `mean_activities` của v2 nay là 3,38 chứ không
  phải 3,86 như `gold_v2.json` ghi (13/30 lịch gold v2 khác; `main` @ `9e5843a` cũng ra 3,38), file chưa dựng lại.
  `bench_latency` trên v2: p95 7,21 s < 8 s nhưng FAIL vì plan `experience` của yêu cầu cặp đôi + chùa + 600k trượt
  BCS/HCS (trên v1 qua, 440k).

### WP12 — Exports + báo cáo chốt · CC
- Dựng lại `BE/data/exports/danang-v2/` theo v2.1 (thêm `price_tier`, `hours_kind`, `prize_prior`).
- `reports/p0/P0_final.md`: bảng trước/sau, trạng thái 12 luật + 5 cổng, việc còn lại.

## 3. Dữ liệu kiến trúc cần thêm (không phải POI) — P1

| Dữ liệu | File đề xuất | Nguồn | Ghi chú |
|---|---|---|---|
| ~~Đường cong `u(t)`~~ **xong 20/11** cho 11 `time_profile` đang dùng | `BE/data/priors/time_profiles.json` + `BE/app/services/time_utility.py` (`u_at`, `u_mean`) | thiết kế (design prior) + log sau này | neo bình minh/hoàng hôn/chính trưa hoặc giờ đồng hồ, phủ 24 h, đỉnh = 1; test `test_time_utility.py` |
| ~~Giờ mặt trời theo ngày~~ **xong 20/11** | `time_utility.sun_times` (NOAA, không mạng) | — | đối chiếu weatherspark/alpenglow: lệch ≤ 3 phút |
| ~~Khí hậu bình thường theo tháng × giờ~~ **xong 20/11** | `BE/data/priors/climate.json` + `BE/app/services/climate.py` | Open-Meteo, ERA5 2016–2025 | 6 vùng × 12 tháng × 24 giờ; `as_forecast` cùng dạng dự báo; thử nghiệm `reports/p0/16_context_sufficiency.md` |
| Tham số trạng thái (năng lượng, độ no, nhiệt) | `BE/data/priors/state_params.json` | thiết kế, hiệu chỉnh từ pilot | mô phỏng, không thu thập |
| ~~Ma trận theo khung giờ~~ **xong 20/11 (dạng hệ số)** | `BE/data/priors/travel_time_factors.json` + `BE/app/services/travel_time.py` | ước lượng (không có nguồn kẹt xe mở) | thử nghiệm: lịch thông thoáng + đệm 12 phút không bị phá (0/30) → không cần cung phụ thuộc giờ trong lõi bộ giải; P50/P90 thật chờ log pilot |
| Gold 30 → 100 | `BE/eval/gold/` | thủ công + tạo sinh | |

## 4. Điều kiện "chốt dữ liệu" để triển khai kiến trúc

Trạng thái 20/11 — đều kiểm bằng `P0_GATE=1 pytest BE/tests/data/test_snapshot_v2.py` (xanh):

- [x] 12 luật cấu trúc xanh; G1–G5 xanh. (`test_01`…`test_11`, `test_gate_12`, `test_gate_G1`…`G5`)
- [x] Mỗi POI đúng một trường giá, một trường giờ; không còn khoá ngoài danh sách trắng. (`test_11_whitelisted_keys_only`)
- [x] Mọi POI active có ma trận; không còn cờ `verified` cũ. (`test_gate_G1`, `test_view_verified_is_eligibility_rule`)
- [x] Mỗi khu có attraction + meal + rest. (`test_gate_G2`)
- [x] ~~≥ 50 điểm tiêu biểu có giờ do người kiểm~~ — người dùng bỏ tiêu chí 20/11 (đã tự kiểm các điểm cần thiết; hiện 30).
- [x] `prize_prior` thay `rating`; chạy được với `GOOGLE_POLICY=cach_ly`. (`test_prize_prior_is_clean…`, `test_view_clean_policy_never_reads_google`)
- [x] Gold dựng lại trên v2.1, tỉ lệ qua gate ≥ v1. (`test_gate_G5`, `BE/eval/gold/gold_v2.json`)

## 4b. Còn lại để dữ liệu sạch + đúng format cho kiến trúc mới (P1, sau PR #25)

Chất lượng (không đổi format):
1. Giờ `safe_window` 557 → **498** (20/11: +19 chùa/hội quán, +10 ngoài trời/chợ, +30 spa/nightlife có nguồn). Phần còn lại không có nguồn đọc được (chùa làng, quán nhỏ). Quán ăn/cà phê giữ khung an toàn.
2. Giá: 677/745 điểm là ước lượng theo loại → lấy giá thật cho điểm hay vào lịch (paid_attraction, signature, chợ đêm), quán ăn giữ khoảng giá.
3. Toạ độ: 627 điểm gốc Google, 180 đã liên kết OSM (lệch trung vị 14 m); phần còn lại không có trên OSM (rủi ro thấp).

Format (đổi `DATA_SPEC_v2_1` — cần người dùng duyệt):
4. ~~`hours.kind = by_booking`~~ — **xong 20/11** (spec + retrieval + optimizer + `booking_*.json`); 21/11: 7 lớp có suất có nguồn, 6 lớp không có lịch → excluded. Lớp nấu ăn trùng khung bữa = bữa đó (optimizer + gate).
5. Suất/giờ khởi hành cho show, tour (Ký ức Hội An 20:00, tour lặn 4 suất) thay vì một khung mở cửa.
6. Vé nhiều mức (người lớn/trẻ em/cư dân, ECO/HIGH/VIP) + phí bắt buộc (gửi xe, thang máy, thuyền) thành trường có cấu trúc; hiện chỉ ở `price.note`.
7. Đếm khoản "chưa biết" khi tính chi phí thay vì coi = 0.

Dữ liệu kiến trúc (mục 3): `time_profiles`, giờ mặt trời, khí hậu theo tháng × giờ, tham số trạng thái, ma trận theo khung giờ (P50/P90), gold 30 → 100.

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
| 19/11 | Duyệt vòng 1b: VỌC, Hải Vân Quan (giờ + cụm hai_van), Thủy Vân Sơn xóa, Bãi Đá Đen | 873 POI, review 0, **G1–G5 + rule 12 xanh**; còn Bãi Rạng, Hồ Xanh |
| 19/11 | Vòng 1c: Hồ Xanh (OSM way/140401174), Bãi Rạng (manual, cụm `bai_rang` với KDL Suối Rạng), bỏ alias "Bãi Obama" | 875 POI, ma trận 792, gate xanh; `reports/p0/14_review_round1.md` mục Vòng 1c |

| 19/11 | **Trang chốt cuối** `reports/p0/final_review.html` (`BE/tools/build_final_review.py`, công cụ một lần, đã xoá 21/11; trang HTML giữ lại): A 6 quyết định chính sách · B 12 giá trị Claude tự chọn · C 45 điểm xác nhận giờ/giá | export `final_review_*.json` → `ingest_review.py` ghi `decisions_zfinal_*` + `human_verify_v2_*_zfinal` (sắp sau cùng nên thắng) |

| 20/11 | Bổ sung 124 điểm Hội An từ OSM (nhà hàng/cà phê có giờ OSM, spa, bar, chùa, nhà thờ tộc, phòng tranh) | 1000 POI, 945 active, ma trận 917; `reports/p0/14_review_round1.md` |
| 20/11 | **Chốt cuối** (`reports/p0/final_review_20261120.json`): A/B giữ mặc định (người dùng đồng ý); C = 7 dòng AI-Hay báo sai, người dùng tự kiểm kèm link | 876 POI (821 active, 55 excluded sau loại khu cấm Sơn Trà), ma trận 793, gate xanh; `reports/p0/14_review_round1.md` mục Chốt cuối |

**Trạng thái sau chốt cuối 20/11 — dữ liệu P0 đóng băng:**
- Giờ do người kiểm: 30 điểm. Tiêu chí ≥ 50 đã được người dùng bỏ (20/11).
- Giờ `unknown`: **0 POI active** (21/11). 7 lớp theo suất có lịch có nguồn (`by_booking`); 6 lớp không có lịch suất công bố → excluded có lý do. Helio và Nhà biểu diễn 66 Bạch Đằng đã loại.
- 76 lưu trú: giá null (chủ ý); giờ `00:00-23:59` safe_window theo quy ước lễ tân 24h (21/11); có hàng ma trận (21/11).
- Khung bán đảo Sơn Trà: đã có `access_route_*.json` + cắt giờ theo khung đường (20/11); giữ 07:30-17:30 quanh năm. Người dùng loại Mũi Nghê, Hải đăng Tiên Sa, Ghềnh Bàng, Bãi Đá Đen, Bãi Obama (khu cấm). Còn 6 điểm 'chưa rõ' giữ luật cũ (xem `reports/p0/14_review_round1.md`).
- Data contract P1 (mục 3): ngày ngoại lệ, suất diễn/khởi hành; vé nhiều mức; phí bắt buộc (gửi xe, thuyền Cù Lao Chàm); đếm khoản "chưa biết" thay vì coi = 0.

**Nhật ký tiếp (sau chốt cuối 20/11):**

| Ngày | Việc | Kết quả / chỗ xem |
|---|---|---|
| 20/11 | Thử `u(t)` trên CP-SAT (30 câu mẫu): +18% hàm mục tiêu, điểm giờ xấu −58%; bỏ `description` + `ext_ids.overture`; sửa bộ sinh gold (điểm bắt buộc ngoài giờ) | `reports/p0/15_ut_sufficiency.md` |
| 20/11 | Khí hậu ERA5 (6 vùng × tháng × giờ), hệ số kẹt xe theo giờ, `lodging_rest`, mức phơi nắng/mưa cho 258 POI OSM/nhập tay | `reports/p0/16_context_sufficiency.md`; 1000/1000 có `time_profile` + `rain_cover` |
| 21/11 | **Dọn format**: ma trận +71 lưu trú (988 id, 0 ô thiếu); một bộ 13 khoá `tags` (bỏ `rain_protection`, `indoor` = `space`); lưu trú 24h; Da Nang Family Class có suất (Pelago), 6 lớp không có lịch suất → excluded; Café 43 → restaurant, Café 41 excluded; ma trận `dense_v1` 73,6 → 7,2 MB; luật 13–15 + test | 1000 POI: 938 active (862 điểm dừng + 76 lưu trú), 62 excluded; gold v2 29/30 gate (q25: 2 điểm bắt buộc cùng nhóm cap cứng — hợp lệ) |
| 21/11 | Dọn file: xoá 12 đề bài `reports/p0/links/TASK_*.md`, 9 danh sách đầu vào đã dùng, `urls.json`, `matrix_ref.json` (người dùng duyệt xoá thẳng; còn trong lịch sử git `5dea9d4`); giữ bằng chứng `*_codex.json`, trang duyệt, toàn bộ `BE/data/sources` | README snapshot + metadata `google_policy_default = cach_ly` cập nhật |
| 21/11 | Rà soát cuối: **sửa export** `poi_features.csv` lệch `pois.json` (63 trạng thái, 5 loại) → đọc bản ghi v2.1 cuối; 37 tên chuẩn hoá (viết hoa toàn bộ, dấu câu thừa); "Nhà hàng hải sản ." excluded (tên chung, giờ chép nhầm từ Bé Ni 2); Biển Rạng Sơn Trà (nhà hàng) bỏ giờ 24h suy sai → khung an toàn; luật 16–17 + test; yêu cầu kiến trúc `ARCHITECTURE_BACKLOG.md` (điểm neo, closed_days…) | `decisions_zfinal_20261121b.json` |
| 21/11 | **Đồng bộ với `main`** (PR #25 đóng; nhánh `task/p0-sync-main` → `main`): code platform theo `main`; gắn lại by_booking, `poi_view` v2.1, lớp nấu ăn tính là bữa; bỏ 2 commit thử nghiệm cũ (`bf58dda`, `a1ef7a2`) không có trên `main`; ma trận theo `dense-v1` của `main`, dựng lại bằng OSRM **xe máy** cho 1008 POI; `danang-v1` lấy bản của `main` (+8 POI nhập tay, nguồn giờ gắn nhãn lại `claude-google-maps-v1` → theo `cach_ly` lùi về khung an toàn); "Nhà thờ Con Gà" trùng → excluded; `osm_add.py` → `v2_osm.py`, `geo_answers.json` → `sources/dwell_user_ok_geo_review.json` | 1008 POI: 944 active, 64 excluded; gold v2 27/30 (v1 26/30) |

