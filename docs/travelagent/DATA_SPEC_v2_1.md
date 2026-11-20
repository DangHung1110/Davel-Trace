# Đặc tả dữ liệu đích `danang-v2.1` (form chuẩn) — chốt 18/11/2026

> Tài liệu này mô tả **trạng thái cuối** của một POI sau khi làm sạch. Cách đi tới đó: `DATA_FIX_PLAN.md`.
> Bản đang có trong repo là `danang-v2` (v2.0, xem `BE/data/snapshots/danang-v2/README.md`): đúng nội dung nhưng còn
> mang ~79 trường cấp cao nhất (trường v1 + trường v2 song song). v2.1 = cùng dữ liệu, **mỗi khái niệm đúng một trường**.

## 1. Nguyên tắc

1. **Một khái niệm = một trường.** Không lưu song song (vd. giá: chỉ `price.tier`; giờ: chỉ `hours.open`).
2. **Độ chính xác của trường = độ chính xác của hiểu biết.** Không biết thì `null`, không đoán số cụ thể.
3. **Mọi giá trị có nguồn** trong `provenance.<trường>`.
4. **`pois.json` sạch tuyệt đối:** không có giá trị gốc Google. Google nằm ở `quarantine_google.json`;
   có dùng hay không do chính sách lúc **chạy** (`GOOGLE_POLICY`), không phải lúc build.
5. **App không đọc thẳng file.** Mọi module đọc POI qua một bộ chuyển (`BE/common.py::poi_view`) — nhờ vậy đổi
   schema không làm gãy code; khi mọi module đã đọc trường v2.1 thì bỏ phần tương thích.

## 2. Bản ghi POI v2.1

```json
{
  "poi_id": "osm:way/39268284",
  "name": "Chùa Cầu",
  "name_raw": "Chùa Cầu",
  "name_en": "Japanese Bridge",
  "lat": 15.877117, "lon": 108.326023,

  "category": "outdoor_landmark",
  "role": "attraction",
  "status": "active", "status_reason": null,
  "zone": "hoi_an",
  "cluster_id": "hoi_an_old_town", "alt_group": null,
  "requires_ticket_of": "osm:node/4601279489",

  "hours": {
    "open": ["05:00-22:00"],
    "kind": "safe_window",
    "closed_days": [],
    "access_window": null,
    "archetype": "ngoai_troi_do_thi"
  },
  "price": { "tier": "included", "note": "trong vé phố cổ" },
  "dwell": { "p25": 10, "p50": 20, "p75": 40 },
  "tags": {
    "indoor": false, "effort": 1, "sun_exposure": 0.7, "rain_cover": "partial",
    "kid_friendly": true, "weather_sensitive": true,
    "good_times": ["morning", "sunset", "night"], "time_budget": "quick"
  },
  "time_profile": "outdoor_heat_sensitive",
  "popularity": { "signature": true, "prize_prior": 0.92, "wikidata": "Q1091054",
                  "wikidata_sitelinks": null, "wikipedia_views_90d": null },
  "ext_ids": { "osm": "way/39268284", "google_place_id": null },

  "provenance": {
    "name":     {"source": "osm", "verified_by": "open_data", "confidence": 0.7, "evidence_url": null, "verified_at": "2026-11-18", "note": null},
    "location": {"...": "..."}, "category": {"...": "..."}, "hours": {"...": "..."},
    "price": {"...": "..."}, "dwell": {"...": "..."}, "tags": {"...": "..."}, "popularity": {"...": "..."}
  },
  "data_version": "v2.1", "valid_from": "2026-11-18", "valid_to": null
}
```

### Ý nghĩa từng nhóm

| Trường | Giá trị hợp lệ | Ghi chú |
|---|---|---|
| `name` | tên hiển thị sạch | không chứa `\|`, địa chỉ, quảng cáo, chữ Hàn/Trung; ≤ 60 ký tự |
| `name_raw` | tên gốc từ nguồn | để tra lại, không hiển thị |
| `category` | beach, viewpoint, outdoor_landmark, religious, museum_indoor, day_market, night_market, restaurant, cafe, nightlife, wellness, paid_attraction, lodging | |
| `role` | attraction, meal, rest, nightlife, wellness, base | suy ra từ `category`; `base` (lưu trú) không bao giờ là điểm dừng |
| `status` | active, review, excluded | excluded: giữ trong dữ liệu, không vào ứng viên |
| `zone` | trung_tam, son_tra_my_khe, ngu_hanh_son, hoi_an, ba_na_tay, hai_van_lien_chieu | ranh giới gần đúng theo toạ độ (`v2_rules.zone_of`) |
| `cluster_id` | ba_na, ngu_hanh_son, bay_mau, hoi_an_old_town | đi thành một khối |
| `alt_group` | bay_mau, ba_na_entry | chỉ chọn 1 trong nhóm |
| `requires_ticket_of` | poi_id điểm cha | điểm tham quan con: giá đã nằm trong vé cha; quán ăn trong khu: phải có vé cha mới vào, giá bữa tính riêng |
| `hours.open` | danh sách `HH:MM-HH:MM`, hợp lệ **mọi ngày mở cửa** | solver chỉ đọc trường này; qua nửa đêm ghi `19:30-23:59` hoặc `17:00-02:00` |
| `hours.kind` | fixed, safe_window, by_booking, unknown | fixed = giờ thật có nguồn; safe_window = khung an toàn theo nhóm (luôn gắn nhãn "nên kiểm tra giờ"); **by_booking** = trải nghiệm bán theo suất cố định, cần đặt trước (lớp nấu ăn, workshop): `open` liệt kê các suất, `dwell` = độ dài suất nên chỉ xếp trọn một suất; chỉ gợi ý khi khách chọn ẩm thực/văn hoá (hoặc must-visit), tối đa 1/ngày; suất trùng khung bữa (trưa 11–14, tối 17–21) **chính là bữa đó** (gate A1 đếm, thỏa bữa trưa bắt buộc, nghỉ trưa tính từ lúc kết thúc lớp, không xếp thêm nhà hàng trong khung); nhãn "cần đặt trước"; nguồn ở `BE/data/sources/booking_*.json` (link đặt chỗ ở `provenance.hours`); unknown = không xếp được |
| `hours.closed_days` | Mo…Su | lịch chưa xét thứ; dữ liệu đã sẵn cho P1 |
| `price.tier` | free, cheap, medium, expensive, included, `null` | **chi tiêu một người cho một lần ghé**, gồm vé + khoản bắt buộc (vd. cano Cù Lao Chàm). `included` = đã nằm trong vé điểm cha (`requires_ticket_of`), solver cộng vé cha đúng 1 lần. `null` = chưa biết |
| `dwell` | phút, p25 ≤ p50 ≤ p75 | |
| `tags.time_budget` | quick, half_day, full_day | đổi tên từ `smart_tags.budget` (không phải tiền) |
| `popularity.prize_prior` | 0–1 | tín hiệu xếp hạng sạch thay `rating` (cách tính: `DATA_FIX_PLAN.md` WP6) |

### Bảng mức giá (sống trong code, không lưu từng POI)

| tier | Khoảng / người | Trung điểm (dự kiến) | Cận trên (cảnh báo) | Ví dụ |
|---|---|---|---|---|
| free | 0 | 0 | 0 | biển, chùa, công viên, cầu |
| included | 0 (vé cha tính riêng 1 lần) | 0 | 0 | Cầu Vàng ⊂ vé Bà Nà; hội quán ⊂ vé phố cổ |
| cheap | < 100k | 50k | 100k | bảo tàng 20–60k, cà phê, bánh mì, vé phố cổ khách Việt |
| medium | 100k – 500k | 250k | 500k | nhà hàng, Mỹ Sơn, Cù Lao Chàm, spa |
| expensive | 500k – 1,2tr | 850k | 1,2tr | Bà Nà, VinWonders, lớp nấu ăn, show Ký ức Hội An |

Ngân sách: so **tổng trung điểm** với ngân sách; **tổng cận trên** chỉ để cảnh báo. Ngưỡng là đề xuất — chỉnh lại khi có sổ chi tiêu pilot.

### `verified_by` → confidence

| verified_by | confidence | Điều kiện |
|---|---|---|
| human | 0.9 | bắt buộc `evidence_url` |
| open_data | 0.7 | OSM/Wikidata khớp **khoảng cách ≤ 60 m và tên** |
| user | 0.7 | người dùng tự nhập/xác nhận |
| agent_web | 0.5–0.7 | Claude tra web có URL, chưa ai kiểm tại chỗ |
| inferred | 0.4–0.7 | luật / nhóm / ước lượng |

(`google_demo` không còn xuất hiện trong `pois.json` v2.1 — chỉ do bộ chuyển sinh ra lúc chạy khi `GOOGLE_POLICY=demo_phi_thuong_mai`.)

## 3. Ánh xạ trường hiện có → v2.1

| Trường hiện có (v1 + v2.0) | Đi đâu |
|---|---|
| `name_vi` | → `name` (sau khi làm sạch); `name` cũ → `name_raw` |
| `name_osm` | → `name_raw` |
| `opening_hours`, `hours.spans`, `hours.safe_windows` | → `hours.open` (+ `hours.kind`) |
| `hours.raw_v1`, `hours.spans_any_day`, `hours.archetype_default`, `hours.weekly`, `hours.conflict` | → `archive_fields.json` |
| `smart_tags.price_band`, `free_entry`, `fee`, `ticket_vnd`, `ticket_note`, `price_note`(user), `price_sources`, `price.*`, `smart_tags.ticket`, `band_verified`, `band_source`, `price_band_v1`, `legacy_band_*` | → `price.tier` + `price.note`; số VND gốc và URL → `provenance.price` / `archive_fields.json` |
| `price_level`, `rating`, `type`, `ambience`, `pros`, `cons`, `price_note`(Google) | → `quarantine_google.json` |
| `visit_min`, `dur_source`, `dur_confidence`, `dur_note`, `dwell.v1`, `dwell.kind` | → `dwell` + `provenance.dwell` |
| `smart_tags.*`, `intensity`, `weather_sensitive`, `space*`, `rain_protection*`, `io_label`, `ws_source`, `intensity_source`, `smart_tag_source` | → `tags` + `provenance.tags` |
| `smart_tags.budget` | → `tags.time_budget` |
| `must_go` | → `popularity.signature` |
| `verified`, `verified_by`, `verified_at` (v1) | **bỏ cờ**; giữ dấu vết ở `archive_fields.json` (thay bằng luật đủ điều kiện — WP4) |
| `category_evidence`, `cat` | → `provenance.category.note` / archive |
| `requires_ticket_of_name` | bỏ (suy ra từ poi_id) |
| `osm_evidence`, `web_evidence`, `access_note`, `access_source`, `parking_note`, `hours_note`, `rating_note`, `crawl_query`, `excursion`, `hours_source`, `tags` (list v1), `source`, `fetched_at`, `added_in` | → `provenance.*` hoặc `archive_fields.json` |

## 4. File của snapshot v2.1

| File | Nội dung |
|---|---|
| `pois.json` | bản ghi v2.1 (mục 2), metadata (`data_version`, `count`, `built_at`, `sources`) |
| `quarantine_google.json` | mọi giá trị gốc Google, theo `poi_id` |
| `archive_fields.json` | trường cũ không còn dùng, theo `poi_id` (để truy vết, không ai đọc lúc chạy) |
| `matrix.json` (hoặc `matrix_ref.json`) | ma trận di chuyển phủ **mọi** POI active |
| `README.md` | đặc tả rút gọn + cách build lại |

## 5. Luật kiểm tra (pytest `BE/tests/data/`)

Cấu trúc (luôn bật):
1. Toạ độ trong khung bao; `zone` hợp lệ.
2. `poi_id` duy nhất.
3. Mọi POI active không phải base có `hours.open` hoặc `hours.kind = unknown` có lý do.
4. `price.tier` thuộc từ vựng hoặc `null`; `included` ⇔ có `requires_ticket_of` và role = attraction.
5. Provenance đủ 8 trường, confidence ∈ [0,1], `human` có `evidence_url`.
6. `pois.json` và exports không có khoá/giá trị Google (`rating`, `price_level`, `type`, `ambience`, `pros`, `cons`).
7. Không có `description` và `ext_ids.overture` (đã bỏ 2026-11-20: OSM chỉ có 15/869 mô tả, 0 tiếng Việt; Overture không dùng). Lời giải thích ghép từ các trường dữ liệu.
8. `role = base` và `status = excluded` không vào ứng viên.
9. `count` khớp metadata.
10. Từ vựng `category/role/status/hours.kind/tags.*` hợp lệ.
11. **Chỉ có các khoá cấp cao nhất của mục 2** (danh sách trắng).
12. `name` sạch (không `|`, không chữ Hàn/Trung/Nhật, ≤ 60 ký tự).

Cổng chốt dữ liệu (`P0_GATE=1`):
- G1. Mọi POI active không phải base có hàng ma trận.
- G2. Mỗi khu có attraction + meal + rest.
- G3. Mọi điểm `signature` có `hours.kind = fixed` và `price.tier` có nguồn.
- G4. Không còn POI `status = review`.
- G5. Gold v2 chạy xong, tỉ lệ qua gate ≥ v1.
