# Độ trễ p95 của objective v1 (26/11/2026)

`BE/tools/bench_latency.py` trên `main` 707f084 trượt gate (p95 < 8 s) chỉ vì một kịch bản: `{"activities": ["tắm biển", "hải sản"]}`, không profile, 8,8–9,0 s mỗi lần. Nhánh `fix/v1-latency-p95` sửa ba chỗ trong `BE/app/services/optimizer.py` và hạ `search_scale` 1,6 → 1,2; bench qua gate, lịch trung bình tốt hơn.

## Thời gian đi đâu

Một request = ba profile giải song song, mỗi profile một lần CP-SAT một luồng, ngân sách 5 × `search_scale` 1,6 = 8 đơn vị (~1,05 s mỗi đơn vị trên máy 12 nhân này).

| Bước (kịch bản chậm, `main`) | savings | balanced | experience |
|---|---|---|---|
| retrieval, rank, dựng mô hình | 0,6 s chung | | |
| CP-SAT chính | 8,4 s: hết 8/8 đơn vị, chưa chứng minh tối ưu | 6,7 s: tối ưu ở 6,1 đơn vị | 7,3 s: hết 8/8 |
| thang nới nguyện vọng / refill Jaccard / hậu xử lý | 0 lần / 0 s / ~0 s | | |

Lịch cuối đã có từ giây 2–4,6; phần còn lại của ngân sách là phép chứng minh tối ưu không bao giờ xong. Không riêng kịch bản này: trên 67 request của `BE/tools/audit_plans.py`, 67/222 lời giải của `main` chạy hết ngân sách (balanced 27/74, experience 28/74, savings 12/74).

## Ba nguyên nhân

**1. A2 phạt mọi cặp quán.** Điều kiện "hai quán gần nhau" viết là `earlier OR later` (t_j − t_i < 150 *hoặc* t_i − t_j < 150): luôn đúng. Ví dụ lịch savings của kịch bản chậm: trưa 12:22 ở Quán Hải Sản Thời Cổ, tối 18:18 ở Mỳ Quảng Cô Sáu, cách nhau 6 giờ, vẫn bị trừ 1U (bằng một điểm tham quan). Lỗi có từ commit đầu (2732fce, 28/10); `main` phạt 0/1/3 cặp cho 1/2/3 quán cách xa nhau (test `test_optimizer_encoding.py` chạy trên `main` xác nhận). Mỗi cặp là 5 biến bool + 4 ràng buộc thời gian (45 cặp với 10 quán), LP của CP-SAT không thấy chúng nên coi cặp nào cũng miễn phí.

**2. Mọi phép thử "bắt đầu trong khung giờ" đều ràng buộc trên giờ t.** Quán hải sản mở 11:00–13:30 và 17:30–20:30: hễ ăn là chắc chắn trúng khung trưa hoặc khung tối, nhưng mô hình vẫn hỏi "t ≥ 11:00? t < 13:00?" bằng hai ràng buộc thời gian cho từng câu hỏi (A1, bữa trưa, bữa tối, T5, giờ nguyện vọng, cafe, khung trạng thái). LP không thấy, nên coi thưởng bữa là miễn phí.

**3. Greedy hint chưa biết v1.** Lời giải mồi của tìm kiếm một luồng chấm điểm theo legacy (điểm mỗi phút + thưởng loại mới), không tính phút chạy xe; savings trả 0,045U mỗi phút nên lời giải mồi âm ở 61/74 lời giải savings của audit. Với các ngày không chứng minh được tối ưu, lời giải mồi quyết định lịch tốt tới đâu trong ngân sách: một ngày (E02-wheelchair savings) không tìm được gì hơn lời giải mồi −8653 trong cả 8 đơn vị.

Ba thứ này làm tìm kiếm hội tụ chậm; ×1,6 của 25/11 là để bù cho việc đó.

## Sửa

- A2 viết thành bậc thang trên số quán: R quán = R(R−1)/2 cặp, **giữ nguyên giá trị** (trọng số v1, như thưởng bữa tối 1,2, đã chỉnh trên hành vi này). Đổi sang đúng "cách dưới 2,5 giờ" như tài liệu là quyết định riêng.
- `_window_hits`: quán có mọi khung mở cửa nằm gọn trong hoặc ngoài khung hỏi thì "trúng khung" chính là biến chọn khung mở cửa; khung vắt qua ranh giới mới ràng buộc trên t như cũ. Test so với định nghĩa trên từng phút.
- Greedy hint dưới v1 tính giá trị một điểm như hàm mục tiêu: chặng T9/T4, lặp nhóm T3, cặp quán A2, nhịp T8, trùng món T11; thưởng bữa T5 chỉ khi bàn sẵn ngay (chờ ≤ 30 phút; không có điều kiện này, lượt greedy chờ 6 tiếng để ăn trưa).
- `search_scale` 1,6 → 1,2 (5 → 6 đơn vị).

Hai sửa đầu không đổi giá trị hàm mục tiêu của bất kỳ lịch nào; cả ba đổi đường tìm kiếm, nên ở các ngày không chứng minh được tối ưu, lịch tìm được có thể khác.

## Trước / sau

Đo trên bản `git archive` của `main` 707f084 và của nhánh, cùng máy, thời tiết offline, chạy xen kẽ (sau, trước, sau).

**`bench_latency.py --rounds 3`** (21 request một ngày):

| | trước | sau (lần 1 / lần 2) |
|---|---|---|
| p95 | 8,85 s — FAIL | 6,77 / 6,69 s — PASS |
| max | 9,04 s | 6,86 / 6,70 s |
| median | 4,13 s | 4,80 / 4,72 s |
| trung bình | 4,85 s | 4,41 s |
| "tắm biển + hải sản" | 8,84–9,04 s | 6,70–6,86 s |

Median tăng vì ba kịch bản chậm hơn 0,5–1 s (`{}`, couple + tắm biển, couple + chùa 600k): ở mỗi cái, một profile chứng minh tối ưu muộn hơn trên đường tìm kiếm mới (3,1 → 5,5 đơn vị với balanced của couple + tắm biển), lịch cùng giá trị trừ experience của `{}` (hết 6 đơn vị, −0,06%). Trên 21 lời giải của bench, tổng công việc CP-SAT giảm 27% (69,7 → 50,7 đơn vị); savings của "tắm biển + hải sản" ở 6 đơn vị kém `main` 2,6% (4653 so với 4776; ở 8 đơn vị nhánh đạt 5087, tối ưu).

**`audit_plans.py`** (67 request, 201 lịch, qua API):

| | trước | sau |
|---|---|---|
| lịch trống / trượt gate | 0 / 0 | 0 / 0 |
| lịch không cờ nào | 25 | 27 |
| nguyện vọng đạt | 96/108 | 96/108 |
| chạy xe mỗi ngày, trung bình | 30,4 phút | 28,4 phút |
| 1 ngày: median / p95 / max | 5,9 / 8,7 / 9,3 s | 4,7 / 6,5 / 6,8 s |
| 2 ngày: median / p95 | 10,4 / 18,1 s | 8,8 / 13,7 s |
| CPU mỗi request, median | 10,4 s | 7,7 s |

Lịch đổi: 77 giống hệt, 60 cùng điểm khác giờ, 64 khác điểm. Cờ: Q_LONG_LEG 25 → 21, Q_LATE_START 14 → 11, SOFT_CATEGORY_CAP 122 → 116, Q_DETOUR 3 → 1; tăng: Q_HOLE 95 → 100, Q_NO_DINNER 15 → 16, SOFT_DINNER 14 → 15.

**Giá trị hàm mục tiêu từng lời giải** (222 lời gọi `build_plan` của audit, chạy lại cùng đầu vào; hàm mục tiêu không đổi nên so trực tiếp được), so với `main` 8 đơn vị:

| | bằng | tốt hơn | kém hơn | trung bình | lệch > 5%: tốt / kém |
|---|---|---|---|---|---|
| chỉ hạ ngân sách trên `main` (5 đơn vị) | 192 | 0 | 30 | −0,6% | 0 / 5 |
| nhánh, ngân sách cũ (8 đơn vị) | 185 | 28 | 9 | +3,3% | 13 / 4 |
| **nhánh, 6 đơn vị (chốt)** | 177 | 26 | 19 | **+3,0%** | 11 / 5 |

Bốn ca kém > 5% có ở cả 6 lẫn 8 đơn vị (M05-ba-na balanced −13%, M07 experience −10%, X04 savings −7%, X05 balanced −19%): do đường tìm kiếm mới ở những ngày không chứng minh được tối ưu, không do cắt ngân sách. Ngày khó nào cũng vậy: đổi bất cứ gì trong mô hình hay lời giải mồi là kết quả xáo lại.

**Gold 30** (`eval_gold.py`, ba profile): có lịch 29/30, qua gate 29/29, bữa trưa 10/10 không đổi ở cả ba. Lịch giống hệt 25/30 (balanced), 13/30 (savings, thêm 11 cùng điểm khác giờ), 19/30 (experience). Chạy xe trung bình +0,7 / +0,3 / −0,6 phút; lặp nhóm 10 → 10 / 13 → 14 / 3 → 3; thời gian giải trung vị 2,16 → 2,21 / 2,76 → 2,40 / 5,15 → 3,99 s.

## Còn mở

- Ngữ nghĩa A2 (mọi cặp hay cách dưới 2,5 giờ) cần Cường / nhóm quyết; đổi thì chỉnh lại thưởng bữa tối.
- Lời giải mồi vẫn là lượt greedy cận thị; gợi ý tốt hơn (pointer, "bước 5" của README) là đòn bẩy lớn nhất còn lại cho các ngày khó.
