# Độ chính xác lập lịch (cập nhật 12/11/2026)

Nhánh `task/plan-accuracy`, tách từ `feat/stable-p1-p4`. Mười bước sửa theo kết quả kiểm tra 141 lịch thật. Nhánh `task/patm-retrain` huấn luyện lại mô hình PATM trên dữ liệu đã làm sạch, sửa thêm các lỗi tìm thấy khi đo, rồi đo lại toàn bộ.

Mọi số dưới đây đo bằng cùng một bộ yêu cầu, cùng quy tắc chấm, trước và sau khi sửa. Cột "Sau" chạy với mô hình PATM đã huấn luyện lại. Quy tắc chấm do máy và Claude đặt ra, chưa có người thật chấm (xem mục 10). Bộ đo: 10 yêu cầu điển hình và 30 yêu cầu gold, mỗi yêu cầu 3 lịch; 10 yêu cầu 2 ngày. Gold đo trên bộ câu hỏi cũ để so được với trước.

## Kết quả

| Chỉ số | Trước | Sau |
|---|---|---|
| Lịch không có lỗi nào, toàn bộ | 22/141 (16%) | 118/138 (86%) |
| Bộ điển hình | 0/30 | 26/30 (87%) |
| Bộ gold | 22/81 (27%) | 63/78 (81%) |
| Bộ 2 ngày | 0/30 | 29/30 (97%) |
| Có bữa tối khi lịch qua giờ tối | 7% | 100% |
| Có bữa trưa khi lịch qua giờ trưa | 81% | 100% |
| Mong muốn được đáp ứng thật | 67% | 85% |
| Báo "đạt" nhưng sai | 9/102 | 0/102 |
| Ngày có điểm xếp sai giờ | 27% | 4% (đều là điểm khách tự chọn) |
| Đường đi so với thứ tự ngắn nhất, bộ điển hình | gấp 1,41 lần | gấp 1,11 lần |
| Lịch đi vòng quá 1,5 lần, bộ điển hình | 40% | 0% |
| Đi xe mỗi ngày, bộ điển hình | 62,7 phút | 25,9 phút |
| Thời lượng khớp Google (19 điểm tra được) | 70% | 97% |
| Lượt ghé điểm sai nhóm loại | 65/884 | 0/1082 |
| Cùng yêu cầu ra cùng lịch | 4/21 | 204/204 |
| Recall@10 trong đúng nhóm loại | 46% | 61% |

Bộ 141 lịch có 9 lịch rỗng trước khi sửa. Sau khi sửa có 12 lịch rỗng: thêm 1 câu hỏi (3 lịch) không còn vừa khung giờ khi thời lượng đã đúng thực tế (mục 4). Các lịch rỗng này đều kèm cảnh báo nêu lý do.

Lỗi còn lại trong bộ gold: 12% là mong muốn không đáp ứng được (6 lịch vì nửa ngày đã kín hai điểm khách chọn, 3 lịch vì không đủ tiền), 9% là điểm khách tự chọn ở giờ không đẹp, 3% ở lâu hơn Google, 1% đi vòng do thứ tự khách yêu cầu. Ở bộ điển hình và bộ 2 ngày, lỗi còn lại chỉ là ở lâu hơn Google (5/60 lịch).

### Hiệu năng

| Chỉ số | Trước | Sau |
|---|---|---|
| Độ trễ điển hình, trung vị / p95 | 5,6 / 10,7 giây | 6,7 / 8,2 giây |
| Độ trễ 2 ngày, trung vị / lớn nhất | 10,8 / 21,7 giây | 12,8 / 13,9 giây |
| CPU mỗi yêu cầu, 1 ngày / 2 ngày | 42 / 88 giây | 18 / 35 giây |
| 12 yêu cầu cùng lúc, máy chủ thật | 6/36 lịch đạt | 36/36 lịch đạt |
| Thông lượng lớn nhất | 19 yêu cầu/phút | 24 yêu cầu/phút |
| Giả lập máy khoảng 2 nhân | 29,2 giây, 10/24 đạt | 15,2 giây, 24/24 đạt |
| Xếp lại lịch, 360 lần | 356 có lịch, 16 ms | 357 có lịch, 7 ms |
| Bộ nhớ sau phép thử tải (42 yêu cầu) | 2,76 GB | 2,12 GB |

Độ trễ trung vị tăng 1 giây để đổi lấy kết quả cố định. Đổi lại p95 giảm 2,5 giây và quá tải không còn làm hỏng lịch: máy bận thì trả chậm hơn chứ không trả lịch rỗng.

## Kiểm tra độc lập (12/11/2026)

Nhánh `task/perf-quality-fixes`. Các số ở trên do quy tắc của chính ứng dụng chấm. Lần này 67 yêu cầu thật (201 lịch) được chấm bằng bộ quy tắc viết riêng trong `BE/tools/audit_plans.py`, không gọi cổng của ứng dụng, nên lỗi mà cổng và bộ giải cùng mắc vẫn lộ ra. Bộ yêu cầu gồm 16 ngày điển hình, 28 mong muốn, 8 điểm khách nêu tên, 3 ngày có thứ, 7 chuyến 2 ngày, 5 hồ sơ có bộ lọc cứng. Quy tắc chấm và ngưỡng do Claude đặt (khoảng trống là 75 phút không làm gì, đi vòng là từ 1,5 lần đường ngắn nhất và thêm 15 phút), chưa có người thật chấm.

Chạy lại: `python BE/tools/audit_plans.py --out audit.json --plans plans.txt` (khoảng 6 phút, thời tiết tắt).

### Đánh giá tổng quát

- **Phần đúng từ trước.** Trong 201 lịch không có lịch nào sai giờ mở cửa, thiếu thời gian di chuyển, vượt ngân sách hay trùng giờ, cả trước lẫn sau khi sửa. Cùng một yêu cầu cho cùng một lịch (8 yêu cầu chạy hai lần).
- **Phần chưa đạt trước khi sửa.** 9 lịch rỗng, trong đó 6 lịch của Bà Nà Hills, điểm nổi tiếng nhất trong dữ liệu. 41 lịch có khoảng trống trên 75 phút, 14 lịch bắt đầu muộn hơn một giờ. Dự báo mưa không đổi được lịch. Mức chi tiêu, thiên hướng trong hay ngoài trời, hoạt động yêu thích và mã món ăn của trang onboarding gần như không tới được lịch. Bộ giải mất khoảng nửa ngân sách trước khi bắt đầu tìm.
- **Sau khi sửa.** Lịch không bị cờ nào tăng từ 59% lên 72%, lịch đi theo được từ 96% lên 99%, độ trễ trung vị giảm từ 7,3 xuống 6,0 giây. Bảy thay đổi được mô tả bên dưới, mỗi thay đổi có phép đo riêng.
- **Phần còn lại.** Ngày của nhóm bạn (10–11 điểm) vẫn là bài toán khó nhất. Số ngày bị tính là đi vòng tăng. Chưa có người thật chấm. Chi tiết ở cuối mục này và ở mục Giới hạn.

### Kết quả trước và sau

| Chỉ số | Trước | Sau |
|---|---|---|
| Lịch không bị cờ nào | 119/201 (59%) | 144/201 (72%) |
| Lịch đi theo được (không rỗng, không lỗi cứng) | 192/201 (96%) | 198/201 (99%) |
| Lỗi cứng: sai giờ mở cửa, không kịp di chuyển, vượt ngân sách, trùng giờ | 0 | 0 |
| Lịch rỗng | 9 | 3 |
| Mong muốn được đáp ứng | 102/108 (94%) | 105/108 (97%) |
| Khoảng trống trên 75 phút giữa hai điểm | 42 | 9 |
| Ngày bắt đầu muộn hơn 60 phút | 14 | 2 |
| Ngày đi vòng | 9 | 16 |
| Đi xe mỗi ngày, 213 ngày có ở cả hai lượt | 28,6 phút | 30,5 phút |
| Thời gian trống mỗi ngày, cùng 213 ngày | 126 phút | 111 phút |
| Lịch không có ngày đi mà chứa điểm nghỉ một ngày trong tuần (có cảnh báo) | 6 | 13 |
| Điểm lộ thiên nằm trong giờ mưa, 12 lịch mỗi kiểu mưa: cả ngày, 13–17 giờ, đến 11 giờ | 30, 14, 15 | 0, 0, 3 |
| Mức giá trung bình các điểm trả tiền khi hồ sơ chọn chi tiêu 1 và 3 (12 lịch mỗi mức) | 1,37 và 1,40 | 1,02 và 1,82 |
| Số điểm ngoài trời mỗi ngày khi `outdoor_bias` là -1, 0, +1 (12 lịch mỗi mức) | 3,0 / 3,3 / 3,1 | 2,7 / 3,3 / 6,3 |
| Điểm thuộc hoạt động yêu thích trên 9 lịch của 3 hồ sơ mẫu, so với khi bỏ trống phần yêu thích | 19 so với 18 | 25 so với 16 |
| Độ trễ 1 ngày, trung vị và p95 (`bench_latency.py`, 21 yêu cầu mỗi lượt, đo xen kẽ, 5 lượt trước và 2 lượt sau) | 7,2–7,4 và 8,0–8,2 giây | 6,0 và 6,4–6,5 giây |
| Độ trễ 2 ngày, trung vị và p95 (14 yêu cầu) | 12,5 và 14,2 giây | 9,5 và 12,3 giây |
| CPU mỗi yêu cầu, trung vị | 18,6 giây | 13,0 giây |
| Bộ test | 925 đạt | 1029 đạt |

3 lịch rỗng còn lại là yêu cầu hai chùa do khách nêu tên trong một ngày (quyết định đã có, xem Giới hạn). 3 mong muốn chưa đáp ứng là "bún": dữ liệu chưa có quán. Mục tiêu p95 dưới 8 giây trước đây hụt 0,0–0,2 giây trên máy này, nay đạt.

Trong 16 ngày bị tính là đi vòng, 11 ngày chỉ dài hơn tối đa 4 phút so với thứ tự ngắn nhất mà các quy tắc của ngày cho phép (bữa ăn đúng giờ, nghỉ trưa, khung giờ theo loại điểm): phép so với đường ngắn nhất bất kể quy tắc không đạt được ở những ngày đó. 5 ngày còn lại là đánh đổi có chủ ý của thay đổi 4: đi thêm 10–14 phút để bỏ một khoảng trống 113 phút, một lần bắt đầu muộn 77 hoặc 180 phút, hoặc để điểm khách nêu tên nằm đúng khung giờ. 11 trong 16 ngày là ngày của nhóm bạn.

Số lịch chứa điểm có ngày nghỉ tăng vì Chợ đêm Helio (nghỉ thứ 4) được chọn nhiều hơn. Các lịch đó không có ngày đi và đều kèm cảnh báo chọn ngày để kiểm tra.

### Bảy thay đổi

**1. Mong muốn không xếp được làm rỗng cả lịch.** Từ khi thang nới lỏng dừng sau hai bậc hết ngân sách tìm kiếm, một mong muốn không thể xếp ("cáp treo": Bà Nà 7 giờ) làm cả ba lịch rỗng sau 12 giây, trong khi hợp đồng nói là bỏ mong muốn đó và cảnh báo. Nay hai bậc hết ngân sách khi còn mang mong muốn thì bỏ các bậc có mong muốn và lập ngày bình thường, mong muốn được báo `unmet`.

**2. Điểm đi cả ngày không lập được.** Bà Nà Hills (73.057 đánh giá), VinWonders và Cù Lao Chàm cho lịch rỗng dù khách nêu tên hay nêu mong muốn: ngày nào cũng phải có nhà hàng trưa bắt đầu 11:00–13:00 và nghỉ sau đó, không còn chỗ cho 7 giờ ở một nơi. Nay điểm có thời lượng từ 5 giờ (`soft_rules.ALL_DAY_MIN`) chạy suốt khung 11:00–13:00 được coi là nơi ăn trưa và nghỉ tại chỗ. Bộ giải, lời giải khởi đầu, cổng `REST_FOLLOWS_LUNCH` và bước chọn thứ tự dùng chung một quy tắc; số điểm tối thiểu của ngày chỉ tính trên phần ngày còn lại. Lịch ra: Bà Nà 08:00–15:00, 48 phút về phố, cà phê, bữa tối, cầu; `template.lunch_on_site` ghi điểm đó.

**3. Dự báo mưa không tới được lịch.** Xác suất mưa chỉ vào bảng xếp hạng, mà bảng này chỉ sắp thứ tự ứng viên và ghi lý do. Mưa 90% cả ngày, cả ba lịch vẫn mở đầu ở biển hoặc công viên. Dự báo còn được đọc theo giờ mà không theo ngày: chuyến đi thứ Bảy tuần sau dùng mưa của hôm nay, và ngày thứ hai của chuyến dùng lại mưa của ngày đầu. Nay:

- `trip_ctx.rain_costs`: giờ có xác suất mưa từ 50% làm điểm ngoài trời mất điểm trong bộ giải theo mức che mưa (`smart_tags.rain_cover`). Mưa từ 80%, điểm lộ thiên mất nhiều hơn giá trị của nó, nên chỉ còn trong lịch khi khách yêu cầu hoặc lịch cần đủ số điểm. Mưa một phần ngày thì điểm dời sang giờ khô.
- Lời giải khởi đầu cũng tính chi phí này. Không có nó, bộ giải hết ngân sách khi còn kém 38% so với lịch tốt nhất.
- Lịch có một dòng trong `warnings` nêu các khung giờ mưa, các điểm ngoài trời còn nằm trong giờ mưa, và ngày dự báo đã dùng nếu chuyến không có ngày đi.
- Dự báo đọc theo `trip.date`, mỗi ngày của chuyến đọc ngày của nó (chuyến không có ngày đi thì ngày thứ hai đọc ngày kế tiếp của dự báo). Ngày ngoài tầm dự báo (quá một tuần) thì không dùng dự báo và lịch của ngày đó nói rõ.
- Yêu cầu không có hồ sơ cũng được tránh mưa; ngày khô thì lịch của nó không đổi.

Phép đo mưa dùng dự báo giả lập (4 yêu cầu, 3 lịch mỗi yêu cầu, 3 kiểu mưa), chưa đo với dự báo thật. Điểm che một phần (chùa, chợ có mái) vẫn được xếp trong mưa: 12 lượt khi mưa cả ngày, như trước.

**4. Thứ tự chỉ tính quãng đường.** Hàm mục tiêu của bộ giải không có khái niệm thời gian chết, và bước chọn thứ tự chỉ lấy đường ngắn nhất. Kết quả: ngày 08:00 mở đầu bằng bữa trưa lúc 11:00, cà phê ngay trước bữa trưa rồi 3 giờ trống sau đó, chùa khách nêu tên bị xếp 18:42 trong khi buổi sáng trống. Nay `route_order.timing_cost` cộng thêm vào quãng đường: mỗi phút chết tính 0,25 phút đi xe (bắt đầu muộn hơn 30 phút, trống hơn 30 phút giữa hai điểm, nghỉ trưa dài hơn mức nghỉ 45 phút), điểm khách nêu tên nằm ngoài khung giờ hợp lý tính 30 phút. Bước này cũng không dời điểm ngoài trời từ giờ khô vào giờ mưa. Thời gian cuối ngày sau điểm cuối không bị tính.

Trọng số 0,25 chọn từ phép đo trên 219 ngày, cùng tập điểm, chỉ đổi trọng số (đo trước thay đổi 5):

| Trọng số | Đi xe mỗi ngày | Ngày bắt đầu muộn hơn 60 phút | Khoảng trống |
|---|---|---|---|
| 0 (như cũ) | 29,6 phút | 17 | 37 |
| 0,25 | 30,7 phút | 0 | 8 |
| 0,5 | 30,9 phút | 0 | 6 |

Mức 30 phút cho điểm nêu tên: trên 21 ngày có điểm như vậy, mọi giá trị từ 15 đến 90 cho cùng kết quả (6 trong 27 điểm nêu tên nằm sai khung giờ giảm còn 1, đi thêm 2,6 phút mỗi ngày, nhiều nhất 14 phút). Bước này mất trung bình 10 ms mỗi ngày, lâu nhất 0,1 giây.

**5. Bộ giải tốn nửa ngân sách trước khi bắt đầu tìm.** Thời gian một yêu cầu nằm gần hết trong CP-SAT (6,2 trong 6,5 giây; xếp hạng, chấm cặp điểm và dựng mô hình cộng lại dưới 0,3 giây). Presolve mặc định chạy 3 vòng và probing đầy đủ, mất khoảng 3–4 trong 8 đơn vị ngân sách; ở ngân sách 4, lịch trả về thường chỉ là lời giải khởi đầu. Nay tìm kiếm theo ngân sách chạy 1 vòng presolve và probing mức 1 (`optimizer.SEARCH_PRESOLVE_ITERATIONS`, `SEARCH_PROBING_LEVEL`), và `PLAN_DETERMINISTIC_TIME` giảm từ 8 xuống 5. Bộ đo SC (`BE/eval/baselines.py`) dùng cùng ngân sách.

Đo trên 72 bài toán thật (24 yêu cầu, 3 kiểu lịch), so với giá trị tốt nhất tìm được, kể cả lượt chạy ngân sách 24. Thời gian một yêu cầu là kiểu lịch chậm nhất trong ba:

| Cài đặt | Giá trị lời giải, trung bình | Thấp nhất | Bài dưới 95% | Chứng minh tối ưu | Yêu cầu, trung vị và p95 |
|---|---|---|---|---|---|
| Mặc định, ngân sách 8 (cũ) | 98,2% | 69,2% | 5 | 11 | 6,4 và 7,8 giây |
| 1 vòng presolve, probing mức 1, ngân sách 5 (mới) | 99,3% | 88,1% | 1 | 18 | 5,7 và 6,1 giây |
| Như trên, ngân sách 6 | 99,4% | 88,1% | 1 | 19 | 6,8 và 7,5 giây |
| Như trên, ngân sách 8 | 99,6% | 95,3% | 0 | 24 | 8,3 và 11,1 giây |

Đã thử thêm 14 cài đặt (tắt probing, tắt presolve, tắt phát hiện đối xứng, mức tuyến tính hóa 0 và 2, tắt inprocessing, các tổ hợp), phần lớn trên 24 bài toán đầu. Chỉ giảm presolve còn 1 vòng, hoặc cặp được chọn cộng thêm tắt phát hiện đối xứng, để lại 1 trong 72 bài không có lịch ở ngân sách 5; cặp được chọn không để lại bài nào. Bảng này đo trước thay đổi 6 và 7.

**6. Câu trả lời SOFT của hồ sơ không tới được lịch.** Trang onboarding ghi `spending_level`, `outdoor_bias`, `activities` là "SOFT — trọng số điểm". Cả ba chỉ vào bảng xếp hạng. Trên 12 lịch, mức giá quán ăn giống nhau ở cả ba mức chi tiêu trong 10 lịch; khác biệt còn lại không theo hướng nào, vì đổi thứ tự xếp hạng chỉ làm bộ giải đi đường khác. Mã món ăn của trang (`seafood`, `local_cuisine`...) được so nguyên văn với dữ liệu tiếng Việt nên hầu như không khớp quán nào. Nay:

- `profiles.soft_lean` cộng hoặc trừ điểm cho từng điểm trong bộ giải, tính theo đơn vị điểm cao nhất như `TASTE_WEIGHT`: chi tiêu 0,15 (quán rẻ hơn hoặc đắt hơn mức thường gặp của loại đó), ngoài trời 0,15 nhân với `outdoor_bias`, hoạt động yêu thích 0,20.
- Mã hoạt động của trang (`beach`, `museum`, `nightlife`...) được đổi sang đúng mong muốn tương ứng và dùng chung bộ so khớp của mong muốn (`retrieval.poi_is_liked`). Đây là sở thích, không phải điểm bắt buộc.
- Mã món ăn được mở rộng thành các từ dữ liệu dùng (`profile_filter.FOOD_PREF_GROUPS`). "Có món chay để chọn" không tạo xung đột ẩm thực, "chỉ ăn chay" thì có.
- Hồ sơ trung tính (mức 2, 0, không chọn gì) không đổi điểm số nào: 63 trong 67 yêu cầu của bộ kiểm tra cho đúng lịch như trước thay đổi này, 4 yêu cầu còn lại là nhóm bạn và đổi do thay đổi 7.
- Lý do chọn điểm có thêm "hop muc chi tieu", "hop gu ngoai troi", "hop hoat dong ban thich".

Đo trên 4 nhóm khách, 3 kiểu lịch, rồi 3 hồ sơ mẫu của trang onboarding (cả 90 lịch đều qua cổng): chi tiêu 3 so với 1 cho điểm trả tiền đắt hơn ở 12/12 lịch (trước: 1/12); số điểm ngoài trời không bao giờ giảm khi `outdoor_bias` tăng, ở cả 12 lịch (trước: 8/12); 7 trong 9 lịch của hồ sơ mẫu có thêm điểm thuộc hoạt động yêu thích, không lịch nào ít đi. Ba trọng số do Claude chọn theo phép đo này, chưa có người chấm.

**7. Lời giải khởi đầu không hợp lệ.** Bộ giải xuất phát từ một lịch dựng nhanh. Lịch đó không biết hai quy tắc của mô hình: nhóm bạn phải có một điểm kết thúc sau 20:00, và hai quán cà phê phải nằm ở hai buổi (trước 11:00 và sau 13:00). Khi lịch dựng nhanh bị từ chối, bộ giải phải tự tìm lịch đầu tiên, và với ngày 11 điểm thì có lúc không kịp: 3 trong 9 lượt giải như vậy không ra lịch nào, khách nhận lịch rỗng. Lỗi lộ ra khi thử thay đổi 6 với hồ sơ nhóm bạn. Nay:

- Lịch dựng nhanh dời điểm cuối cho kết thúc muộn; nếu không được thì dựng lại, giữ trước một điểm buổi tối (giữ cả loại điểm và tiền cho nó).
- Quán cà phê đầu nằm trong 11:00–13:00 thì không xếp quán thứ hai.
- Nếu lịch dựng nhanh vẫn bị từ chối và bộ giải không tìm được gì, bộ giải chạy lại một lần, bắt đầu bằng việc sửa lịch đó (`optimizer._repair_hint`). Tắt hai sửa đổi trên để thử riêng lớp này: 9/9 lượt giải có lịch, so với 7/9.

Sau khi sửa: 23/23 lượt giải của nhóm bạn có lịch dựng nhanh hợp lệ (trước 14/23), 71/72 trên các bài toán khác, không lượt nào rỗng. Trên 24 bài toán nhóm bạn của bộ kiểm tra: có lịch dựng nhanh thì 24/24 ra lịch, trung bình 96,2% giá trị tốt nhất tìm được (thấp nhất 83,7%); không có thì chỉ 15/24 ra lịch.

### Dữ liệu đánh giá dựng lại

- `BE/eval/gold/t053_baselines.json` (bảng SC), dựng lại 12/11/2026 ở ngân sách 5: hybrid 26/26 qua cổng, đánh giá trung bình 4,561 (trước 4,558), 19/27 mong muốn, 7/7 chuyến 2 ngày, khôi phục 26/26. SC-009 vẫn 1,02 lần, chưa đạt 1,10. Baseline LLM-only vẫn SKIP vì máy này không có LLM.
- `BE/eval/human/plan_review_v1.json` (24 lịch cho người chấm), dựng lại 12/11/2026: 24/24 qua cổng, 3 lịch giữ nguyên, 21 lịch đổi. Chưa có kết quả chấm nào, nên không mất gì.
- Bộ gold (`t051_scoped_suite.json`) dựng lại cho ra đúng tệp cũ.

## Mười bước

### 1. Kiểm mong muốn theo đúng điểm

`retrieval.poi_fits_wish`: "hải sản" phải là quán hải sản, "chùa" phải là chùa, không chỉ cùng nhóm loại. Từ một âm tiết phải khớp cả dấu: bỏ dấu thì "phố" thành "phở", "cửa hàng" thành "cua". Cụm từ thì khớp cả khi tên không dấu. Trước đó quán mì vẫn được báo là đáp ứng "hải sản" (7 lần) vì cùng là nhà hàng.

`activity_match.status` nêu đúng lý do: `over_budget`, `no_verified_poi`, `blocked_by_profile`, `outside_trip_hours`, `unmet`, `not_understood`.

"Ngắm hoàng hôn" và "ngắm bình minh" là mong muốn có giờ: điểm đáp ứng phải bắt đầu trong khung 16:00–18:00, 05:00–07:00. Bãi biển lúc 9 giờ sáng không tính là ngắm hoàng hôn.

### 2. Bữa tối

Ngày đi qua 17:30–20:30 phải có bữa tối, cách làm như bữa trưa. Tiền hoặc giờ không đủ thì bỏ bữa tối ở bậc cuối kèm cảnh báo. Danh sách ứng viên luôn giữ 4 quán rẻ nhất, nếu không lịch ngân sách thấp sẽ không còn quán nào đủ tiền cho hai bữa. Ngân sách chuyến nhiều ngày chia đều trước; ngày nào cần nhiều hơn vẫn phải chừa tiền hai bữa cho các ngày sau.

### 3. Khung giờ theo loại điểm

`soft_rules.TIME_FIT_BY_CAT`, `TIME_FIT_BY_SUBCAT`: nhà hàng theo bữa, bar từ 16:30, biển tránh 11:30–15:00, công viên tránh giữa trưa, chùa trước 18:00, chợ đêm từ 17:00, điểm ngắm bình minh trước 09:30. Bộ giải chỉ xếp trong các khung này. Điểm khách tự chọn thì không áp dụng. Khi cần đáp ứng một mong muốn, lịch có thể ra ngoài khung kèm cảnh báo. Cổng mềm `TIME_FIT`, `DINNER` báo vi phạm nhưng không làm rớt lịch.

Các khung này do Claude đặt theo thói quen du lịch, chưa có dữ liệu đo.

### 4. Thời lượng

`visit_min` chia theo loại con và ghi nguồn ở `dur_source`:

| Nguồn | Số điểm | Ý nghĩa |
|---|---|---|
| `subcat_rule` | 472 | Luật theo loại con (cầu 20 phút, tượng 20, chợ dân sinh 30, quán ăn nhỏ 40...) |
| `curated` | 51 | Claude chỉnh theo tên, ví dụ Bán đảo Sơn Trà |
| `google_typical` | 23 | Lấy từ "Mọi người thường dành..." của Google |
| `human` | 3 | Người duyệt đã sửa, công cụ không đè lên |

Điểm khách tự chọn mà không vừa ở p50 sẽ được xếp ở p25 (thời gian ở ngắn nhất thường gặp) kèm cảnh báo. Khi còn dư giờ, điểm được kéo dài tới p75.

### 5. Làm sạch loại điểm

`BE/tools/fix_poi_accuracy.py` (đã gỡ sau khi chạy xong, xem `git show de7e0be:BE/tools/fix_poi_accuracy.py`), đổi 71 nhãn loại:

- Tách `temple` (chùa, nhà thờ, đền, đình: 58 điểm) khỏi `landmark`, tách `shop` (cửa hàng quà: 11 điểm) khỏi `market`. Một ngày nay có thể có cả cầu và chùa.
- `plan_tier` trên 549 điểm đã xác minh: `main` 386 (lịch mặc định), `local` 110 (chỉ khi một mong muốn có dưới 3 điểm `main` dùng được), `wish_only` 41 (đi cả ngày, lớp học, cửa hàng quà: chỉ khi khách hỏi), `excluded` 12 (phòng khám, các hang nằm trong Ngũ Hành Sơn, nơi phải liên hệ trước).
- Ngưỡng đánh giá tối thiểu theo loại (`MIN_REVIEWS`), dưới ngưỡng thành `local`.
- Cờ "không bán vé" được đọc: bảo tàng, chùa không bán vé thì miễn phí. Mức giá nay khác theo loại: cà phê mức trung bình 100.000đ thay vì 300.000đ.

### 6. Giảm đi vòng

- `EDGE_TRAVEL_WEIGHT`: mỗi phút đi xe trừ điểm ở cả ba kiểu lịch.
- `route_order.best_order` (mới): bộ giải chọn điểm, rồi bước này tìm chính xác thứ tự ngắn nhất, giữ mọi quy tắc của ngày, có giới hạn số nút nên kết quả vẫn cố định. Cách này thay cho việc phạt quay lại cùng khu vực vì đường ngắn nhất đã không quay lại.
- Thời gian rảnh trước tiên kéo dài các điểm, phần còn lại dồn về đầu ngày hoặc sau nghỉ trưa, không thành khoảng trống trước bữa tối.

### 7. Giờ mở cửa theo thứ

`hours_by_day` (7 chuỗi, thứ 2 trước, rỗng là nghỉ) có trên 412/549 điểm, lấy từ bảng giờ Google. `common.poi_on_date` chiếu POI về đúng ngày đi. 8 điểm có ngày nghỉ. Có `trip.date` thì không xếp điểm nghỉ ngày đó, điểm khách chọn mà nghỉ thì bị bỏ kèm cảnh báo. Không có `date` thì cảnh báo để khách chọn ngày.

### 8. Độ nổi tiếng và điểm còn thiếu

`rank.WEIGHTS["fame"]` = 0,15, tính theo log số đánh giá, đủ điểm ở 30.000. Thêm 8 điểm: Cầu Tình Yêu, Tượng Cá Chép Hóa Rồng, Nhà thờ Con Gà, Bãi tắm Phạm Văn Đồng, Hải Sản Bé Mặn, Bánh Xèo Bà Dưỡng, New Golden Pine Club, Sky36.

Recall@10: toàn bộ 33% → 45%, trong đúng loại 46% → 61%, chỉ tính điểm có trong dữ liệu 55% → 74%. Trong đó 5 và 6 điểm phần trăm đến từ việc `local` không còn chen vào khi `main` đã đủ (xem mục Lỗi tìm thấy khi đo lại).

### 9. Cố định kết quả

Bộ giải chạy 1 luồng, giới hạn theo khối lượng tính toán (`PLAN_DETERMINISTIC_TIME = 8`; từ 12/11/2026 là 5 với presolve nhẹ hơn, xem Kiểm tra độc lập, giải lại khi trùng lịch `DISTINCT_DETERMINISTIC_TIME = 3`, xếp lại lịch 2), đồng hồ 60 giây chỉ là chốt an toàn. Hai lượt đo khác `PYTHONHASHSEED`, chạy khi máy bận: 204/204 lịch giống hệt nhau.

Thử nghiệm trên 30 lịch, 10 yêu cầu, 4 cấu hình chạy cùng lúc nên thời gian cao hơn khi chạy riêng:

| Cài đặt | Thời gian trung vị | CPU | Lịch đạt |
|---|---|---|---|
| Thường, ngân sách 8 | 8,3 giây | 25 giây | 30/30 |
| Luân phiên, ngân sách 16 | 23,1 giây | 63 giây | 30/30 |
| Luân phiên, ngân sách 8 | 28,0 giây | 60 giây | 30/30 |
| Luân phiên, ngân sách 4 | 49,1 giây | 86 giây | 21/30 |

Một luồng thì lời giải ban đầu (`_greedy_hint`) rất quan trọng: lời giải sai thứ tự hoặc vượt ngân sách có thể khiến cả lượt không ra lịch. Nay nó giữ chỗ cho điểm khách chọn theo đúng thứ tự, cho hai bữa, cho mong muốn, cả tiền lẫn giờ.

Phép đo này chạy trên một máy, cùng bản cài đặt. Máy khác có thể cho lịch khác nếu khác phiên bản bộ giải hoặc không nạp được mô hình PATM (xem Giới hạn). Thời tiết là đầu vào của lịch: dự báo đổi thì lịch có thể đổi.

### 10. Người thật chấm

Tất cả số trên vẫn do máy và Claude chấm. `BE/tools/build_plan_review.py` lập 24 lịch thật (`BE/eval/human/plan_review_v1.json`) và tạo `FE/plan_review.html`: người chấm không thấy điểm máy hay kết quả cổng, chỉ thấy yêu cầu và lịch như khách thấy, rồi chấm 1–5, có đi theo không, chọn lỗi, ghi chú.

**Chưa có kết quả chấm nào.** Việc này cần người thật. 24 lịch đã được dựng lại bằng mô hình mới ngày 01/11/2026, và dựng lại lần nữa ngày 12/11/2026 sau các thay đổi ở mục Kiểm tra độc lập.

## Mô hình PATM

PATM chấm từng cặp điểm: đi A rồi đến B có hợp không. Bộ giải cộng điểm này khi chọn điểm vào lịch. Thứ tự cuối cùng do `route_order` chọn theo đường ngắn nhất (bước 6), nên mô hình không quyết định thứ tự. Khoảng chênh điểm giữa các cặp (p10 đến p90) chỉ bằng 2,6 phút đi xe trong hàm mục tiêu. Chi tiết ở `BE/ml/patm/MODEL_CARD.md`.

Các lần đo trước chạy bằng luật dự phòng vì máy thiếu libomp. Nay đã cài, mô hình nạp được.

### Làm sạch dữ liệu huấn luyện

LLM được hỏi cả hai chiều trên 466 cặp và tự mâu thuẫn ở 129 cặp (28%): đổi thứ tự câu hỏi là đổi câu trả lời. Bỏ 258 dòng đó, còn 1.770 dòng, trong đó 1.342 dòng dùng để huấn luyện (`pairs_v5_final.json`).

| | Dữ liệu cũ | Dữ liệu sạch |
|---|---|---|
| Kiểm tra chéo 5 phần | 77,4% | 81,7% |
| Tập giữ lại | 74,9% | 82,1% |
| Đảo chiều cặp thì đảo kết quả | 85,1% | 96,8% |
| Đúng với người, trên điểm chưa từng thấy (40 lần chia) | 70,3% | 70,4% |
| Luật viết tay, cùng phép đo | 49,7% | 50,8% |

Hai dòng đầu tăng một phần vì đã bỏ những dòng khó đoán. Dòng thứ tư mới là so với người, và nó không đổi: làm sạch giúp mô hình bớt tự mâu thuẫn, không giúp nó đúng hơn. Con số 81–83% từng báo là từ một lần chia may mắn. Con số nên dùng là khoảng 70% so với khoảng 50%.

### Mô hình so với luật dự phòng

Cùng mã, cùng yêu cầu, chỉ khác bên chấm cặp điểm:

| | Luật dự phòng | Mô hình |
|---|---|---|
| Lịch không có lỗi nào | 116/138 (84%) | 118/138 (86%) |
| Bộ điển hình, gold, 2 ngày | 27/30, 61/78, 28/30 | 26/30, 63/78, 29/30 |
| Mong muốn được đáp ứng thật | 85% | 85% |
| Ngày có điểm xếp sai giờ | 4% | 4% |
| Đi xe mỗi ngày, 192 lịch có điểm | 26,5 phút | 26,5 phút |
| Đánh giá trung bình của điểm | 4,52 | 4,51 |
| Ngày đi hết lịch khi trễ 10 phút mỗi chặng, kẹt xe gấp 1,2 lần, điển hình và gold | 67%, 39% | 70%, 43% |

Chỉ 51/204 lịch có cùng tập điểm, trung bình hai bên trùng 61%. Mô hình đổi lịch rất nhiều, nhưng quy tắc chấm ở đây không thấy bên nào tốt hơn rõ rệt: chênh 2 lịch trên 138 là quá nhỏ để kết luận. Các quy tắc này cũng không đo độ hợp lý khi chuyển giữa hai điểm, đúng thứ mô hình học. Chỉ người thật chấm (mục 10) mới cho biết khác biệt đó có đáng giá không.

## Lỗi tìm thấy khi đo lại

- **Điểm chưa xác minh làm rỗng cả lịch.** Khách nêu tên một điểm chưa xác minh thì bộ giải buộc phải ghé một điểm không có trong danh sách, và trả lịch rỗng. Nay điểm đó bị bỏ kèm cảnh báo, phần còn lại vẫn được lập, điểm đó nằm đầu `needs_verification`.
- **`local` chạy khác tài liệu.** Tài liệu nói `local` chỉ vào khi `main` không đủ, mã lại mở cho mọi mong muốn. Nay chỉ mở khi mong muốn có dưới 3 điểm `main` dùng được (không bị khách tránh, mở trong khung giờ chuyến đi, vé không vượt ngân sách). Recall@10 trong đúng loại 56% → 61%, chỉ tính điểm có trong dữ liệu 68% → 74%. Lượt ghé điểm `local` mà khách không nêu tên 4 → 1.
- **Luật dự phòng có một điều khoản không chạy.** Điều khoản "ăn sau khi tham quan" đọc `type == "restaurant"`, giá trị không có trong dữ liệu thật. Nay đọc theo `poi_category`.
- **`count` trong `pois.json`** ghi 753, thực tế 750. Công cụ nay ghi theo số điểm thật.

## Dữ liệu sau bước sửa

750 POI, 549 đã xác minh. Kết quả nằm trong `pois.json`. Công cụ đã gỡ khỏi nhánh, lấy lại bằng `git show de7e0be:BE/tools/fix_poi_accuracy.py`; nó cần `--lookups` là thư mục tra Google đã lưu trên máy, không có trong git.

Nguồn giá vé, các nguồn không khớp nhau nên đây là mức tham khảo:

- Ngũ Hành Sơn 40.000đ: [Vinpearl](https://vinpearl.com/vi/ngu-hanh-son-da-nang-nam-thien-danh-thang-tru-danh), [Vietnam Airlines](https://www.vietnamairlines.com/cz/vi/plan-book/travel/travel-guide/ngu-hanh-son-da-nang), [Danang Fantastic City](https://danangfantasticity.com/en/di-san-canh-quan/danh-thang-ngu-hanh-son). Các nguồn ghi 20.000–40.000đ, dùng mức cao.
- Bà Nà 1.000.000đ: [giá vé 2026](https://sunparadiseland.com/SunParadiseLandDaNang/tin-tuc/gia-ve-ba-na-hills-2026-moi-nhat-cach-mua-tiet-kiem-20215), [vé cáp treo 2026](https://sunparadiseland.com/SunParadiseLandDaNang/tin-tuc/cap-nhat-ve-cap-treo-ba-na-hills-2026-huong-dan-cach-mua-online-20210). Không phải trang chính thức.

## Giới hạn

- Quy tắc chấm và khung giờ do Claude đặt. Con số phản ánh các quy tắc đó, chưa phải cảm nhận của khách.
- Máy không nạp được lightgbm (macOS thiếu libomp) tự dùng luật dự phòng, không báo lỗi, và lịch sẽ khác. `scorer.describe()` cho biết đang dùng gì.
- Mô hình PATM chỉ học từ đặc điểm của hai điểm, mới có 150 cặp do người gán, chưa có dữ liệu theo khách hay thời tiết: mọi khách nhận cùng một điểm số.
- Khi đo lập lịch, dự báo thời tiết bị tắt. Ảnh hưởng của mưa mới đo bằng dự báo giả lập (mục Kiểm tra độc lập), chưa đo với dự báo thật; nắng nóng chưa đo.
- `trip_purpose` của hồ sơ chưa được dùng ở đâu trong lập lịch. Ba trọng số sở thích (chi tiêu, ngoài trời, hoạt động yêu thích) do Claude chọn theo phép đo trên 3 hồ sơ mẫu, chưa có người chấm.
- Ngày của nhóm bạn (10–11 điểm, kết thúc muộn) là bài toán khó nhất: lời giải đạt trung bình 96% giá trị tốt nhất tìm được, so với trên 99% ở các nhóm khác, và chiếm 11 trong 16 ngày bị tính là đi vòng.
- Điểm che một phần (chùa, chợ có mái) vẫn được xếp trong giờ mưa. Lịch không có ngày đi có thể chứa điểm nghỉ một ngày trong tuần (13/201 lịch), có cảnh báo.
- Xếp lại lịch khi đang ở giữa một điểm đi cả ngày (chưa đánh dấu xong) có thể trả `no_solution`: bữa trưa tại chỗ chỉ được tính khi điểm đó còn bắt đầu trước 11:00.
- Mong muốn không xếp được vẫn tốn hai lượt giải trước khi bị bỏ (khoảng 20 giây cho hồ sơ đó). Nhiều mong muốn không cùng xếp được thì bỏ hết, chưa thử giữ một phần.
- 8 điểm mới chưa có đường đi OSRM: ma trận mượn hàng của điểm gần nhất cộng đoạn ngắn tới đó (`coverage.estimated_ids`). Kiểm tra trên 111 điểm có OSRM cách điểm gần nhất dưới 0,6 km: sai số trung vị 1 phút, p90 2 phút.
- 8 điểm mới chưa đối chiếu OSM vì không có file `pbf` trên máy (`osm_crosscheck.json` ghi `not_run`).
- Chỉ 23 điểm có thời lượng từ Google; 137 điểm đã xác minh chưa có giờ theo thứ.
- 89% số tiền hiển thị vẫn là ước tính theo mức giá.
- Dữ liệu chưa có quán bún, phở, chè. Hỏi "bún" được báo `no_verified_poi`.
- Asia Park không được thêm: "DA NANG DOWNTOWN" hiện "Bị đóng vĩnh viễn" trên Google. Công viên Kỳ Quan (01 Lê Văn Duyệt) là nơi khác.
- Hai điểm cùng loại do khách tự chọn (hai chùa, hai quán cà phê trong một buổi) vẫn cho lịch rỗng vì cổng cứng một điểm mỗi loại mỗi ngày. Lịch rỗng có cảnh báo nêu đúng lý do. Đây là quyết định đã có, chưa đổi.
- Xếp lại lịch giữ đúng giờ giấc nhưng chưa thêm điểm mới: sau mưa, cuối ngày còn trống trung bình 236 phút.
- SC-009 vẫn chưa đạt (1,02 lần, mục tiêu 1,10 lần), như trước khi sửa. SC-001, SC-002 cần LLM, máy này chưa có.
- Bộ nhớ: 807 MB sau 67 yêu cầu. Kho plan đã giới hạn 300 plan, mỗi plan giữ khoảng 1 MB ngữ cảnh để xếp lại lịch (ước tính từ mức tăng bộ nhớ).
- Son Tra Viewpoint (4,9 sao, 203 đánh giá) chưa xác minh nên không vào lịch.
- Ma trận có một chỗ lệch chưa kiểm tra: Bán đảo Sơn Trà đến Núi Sơn Trà 7 phút, chiều ngược lại 62 phút.
