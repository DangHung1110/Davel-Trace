# Nhiệm vụ P0 — Hoàn thiện dữ liệu (snapshot `danang-v2`)

## Tham số (người dùng điền trước khi chạy)

- `CHINH_SACH_GOOGLE`: `cach_ly` (mặc định: không dùng trường gốc Google cho train và production)
  hoặc `demo_phi_thuong_mai` (được dùng tạm giờ mở cửa gốc Google với `verified_by = inferred`, chỉ cho bản demo).
- `GIOI_HAN_POI_MOI`: 150 (vượt quá thì dừng và hỏi).
- `SO_PHIEN`: 3 (làm theo phiên, báo cáo sau mỗi phiên).

## Đọc trước

1. `TRAVELAGENT_CONTEXT.md` (đặc biệt mục 5–8).
2. `AGENTS.md`, `HANDOFF.md`, `specs/001-travel-agent-mvp/`.
Mâu thuẫn giữa các tài liệu → dừng và hỏi.

## Phiên 1 — Nền móng (bước 0–4)

**Bước 0. Baseline test.** Cài pytest nếu thiếu, chạy toàn bộ `BE/tests`. Ghi `reports/p0/00_baseline.md`
(số pass/fail/skip, danh sách test đỏ và lý do sơ bộ). Test đỏ không rõ lý do → dừng và hỏi.

**Bước 1. Schema v2.** Thêm schema POI v2 (Pydantic) theo mục 7 của context; xuất JSON Schema.
Viết `BE/ml/data/migrate_v2.py` chuyển `danang-v1` → `BE/data/snapshots/danang-v2/` (KHÔNG sửa v1).
Loader `snapshot.py` đọc được cả v1 và v2. Test cho migrate.

**Bước 2. Cách ly Google.** Theo `CHINH_SACH_GOOGLE`. Chuyển mọi trường gốc Google
(`rating`, `price_level`, giờ mở cửa có nguồn Google, `type` gốc nếu chỉ từ Google...) vào `quarantine.google`.
Liệt kê trường bị cách ly trong báo cáo.

**Bước 3. Khớp nguồn mở.** Với từng POI:
- OSM qua Overpass (dùng lại `BE/ml/weather_label/fetch_osm.py`, `BE/ml/data/osm_join.py`; cache cục bộ).
- Overture places qua DuckDB đọc GeoParquet theo khung bao.
- Wikidata qua SPARQL (tên + toạ độ).
Luật khớp: < 50 m và tên bỏ dấu giống ≥ 0,85 → khớp; < 150 m, cùng thể loại, tên ≥ 0,70 → "cần duyệt".
Ghi `ext_ids`. Xuất `reports/p0/03_match.md`: tỉ lệ khớp theo thể loại và theo nguồn.
Tỉ lệ khớp tổng < 50% → dừng và hỏi.

**Bước 4. Thể loại và vai trò.** Ánh xạ sang 12 thể loại + `role`: khách sạn → `base`; spa → `wellness`;
"Đỉnh núi" → `viewpoint`; chợ đêm → `night_market`; điểm có vé → `paid_attraction`. Gán `zone` theo toạ độ.
Báo bảng trước/sau.

→ Báo cáo phiên 1, chờ người dùng xác nhận trước khi sang phiên 2.

## Phiên 2 — Làm giàu dữ liệu (bước 5–9)

**Bước 5. Mở rộng độ phủ.** Truy vấn OSM/Overture cho Hội An, Bà Nà–phía tây, Sơn Trà, Hải Vân–Liên Chiểu
(tag tourism, historic, leisure, amenity=restaurant|cafe). Xuất `reports/p0/05_candidates.csv`.
Chỉ tự thêm khi có Wikidata HOẶC có ở cả OSM và Overture; còn lại chờ duyệt. Vượt `GIOI_HAN_POI_MOI` → dừng và hỏi.

**Bước 6. Giờ mở cửa.** Sửa parser cho chuỗi nhiều khoảng (`"11:00-14:00, 17:00-22:00"`).
Lấy OSM `opening_hours` theo thứ khi có. POI còn lại: gán nhóm giờ bằng từ khoá (bảng ở mục 7 context),
`verified_by = inferred`, tính `safe_windows`. Báo tỉ lệ theo `verified_by`.

**Bước 7. Giá.** Parse `price_note` → `min_vnd`/`max_vnd` → nhóm giá. POI không có → nhóm giá mặc định theo thể loại.
Với `paid_attraction`: xuất `reports/p0/07_ticket_checklist.csv` (tên, khu, link trang chính thức nếu tìm được)
để NGƯỜI DÙNG điền giá vé. Agent KHÔNG đoán giá vé.

**Bước 8. Mô tả và độ nổi tiếng.** Với POI có Wikidata: lượt xem Wikipedia 12 tháng (Wikimedia REST),
số sitelinks; đoạn mô tả từ Wikivoyage (en/vi) hoặc Wikipedia, lưu `source`, URL, `license = CC BY-SA 4.0`.
KHÔNG để LLM tự viết mô tả.

**Bước 9. Provenance.** Gắn `provenance` theo từng trường với `verified_by` và `confidence` (mục 7 context).
`auto-verify-v1` → `inferred`.

→ Báo cáo phiên 2.

## Phiên 3 — Kiểm tra và hàng đợi (bước 10–13)

**Bước 10. Luật kiểm tra.** Viết `BE/tests/data/test_snapshot_v2.py` cho 10 luật ở mục 7 context. Chạy, báo kết quả.

**Bước 11. Hàng đợi xác minh.** Sinh khoảng 300 `TripSpec` biến thể từ `BE/eval/gold/queries.py`
(kiểu nhóm × thời tiết × ràng buộc). Chạy optimizer hiện có trên `danang-v2`, đếm tần suất mỗi POI vào lịch.
Xếp hàng theo `số lần vào lịch × (1 − confidence)`. Xuất trang duyệt bằng `BE/tools/build_verify_page.py`
→ `reports/p0/11_verify_queue.html` (50 POI đầu, kèm link để người dùng kiểm tra giờ và giá).

**Bước 12. So sánh gold.** Chạy 30 gold trên v1 và v2; so số lịch qua gate và các chỉ số hiện có.

**Bước 13. Báo cáo tổng.** `reports/p0/P0_report.md` theo khung dưới.

## Dừng và hỏi người dùng khi

- Cần xoá bất cứ thứ gì.
- Baseline test đỏ không rõ lý do.
- Tỉ lệ khớp nguồn mở < 50%.
- Số POI mới vượt `GIOI_HAN_POI_MOI`.
- Cần đổi hợp đồng API.
- Gặp nguồn có điều khoản sử dụng không rõ.

## Khung báo cáo (mỗi phiên và báo cáo tổng)

0. Tóm tắt (tối đa 6 dòng, có số)
1. Baseline test
2. Chính sách Google và các trường bị cách ly
3. Khớp nguồn mở (bảng theo thể loại × nguồn)
4. Thể loại và vai trò trước/sau
5. Mở rộng độ phủ (theo khu)
6. Giờ mở cửa (tỉ lệ theo `verified_by`)
7. Giá (tỉ lệ có khoảng giá; danh sách vé cần điền)
8. Mô tả và độ nổi tiếng
9. Kết quả 10 luật kiểm tra
10. Hàng đợi xác minh (50 POI đầu)
11. Gold v1 so với v2
12. Việc người dùng cần làm (điền giá vé, duyệt ứng viên, duyệt mẫu)
13. Những điều KHÔNG XÁC ĐỊNH

Cuối báo cáo, một khối ```json:
```json
{"phien": 0, "test": {"pass": 0, "fail": 0}, "google_policy": "", "quarantined_fields": [],
 "match_rate": {"osm": 0, "overture": 0, "wikidata": 0, "any": 0},
 "poi_total_v2": 0, "poi_added": 0, "by_zone": {}, "by_category": {},
 "hours_by_verified_by": {}, "price_band_coverage": 0, "ticket_missing": 0,
 "description_coverage": 0, "rules_passed": 0, "rules_total": 10,
 "gold_pass_v1": 0, "gold_pass_v2": 0, "user_todo": []}
```
