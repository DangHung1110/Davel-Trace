# Snapshot `danang-v2` — format v2.1

Đặc tả đầy đủ: `docs/travelagent/DATA_SPEC_v2_1.md`. Sinh lại bất cứ lúc nào, kết quả xác định:

```powershell
python BE/ml/data/migrate_v2.py          # đọc danang-v1 (không sửa) + BE/data/sources/*
```

## File

| File | Nội dung |
|---|---|
| `pois.json` | **1000 POI**: 938 active (862 điểm dừng + 76 lưu trú), 62 excluded, mỗi cái có lý do. Mỗi khái niệm đúng một trường, đúng 25 khoá cấp cao nhất (luật 11), một bộ 13 khoá `tags` cho mọi POI (luật 13). **Luôn sạch**: không có giá trị gốc Google. |
| `matrix.json` | Ma trận di chuyển **phủ mọi POI active, gồm lưu trú** (988 id = 938 active + 50 POI bị loại sau khi đã có hàng; hàng thừa vô hại); OSRM `car` MLD, 976 144 ô, 0 ô thiếu. Định dạng `dense_v1` (7,2 MB), đọc qua `BE.matrix_format.cells_of`. Mở rộng bằng `BE/tools/expand_poi_matrix.py --select active`. |
| `quarantine_google.json` | Giá trị gốc Google (rating, price_level, type, ambience, pros/cons, giờ mọi ngày, tag v1) theo `poi_id`. Chỉ `BE.common.poi_view` đọc, và chỉ khi `GOOGLE_POLICY=demo_phi_thuong_mai`; mặc định lúc chạy là `cach_ly`. |
| `archive_fields.json` | Trường v1/v2.0 không còn dùng, chỉ để truy vết; không module nào đọc lúc chạy. |

## Trường chính (chi tiết: DATA_SPEC_v2_1 §2)

| Trường | Giá trị |
|---|---|
| `hours` | `{open, kind, closed_days, access_window, archetype}`. `kind` (POI active): fixed 341 (có nguồn) · safe_window 590 (khung an toàn theo nhóm, nhãn "nên kiểm tra giờ"; gồm 76 lưu trú 24h theo quy ước) · by_booking 7 (lớp học theo suất). Không POI active nào `unknown`. `access_window` = khung đường Sơn Trà 07:30–17:30. |
| `price` | `{tier, note}`. `tier` ∈ free / cheap (<100k) / medium (100–500k) / expensive (500k–1,2tr) / included (trong vé điểm cha `requires_ticket_of`) / `null` (lưu trú). Số VND gốc + URL ở `provenance.price.note`. |
| `dwell` | `{p25, p50, p75}` phút. |
| `tags` | `space`, `indoor` (= space == indoor), `effort`, `kid_friendly`, `party`, `good_times`, `time_budget`, `weather_sensitive`, `outdoor_exposure`, `sun_exposure`, `wind_exposure`, `rain_cover`, `exposure_source` (explicit / category_prior). |
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
`snapshot.load_snapshot`) đi qua `BE.common.poi_view`, sinh lại các trường cũ app đang đọc:
`opening_hours` ← `hours.open`; `visit_min` ← `dwell`; `smart_tags.price_band` / `free_entry` ← `price.tier`;
`rating` ← `3 + 2·prize_prior` (demo: rating Google nếu có); `verified` ← luật đủ điều kiện (active, không base, giờ ≠ unknown);
`cat`/`type` ← `category`. Bản ghi v1 đi qua nguyên vẹn. Kiến trúc mới nên đọc thẳng v2.1 (`prize_prior` thay `rating`).

## Nguồn đầu vào (`BE/data/sources/`)

Tất cả là file JSON có trích nguồn; với cùng một tiền tố, file đứng sau theo thứ tự tên sẽ ghi đè.

| Tiền tố | Nội dung |
|---|---|
| `decisions_*` | Quyết định của người dùng: tên, trạng thái, loại |
| `human_verify_v2_*` | Giờ/giá người dùng kiểm (xuất từ `reports/p0/11_verify_queue.html`; `human` cần URL) |
| `agent_web_*` | Giờ/giá tra web có URL (bằng chứng gốc ở `reports/p0/links/*_codex.json`) |
| `new_pois_*` | POI mới từ OSM / nhập tay |
| `access_route_*` | Điểm nằm trên tuyến đường có kiểm soát (Sơn Trà) |
| `booking_*` | Lịch suất của trải nghiệm theo suất |
| `popularity_guides_*` | Số cẩm nang du lịch nhắc tới, Michelin |
| `osm_match.json` · `osm_gap_candidates.json` | Liên kết OSM (Overpass, ODbL) · kho ứng viên OSM chưa thêm (`BE/ml/data/fetch_open_data.py`) |
