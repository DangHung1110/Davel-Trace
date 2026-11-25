# Snapshot `danang-v2` — format v2.1

Đặc tả đầy đủ: `docs/travelagent/DATA_SPEC_v2_1.md`. Sinh lại bất cứ lúc nào, kết quả xác định:

```powershell
python BE/ml/data/migrate_v2.py          # đọc danang-v1 (không sửa) + BE/data/sources/*
```

## File

| File | Nội dung |
|---|---|
| `pois.json` | **1029 POI** (build 25/11/2026): 936 active (860 điểm dừng + 76 lưu trú, gồm 20 quán đặc sản thêm 24/11, active từ khi có hàng ma trận 25/11), 93 excluded (25/11: gộp Bãi tắm Nguyễn Thần Hiến vào Bãi biển Non Nước, Bãi Biển Thiên Đường vào Bãi Tắm Thanh Khê), 0 review, mỗi cái có lý do. Đầu vào là `danang-v1` của `main` (750 POI, gồm 8 điểm nhập tay mới, đồng bộ 21/11). Mỗi khái niệm đúng một trường, đúng 25 khoá cấp cao nhất (luật 11), một bộ 14 khoá `tags` cho mọi POI (luật 13). **Luôn sạch**: không có giá trị gốc Google. |
| `matrix.json` | Ma trận di chuyển **xe máy** (OSRM, `BE/tools/osrm/motorbike.lua`, như `danang-v1` của `main`) cho 1029 POI (1 058 841 ô, 0 ô thiếu). Mọi ô giữa 1009 POI cũ giữ nguyên bản dựng 21/11/2026 (`osrm`); hàng và cột của 20 quán thêm 24/11 lấy từ đồ thị dựng 25/11/2026 (`appended`: cùng `motorbike.lua`, image và bbox, OSM 2026-11-24). Đồ thị mới lệch đồ thị cũ trên các cặp cũ: 98,2% trùng, tối đa 2 phút. POI không có hàng ma trận bị `migrate_v2` để `status=review` (luật 15) tới khi dựng lại OSRM và chạy lại migrate. Định dạng `dense-v1`, đọc qua `BE.app.services.matrix.load_cells`. Dựng lại: `BE/tools/osrm/build_osrm.sh <data_dir> 107.85,15.72,108.55,16.3` (bbox của bản 21/11) rồi `python BE/tools/build_poi_matrix.py --all --pois BE/data/snapshots/danang-v2/pois.json --osrm-meta <data>/osrm-meta.json`. |
| `quarantine_google.json` | Giá trị gốc Google (rating, price_level, type, ambience, pros/cons, giờ mọi ngày, tag v1) theo `poi_id`. Chỉ `BE.common.poi_view` đọc, và chỉ khi `GOOGLE_POLICY=demo_phi_thuong_mai`; mặc định lúc chạy là `cach_ly`. |
| `archive_fields.json` | Trường v1/v2.0 không còn dùng, chỉ để truy vết; không module nào đọc lúc chạy. |

## Trường chính (chi tiết: DATA_SPEC_v2_1 §2)

| Trường | Giá trị |
|---|---|
| `hours` | `{open, kind, closed_days, access_window, archetype}`. `kind` (POI active, 25/11): fixed 350 (có nguồn) · safe_window 579 (khung an toàn theo nhóm, nhãn "nên kiểm tra giờ"; gồm lưu trú 24h theo quy ước) · by_booking 7 (lớp học theo suất). Không POI active nào `unknown`. `access_window` = khung đường Sơn Trà 07:30–17:30. |
| `price` | `{tier, note}`. `tier` ∈ free / cheap (<100k) / medium (100–500k) / expensive (500k–1,2tr) / included (trong vé điểm cha `requires_ticket_of`) / `null` (lưu trú). Số VND gốc + URL ở `provenance.price.note`. Build 25/11/2026: 167/860 điểm dừng active có giá có nguồn (`provenance.price.verified_by` = agent_web / human / user); còn lại là mặc định theo loại (`category_default:*`), luật "nơi công cộng vào tự do" (`rule_free_public`) hoặc vé điểm cha (`cluster_rule`). |
| `dwell` | `{p25, p50, p75}` phút. |
| `tags` | `space`, `indoor` (= space == indoor), `effort`, `kid_friendly`, `party`, `good_times`, `time_budget`, `weather_sensitive`, `outdoor_exposure`, `sun_exposure`, `wind_exposure`, `rain_cover`, `exposure_source` (explicit / category_prior), `dishes`. |
| `tags.dishes` | Món chính của nơi ăn uống: `[{dish, source, url}]`, `dish` = id trong `BE.common.DISHES` (27 món). `source`: `name` (tên quán nói món, bằng chứng là `name`), `osm` (thẻ `cuisine` của phần tử OSM, `url` = trang OSM), `web` (thực đơn / trang quán / cẩm nang, `url` bắt buộc, file `dishes_*`). Build 24/11: 123 POI có món (86 theo tên, 25 OSM, 27 web); 25/11: 116/239 quán ăn active có món. App đọc qua `poi_view` → `dishes` (tên) và `cuisine` (mọi cách gọi món) — chấm gu ăn, dị ứng, gate PROFILE_SAFE và ý muốn món (`retrieval.poi_fits_wish`) cùng đọc. |
| `time_profile` | Dạng đường cong `u(t)` (12 dạng, `BE/data/priors/time_profiles.json`, code `BE/app/services/time_utility.py`); phủ 1000/1000. |
| `popularity` | `prize_prior` 0–1 (32 mức: loại + signature + số cẩm nang nhắc tới + Michelin + Wikidata), `guide_mentions`, `michelin`, `signature`. |
| `provenance` | 8 nhóm (name, location, category, hours, price, dwell, tags, popularity): `{source, verified_by, confidence, evidence_url, verified_at, note}`. |

## Dữ liệu ngữ cảnh đi kèm (`BE/data/priors/`)

| File | Nội dung | Mức tin cậy |
|---|---|---|
| `time_profiles.json` | Đường cong u(t) neo theo mặt trời / đồng hồ | Thiết kế, chỉnh bằng log pilot |
| `climate.json` | 6 vùng × 12 tháng × 24 giờ: nhiệt độ, cảm giác nhiệt, xác suất mưa, gió… (ERA5 2016–2025 qua Open-Meteo, `BE/tools/build_climate.py`) | Số đo |
| `travel_time_factors.json` | Hệ số di chuyển theo khung giờ × vùng (`BE/app/services/travel_time.py`) | Ước lượng, chỉnh bằng log pilot |

## App đọc dữ liệu thế nào

Mọi chỗ nạp `pois.json` (`BE.common.load_pois`, `retrieval.load_pois_json`, `routers/evaluate.load_eval_context`,
đi qua `BE.common.poi_view`, sinh lại các trường cũ app đang đọc:
`opening_hours` ← `hours.open`; `visit_min` ← `dwell`; `smart_tags.price_band` / `free_entry` ← `price.tier`;
`rating` ← `3 + 2·prize_prior` (demo: rating Google nếu có); `verified` ← luật đủ điều kiện (active, không base, giờ ≠ unknown);
`cat`/`type` ← `category`. Bản ghi v1 đi qua nguyên vẹn. Kiến trúc mới nên đọc thẳng v2.1 (`prize_prior` thay `rating`).

## Nguồn đầu vào (`BE/data/sources/`)

Tất cả là file JSON có trích nguồn; với cùng một tiền tố, file đứng sau theo thứ tự tên sẽ ghi đè.

| Tiền tố | Nội dung |
|---|---|
| `decisions_*` | Quyết định của người dùng: tên, trạng thái, loại |
| `human_verify_v2_*` | Giờ/giá người dùng kiểm (xuất từ `reports/p0/11_verify_queue.html`; `human` cần URL) |
| `agent_web_*` | Giờ/giá tra web có URL (bằng chứng gốc ở `reports/p0/links/*_codex.json`; `agent_web_2026-11-25`: 59 giá cho điểm hay vào lịch, bằng chứng + 90 điểm chưa có nguồn ở `reports/p0/links/prices_claude_20261125.json`). File sau thay CẢ dòng cùng POI, nên dòng mới phải chép lại giờ của dòng cũ. |
| `new_pois_*` | POI mới từ OSM / nhập tay (`new_pois_food_2026-11-24`: 20 quán đặc sản trung tâm + Sơn Trà, toạ độ OSM, Google Maps chỉ để giữ/bỏ) |
| `dishes_*` | Món chính đọc trên trang có URL (cẩm nang, thực đơn của quán) → `tags.dishes` source=web |
| `access_route_*` | Điểm nằm trên tuyến đường có kiểm soát (Sơn Trà) |
| `booking_*` | Lịch suất của trải nghiệm theo suất |
| `popularity_guides_*` | Số cẩm nang du lịch nhắc tới, Michelin |
| `osm_match.json` · `osm_gap_candidates.json` | Liên kết OSM (Overpass, ODbL) · kho ứng viên OSM chưa thêm (`BE/ml/data/fetch_open_data.py`) |
