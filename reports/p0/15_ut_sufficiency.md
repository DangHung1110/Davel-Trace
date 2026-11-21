# 15 — u(t) có đủ để làm kiến trúc không? (thử nghiệm trước kiến trúc)

> **Chạy lại 21/11 trên platform `main`**: ma trận **xe máy** (`dense-v1`, 1008 POI), planner của `main`, `STATE_WEIGHT` = 1,0 cho thử nghiệm; data trước lần loại 26 điểm.
>
> | | A (không u) | B (có u) |
> |---|---|---|
> | Câu có lịch | 28/30 | 29/30 |
> | Σ prize·ū | 94,3 | **112,8 (+20%)** |
> | ū trung bình | 0,70 | **0,87** |
> | Điểm đi vào giờ xấu (ū < 0,5) | 39 | **2 (−95%)** |
> | Tổng số điểm | 157 | 149 (−5%) |
>
> Câu không có lịch: q25 (cả A lẫn B) và q05 (chỉ A). Lý do: bộ giải hết giờ trước khi tìm được nghiệm, vì chặng xe máy dài hơn. 28/30 lần giải vẫn dừng vì hết giờ. Kết luận giữ nguyên: u(t) đủ dùng; ngân sách bộ giải và warm start là việc của kiến trúc. Phần dưới đây là số đo 20–21/11 trên ma trận ô tô.

Ngày: 2026-11-20, chạy lại 21/11 trên data cuối · Script: `BE/tools/ut_sufficiency.py` · Số liệu thô: `15_ut_sufficiency.json`
Ngày mô phỏng: 15/6/2026 (mùa cao điểm). Không gọi mạng.

## 1. Độ phủ

- 862/862 POI active (không gồm lưu trú) có `time_profile` khớp `time_profiles.json`. Thiếu: 0.
- 0 POI mà giờ mở cửa không chứa nổi một thời điểm tốt (max ū ≥ 0.6).
- 238 POI có u gần như phẳng trong giờ mở (biên độ < 0.2): bảo tàng, khu vui chơi có vé, phần lớn bar
  và một nửa nhà hàng. Đây là **thiết kế**: các nơi này không có giờ đẹp riêng, nên `u(t)` không đẩy chúng.

| Loại | n | Biên độ u trung vị trong giờ mở |
|---|---|---|
| beach | 22 | 0.78 |
| outdoor_landmark | 58 | 0.67 |
| viewpoint | 12 | 0.52 |
| day_market | 45 | 0.42 |
| wellness / night_market / religious / cafe / restaurant | | 0.29 – 0.38 |
| museum_indoor / nightlife / paid_attraction | | 0.00 – 0.11 (phẳng) |

## 2. Chạy thật với CP-SAT hiện tại (30 câu mẫu gold_v2)

Cùng ứng viên (tối đa 25 + điểm bắt buộc), prize = `prize_prior`.

- **A:** không có `u(t)`.
- **B:** `u(t)` cắm vào hook `state_bands/state_score` có sẵn, chia băng 30 phút, `state_weight = 1`.

Chấm cả hai theo hàm mục tiêu thật Σ prize·ū.

| | A (không u) | B (có u) |
|---|---|---|
| Câu có lịch | 30/30 | 30/30 |
| Σ prize·ū | 107.2 | **124.1 (+16%)** |
| ū trung bình mỗi điểm | 0.67 | **0.82** |
| Điểm đi vào giờ xấu (ū < 0.5) | 46 | **19 (−59%)** |
| Tổng số điểm | 184 | 175 (−5%) |
| Thời gian giải tối đa | 15.4 s | 10.1 s |

Các lần giải dừng theo thời gian thực, nên số có thể dao động ±2% giữa các lần chạy.

- Lần chạy 21/11: 3/30 câu B thấp hơn A (q07, q09, q17). Lần chạy 20/11 (4 câu q07, q09, q11, q29) đã thử: Khi cho bộ giải 30 đơn vị công thay vì 5:
  - q09, q11, q29: B vượt A;
  - q07: còn thấp hơn 8%.
- Vậy nguyên nhân là **ngân sách thời gian giải**, không phải `u(t)`: 28/30 lần giải ở cả A lẫn B đều dừng vì hết giờ.
- 19 điểm giờ xấu còn lại phần lớn là chợ ban ngày lúc 13–14h và điểm ngắm cảnh lúc 11h. Khi tăng trọng số `u` thì số này giảm; việc chỉnh trọng số thuộc phần kiến trúc.

## 3. Lỗi bộ mẫu tìm thấy và đã sửa

- **Lỗi:** `gold_v2` cũ có 7/30 câu vô nghiệm. Dựng lại thì thành 15/30, đúng tất cả các câu có điểm bắt buộc.
- **Nguyên nhân:**
  1. `queries.py` bốc ngẫu nhiên 2 điểm bắt buộc mà không xét giờ mở.
  2. Chuỗi Approach-B nhặt các điểm gần trước cho tới khi hết giờ, đẩy điểm bắt buộc ra ngoài giờ. Với 862 điểm đủ điều kiện thì lỗi xảy ra gần như chắc chắn.
- **Sửa:**
  1. `build_queries(..., fits=)` bốc lại cặp điểm cho tới khi xếp được trong khung giờ.
  2. `chain_order` bỏ qua điểm tự chọn nếu nó làm điểm bắt buộc còn lại không xếp được (`_musts_fit_after`).
- **Kết quả:** v2 có 30/30 câu dựng được lịch. Sau lần sửa thứ hai (21/11: điểm tự chọn không được chiếm suất cap/ngân sách của điểm bắt buộc) và data cuối: v2 qua gate 29/30, v1 27/30.
  - Câu còn rớt là q25: 2 điểm bắt buộc (Cầu An Hội, Rừng Dừa) cùng nhóm `attraction` mà luật cứng chỉ cho 1/ngày. Câu rớt là đúng.

## Kết luận

`u(t)` **đủ** để đưa vào kiến trúc:
- phủ 100%;
- không mâu thuẫn với giờ mở cửa;
- tăng 16% hàm mục tiêu và giảm một nửa số điểm đi vào giờ xấu;
- không làm mất lịch, không chậm hơn.

Không cần đường lui bỏ `u(t)`.

**Việc cho kiến trúc:**
1. Ngân sách hoặc warm start của bộ giải: gợi ý tham lam hiện chưa biết tới `u`.
2. Chỉnh `state_weight`.
3. Hiệu chỉnh các điểm neo của profile bằng log sau pilot.
