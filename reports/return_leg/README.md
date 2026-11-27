# Chặng về khách sạn (27/11/2026)

Một ngày bắt đầu ở khách sạn giờ phải trả cho cả chặng về. Đo trên 201 lịch từ Sala Danang Beach Hotel: điểm cuối cách khách sạn trung vị 10 → 6 phút, tổng phút ngồi xe (tính cả chặng về) giảm 2,5 phút/ngày, gate và mong muốn giữ nguyên. Cái giá: request có khách sạn chậm hơn, trung vị 4,4 → 7,0 giây trên `main` (3,5 → 5,0 giây nếu merge cùng `fix/v1-latency-p95`, p95 khi đó vẫn dưới 8 giây). Lịch không có khách sạn không đổi.

## Lỗi là gì

Hàm mục tiêu v1 trừ điểm cho mỗi phút chạy xe (T9), đọc số phút từ bảng `travel`. Khi ngày bắt đầu ở khách sạn, `profiles.build_plan` chỉ đưa vào bảng chặng đi (khách sạn → từng điểm). Chặng về (điểm cuối → khách sạn) không có trong bảng nên được tính 0 phút. Với solver, kết thúc ngày cách khách sạn 50 phút cũng "miễn phí" như kết thúc ngay cạnh khách sạn.

**Ví dụ thật** (kịch bản `W20-vegan`: cặp đôi muốn ăn chay, 08:00–20:00, profile tiết kiệm, ở Sala trên bãi Mỹ Khê):

- **Trước:** An Thượng → biển Non Nước → chùa Non Nước → Hoa Sen Bánh Mì Chay → Bảo tàng Hội An → Cơm chay Thiện Tâm → Nghé Coffee Hội An (18:49–20:00). App báo "đi 62 phút". Nhưng từ Hội An về khách sạn còn 48 phút (24 km), về tới nơi 20:48. Thật ra ngồi xe 110 phút; 48 phút cuối solver coi như không có.
- **Sau:** Công viên Sao Biển → biển Mỹ Khê → chùa Bát Nhã → nhà hàng chay Shanti → Làng Bích họa → Cầu Rồng → Mỳ Quảng Cô Sáu (18:04–19:04). Đi 24 phút, về 5 phút, tới khách sạn 19:09. Vẫn 7 điểm, vẫn có bữa chay.

## Sửa gì

- `matrix.legs_to`: đọc cột của khách sạn trong ma trận (từng điểm → khách sạn).
- `profiles.build_plan`: khi điểm xuất phát là nơi lưu trú (`role: "base"`, 76 khách sạn trong danang-v2), thêm các chặng về vào `travel`.
- Mô hình CP-SAT (cung "điểm cuối → depot") và `objective.features` vốn đã đọc chặng (điểm cuối, khách sạn); chỉ thiếu số. Giờ hai bên đọc cùng một số nên J của solver bằng J tính lại từ lịch (test `TestModelAndFeaturesAgree`).
- Chặng về chỉ là chi phí: không giữ giờ cho nó, gate B3 không đổi.

Không tính chặng về khi ngày bắt đầu ở chỗ người đi không ngủ: vị trí GPS (`@gps:…`, nhánh `feat/gps-origin`: không ai quay về chỗ điện thoại đứng lúc replan), replan bắt đầu từ điểm vừa đi xong, hay một điểm tham quan được chọn làm nơi xuất phát.

## Số đo

`audit_plans.py --origin ChIJMeyhoXgXQjERqCs6CuNR5yI`: 67 kịch bản × 3 profile = 201 lịch, 222 ngày. "Trước" là bản `git archive` của `origin/main` 707f084, "sau" là nhánh này; cùng máy, snapshot danang-v2, thời tiết giả offline. Chặng về đo bằng ma trận (điểm cuối → Sala).

| Chỉ số | Trước | Sau |
|---|---|---|
| Lịch qua gate | 201/201 | 201/201 |
| Mong muốn đạt | 96/108 | 96/108 (không lịch nào mất) |
| Điểm mỗi ngày | 7,26 | 7,29 |
| Phút đi mỗi ngày như app báo (chưa gồm chặng về) | 44,4 | 45,1 |
| Chặng về, trung vị / trung bình | 10 / 22,2 phút | 6 / 19,0 phút |
| Chặng về, trung vị theo km | 4,7 km | 2,7 km |
| Ngày kết thúc cách khách sạn hơn 30 phút | 78 | 69 |
| Phút đi mỗi ngày, gồm chặng về | 66,6 | 64,1 |

Theo profile (chặng về trung bình; ngày xa hơn 30 phút; phút đi mỗi ngày gồm chặng về): savings 8,6 → 5,7; 3 → 2; 32,8 → 31,7. Balanced 10,9 → 7,8; 5 → 2; 48,3 → 47,1. Experience 47,2 → 43,4; 70 → 65; 118,9 → 113,5. Experience vẫn hay kết thúc ở Hội An: profile này thích Hội An, và ngày nào có Hội An cũng phải chạy khứ hồi, dù Hội An ở giữa hay cuối ngày. Trước đây chuyến về được miễn phí; giờ ngày Hội An đắt thêm đúng chuyến về, nên 67 → 59/74 ngày kết thúc ở Hội An.

Từng lịch (`compare_plan_runs.py`): 44/201 giống hệt, 93 cùng tập điểm, Jaccard trung bình 0,79. Chặng về ngắn hơn ở 97 lịch, như cũ ở 101, dài hơn ở 3. Tổng phút đi gồm chặng về tốt hơn ở 75 lịch, như cũ ở 103, tệ hơn ở 23. Ở 23 lịch tệ hơn, chặng về còn ngắn đi (tổng −90 phút); phần tăng (+384 phút) là một ngày khác hẳn mà lượt tìm kiếm 5 đơn vị tìm ra, ví dụ `X01-two-couple` balanced, ngày 2 thêm chuyến Hội An giữa ngày (8 điểm thay vì 7, +71 phút).

## Chặng về có phải xong trước giờ kết thúc không?

Không ràng buộc. `end_time` hiện là giờ điểm cuối kết thúc (gate ETB), không phải giờ về tới khách sạn. Ngay trước khi sửa, 124/222 ngày đã về tới khách sạn sau `end_time` (trễ trung bình 27 phút), vì điểm cuối thường là bữa tối hay du thuyền đến 20:00. Bắt chặng về phải xong trước `end_time` thì hơn nửa số ngày phải bỏ điểm tối. Sau sửa: 125/222 ngày, trễ trung bình 25 phút. Đổi nghĩa `end_time` thành "giờ về tới khách sạn" là quyết định sản phẩm.

## Độ trễ

`bench_latency.py` (7 kịch bản × 3 vòng, mọi request từ Sala, máy 12 nhân, chạy xen kẽ trước/sau):

| Từ Sala, mỗi bên 2 lượt | Trung vị | p95 |
|---|---|---|
| `main` → nhánh này | 4,40 / 4,38 → 6,97 / 7,09 s | 9,42 / 9,40 → 9,70 / 9,92 s |
| `fix/v1-latency-p95` → nhánh đó + nhánh này (merge thử) | 3,60 / 3,34 → 5,00 / 5,03 s | 6,45 / 6,31 → 5,51 / 5,68 s |
| Không khách sạn (open tour), `main` → nhánh này | 4,12 → 4,07 s | 8,92 → 8,84 s |

Nguyên nhân: mỗi request giải 3 profile song song, chậm bằng profile chậm nhất. Có chặng về, lần giải của experience không còn chứng minh được tối ưu trong ngân sách 5 đơn vị: trên `main` 7/21 lần giải chạy hết ngân sách (trước sửa 2/21), lúc dừng còn cách cận 25–39%, nên đặt ngưỡng dừng theo khoảng cách không giúp được. Ngân sách vẫn chặn trần nên p95 không tăng bao nhiêu (trên `main` +0,3–0,5 s, trên nhánh tốc độ còn giảm), nhưng trung vị tăng 1,5–2,6 s. p95 của `main` đã trượt mốc 8 s từ trước, cả khi có lẫn không có khách sạn; `fix/v1-latency-p95` đưa nó về dưới 8 s, có hay không có bản sửa này.

## Test

- `BE/tests/unit/test_return_leg.py`, 14 test: ví dụ gần/xa (trên `main` ra `far`, sau sửa ra `near`), cột ma trận dict và dense, chỉ nơi lưu trú, GPS, mô hình = features (3 ngày), chặng về sau `end_time` được phép, B3 không kiểm tra chặng về.
- Lịch không có khách sạn (open tour) không đổi: 7 kịch bản × 3 profile, 21/21 lịch giống hệt cả điểm lẫn giờ.
- Toàn bộ BE: 1531 qua, 9 bỏ qua; 19 failed + 11 error giống hệt `main` (thiếu `DATABASE_URL`/PostgreSQL, Google OAuth, 2 test ranh giới Flutter).
- Merge thử với 6 nhánh đang mở (`feat/gps-origin`, `feat/plan-features`, `feat/single-poi-value`, `fix/v1-latency-p95`, `feat/p0-coord-check-osm`, `feat/data-osrm-food-shops`): đều sạch. Trên bản merge với `feat/gps-origin`, 94 test GPS/replan qua và một ngày từ GPS không có chặng về; trên bản merge với `feat/plan-features`, test mới vẫn qua.

## Chưa làm

- **Độ trễ:** hạt giống (`_greedy_hint`) chưa biết chặng về, nên lời giải ban đầu hay kết thúc xa khách sạn. Một hạt giống biết chặng về là cách đáng thử đầu tiên; cần đo riêng.
- **App chưa hiện chặng về:** `segments` và `travel_min` vẫn dừng ở điểm cuối. Muốn hiện "về khách sạn N phút" cần sửa hợp đồng API và FE.
- **Replan một ngày từ điểm vừa đi xong:** `TripRequest` gộp `resume.origin` vào `origin`, nên planner không biết khách sạn và ngày đó không tính chặng về. Muốn tính, lifecycle phải gửi khách sạn riêng.
- Sau khi merge `feat/gps-origin`: GPS đứng ngay tại khách sạn không còn cho lịch y hệt khách sạn (khách sạn có chặng về, GPS thì không), đúng theo quy tắc trên.
- Bộ lọc xe lăn loại 1/76 khách sạn khỏi pool; nếu khách ở đúng khách sạn đó thì ngày không tính chặng về.
- Objective legacy (`DAVEL_OBJECTIVE=legacy`) không đổi và không tính chặng về.

Số liệu gọn: `summary.json`. Tính chặng về từ hai lượt audit: `scripts/return_stats.py`. Cờ `audit_plans.py --origin` và `compare_plan_runs.py` lấy từ `feat/gps-origin` (chưa có trên `main`), chỉ dùng trong bản sao để đo.
