# Exports `danang-v2` (training-safe)

Sinh bởi `BE/ml/data/migrate_v2.py`. **Không chứa trường gốc Google** (rating,
price_level, type, ambience, pros/cons, giờ/giá lấy từ Google) — bất kể chính sách
khi build snapshot. Giá trị nào chỉ có nguồn Google thì để trống và confidence thấp.

## poi_features.csv — đặc trưng POI cho ranker / candidate pruner / u(t)

| cột | ý nghĩa |
|---|---|
| category, role, zone | nhãn v2 (12 thể loại + lodging) |
| cluster_id, alt_group | cụm vé chung (ba_na, ngu_hanh_son) / nhóm thay thế (chỉ chọn 1) |
| space, indoor, effort, sun_exposure, rain_cover, time_of_day | nhãn v2.1 (`tags`); `exposure_source` = explicit (bộ gán nhãn T063) hoặc category_prior (ước lượng) |
| archetype, time_profile | nhóm giờ + id đường cong u(t) (định nghĩa ở P1) |
| dwell_p25/p50/p75 | phút ở lại (ước lượng theo thể loại trừ khi `dwell_conf` >= 0.6) |
| price_band (re/vua/kha/cao), price_min/max_vnd, price_conf | chỉ nguồn sạch; trống nếu chỉ có Google |
| hours_spans, hours_conf, hours_verified_by | giờ mở mọi ngày từ nguồn sạch, nếu không có thì khung an toàn của nhóm giờ |
| signature | điểm tiêu biểu (danh sách must-go đã duyệt) |
| price_tier | v2.1: free / cheap / medium / expensive / included / trống (DATA_SPEC_v2_1) |
| hours_kind | v2.1: fixed (giờ có nguồn) / safe_window (khung an toàn theo nhóm) / by_booking (theo suất, cần đặt trước) / unknown |
| prize_prior | v2.1: tín hiệu xếp hạng sạch 0–1 (thể loại + tiêu biểu + số trang cẩm nang + Michelin + Wikidata/Wikipedia), thay rating Google |
| guide_mentions, michelin | số trang cẩm nang độc lập giới thiệu điểm; có trong Michelin Guide (`popularity_guides_*.json`) |
| name_en | tên tiếng Anh từ OSM `name:en` |

## poi_classifier_weak.csv — nhãn yếu cho bộ phân loại POI (TF-IDF + LightGBM)

`label` = luật v2 (tên → loại Google → v1). `label_uses_google_type = true` nghĩa là
nhãn dựa vào loại Google: khi train sạch, bỏ các dòng này hoặc để cleanlab xử lý,
và ưu tiên dòng `label_conf >= 0.6`. Nhãn phải được người duyệt trước khi coi là gold.
