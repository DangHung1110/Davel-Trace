# Đặc tả dữ liệu `danang-v2`, format v2.3 — 19/11/2026 (bản chốt)

> Thay `DATA_SPEC_v2_1.md` (nhánh `feat/p0-data-v2`) và bản v2.2 sáng 19/11. Căn cứ: doc "TravelAgent – Kiến
> trúc Agent lập lịch du lịch Đà Nẵng", mục 12 (kiến trúc chốt) và 17 (hợp đồng dữ liệu P0); quyết định của người
> dùng chiều 19/11: *giá không cần chính xác; điểm không đủ thông tin trên Google Maps thì bỏ; máy làm được gì
> thì xử lý hết*. Rà soát: `DATA_AUDIT_2026-11-19.md`. Code dựng: `BE/ml/data/migrate_v2.py` + `curate_v2.py`.

**Con số chốt:** 877 POI ứng viên → **556 POI giữ** trong `pois.json` (186 tham quan, 149 ăn, 111 cà phê nghỉ,
57 bar/đêm, 53 spa) + 321 POI bỏ trong `dropped.json`, mỗi POI một lý do (mục 10).

## 1. Nguyên tắc

1. **Một khái niệm = một trường.** Không lưu song song hai cách nói cùng một điều.
2. **Mọi điểm đều xếp lịch được.** Mỗi POI có giờ (`fixed` hoặc khung an toàn) và mức giá; ước lượng theo nhóm
   được phép nhưng luôn ghi `verified_by = inferred` và confidence thấp.
3. **Mọi giá trị có nguồn** ở `provenance.<nhóm>`.
4. **`pois.json` không chứa giá trị gốc Google.** Chúng nằm ở `quarantine_google.json`. Thông tin Google Maps
   (số đánh giá, có giờ hay không, đã đóng cửa) chỉ dùng để **quyết giữ hay bỏ** một POI.
5. **Không sửa tay `pois.json`.** Sửa file nguồn (`BE/data/sources/`) rồi build lại; build là tất định.
6. **`danang-v1` đóng băng** để đối chiếu; app vẫn chạy trên v1 cho tới khi có bộ đọc v2.3.
7. **`pois.json` chỉ chứa điểm dùng được.** Điểm bị loại, lưu trú, điểm thiếu thông tin nằm ở `dropped.json`.

## 2. Một bản ghi (dữ liệu thật, `provenance` rút gọn)

```json
{
 "poi_id": "osm:way/39268284", "name": "Chùa Cầu", "name_raw": "Chùa Cầu", "name_en": "Japanese Bridge",
 "lat": 15.877117, "lon": 108.326023,
 "category": "outdoor_landmark", "role": "attraction", "status": "active", "status_reason": null,
 "zone": "hoi_an", "cluster_id": "hoi_an_old_town", "alt_group": null,
 "requires_ticket_of": "osm:node/4601279489",
 "hours": {"open": ["07:30-21:00"], "kind": "safe_window", "closed_days": [],
           "access_window": ["07:30-21:00"], "archetype": "ngoai_troi_do_thi"},
 "price": {"tier": "included", "min_vnd": 0, "max_vnd": 0, "note": null},
 "dwell": {"p25": 10, "p50": 20, "p75": 40},
 "tags": {"indoor": false, "effort": 1, "kid_friendly": true, "party": ["solo", "couple", "family", "group"],
          "good_times": ["morning"], "time_budget": "quick", "on_request": false,
          "sun_exposure": 0.75, "outdoor_exposure": 0.75, "rain_cover": "open", "weather_sensitive": true},
 "time_profile": "outdoor_heat_sensitive",
 "popularity": {"signature": true, "audience": null, "prize_prior": 0.9,
                "wikidata_sitelinks": null, "wikipedia_views_90d": null},
 "description": {"text": null, "source": null, "license": null},
 "ext_ids": {"osm": "way/39268284", "wikidata": "Q1091054", "overture": null, "google_place_id": null},
 "provenance": {
  "hours": {"source": "archetype:ngoai_troi_do_thi", "verified_by": "inferred", "confidence": 0.45,
            "evidence_url": null, "verified_at": null,
            "note": "khung an toàn theo nhóm giờ — nên kiểm tra giờ thật; cắt theo giờ cổng Phố cổ Hội An"},
  "price": {"source": "cluster_rule", "verified_by": "inferred", "confidence": 0.6, "evidence_url": null,
            "verified_at": null, "note": "vé tính ở Phố cổ Hội An"},
  "...": "name, location, category, status, dwell, tags, popularity cùng dạng 6 khoá"
 },
 "data_version": "v2.3", "valid_from": "2026-11-19", "valid_to": null
}
```

Đúng 26 khoá cấp cao nhất; mỗi object con cũng có danh sách khoá cố định (test 11).

## 3. Ý nghĩa và từ vựng

| Trường | Giá trị | Ghi chú |
|---|---|---|
| `poi_id` | Google place id (`ChIJ…`), `osm:<type>/<id>`, `manual:<slug>` | Giữ id cũ, không dùng lại |
| `name` / `name_raw` / `name_en` | tên hiển thị / tên gốc nguồn / tên tiếng Anh (OSM `name:en`) | `name` sạch: không `\|`, không chữ Hàn/Trung/Nhật, ≤ 60 ký tự (cổng G5) |
| `category` | beach, viewpoint, outdoor_landmark, religious, museum_indoor, day_market, night_market, restaurant, cafe, nightlife, wellness, paid_attraction | Luật tên trước, loại Google chỉ phá hoà (không lưu). `lodging` chỉ còn trong `dropped.json` |
| `role` | attraction, meal, rest, nightlife, wellness | Suy từ `category` |
| `status` / `status_reason` | luôn `active` / `null` trong `pois.json` | Giữ trường để replan đánh dấu đóng cửa tạm; điểm bị bỏ và lý do ở `dropped.json` |
| `zone` | trung_tam, son_tra_my_khe, ngu_hanh_son, hoi_an, ba_na_tay, hai_van_lien_chieu | `v2_rules.zone_of(lat, lon)` |
| `cluster_id` / `alt_group` | ba_na, ngu_hanh_son, bay_mau, hoi_an_old_town / bay_mau, ba_na_entry | Cụm đi cùng một khối / chỉ chọn một trong nhóm |
| `requires_ticket_of` | `poi_id` điểm cha | Điểm con phải vào cổng cha; giờ bị cắt theo giờ cổng |
| `hours` | xem mục 5 | |
| `price` | xem mục 4 | |
| `dwell` | phút ở lại p25 ≤ p50 ≤ p75 | Log-normal: trung vị = p50, `sigma_log ≈ ln(p75/p25)/1.349` |
| `tags.indoor` | true / false / null | null = vừa trong vừa ngoài (xem `rain_cover`) |
| `tags.effort` | 1 nhẹ … 3 nặng | |
| `tags.party` | ⊂ {solo, couple, family, group} | `kid_friendly` = có family và không phải nightlife |
| `tags.good_times` | ⊂ {sunrise, morning, sunset, night} | Không mâu thuẫn với giờ mở có nguồn (test 14) |
| `tags.time_budget` | quick / half_day / full_day | Luôn suy từ `dwell.p50`: ≤ 45 phút quick, ≤ 240 phút half_day, dài hơn full_day (luật 19) |
| `tags.on_request` | true / false | Chỉ xếp khi khách hỏi (lớp học, mua quà, đi cả ngày…) |
| `tags.sun_exposure`, `outdoor_exposure` | 0–1 | Dùng cho nắng/mưa và `u(t)` |
| `tags.rain_cover` | enclosed / mixed / open | |
| `tags.weather_sensitive` | true / false | |
| `time_profile` | id đường cong `u(t)` theo thể loại | Đường cong định nghĩa ở P1 (`BE/data/priors/`) |
| `popularity.signature` | true / false | Danh sách điểm tiêu biểu đã duyệt |
| `popularity.audience` | tourist / local / null | local = chủ yếu người địa phương (duyệt v1); null = chưa duyệt |
| `popularity.prize_prior` | 0–1 (null cho lưu trú) | Thể loại + tiêu biểu + Wikidata/Wikipedia; local trừ 0,1; KHÔNG dùng rating Google |
| `ext_ids` | osm, wikidata, overture, google_place_id | OSM chỉ nhận khi tên khớp |
| `description` | text + source + license | Chỉ từ nguồn có giấy phép; không để LLM viết |

## 4. Giá: một mức + khoảng VND

`price = {tier, min_vnd, max_vnd, note}`: **chi tiêu một người cho một lần ghé** (vé + khoản bắt buộc).

| tier | Khoảng / người | Khi nào |
|---|---|---|
| free | 0 | nơi công cộng không cổng |
| included | 0 (vé cha tính một lần) | điểm con có `requires_ticket_of` |
| cheap | < 100k | |
| medium | 100k – 500k | |
| expensive | > 500k | |

Không còn `null`: điểm có vé chưa tra được giá lấy khoảng theo thể loại (bảo tàng 20–100k, điểm có vé khác
50–300k; `verified_by = inferred`, ghi "ƯỚC LƯỢNG"). `tier` luôn suy ra từ khoảng (trung điểm), nên đổi ngưỡng
(câu hỏi Q1, tài liệu kiến trúc đề xuất <50k / 50–150k / 150–400k / >400k) chỉ cần build lại. Verifier kiểm ngân sách bằng **tổng `max_vnd` + 10%**
(kiến trúc mục 14.4); người dùng thấy khoảng `min–max`.

## 5. Giờ

`hours = {open, kind, closed_days, access_window, archetype}`

- `open`: các khung `HH:MM-HH:MM` đúng **mọi ngày mở**; qua nửa đêm ghi `18:00-02:00`.
- `kind`: `fixed` (có nguồn: human / open_data / user / agent_web), `safe_window` (khung an toàn theo nhóm giờ —
  luôn gắn nhãn "nên kiểm tra giờ"). `unknown` vẫn là từ vựng hợp lệ nhưng điểm `unknown` không vào `pois.json`.
- Nhóm giờ (`archetype`) thêm ở v2.3: `co_ve` (điểm có vé, lớp học, khu vui chơi) khung 09:00–16:00 — 26/29 bộ giờ
  Google của nhóm chứa trọn khung này; `su_kien_toi` (show buổi tối) 18:30–21:30. Khi khung của nhóm nằm ngoài giờ
  Google quá nửa (vd. quán mì Quảng chỉ bán sáng bị xếp nhóm "cơm trưa"), build chọn nhóm khác cùng thể loại khớp
  ≥ 85 %; không nhóm nào khớp thì bỏ điểm (`hours_conflict`). Chỉ **nhóm** đổi, khung vẫn là của bảng nhóm.
- `closed_days`: ⊂ Mo…Su. `access_window`: giới hạn vào cổng (đường lên Sơn Trà, giờ cổng điểm cha).
- Thứ tự tin nguồn: người kiểm → web có URL → OSM `opening_hours` → luật không gian mở → khung an toàn.
  Giờ đọc từ Google Maps chỉ ở `quarantine_google.json`.

## 6. `verified_by` → confidence

| verified_by | confidence | Điều kiện |
|---|---|---|
| human | 0.9 | bắt buộc `evidence_url` + `verified_at` |
| open_data | 0.65–0.7 | OSM/Wikidata khớp vị trí và tên |
| user | 0.7 | người dùng xác nhận, không URL |
| agent_web | 0.5–0.65 | Claude tra web có URL, chưa ai kiểm tại chỗ |
| inferred | 0–0.6 | luật, nhóm, ước lượng; 0 = không xác định |

## 7. File

| File | Nội dung |
|---|---|
| `BE/data/snapshots/danang-v2/pois.json` | metadata (`count`, `count_candidates`, `count_dropped_by_rule`, `count_by_*`, `sources`) + `pois` (556) |
| `BE/data/snapshots/danang-v2/dropped.json` | 321 POI không giữ: `poi_id, name, category, zone, rule, reason, decided_by` |
| `BE/data/snapshots/danang-v2/quarantine_google.json` | giá trị gốc Google theo `poi_id` (chỉ POI được giữ; `gmaps_check` = lượt tra 19/11) |
| `BE/data/snapshots/danang-v2/matrix.json` | ma trận xe máy `dense-v1` cho mọi POI (`BE/tools/build_matrix_v2.py`) |
| `BE/data/sources/*.json` | đầu vào có ngày (README trong thư mục) |
| `BE/data/exports/danang-v2/*.csv` | bảng sạch cho ML, sinh lại mỗi lần build (gitignore) |
| `reports/p0/*` | `01_build_summary.json`, `02_dropped.csv`, `11_verify_queue.*` (điểm nên kiểm giờ/giá trước), sinh lại mỗi lần build |

## 8. Luật kiểm tra (`BE/tests/data/test_snapshot_v2.py`)

Luôn bật (1–10 là mười luật của kiến trúc mục 17.3):

1. Toạ độ trong khung bao; `zone` = `zone_of(lat, lon)`.
2. Không trùng: `poi_id` duy nhất; không hai điểm dừng cùng đối tượng OSM hoặc cách < 50 m và tên giống ≥ 85%.
3. Giờ đúng cú pháp; `kind` khớp nguồn; điểm dừng `unknown` phải có lý do.
4. `tier` thuộc từ vựng và khớp khoảng VND; `included` ⇔ có điểm cha.
5. `provenance` đủ 9 nhóm × 6 khoá; `human` có URL và ngày.
6. Không giá trị Google trong `pois.json` và exports.
7. `description.text` ⇒ có `source` + `license`.
8. `pois.json` chỉ có điểm dừng `active`; mọi POI bị bỏ nằm trong `dropped.json` với một luật và lý do.
9. Số đếm khớp metadata.
10. Mỗi khu có điểm tham quan, quán ăn, cà phê nghỉ và điểm trong nhà cho ngày mưa.
11. Chỉ các khoá trong danh sách trắng, ở mọi cấp.
12. Một từ vựng cho mỗi trường.
13. Thời lượng tăng dần; điểm cha tồn tại; mã OSM/Wikidata đúng dạng.
14. `good_times` không mâu thuẫn giờ có nguồn.
15. Ma trận phủ mọi POI, không thiếu cặp giữa các điểm dừng.

16. (G3) Điểm tiêu biểu xếp lịch được: có giờ và mức giá.
17. (G5) Tên hiển thị sạch: không `|`, không chữ Hàn/Trung/Nhật/Nga, ≤ 60 ký tự.
18. (G6) Mọi điểm có giờ và mức giá.
19. `tags.time_budget` khớp `dwell.p50` (không còn lấy tag `budget` cũ của v1).

Luật 8 kiểm thêm: `pois.json` chỉ có điểm dừng `active` (G4 cũ), `dropped.json` không trùng id và mỗi dòng có lý do.
Bỏ G7 (giá vé kèm URL) theo quyết định giá gần đúng; bỏ biến `P0_GATE`, mọi luật luôn chạy.

## 9. Thay đổi so với v2.1 (`feat/p0-data-v2`)

| Chỗ | v2.1 | v2.2 | Vì sao |
|---|---|---|---|
| Nền | `danang-v1` cũ (742 POI, 29/10) | `danang-v1` của `main` (750 POI, đã duyệt) | v2.1 bỏ sót 8 POI và 124 quyết định loại |
| `price` | `{tier, note}`; số VND nằm trong chữ ở `provenance.price.note` | `{tier, min_vnd, max_vnd, note}` | Kiến trúc cần khoảng giá cho verifier |
| `tags` | 14 khoá, có trùng (`space`/`indoor`, `rain_protection` toàn `unknown`, `exposure_source`) | 11 khoá, không trùng; thêm `on_request` | Một khái niệm một trường |
| `tags.time_budget` | danh sách, lẫn `must-go` | một giá trị quick / half_day / full_day | `must-go` là `popularity.signature` |
| `popularity` | có `wikidata` | `wikidata` chuyển sang `ext_ids`; thêm `audience` | Đúng mục 17.1 |
| `provenance` | 8 nhóm | 9 nhóm (+ `status`) | Biết ai quyết định trạng thái |
| `status_reason` | — | lý do ngắn, không số liệu Google | Ghi chú gốc vào quarantine |
| Ma trận | OSRM ô tô 784 POI, 48 MB, `cells` | xe máy `dense-v1` 876 POI, 6,4 MB | Kiến trúc yêu cầu xe máy, phủ mọi POI |
| `archive_fields.json` | 1,7 MB trường cũ | bỏ | `danang-v1` + lịch sử git đã giữ |

## 10. Luật giữ/bỏ (v2.3, `BE/ml/data/curate_v2.py`)

Thứ tự xét, luật đầu tiên đúng là lý do bỏ. Quyết định `status = active` của người dùng trong `decisions_*.json`
luôn thắng (trừ lưu trú).

| Luật | Bỏ khi | Số POI |
|---|---|---|
| `excluded` | đã loại ở lần duyệt v1 (Google Maps), `plan_tier` v1, luật tên v2 | 136 |
| `lodging` | khách sạn: app không xếp lưu trú vào lịch, điểm xuất phát lấy từ bản đồ | 76 |
| `review` | POI luật v2 không phân loại được (Núi Sơn Trà: đã có Bán đảo Sơn Trà, Đỉnh Bàn Cờ) | 1 |
| `closed` | Google Maps ghi đóng cửa vĩnh viễn / tạm đóng (lượt tra 19/11) | 6 |
| `not_listed` | không tìm thấy trên Google Maps (trừ di tích trong vé phố cổ / Bà Nà) | 17 |
| `few_reviews` | dưới 30 đánh giá trên Google Maps, hoặc điểm "local" không rõ số đánh giá (điểm tiêu biểu được miễn) | 77 |
| `no_hours` | quán/cửa hàng/điểm có vé mà Google Maps không có giờ và không nguồn nào có giờ ("mở 24/24" hay giờ chưa đủ ngày vẫn tính là có) | 6 |
| `hours_conflict` | giờ Google lệch hẳn mọi nhóm giờ của thể loại | 1 |
| `duplicate` | cùng một nơi với POI khác (< 50 m, tên giống ≥ 85 %) | 1 |

Nguồn thông tin Google: 457 POI v1 dùng số liệu đã có (SerpAPI 03/10 + lần duyệt Google Maps 30–31/10, ở
quarantine); 126 POI OpenStreetMap được tra trực tiếp trên Google Maps ngày 19/11
(`BE/data/sources/google_maps_check_2026-11-19.json`: 108 khớp, 18 không tìm thấy). Không giá trị Google nào được
chép sang `pois.json`.

Việc máy đã quyết thay form duyệt v2.2: Q1–Q7 giữ mặc định (ngưỡng giá hiện tại, ma trận ước lượng, cách ly
Google, Hội An/Bà Nà/Mỹ Sơn trong phạm vi, điểm local chỉ hạ ưu tiên); 10 tên làm sạch (`name_raw` giữ tên gốc);
4 cặp nghi trùng đều là hai nơi khác nhau; danh sách vé phố cổ giữ theo bản tuyển chọn; giá chưa có nguồn lấy
khoảng theo thể loại; giờ du thuyền sông Hàn và Cù Lao Chàm tra web (`agent_web_2026-11-19b.json`).

## 11. Thay đổi v2.2 → v2.3

| Chỗ | v2.2 | v2.3 |
|---|---|---|
| Số POI trong `pois.json` | 876 (739 active, 136 excluded, 1 review) | 556, tất cả xếp lịch được |
| POI bị bỏ | nằm trong `pois.json` với `status = excluded` | `dropped.json`, mỗi POI một luật + lý do |
| Lưu trú | 76 POI `role = base` | bỏ (app không dùng) |
| Giờ | 102 `unknown` | 0; thêm nhóm `co_ve`, `su_kien_toi`; chọn lại nhóm khi lệch giờ Google |
| Giá | 88 `null` | 0; khoảng theo thể loại cho bảo tàng / điểm có vé |
| Tên | 12 tên bẩn chờ duyệt | làm sạch tự động |
| `tags.time_budget` | lấy tag `budget` v1 nếu có; 139 POI mâu thuẫn `dwell` (vd. điểm ngắm 30 phút ghi "cả ngày") | luôn suy từ `dwell.p50` |
| Cổng P0 | G3–G7 chờ người duyệt (`P0_GATE=1`) | luật 16–19 luôn chạy; bỏ G7 |
| Ma trận | 876 × 876 (6,4 MB) | 556 × 556 (2,5 MB), 107 hàng ước lượng |
| Form duyệt | `reports/p0/review_v22.html` | bỏ (máy quyết); `ingest_review.py` vẫn nhận export v21 nếu người dùng muốn sửa |

