# Độ chính xác lập lịch (31/10/2026)

Nhánh `task/plan-accuracy`, tách từ `feat/stable-p1-p4`. Mười bước sửa theo kết quả kiểm tra 141 lịch thật.

Mọi số dưới đây đo bằng cùng một bộ yêu cầu, cùng quy tắc chấm, trước và sau khi sửa. Quy tắc chấm do máy và Claude đặt ra, chưa có người thật chấm (xem mục 10). Bộ đo: 10 yêu cầu điển hình và 30 yêu cầu gold, mỗi yêu cầu 3 lịch; 10 yêu cầu 2 ngày. Gold đo trên bộ câu hỏi cũ để so được với trước.

## Kết quả

| Chỉ số | Trước | Sau |
|---|---|---|
| Lịch không có lỗi nào, toàn bộ | 22/141 (16%) | 116/138 (84%) |
| Bộ điển hình | 0/30 | 27/30 (90%) |
| Bộ gold | 22/81 (27%) | 62/78 (79%) |
| Bộ 2 ngày | 0/30 | 27/30 (90%) |
| Có bữa tối khi lịch qua giờ tối | 7% | 100% |
| Có bữa trưa khi lịch qua giờ trưa | 81% | 100% |
| Mong muốn được đáp ứng thật | 67% | 85% |
| Báo "đạt" nhưng sai | 9/102 | 0/102 |
| Ngày có điểm xếp sai giờ | 27% | 5% (đều là điểm khách tự chọn) |
| Đường đi so với thứ tự ngắn nhất | gấp 1,41 lần | gấp 1,09 lần |
| Lịch đi vòng quá 1,5 lần | 40% | 0% |
| Đi xe mỗi ngày | 62,7 phút | 26,4 phút |
| Thời lượng khớp Google (19 điểm tra được) | 70% | 97% |
| Lượt ghé điểm sai nhóm loại | 65/884 | 0/1082 |
| Cùng yêu cầu ra cùng lịch | 4/21 | 204/204 |
| Recall@10 trong đúng nhóm loại | 46% | 56% |

Bộ 141 lịch có 9 lịch rỗng trước khi sửa. Sau khi sửa có 12 lịch rỗng: thêm 1 câu hỏi (3 lịch) không còn vừa khung giờ khi thời lượng đã đúng thực tế (mục 4). Các lịch rỗng này đều kèm cảnh báo nêu lý do.

Lỗi còn lại trong bộ gold: 12% là mong muốn không đáp ứng được (6 lịch vì nửa ngày đã kín hai điểm khách chọn, 3 lịch vì không đủ tiền), 10% là điểm khách tự chọn ở giờ không đẹp, 4% đi vòng do thứ tự khách yêu cầu, 3% ở lâu hơn Google.

### Hiệu năng

| Chỉ số | Trước | Sau |
|---|---|---|
| Độ trễ điển hình, trung vị / p95 | 5,6 / 10,7 giây | 6,8 / 7,5 giây |
| Độ trễ 2 ngày, trung vị / lớn nhất | 10,8 / 21,7 giây | 12,7 / 13,6 giây |
| CPU mỗi yêu cầu, 1 ngày / 2 ngày | 42 / 88 giây | 17 / 34 giây |
| 12 yêu cầu cùng lúc, máy chủ thật | 6/36 lịch đạt | 36/36 lịch đạt |
| Thông lượng lớn nhất | 19 yêu cầu/phút | 23 yêu cầu/phút |
| Giả lập máy khoảng 2 nhân | 29,2 giây, 10/24 đạt | 14,3 giây, 24/24 đạt |
| Xếp lại lịch, 360 lần | 356 có lịch, 16 ms | 358 có lịch, 18 ms |
| Bộ nhớ sau phép thử tải (42 yêu cầu) | 2,76 GB | 2,55 GB |

Độ trễ trung vị tăng 1 giây để đổi lấy kết quả cố định. Đổi lại p95 giảm 3 giây và quá tải không còn làm hỏng lịch: máy bận thì trả chậm hơn chứ không trả lịch rỗng.

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

`BE/tools/fix_poi_accuracy.py`, chạy lại nhiều lần vẫn ra cùng kết quả, đổi 71 nhãn loại:

- Tách `temple` (chùa, nhà thờ, đền, đình: 58 điểm) khỏi `landmark`, tách `shop` (cửa hàng quà: 11 điểm) khỏi `market`. Một ngày nay có thể có cả cầu và chùa.
- `plan_tier` trên 549 điểm đã xác minh: `main` 386 (lịch mặc định), `local` 110 (chỉ khi mong muốn cần), `wish_only` 41 (đi cả ngày, lớp học, cửa hàng quà: chỉ khi khách hỏi), `excluded` 12 (phòng khám, các hang nằm trong Ngũ Hành Sơn, nơi phải liên hệ trước).
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

Recall@10: toàn bộ 33% → 45%, trong đúng loại 46% → 56%, chỉ tính điểm có trong dữ liệu 55% → 68%.

### 9. Cố định kết quả

Bộ giải chạy 1 luồng, giới hạn theo khối lượng tính toán (`PLAN_DETERMINISTIC_TIME = 8`, giải lại khi trùng lịch `DISTINCT_DETERMINISTIC_TIME = 3`, xếp lại lịch 2), đồng hồ 60 giây chỉ là chốt an toàn. Hai lượt đo khác `PYTHONHASHSEED`, chạy khi máy bận: 204/204 lịch giống hệt nhau.

Thử nghiệm trên 30 lịch, 10 yêu cầu, 4 cấu hình chạy cùng lúc nên thời gian cao hơn khi chạy riêng:

| Cài đặt | Thời gian trung vị | CPU | Lịch đạt |
|---|---|---|---|
| Thường, ngân sách 8 | 8,3 giây | 25 giây | 30/30 |
| Luân phiên, ngân sách 16 | 23,1 giây | 63 giây | 30/30 |
| Luân phiên, ngân sách 8 | 28,0 giây | 60 giây | 30/30 |
| Luân phiên, ngân sách 4 | 49,1 giây | 86 giây | 21/30 |

Một luồng thì lời giải ban đầu (`_greedy_hint`) rất quan trọng: lời giải sai thứ tự hoặc vượt ngân sách có thể khiến cả lượt không ra lịch. Nay nó giữ chỗ cho điểm khách chọn theo đúng thứ tự, cho hai bữa, cho mong muốn, cả tiền lẫn giờ.

Phép đo này chạy trên một máy, cùng bản cài đặt. Máy khác có thể cho lịch khác nếu khác phiên bản bộ giải hoặc nạp được mô hình PATM (xem Giới hạn). Thời tiết là đầu vào của lịch: dự báo đổi thì lịch có thể đổi.

### 10. Người thật chấm

Tất cả số trên vẫn do máy và Claude chấm. `BE/tools/build_plan_review.py` lập 24 lịch thật (`BE/eval/human/plan_review_v1.json`) và tạo `FE/plan_review.html`: người chấm không thấy điểm máy hay kết quả cổng, chỉ thấy yêu cầu và lịch như khách thấy, rồi chấm 1–5, có đi theo không, chọn lỗi, ghi chú.

**Chưa có kết quả chấm nào.** Việc này cần người thật.

## Dữ liệu sau bước sửa

750 POI, 549 đã xác minh. Chạy lại công cụ:

```bash
python BE/tools/fix_poi_accuracy.py --lookups .claude/verify-old-wip
```

`--lookups` là thư mục tra Google đã lưu trên máy, không có trong git. Không có thư mục đó thì `hours_by_day` giữ nguyên.

Nguồn giá vé, các nguồn không khớp nhau nên đây là mức tham khảo:

- Ngũ Hành Sơn 40.000đ: [Vinpearl](https://vinpearl.com/vi/ngu-hanh-son-da-nang-nam-thien-danh-thang-tru-danh), [Vietnam Airlines](https://www.vietnamairlines.com/cz/vi/plan-book/travel/travel-guide/ngu-hanh-son-da-nang), [Danang Fantastic City](https://danangfantasticity.com/en/di-san-canh-quan/danh-thang-ngu-hanh-son). Các nguồn ghi 20.000–40.000đ, dùng mức cao.
- Bà Nà 1.000.000đ: [giá vé 2026](https://sunparadiseland.com/SunParadiseLandDaNang/tin-tuc/gia-ve-ba-na-hills-2026-moi-nhat-cach-mua-tiet-kiem-20215), [vé cáp treo 2026](https://sunparadiseland.com/SunParadiseLandDaNang/tin-tuc/cap-nhat-ve-cap-treo-ba-na-hills-2026-huong-dan-cach-mua-online-20210). Không phải trang chính thức.

## Giới hạn

- Quy tắc chấm và khung giờ do Claude đặt. Con số phản ánh các quy tắc đó, chưa phải cảm nhận của khách.
- Mọi số đo chạy bằng luật chấm chuyển tiếp dự phòng, không phải mô hình PATM, vì máy đo thiếu libomp nên không nạp được lightgbm (`scorer.describe()` trả `backend: rule`). Máy nạp được mô hình sẽ cho lịch khác và cần đo lại.
- Khi đo lập lịch, dự báo thời tiết bị tắt, nên ảnh hưởng của thời tiết thật lên lịch chưa được đo.
- 8 điểm mới chưa có đường đi OSRM: ma trận mượn hàng của điểm gần nhất cộng đoạn ngắn tới đó (`coverage.estimated_ids`). Kiểm tra trên 111 điểm có OSRM cách điểm gần nhất dưới 0,6 km: sai số trung vị 1 phút, p90 2 phút.
- 8 điểm mới chưa đối chiếu OSM vì không có file `pbf` trên máy (`osm_crosscheck.json` ghi `not_run`).
- Chỉ 23 điểm có thời lượng từ Google; 137 điểm đã xác minh chưa có giờ theo thứ.
- 89% số tiền hiển thị vẫn là ước tính theo mức giá.
- Dữ liệu chưa có quán bún, phở, chè. Hỏi "bún" được báo `no_verified_poi`.
- Asia Park không được thêm: "DA NANG DOWNTOWN" hiện "Bị đóng vĩnh viễn" trên Google. Công viên Kỳ Quan (01 Lê Văn Duyệt) là nơi khác.
- Hai điểm cùng loại do khách tự chọn (hai chùa, hai quán cà phê trong một buổi) vẫn cho lịch rỗng vì cổng cứng một điểm mỗi loại mỗi ngày. Lịch rỗng có cảnh báo nêu đúng lý do. Đây là quyết định đã có, chưa đổi.
- Xếp lại lịch giữ đúng giờ giấc nhưng chưa thêm điểm mới: sau mưa, cuối ngày còn trống trung bình 213 phút.
- SC-009 vẫn chưa đạt, như trước khi sửa. SC-001, SC-002 cần LLM, máy này chưa có.
- Bộ nhớ tăng theo số yêu cầu (2,55 GB sau 42 yêu cầu), chưa xử lý.
