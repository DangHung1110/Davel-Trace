# 16 — Khí hậu, thời tiết, di chuyển theo khung giờ, u(t) cho cả 1000 POI (thử trước kiến trúc)

Ngày: 2026-11-20, chạy lại 21/11 trên data cuối · Script: `BE/tools/context_sufficiency.py` · Số liệu thô: `16_context_sufficiency.json`

## Dữ liệu đã thêm

| Phần | File | Nguồn | Mức tin cậy |
|---|---|---|---|
| Khí hậu: 6 vùng × 12 tháng × 24 giờ (nhiệt độ, cảm giác nhiệt, p90, xác suất mưa, lượng mưa, độ ẩm, gió) và xác suất ngày mưa theo tháng | `BE/data/priors/climate.json`, `BE/app/services/climate.py`, `BE/tools/build_climate.py` | Open-Meteo, tái phân tích ERA5 2016–2025, CC BY 4.0 | **Số đo** |
| Hệ số di chuyển theo khung giờ: 6 vùng × 7 khung | `BE/data/priors/travel_time_factors.json`, `BE/app/services/travel_time.py` | Không có nguồn kẹt xe mở | **Ước lượng, gắn cờ** |
| u(t) cho khách sạn: dạng `lodging_rest` (về phòng nghỉ trưa, buổi tối) | `time_profiles.json` | Thiết kế | Ước lượng |
| Mức phơi nắng/mưa cho 258 POI thêm từ OSM/nhập tay (trước đây trống) | `v2_rules.exposure_prior`; `tags.exposure_source = category_prior` | Giá trị phổ biến nhất của các POI đã có nhãn, cùng không gian và loại | Ước lượng |

Độ phủ hiện tại:
- **1000/1000 POI** có `time_profile` khớp một đường cong.
- **1000/1000 POI** có `rain_cover` và `sun_exposure`.
- Mọi vùng đều có dữ liệu khí hậu và hệ số di chuyển.

Kiểm tra khí hậu với thực tế:
- Tháng 6 lúc 13h ở trung tâm, cảm giác nhiệt 38,9°C; tháng 1 là 25,5°C.
- Tỉ lệ ngày mưa: tháng 10 là 0,55, tháng 11 là 0,49, tháng 4 là 0,07.
- Bà Nà (867 m) mát hơn trung tâm khoảng 7°C.

`climate.as_forecast()` trả về cùng dạng với `weather.fetch_forecast`, nên `trip_ctx` đọc được ngay khi chuyến đi nằm ngoài tầm dự báo.

## E1 — Khí hậu (30 câu mẫu, CP-SAT hiện tại)

- **U:** chỉ dùng u(t).
- **UW:** u(t) × w(thời tiết), với w = 1 − 0,6·phơi_nắng·nóng − 0,8·ngoài_trời·P(mưa). Đây là công thức thử nghiệm; công thức cuối thuộc kiến trúc.

| | Tháng 6, U | Tháng 6, UW | Tháng 11, U | Tháng 11, UW |
|---|---|---|---|---|
| Câu có lịch | 30 | 30 | 30 | 30 |
| Số điểm | 175 | 167 (−5%) | 167 | 170 |
| Điểm phơi nắng gắt (cảm giác ≥ 36°C và phơi nắng ≥ 0,7) | 39 | **15 (−62%)** | 0 | 0 |
| Điểm ngoài trời giờ hay mưa (P ≥ 0,2) | 1 | 1 | 62 | 57 (−8%) |

**Đọc kết quả:**
- **Nóng:** khí hậu đủ dùng. Nắng gắt theo giờ có quy luật, nên lịch dời điểm ngoài trời ra khỏi buổi trưa và giảm được gần 2/3 số điểm phơi nắng gắt.
- **Mưa:** khí hậu chỉ cho tỉ lệ nền. Tháng 11, P(mưa) khoảng 0,25 gần như đều cả ngày, nên dời giờ không tránh được mưa; chỉ giảm được 8%.
  - Muốn tránh mưa phải biết **hôm nào** mưa. Việc đó cần dự báo thật: dịch vụ `weather.fetch_forecast` đã có, tầm khoảng 16 ngày.
  - Khí hậu dùng cho chuyến xa hơn tầm dự báo và làm giá trị mặc định. Hành vi này đúng: không nên loại hết biển chỉ vì tháng 11 trung bình hay mưa.
  - Việc cho kiến trúc: khi gần ngày đi, ưu tiên dự báo, và cho phép xếp lại lịch.

## E2 — Di chuyển theo khung giờ

- **R:** lấy 30 lịch xếp trên ma trận thông thoáng (OSRM), chạy lại với hệ số kẹt xe.
  - Kết quả: **0/30 lịch bị phá**, độ trễ trung bình 0 phút.
  - Lý do: mỗi chặng có sẵn 12 phút đệm (`STOP_OVERHEAD_MIN`), mà các chặng trong lịch ngắn, nên đệm hấp thụ được hệ số tới ×1,4.
- **T:** xếp lại trên ma trận nhân hệ số xấu nhất trong khung giờ chuyến đi.
  - Kết quả: 30/30 câu có lịch nhưng **160 điểm so với 175 (−9%)**.
  - Cách bi quan này mất nhiều điểm mà không đổi lại gì, vì R đã cho thấy lịch thông thoáng vẫn giữ được.

**Kết luận E2:**
- Giữ ma trận thông thoáng cộng phần đệm cho bộ giải.
- Dùng hệ số khung giờ để kiểm tra lịch và hiển thị giờ đến dự kiến.
- **Không cần** đưa cung thời gian phụ thuộc giờ vào lõi bộ giải lúc này.
- Sau pilot: nếu log cho thấy trễ thật (đặc biệt chuyến liên vùng giờ cao điểm), chỉnh lại hệ số hoặc phần đệm.

## Kết luận chung

Dữ liệu khí hậu, thời tiết, di chuyển theo khung giờ và u(t) **đủ để chốt kiến trúc**. Không phần nào cần đường lui bỏ.

**Quyết định cho kiến trúc:**
1. Nóng: u(t) × w(khí hậu theo tháng).
2. Mưa: ưu tiên dự báo thật khi trong tầm; khí hậu làm giá trị mặc định; cho phép xếp lại.
3. Di chuyển: ma trận thông thoáng cộng đệm; hệ số khung giờ dùng để kiểm tra và hiển thị giờ đến dự kiến.
4. Tránh đếm trùng: đường cong của biển và điểm ngắm cảnh đã ngầm tính nắng trưa, nên khi ghép với w cần chỉnh lại trọng số.
5. Hiệu chỉnh hệ số kẹt xe, mức phơi nắng/mưa ước lượng và u(t) bằng log pilot.
