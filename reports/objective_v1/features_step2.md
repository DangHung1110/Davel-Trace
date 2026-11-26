# Bước 2: đặc trưng của J đọc từ chính lịch (26/11/2026)

Nhánh `feat/plan-features`, cắt từ `main` 707f084. Đây là bước 2 của kế hoạch học trọng số J bằng Bradley–Terry: đặc trưng phải mô tả đúng lịch mà judge thấy, và test phải bắt được các lỗi đã review.

**Kết luận.**
- Sau khi sửa, J tính từ đặc trưng khớp J mà CP-SAT báo trên 309/309 ngày, cả trời khô lẫn trời mưa. Sai lệch lớn nhất là 0,009U, chỉ do làm tròn.
- Lịch không đổi: 201/201 lịch audit giống hệt `main`, từng điểm và từng giờ.
- Phép đo lộ ra một chỗ hở nằm ngoài phần đặc trưng: bước `_polished` tính lại giờ sau khi solver giải. Bước này làm 46% số ngày (trời khô) và 50% số ngày (trời mưa) mất J. Ngày tệ nhất mất 2,36U, có điểm ngoài trời bị dời vào giữa cơn mưa. Cần quyết cách xử lý trước pilot 40 request (bước 3).

U là điểm của POI tốt nhất trong pool của ngày đó. J trung vị của một ngày khoảng 5–8U.

## Bốn lỗi của bản cũ, đã sửa

1. **T2 trạng thái theo giờ.** `features()` nhận giá trị này từ bên ngoài. Không nơi nào có giá trị đó cho một lịch đã xong, nên nó luôn bằng 0. Giờ nó được tính từ giờ của từng điểm: dò ở 1/4 và 3/4 thời gian ở, đúng như solver (`objective.state_terms`).
2. **Phạt mưa.** Solver trừ phạt mưa trong cùng phép dò của T2; bản cũ không tính. Giờ đây là cột riêng `rain`, có trọng số `w_rain` = 1,0 trong `v1.json`. Solver đọc trọng số này (bằng 1,0 thì lịch y như cũ), nên file trọng số học được có thể đặt lại.
3. **T7 nghỉ trưa.** Bản cũ cũng nhận từ bên ngoài, nên luôn bằng 0. Giờ T7 có khi ngày có đúng một bữa trưa (quán bắt đầu 11:00–13:00, hoặc một lớp nấu ăn chồng lên khung trưa) và không điểm nào nằm trong giờ nghỉ ngay sau bữa đó (`objective.rest_taken`). Nghỉ trưa mà user bắt buộc là ràng buộc, không được thưởng.
4. **T6, phạt hai bữa dồn (A2).** Thiết kế là phạt cặp quán cách nhau dưới 2,5 giờ. Nhưng phép thử "gần" trong solver là `earlier OR later`, luôn đúng, nên **mọi cặp quán trong ngày đều bị phạt A**, kể cả bữa trưa với bữa tối. Bản cũ chỉ đếm cặp dưới 2,5 giờ. Giờ đặc trưng tách làm hai cột, cùng trọng số A như solver:
   - `meal_crowd`: cặp gần, cộng quán thừa trong một khung bữa. Lớp nấu ăn đặt chỗ được tính là bữa của mọi khung nó chồng lên.
   - `meal_far`: cặp cách nhau từ 2,5 giờ.

Với các lịch nhỏ trong `test_objective_features`, J theo bản cũ lệch J của solver 0,5–1,05U, còn bản mới khớp đúng:

| Lịch thử | J solver | J bản mới | J bản cũ |
|---|---|---|---|
| trạng thái + mưa | 1,910 | 1,910 | 2,960 |
| nghỉ trưa | 3,565 | 3,565 | 3,065 |
| bữa trưa + bữa tối | 4,030 | 4,030 | 5,030 |
| lớp nấu ăn + bữa trưa cùng khung | 2,425 | 2,425 | 3,425 |

Mỗi lịch v1 giờ mang `_features`. Khóa này không ra API công khai; lịch nhiều ngày có `_features_by_day`, mỗi ngày một mục. Gồm:
- `raw`: đọc ở giờ của solver, có `j` khớp `solver_j`.
- `shown`: đọc ở giờ lịch hiển thị.

Cặp lịch đưa judge chấm phải dùng `shown`.

## Đo trên 97 request

Bộ đo gồm 67 request audit (`BE/tools/audit_plans.py`) và 30 câu gold (`gold_v2.json`), mỗi request 3 profile, qua `POST /v1/itinerary`. Có hai lượt:
- Thời tiết offline.
- Trời mưa dựng sẵn: 90% từ 12:00 đến 17:00, các giờ khác 10%, ngày 28/11.

G-q21 không có lịch ở cả hai lượt (đã biết từ trước).

| | Trời khô | Trời mưa |
|---|---|---|
| Ngày có lịch | 309 | 309 |
| J đặc trưng ở giờ solver khớp J CP-SAT (±0,01U) | 309 | 309 |
| Ngày đổi đặc trưng khi tính lại giờ | 142 (46%) | 155 (50%) |
| Trong số đó, J giảm | 141 | 155 |
| J giảm trung bình (ngày bị đổi) | 0,30U | 0,70U |
| Ngày mất từ 0,5U | 24 | 57 |
| Ngày có điểm ngoài trời dính mưa: ở giờ solver → ở giờ hiển thị | 0 → 0 | 19 → 68 |
| Ngày có cặp quán xa (`meal_far`) | 176 | 167 |
| Ngày có nghỉ trưa (`rest`) | 202 | 207 |

Ở lượt trời khô, chỉ T2 thay đổi. Lượt trời mưa có thêm `rain` ở 55 ngày. Theo profile (trời khô), số ngày bị đổi là: savings 11/103, balanced 60/103, experience 71/103.

## Ví dụ: W09, gia đình 4 người, muốn ăn mì Quảng, lịch balanced, chiều mưa

| Điểm | Giờ solver | Giờ hiển thị |
|---|---|---|
| Bãi biển Mỹ Khê (ngoài trời) | 08:02–09:42 | 08:00–09:54 |
| Nhà thờ Chính tòa Đà Nẵng | 10:01–10:31 | 10:13–10:43 |
| Mỳ Quảng Quê Xưa | 11:31–12:31 | 11:00–12:00 |
| Bảo tàng Điêu khắc Chăm | 13:31–14:46 | 13:00–14:50 |
| Cầu Rồng (ngoài trời) | 16:55–17:15 | **15:04–15:44** |
| Chợ Cồn | 17:45–18:45 | 16:02–17:16 |
| Mì Quảng 1A | 19:00–20:00 | 17:30–19:00 |

Solver cố ý chờ để Cầu Rồng ra sau cơn mưa: hai điểm dò ở 17:00 và 17:10 đều khô. Bước tính lại giờ ép cả ngày lên sớm, đưa Cầu Rồng vào giữa giờ mưa to. J giảm từ 8,05 xuống 5,69U: mưa 0 → 2,0, trạng thái 0,62 → −0,09.

`_polished` có luật giữ khô (`kept_dry`), nhưng luật này chỉ giữ một điểm khi **cả lượt ghé** nằm ngoài giờ mưa. Cầu Rồng 16:55–17:15 lấn 5 phút vào khung mưa nên không được giữ. Hai nơi dùng hai cách hiểu "khô" khác nhau.

Cái giá của giờ solver là lỗ trống. Khách rời nhà thờ lúc 10:31, nhưng 11:31 mới ăn trưa; trừ thời gian đi lại (khoảng 17 phút, theo lịch hiển thị) thì còn khoảng 40 phút không làm gì. `_polished` sinh ra chính là để bỏ những lỗ trống như vậy.

## Còn mở, cần quyết trước pilot

1. **Tính lại giờ.**
   - Đề xuất: ở v1 hiển thị đúng giờ của solver, và đưa phút chờ vào J (một số hạng phạt thời gian rảnh). Khi đó solver tự cân giữa chờ và trạng thái, và lịch user thấy chính là lịch J chọn.
   - Cách nhẹ hơn: vẫn tính lại giờ, nhưng giữ mỗi điểm trong khung trạng thái và tình trạng mưa của nó, dùng cùng phép dò 1/4 và 3/4 như solver.
   - Nếu không sửa, cặp lịch sinh bằng hai bộ trọng số có thể bị bước tính lại giờ xóa mất chỗ khác nhau, nhất là trạng thái và mưa.
   - Cần Cường quyết.
2. **A2.** `meal_far` cho phép pilot đo xem judge có coi "bữa trưa + bữa tối" là xấu không. Trọng số học được cho `meal_far` chưa cắm được vào solver cho tới khi sửa phép thử "gần". Nhánh `fix/v1-latency-p95` viết lại A2 dạng bậc thang, vẫn giữ nghĩa "mọi cặp". Quyết định thuộc về Cường, vì trọng số bữa tối 1,2 đã được chỉnh trên hành vi này.
3. **Gợi ý lời giải ban đầu (greedy seed)** vẫn tính đủ phạt mưa, không nhân `w_rain`. Điều này chỉ ảnh hưởng khi học ra `w_rain` khác 1.
4. **Lịch trong pool** (`_pool_plans`, khi gọi với `pool_size` > 1) chưa có `_features`. Luồng 3 profile không dùng pool.

## Kiểm tra

- Test mới:
  - `BE/tests/unit/test_objective_features.py` (11 test): solver khớp đặc trưng khi có trạng thái, mưa, `w_rain` khác 1, nghỉ trưa, bữa trưa + tối và lớp nấu ăn; đặc trưng đi theo giờ hiển thị.
  - `BE/tests/integration/test_plan_features.py` (2 test trên danang-v2): lịch 1 ngày và lịch 2 ngày.
- Toàn bộ suite: 1.530 qua, 19 lỗi + 11 error. Chạy lại đúng 30 test đó trên `main` cho kết quả lỗi y hệt (Google OAuth, PostgreSQL, Flutter).
- Audit 201 lịch: giống hệt `main`.

## Chạy lại

```bash
python reports/objective_v1/scripts/features_check.py run out_dry.json
python reports/objective_v1/scripts/features_check.py run out_wet.json --wet
python reports/objective_v1/scripts/features_check.py report out_dry.json out_wet.json
```

Mỗi lượt khoảng 10 phút trên máy 12 nhân. Thời tiết được mock, nên kết quả không phụ thuộc dự báo thật.
