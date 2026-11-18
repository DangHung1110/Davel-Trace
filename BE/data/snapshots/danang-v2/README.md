# Snapshot `danang-v2` — format v2.1

Đặc tả đầy đủ: `docs/travelagent/DATA_SPEC_v2_1.md`. Sinh lại bất cứ lúc nào (kết quả xác định):

```powershell
python BE/ml/data/migrate_v2.py          # đọc danang-v1 (không sửa) + BE/data/sources/*
```

| File | Nội dung |
|---|---|
| `pois.json` | 869 POI, **mỗi khái niệm đúng một trường**, đúng 26 khoá cấp cao nhất (luật 11). **Luôn sạch**: không có giá trị gốc Google. |
| `quarantine_google.json` | Giá trị gốc Google (rating, price_level, type, ambience, pros/cons, giờ mọi ngày `hours_open`, khoảng giá, tag v1) theo `poi_id`. Chỉ `BE.common.poi_view` đọc, và chỉ khi `GOOGLE_POLICY=demo_phi_thuong_mai`. |
| `archive_fields.json` | Trường v1/v2.0 không còn dùng (cờ `verified` cũ, `hours.spans/weekly/safe_windows`, `price.min/max/typical/ticket_vnd/band`, `dwell.kind/v1`, ...). Chỉ để truy vết, không module nào đọc lúc chạy. |
| `matrix.json` | Ma trận riêng của v2 (Q2): 784 id = mọi POI active không phải lưu trú (cổng G1), OSRM `car` MLD, bbox Đà Nẵng–Hội An–Mỹ Sơn; 498 id đầu giữ nguyên ô của v1. Dựng bằng `expand_poi_matrix.py --select stops`. |
| `matrix_ref.json` | Con trỏ cũ tới ma trận v1 — **không còn dùng** khi đã có `matrix.json` (`BE.common.matrix_path` ưu tiên file riêng). |

## Trường chính (chi tiết: DATA_SPEC_v2_1 §2)

| Trường | Giá trị |
|---|---|
| `price` | `{tier, note}` — `tier` ∈ free / cheap (<100k) / medium (100–500k) / expensive (500k–1,2tr) / included (trong vé điểm cha `requires_ticket_of`) / `null` (chưa biết). Trung điểm/cận trên sống trong `BE/common.py` (`TIER_MIDPOINT`, `TIER_UPPER`). Số VND gốc + URL nằm trong `provenance.price.note`. |
| `hours` | `{open, kind, closed_days, access_window, archetype}` — `open` hợp lệ **mọi ngày mở**; `kind` fixed (có nguồn) / safe_window (khung an toàn theo nhóm, luôn gắn nhãn "nên kiểm tra giờ") / unknown. |
| `tags` | gom `smart_tags` + `intensity`→`effort` + `weather_sensitive`; `time`→`good_times`, `budget`→`time_budget`. |
| `popularity.prize_prior` | 0–1, tín hiệu xếp hạng sạch thay `rating` Google: prior theo thể loại + `signature` + Wikidata/Wikipedia khi có. |
| `provenance` | 8 nhóm: name, location, category, hours, price, dwell, tags, popularity — `{source, verified_by, confidence, evidence_url, verified_at, note}`. |

## App đọc dữ liệu thế nào

Mọi chỗ nạp `pois.json` (`BE.common.load_pois`, `retrieval.load_pois_json`, `routers/evaluate.load_eval_context`,
`snapshot.load_snapshot`) đi qua `BE.common.poi_view`, sinh lại các trường cũ app đang đọc:
`opening_hours` ← `hours.open`; `visit_min` ← `dwell`; `smart_tags.price_band` / `free_entry` ← `price.tier`;
`rating` ← `3 + 2·prize_prior` (demo: rating Google nếu có); `verified` ← luật đủ điều kiện (active, không base, giờ ≠ unknown);
`cat`/`type` ← `category`. Bản ghi v1 đi qua nguyên vẹn.

## Nguồn đầu vào (`BE/data/sources/`)

`agent_web_*.json` (giá/giờ tra web có URL) · `new_pois_*.json` (POI OSM mới) · `osm_match.json` (Overpass, ODbL) ·
`popularity.json` (Wikidata/Wikipedia — chờ chạy lại, xem P0_final) · `decisions_*.json` (quyết định của người dùng: tên, trạng thái) ·
`human_verify_v2_*.json` (xuất từ `reports/p0/11_verify_queue.html`; `human` cần URL, thiếu URL → `user`).
