# Replan phần còn lại của chuyến

Khi đang đi, khách bấm "lập lại phần còn lại". `POST /v1/trips/{trip_id}/replans` giữ những gì đã đi và chỉ lập phần còn lại: từ ngày và giờ hiện tại, từ điểm vừa đi xong, với đúng các ràng buộc đã xác nhận cho phiên bản đang dùng.

Trên main `e3d1993`, app chỉ gửi `source_version_id` và `target_count` (`FE/lib/features/planning/data/planning_repository.dart`, hàm `replan`), nên:

1. Thiếu `remaining_from` thì lịch bắt đầu lại từ `day_start`: replan lúc 14:00 vẫn xếp từ 08:00.
2. Thiếu `changed_constraints` thì mất `must_visit`, `avoid`, `activities`, `food_preferences`, `areas` và ngân sách đã xác nhận qua AI. Chỉ khách sạn còn lại, vì nó lưu trong `preference_overrides.base_poi_id` của chuyến.
3. Planner luôn nhận `date = start_date` và đủ số ngày, nên replan ở ngày 2 lập lại cả ngày 1.

## Hợp đồng cho app

Phần Flutter do Hùng làm. Server đã chạy đúng với app cũ: thiếu trường nào thì server tự điền như cột cuối.

| Trường | App nên gửi | Server làm gì khi thiếu |
|---|---|---|
| `source_version_id` | phiên bản đang dùng | bắt buộc |
| `remaining_from` | giờ thiết bị lúc bấm, ISO 8601 đủ ngày giờ. Nên có múi giờ, ví dụ `"2026-11-24T14:05:00+07:00"` hoặc `DateTime.now().toUtc().toIso8601String()`; không có múi giờ thì server hiểu là giờ Đà Nẵng. | giờ server theo Asia/Ho_Chi_Minh |
| `completed_activity_ids`, `skipped_activity_ids` | có thể bỏ | đọc `progress_state` của các hoạt động trong chuyến |
| `changed_constraints` | chỉ những gì khách vừa đổi | dùng lại ràng buộc của phiên bản nguồn |
| `unavailable_poi_ids` | điểm vừa biết là đóng cửa | rỗng |

Ví dụ:

```json
{
  "source_version_id": "8f1c…",
  "remaining_from": "2026-11-24T14:05:00+07:00",
  "changed_constraints": {"areas": ["hoi_an"]},
  "target_count": 5
}
```

**`Idempotency-Key`: mỗi lần bấm dùng một khóa mới.** Chỉ dùng lại khóa, với đúng body cũ (cùng `remaining_from`), khi thử lại chính lần bấm đó sau lỗi mạng. Hiện app giữ khóa theo `source.id:trip.version` (`app_state.dart`, `_replanKeys`). Nếu app gửi thêm `remaining_from` mà vẫn đặt khóa như vậy, lần bấm thứ hai sẽ nhận 409 `IDEMPOTENCY_CONFLICT`. Còn nếu không gửi `remaining_from`, lần bấm thứ hai sẽ nhận lại kết quả cũ, lập từ giờ của lần bấm đầu.

### `changed_constraints`

Server lấy `constraint_overrides` của planning request đã tạo phiên bản nguồn (bản sao nằm trong `request_payload` của phiên bản) rồi ghi đè từng khóa có trong `changed_constraints`:

- Khóa có gửi thì thay hẳn giá trị cũ. Danh sách không cộng dồn: muốn thêm một điểm vào `must_visit` thì gửi cả danh sách mới.
- `[]` làm rỗng một danh sách. `null` bỏ một ràng buộc có thể bỏ (`areas`, `base_poi_id`, `indicative_budget`, `day_start`, `day_end`…), khi đó chuyến dùng lại giá trị của chính nó.
- Khóa không gửi thì giữ như khách đã xác nhận trước đó.
- Kết quả gộp được kiểm như `constraint_overrides`: khóa lạ hoặc giá trị sai trả 422.

Điểm đã đi, đã bỏ qua hoặc đóng cửa vẫn vào `avoid`, và được bỏ khỏi `must_visit`: điểm bắt buộc đã đi rồi thì không còn bắt buộc.

### Phần nào của chuyến được lập (`window`)

Server đọc `remaining_from` (hoặc giờ server) theo giờ Đà Nẵng:

- Rơi vào một ngày của chuyến: lập ngày đó từ giờ ấy (không sớm hơn `day_start`) cùng các ngày sau.
- Còn dưới 60 phút trước `day_end`: chuyển sang ngày sau, từ `day_start`. Nếu đó là ngày cuối thì không còn gì để lập: 409 `REPLAN_WINDOW_CLOSED`.
- Trước chuyến hoặc sau chuyến: lập cả chuyến từ `day_start` như một lần lập lịch mới.
- Chỉ có giờ, không có ngày (`"14:05"`): hiểu là hôm nay theo giờ server.

Ngày bắt đầu lại tính từ điểm vừa đi xong **trong ngày đó**. Điểm của hôm trước không tính (khách đã về khách sạn ngủ), nên ngày bắt đầu từ khách sạn, hoặc không có điểm xuất phát nếu chuyến không chọn khách sạn.

Với chuyến 2 ngày, khi replan giữa ngày 1, ngày 1 bắt đầu từ bây giờ và từ điểm vừa đi, còn ngày 2 vẫn từ `day_start` và từ khách sạn. Planner nhận việc này qua trường `TripRequest.resume` (xem `specs/001-travel-agent-mvp/contracts/api.md`).

Response có thêm `remaining_context.window = {day, date, days, start_time}` (ví dụ `{"day": 1, "date": "2026-11-24", "days": 2, "start_time": "14:05"}`), và `plan.window` giống vậy trong từng phương án. App có thể hiện dòng "Lập lại từ 14:05, ngày 1".

Lỗi mới:

| Mã | HTTP | Khi nào | App nên hiện |
|---|---|---|---|
| `REPLAN_WINDOW_CLOSED` | 409 | đã quá giờ (còn dưới 60 phút) của ngày cuối | `message` của server |
| `VALIDATION_ERROR` | 422 | `remaining_from` không đọc được | lỗi nội bộ của app (giờ thiết bị sai định dạng) |

Thử lại đúng khóa cũ luôn nhận lại request đã lưu, kể cả khi lúc thử lại đã hết giờ.

## Việc cho Flutter (chưa làm)

- [ ] `HttpPlanningRepository.replan`: gửi `remaining_from` là giờ thiết bị lúc bấm.
- [ ] `AppState.requestReplan`: tạo khóa mới cho mỗi lần bấm, giữ khóa và body cho các lần thử lại của lần bấm đó.
- [ ] Gửi `changed_constraints` khi khách đổi ràng buộc trước khi replan (ví dụ qua AI). Không cần gửi lại ràng buộc cũ.
- [ ] Hiện `window` của kết quả và thông báo của `REPLAN_WINDOW_CLOSED`.

## Kiểm chứng

- Test đơn vị không cần PostgreSQL: `BE/tests/unit/test_replan_window.py` (đọc giờ, chọn ngày, `_trip_request`, gộp ràng buộc, `resume` trong planner và gate), `BE/tests/contract/test_planning_lifecycle_api.py` (luồng replan qua service trên SQLite với đồng hồ cố định).
- Chạy thử solver thật trên danang-v2 (thời tiết offline), chuyến 2 ngày 10–11/11, 08:00–20:00, ở Sala Danang Beach Hotel, đã đi xong điểm đầu của ngày 1. Cùng kịch bản chạy trên bản sao của main `e3d1993` và trên nhánh này:

  | Replan | main `e3d1993` | Nhánh này |
  |---|---|---|
  | 14:05 ngày 1 | 3 phương án, ngày 1 bắt đầu lại 08:02–08:16 | 3 phương án qua đủ 5 nhóm gate; ngày 1 bắt đầu 14:06–14:51 từ điểm vừa đi, ngày 2 bắt đầu 08:08–08:15 từ khách sạn |
  | 09:15 ngày 2 | 2 phương án cho cả 2 ngày, ngày 1 bắt đầu 08:02 | 2 phương án chỉ cho ngày 2, bắt đầu 09:18 |

- Lập lịch mới (không phải replan) cho kết quả giống hệt main: 4 yêu cầu mẫu (1 và 2 ngày, có và không có khách sạn, có `areas`) × 3 profile, so từng điểm và từng giờ.
