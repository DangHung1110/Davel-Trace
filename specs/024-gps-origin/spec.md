# Điểm xuất phát từ vị trí GPS

Khi khách bấm "lập lại phần còn lại", ngày đang đi nên bắt đầu từ chỗ khách đang đứng. Trước đây planner chỉ nhận `origin.poi_id` của một địa điểm có hàng trong ma trận OSRM. Gửi `lat`/`lon` thì bị bỏ qua mà không báo, ngày thành tour mở (không tính chặng đầu). Replan của app luôn bắt đầu lại từ điểm vừa đi xong, dù khách đã đi chỗ khác.

## Cách tính chặng đầu từ GPS

Vị trí GPS không có hàng trong ma trận, nên server mượn hàng của các địa điểm gần nhất có dữ liệu:

1. Trong 200 m quanh một địa điểm: coi như khách đang ở đó, dùng đúng số phút OSRM của địa điểm ấy. GPS ở khách sạn cho lịch giống hệt chọn khách sạn.
2. Xa hơn: thử đi qua 3 địa điểm gần nhất, lấy đường ngắn nhất.
   - Số phút = đoạn tới địa điểm + phút OSRM từ địa điểm đó.
   - Đoạn tới địa điểm = đường chim bay × 1,19, chạy 29,6 km/h (trung vị trên 1 triệu chặng thật của ma trận danang-v2).
3. Cách địa điểm có dữ liệu gần nhất trên 1 km: vẫn dùng, kèm cảnh báo trong `warnings`.
4. Trên 3 km, ngoài Đà Nẵng, hoặc `accuracy_m` trên 1000: không dùng vị trí. Ngày bắt đầu từ điểm vừa đi xong, không có thì khách sạn, không có nữa thì tour mở; `warnings` nói lý do.

Ví dụ thật: khách đứng ở quán Time Coffee, và ta giả vờ quán chưa có trong dữ liệu (giấu hàng ma trận của nó đi). Ba địa điểm gần nhất có dữ liệu là Hải sản Châu Sơn 1 (456 m, đi khoảng 1,1 phút), Ikigai Cafe (517 m, 1,2 phút) và Chợ An Hải Bắc (601 m, 1,4 phút). Cột "OSRM thật" là hàng ma trận thật của quán:

| Đi tới | OSRM thật | Server ước lượng |
|---|---|---|
| Cầu Rồng | 9 phút | 10 |
| Chợ Hàn | 7 | 7 |
| Bãi biển Mỹ Khê | 11 | 11 |
| Ngũ Hành Sơn | 21 | 21 |
| Chùa Linh Ứng Sơn Trà | 17 | 17 |
| Phố cổ Hội An | 56 | 56 |

## App gửi gì

`POST /v1/trips/{trip_id}/replans` thêm `current_location`:

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `lat`, `lon` | số | vị trí lúc bấm: `lat` trong [-90, 90], `lon` trong [-180, 180] |
| `accuracy_m` | số, có thể bỏ | `Position.accuracy` của geolocator, đơn vị mét |

```json
{
  "source_version_id": "8f1c…",
  "remaining_from": "2026-11-24T14:05:00+07:00",
  "current_location": {"lat": 16.06025, "lon": 108.24216, "accuracy_m": 12},
  "target_count": 5
}
```

- Chỉ gửi **một** lần đọc vị trí lúc bấm, không gửi luồng GPS. Quy tắc FR8 của `specs/014-live-gps` (không gửi luồng vị trí lên server) vẫn giữ cho bản đồ.
- Không có quyền vị trí, tắt định vị, hoặc chờ quá vài giây mà chưa có vị trí: bỏ hẳn trường này. Server làm như cũ (điểm vừa đi xong, rồi khách sạn).
- Khóa trường lạ: chỉ `lat`, `lon`, `accuracy_m`. Sai kiểu hoặc ngoài khoảng trả 422.
- Thử lại sau lỗi mạng: gửi lại **đúng body cũ**, cùng `current_location`, không đọc GPS lần nữa. Nếu vị trí đổi mà khóa giữ nguyên thì nhận 409 `IDEMPOTENCY_CONFLICT`. Mỗi lần bấm mới vẫn dùng khóa mới (`specs/023-replan-remaining`).

## Server làm gì với vị trí

- Làm tròn 4 chữ số thập phân (~11 m) rồi lưu cùng yêu cầu replan: `remaining_context.current_location`, kèm `current_location_date` là ngày (giờ Đà Nẵng) lúc bấm.
- Chỉ dùng vị trí cho ngày đang diễn ra. Nếu phần còn lại bắt đầu từ ngày sau (bấm khi còn dưới 60 phút trước `day_end`) hoặc là cả chuyến (bấm trước chuyến), ngày đó vẫn bắt đầu từ khách sạn.
- Chuyến 2 ngày, replan giữa ngày 1: ngày 1 bắt đầu từ vị trí GPS, ngày 2 vẫn từ khách sạn lúc `day_start`.

## Response

Mỗi phương án (`alternatives[].plan`) có thêm `gps_origin` khi app gửi vị trí. `anchor_*` là địa điểm có dữ liệu gần nhất (để hiển thị); chặng đầu có thể đi qua một trong 3 địa điểm gần nhất.

Dùng được (vị trí ở ví dụ trên, cách Sala Danang Beach Hotel 390 m):

```json
"gps_origin": {
  "used": true, "lat": 16.06025, "lon": 108.24216,
  "origin_id": "@gps:16.06025,108.24216",
  "anchor_poi_id": "ChIJd1ac6eUXQjERQdIGPn3xFwI", "anchor_name": "NHÀN CAFE - 302 Hồ Nghinh",
  "anchor_m": 206, "access_min": 0.5, "estimate": true
}
```

Không dùng được (máy đang ở Hà Nội; điểm dự phòng là khách sạn):

```json
"gps_origin": {
  "used": false, "lat": 21.0285, "lon": 105.8542,
  "origin_id": "ChIJMeyhoXgXQjERqCs6CuNR5yI",
  "reason": "khong dung vi tri GPS: ngoai vung Da Nang, cach dia diem co du lieu gan nhat 580.6 km (toi da 3 km); bat dau tu 'Sala Danang Beach Hotel'"
}
```

- `segments` đầu của ngày có `from_id` bằng `origin_id`. Chặng từ GPS có `source: "gps_estimate"`, các chặng khác vẫn là `"cache"`.
- `from_id` bắt đầu bằng `@gps:` **không phải** `poi_id`: đừng tra catalog với id này. Hãy vẽ chặng đầu từ chấm vị trí của máy.
- Gợi ý hiển thị: "Xuất phát từ vị trí của bạn (gần {anchor_name}, {anchor_m} m)". Khi `used = false`, hiện dòng cảnh báo tương ứng trong `warnings`.

`POST /v1/itinerary` (planner trực tiếp) nhận cùng dữ liệu qua `trip.origin` hoặc `trip.resume.origin`:

```json
"origin": {"lat": 16.06025, "lon": 108.24216, "accuracy_m": 12, "fallback_poi_id": "ChIJMeyhoXgXQjERqCs6CuNR5yI"}
```

Có `poi_id` thì vẫn là địa điểm như trước (`lat`/`lon` chỉ để hiển thị). Xem `specs/001-travel-agent-mvp/contracts/api.md`.

## Độ chính xác

Số liệu đo ngày 26/11/2026 trên danang-v2, bằng `python BE/tools/gps_origin_error.py`. Với đường phố ngẫu nhiên, công cụ cần một OSRM đang chạy (`--osrm`) và tệp đường OSM (`--roads`).

| Tình huống | Lệch trung bình | 90% chặng lệch tối đa | Ước ngắn hơn thật quá 3 phút |
|---|---|---|---|
| GPS cách khách sạn 5–50 m | 0,01 phút | 0 | 0% |
| Điểm ngẫu nhiên trên đường nội thành (150 điểm) | 1,0 | 3 | 1,6% |
| … cách địa điểm có dữ liệu 0,5–1 km | 1,2 | 3 | 1,6% |
| … 1–2 km (có cảnh báo) | 2,0 | 5 | 7,0% |
| … 2–3 km (có cảnh báo) | 2,4 | 6 | 4,6% |

Lúc chọn cách làm (cùng cách lấy điểm, một mẫu 150 điểm nội thành khác): chỉ dùng đường chim bay thì lệch trung bình 2,1 phút và 7% chặng ước thiếu quá 3 phút; neo vào 1 địa điểm thì lệch 1,9 phút. Đường phố nội thành: 50% nằm trong 0,5 km, 71% trong 1 km, 93% trong 3 km quanh một địa điểm có dữ liệu. "Thật" ở đây là OSRM; bản thân ma trận OSRM lệch khoảng 7,8% so với VietMap (`specs/001-travel-agent-mvp/research.md`, R4).

## Việc cho Flutter (chưa làm)

- [ ] `HttpPlanningRepository.replan`: thêm `current_location` từ một lần `getCurrentPosition` (timeout ngắn), kèm `accuracy`. Không có vị trí thì bỏ trường.
- [ ] `AppState.requestReplan`: giữ body (cả `current_location`) cho các lần thử lại của cùng một lần bấm.
- [ ] Hiện `gps_origin` (dòng "Xuất phát từ vị trí của bạn…") và cảnh báo khi `used = false`; vẽ chặng đầu từ chấm vị trí.

## Kiểm chứng

Test:
- `BE/tests/unit/test_gps_origin.py`: định vị, hàng ma trận của điểm GPS, router, lập lịch thật trên ma trận nhỏ.
- `BE/tests/unit/test_replan_window.py`: `current_location` trong `_trip_request`, ngày của vị trí, `ReplanBody`.
- `BE/tests/contract/test_gps_origin_api.py`: `POST /v1/itinerary` với GPS.
- `BE/tests/contract/test_planning_lifecycle_api.py`: replan qua service trên SQLite.
- `BE/tests/integration/test_stable_planner_lifecycle.py`: replan thật từ vị trí GPS, qua đủ 5 nhóm gate.

Audit (`BE/tools/audit_plans.py --origin …`, rồi so bằng `BE/tools/compare_plan_runs.py`): 59 kịch bản × 3 profile = 201 lịch, trên danang-v2, thời tiết offline, so với cùng các kịch bản xuất phát từ Sala Danang Beach Hotel (`poi_id`):

| Xuất phát | Giống hệt (điểm và giờ) | Cùng tập điểm | Jaccard TB | Điểm đầu ngày dời | Phút đi lại/lịch | Qua gate |
|---|---|---|---|---|---|---|
| GPS cách Sala 10 m | 201/201 | 201/201 | 1,00 | 0 phút | như nhau | 201/201 |
| GPS cách Sala 390 m (cách địa điểm gần nhất 206 m) | 81/201 | 141/201 | 0,89 | trung vị 0, 90% ≤ 4 phút | −0,2 | 201/201 |
| Tour mở (không gửi điểm xuất phát), để so | 20/201 | 73/201 | 0,68 | trung bình 16,8 phút | −15,4 (không tính chặng từ khách sạn) | 201/201 |

Ở lượt GPS 390 m, 11 lịch có điểm đầu ngày dời quá 30 phút. Các lịch này vẫn giữ nguyên điểm, thứ tự và chặng đầu, chỉ đổi giờ bắt đầu: ngày `savings` nhiều giờ trống nên solver xếp sớm hay muộn đều cho điểm như nhau. Thời gian phản hồi (5 kịch bản × 2 lần): trung vị 6,4 s khi xuất phát từ khách sạn, 5,0 s khi xuất phát từ GPS.

Bộ test BE trên nhánh này: 1569 qua. 19 hỏng và 11 lỗi đều thuộc nhóm môi trường đã biết (Google OAuth, các test cần PostgreSQL, 2 test kiến trúc Flutter), cùng danh sách với `origin/main` `707f084`.
