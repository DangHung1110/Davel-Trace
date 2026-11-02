# Độ chính xác lập lịch (cập nhật 01/11/2026)

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

Bộ giải chạy 1 luồng, giới hạn theo khối lượng tính toán (`PLAN_DETERMINISTIC_TIME = 8`, giải lại khi trùng lịch `DISTINCT_DETERMINISTIC_TIME = 3`, xếp lại lịch 2), đồng hồ 60 giây chỉ là chốt an toàn. Hai lượt đo khác `PYTHONHASHSEED`, chạy khi máy bận: 204/204 lịch giống hệt nhau.

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

**Chưa có kết quả chấm nào.** Việc này cần người thật. 24 lịch đã được dựng lại bằng mô hình mới ngày 01/11/2026.

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
- Khi đo lập lịch, dự báo thời tiết bị tắt, nên ảnh hưởng của thời tiết thật lên lịch chưa được đo.
- 8 điểm mới chưa có đường đi OSRM: ma trận mượn hàng của điểm gần nhất cộng đoạn ngắn tới đó (`coverage.estimated_ids`). Kiểm tra trên 111 điểm có OSRM cách điểm gần nhất dưới 0,6 km: sai số trung vị 1 phút, p90 2 phút.
- 8 điểm mới chưa đối chiếu OSM vì không có file `pbf` trên máy (`osm_crosscheck.json` ghi `not_run`).
- Chỉ 23 điểm có thời lượng từ Google; 137 điểm đã xác minh chưa có giờ theo thứ.
- 89% số tiền hiển thị vẫn là ước tính theo mức giá.
- Dữ liệu chưa có quán bún, phở, chè. Hỏi "bún" được báo `no_verified_poi`.
- Asia Park không được thêm: "DA NANG DOWNTOWN" hiện "Bị đóng vĩnh viễn" trên Google. Công viên Kỳ Quan (01 Lê Văn Duyệt) là nơi khác.
- Hai điểm cùng loại do khách tự chọn (hai chùa, hai quán cà phê trong một buổi) vẫn cho lịch rỗng vì cổng cứng một điểm mỗi loại mỗi ngày. Lịch rỗng có cảnh báo nêu đúng lý do. Đây là quyết định đã có, chưa đổi.
- Xếp lại lịch giữ đúng giờ giấc nhưng chưa thêm điểm mới: sau mưa, cuối ngày còn trống trung bình 236 phút.
- SC-009 vẫn chưa đạt (1,02 lần, mục tiêu 1,10 lần), như trước khi sửa. SC-001, SC-002 cần LLM, máy này chưa có.
- Bộ nhớ tăng theo số yêu cầu (2,12 GB sau 42 yêu cầu), chưa xử lý.
- Son Tra Viewpoint (4,9 sao, 203 đánh giá) chưa xác minh nên không vào lịch.
- Ma trận có một chỗ lệch chưa kiểm tra: Bán đảo Sơn Trà đến Núi Sơn Trà 7 phút, chiều ngược lại 62 phút.
