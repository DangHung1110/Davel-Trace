# Nguồn đầu vào của `danang-v2`

`BE/ml/data/migrate_v2.py` đọc các file này (cùng `BE/data/snapshots/danang-v1/`) để dựng
`danang-v2`. Mỗi file có ngày trong tên; không sửa file cũ, thêm file mới. Khi hai file
cùng loại nói về một POI, file sau thắng (từng trường).

| File | Là gì | `verified_by` khi vào dữ liệu |
|---|---|---|
| `new_pois_osm_2026-11-18.json` | 127 POI OpenStreetMap (Overpass, ODbL) cho Hội An, Bà Nà, Mỹ Sơn; kèm tên hiển thị, thể loại đã chọn, danh sách vé phố cổ, 3 giá vé có URL | `open_data` (giá: `agent_web`) |
| `osm_match.json` | Khớp POI cũ ↔ đối tượng OSM (Overpass, ODbL). Chỉ được dùng khi tên khớp | `open_data` |
| `agent_web_2026-11-18.json`, `agent_web_2026-11-19.json`, `agent_web_2026-11-19b.json` | Giá vé / giờ Claude tra web, có URL, chưa ai kiểm tại chỗ. Khoá `hours_*` chỉ bổ sung giờ, giữ giá của file trước | `agent_web` |
| `google_maps_check_2026-11-19.json` | Kết quả tra Google Maps cho 126 POI OSM (108 khớp, 18 không tìm thấy). **Giá trị Google**: chỉ dùng để quyết giữ/bỏ POI và vào `quarantine_google.json`, không bao giờ vào `pois.json` | — |
| `decisions_*.json` | Quyết định của người dùng: tên, trạng thái, trùng, vé phố cổ (sinh bởi `BE/tools/ingest_review.py` hoặc viết tay) | `user` |
| `human_verify_v2_*.json` | Giờ/giá người kiểm (có URL → `human`, không URL → `user`), từ `reports/p0/11_verify_queue.html` | `human` / `user` |
| `popularity.json` | Wikidata + lượt xem Wikipedia (`BE/ml/data/fetch_open_data.py popularity`; chưa chạy được vì Wikimedia trả 429) | `open_data` |

## Sửa một quyết định của máy

Từ v2.3 máy quyết mọi mục (luật ở `BE/ml/data/curate_v2.py`, lý do từng POI ở
`BE/data/snapshots/danang-v2/dropped.json`). Người dùng luôn thắng:

- Giữ lại một POI bị bỏ: thêm `{"items": {"<poi_id>": {"status": "active"}}}` vào
  `decisions_<ngày>.json` (trừ lưu trú).
- Bỏ một POI: `{"status": "excluded", "status_reason": "<lý do>"}`.
- Sửa giờ/giá: mở `reports/p0/11_verify_queue.html` → "Xuất JSON" → lưu thành
  `human_verify_v2_<ngày>.json`.

Rồi chạy `python BE/ml/data/migrate_v2.py`, `python BE/tools/build_matrix_v2.py --car <car.json>`
và `python -m pytest BE/tests/data -q`.

Ứng viên POI OSM mới không lưu trong repo: chạy lại `python BE/ml/data/fetch_open_data.py osm`
khi cần mở rộng độ phủ. Cache HTTP ở `cache/` (đã gitignore).
