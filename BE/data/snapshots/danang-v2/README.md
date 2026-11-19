# Snapshot `danang-v2` — format v2.3 (bản chốt 19/11/2026)

Bộ dữ liệu POI thống nhất cho luồng mới (TripSpec → truy xuất → tầng 1/2 → verifier).
Đặc tả: `docs/travelagent/DATA_SPEC.md`. Rà soát và lý do từng quyết định:
`docs/travelagent/DATA_AUDIT_2026-11-19.md`.

**556 POI** dùng được để xếp lịch (877 ứng viên, bỏ 321). App hiện vẫn chạy trên `danang-v1`;
`danang-v2` thay v1 khi app có bộ đọc v2.3 (`BE/common.py::poi_view`).

## File

| File | Nội dung |
|---|---|
| `pois.json` | 556 POI: 186 tham quan, 149 quán ăn, 111 cà phê/nghỉ, 57 bar/đêm, 53 spa. Mỗi POI có giờ (112 có nguồn, 444 khung an toàn theo nhóm) và mức giá (gần đúng nếu chưa có nguồn). Không có giá trị gốc Google. |
| `dropped.json` | 321 POI không giữ, mỗi POI một luật + lý do: 136 đã loại khi duyệt v1, 76 lưu trú, 77 ít thông tin trên Google Maps, 17 không tìm thấy, 6 đã đóng cửa, 6 không có giờ, 3 khác. |
| `quarantine_google.json` | Giá trị gốc Google của 556 POI được giữ (số đánh giá, giờ/giá đọc từ Google Maps, lượt tra 19/11). Chỉ để đối chiếu nội bộ và quyết giữ/bỏ; không train, không hiển thị. |
| `matrix.json` | Ma trận xe máy `dense-v1` 556 × 556, không thiếu cặp. 449 POI cũ: OSRM `motorbike.lua` đã hiệu chỉnh với VietMap (sai số 7,8%). 107 POI mới: ước lượng từ ma trận ô tô (sai số 5,8%), liệt kê ở `coverage.estimated_ids`. |

## Dựng lại (kết quả xác định, cùng đầu vào cùng byte)

```powershell
python BE/ml/data/migrate_v2.py                       # pois.json, dropped.json, quarantine, exports, reports/p0
python BE/tools/build_matrix_v2.py --car <car.json>   # matrix.json (docstring chỉ cách lấy file ô tô)
python -m pytest BE/tests/data -q
```

Đầu vào: `BE/data/snapshots/danang-v1/` (không sửa) và `BE/data/sources/` (README ở đó).
Không sửa tay `pois.json`: mọi thay đổi đi qua file nguồn rồi build lại.
