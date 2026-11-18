# Snapshot `danang-v2`

Sinh bằng `python BE/ml/data/migrate_v2.py` từ `danang-v1` (v1 **không bị sửa**).
Chạy lại bất cứ lúc nào: kết quả xác định (deterministic), đọc thêm nguồn trong `BE/data/sources/`.

| File | Nội dung |
|---|---|
| `pois.json` | 742 POI. **Siêu tập của v1**: mọi trường v1 còn nguyên, cộng trường v2 bên dưới. App hiện tại đọc được bằng `SNAPSHOT_DIR=BE/data/snapshots/danang-v2` (hoặc `data/snapshots/danang-v2` khi chạy trong `BE/`). |
| `quarantine_google.json` | Giá trị gốc Google (SerpAPI): rating, price_level, type, ambience, pros/cons, giờ, khoảng giá. Không dùng để train / xuất production. |
| `matrix_ref.json` | Trỏ tới `../danang-v1/matrix.json` (cùng `poi_id`, tránh chép 26 MB). `BE.common.matrix_path()` tự đi theo con trỏ. |

## Chính sách Google (`--google-policy`)

- `demo_phi_thuong_mai` (**mặc định lúc build hiện tại**): khi không có nguồn sạch, trường legacy app đọc
  (`opening_hours`, `smart_tags.price_band`, `rating`...) lấy từ bản cách ly, provenance ghi `google_demo` (confidence 0.5).
  Lý do: ranking hiện vẫn đọc `rating`; chưa có tín hiệu phổ biến sạch (Wikipedia/Wikidata) cho tới P1.
- `cach_ly`: trường legacy chỉ lấy nguồn sạch; `rating`/`ambience`/`pros`/`cons` của POI gốc Google bị xoá khỏi `pois.json`.
  **Phải dùng trước khi public/thương mại.** Đổi: `python BE/ml/data/migrate_v2.py --google-policy cach_ly`.
- Bản xuất `BE/data/exports/danang-v2/` **luôn sạch**, bất kể chính sách.

## Trường v2 (mỗi POI)

| Trường | Ý nghĩa |
|---|---|
| `data_version` | `v2.0` |
| `name_vi`, `name_en` | tên (name_en chưa có — chờ OSM/Wikidata) |
| `ext_ids{osm, osm_match_m, overture, wikidata}` | chỉ nhận OSM khi gần ≤ 60 m **và tên khớp** (v1 nối theo khoảng cách nên có cặp sai, vd. House Coffee ↔ The Pizza Company) |
| `category` | 12 loại: beach, viewpoint, outdoor_landmark, religious, museum_indoor, day_market, night_market, restaurant, cafe, nightlife, wellness, paid_attraction (+ `lodging`) |
| `category_evidence` | luật đã quyết định: `override:` / `name:<từ khoá>` / `type:<loại Google>` / `v1_cat:` |
| `role` | attraction, meal, rest, nightlife, wellness, base (lodging — không bao giờ là điểm dừng) |
| `status`, `status_reason` | active / review (giữ, chờ người quyết) / excluded (giữ trong dữ liệu, không vào ứng viên) |
| `zone` | trung_tam, son_tra_my_khe, ngu_hanh_son, hoi_an, ba_na_tay, hai_van_lien_chieu (ranh giới gần đúng theo toạ độ) |
| `cluster_id` | ba_na, ngu_hanh_son, bay_mau — các điểm nên đi thành một khối |
| `alt_group` | nhóm thay thế (chỉ chọn 1): bay_mau (các bến thuyền thúng), ba_na_entry |
| `requires_ticket_of(_name)` | điểm nằm trong vé của điểm cha (vd. Động Huyền Không ⊂ vé Thủy Sơn) → `price.basis = included_in_parent` |
| `hours{spans, weekly, spans_any_day, raw_v1, conflict, archetype, archetype_default, safe_windows, access_window}` | `spans` = khung mở **mọi ngày** (giao các biến thể ngày của v1); `access_window` = giới hạn đường lên bán đảo Sơn Trà |
| `price{basis, min_vnd, max_vnd, typical_vnd, band, ticket_vnd, free_entry, status, note}` | band 4 mức/người: `re` <50k, `vua` 50–150k, `kha` 150–400k, `cao` >400k. `status`: known / estimate / band_only / todo / unknown / not_applicable |
| `tags{indoor, space, kid_friendly, effort, sun_exposure, rain_cover, time_of_day, weather_sensitive}` | từ `smart_tags` v1 (suy luận) |
| `time_profile` | id đường cong u(t) (định nghĩa ở P1) |
| `dwell{p25,p50,p75, kind, v1}` | phút ở lại; bảng v2 theo loại điểm thay rule v1 (v1 cho cầu/tượng đài 3–4 giờ) trừ khi người dùng đã xác nhận |
| `popularity{wikipedia_views_90d, wikidata_sitelinks, signature}` | 2 trường đầu chờ `fetch_open_data.py popularity` |
| `description{text, source, license}` | trống — không để LLM viết |
| `provenance{name, location, category, hours, price, dwell, tags}` | `{source, verified_by, confidence, evidence_url, verified_at, note}` |
| `valid_from`, `valid_to` | hiệu lực dữ liệu |

### `verified_by` → confidence mặc định

`human` 0.9 (bắt buộc `evidence_url`) · `open_data` 0.7 · `user` 0.7 · `agent_web` 0.5–0.7 (Claude tra web có URL, **chưa** ai kiểm tại chỗ) ·
`google_demo` 0.5 · `inferred` 0.4–0.7 (luật/nhóm). Giá trị dưới 0.6 (0.5 với google_demo) **không** được ghi vào trường legacy app đọc.
`auto-verify-v1` của v1 được hạ thành `inferred` (giữ nguyên trong `provenance.v1_verified`).

### Trường legacy được ghi lại (app hiện tại đọc)

- `opening_hours` = `hours.spans` (∩ `access_window`); nguồn suy luận thì dùng `safe_windows`.
- `visit_min` = `dwell` v2.
- `smart_tags.price_band` (3 mức cũ: cheap/medium/expensive) + `smart_tags.band_source`; band v1 cũ chuyển sang `price_band_v1`.
- `free_entry = true` khi luật "nơi công cộng" (biển/chùa/công viên/điểm ngắm, không trong cụm có vé) với confidence 0.7.
- `verified = false` cho `status = excluded`.

## Nhóm giờ (ước lượng, đã hiệu chỉnh)

Khung an toàn được thu hẹp sau khi đo trên giờ Google v1 (QA nội bộ, chỉ số tổng hợp): tỉ lệ POI thật sự mở trong khung
an toàn ≈ 0.83–0.93 (cafe 0.85, bar 0.90, spa 0.87, nhà hàng trưa 0.85 / tối 0.93, chợ 0.88, chùa 0.83). Không bao giờ là 100% →
POI dùng giờ suy luận luôn mang nhãn "nên kiểm tra giờ". Chi tiết: `reports/p0/05_archetype_vs_google.csv`.
