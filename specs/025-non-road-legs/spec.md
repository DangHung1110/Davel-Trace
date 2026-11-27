# Chặng không đi bằng xe máy: đảo, cáp treo, đường mòn

Ma trận đường đi (`BE/data/snapshots/danang-v2/matrix.json`) là thời gian **xe máy** do OSRM tính. OSRM gắn mỗi điểm vào con đường xe máy gần nhất. Với vài nơi, con đường gần nhất là con đường sai (kiểm tra toạ độ P0 ngày 26/11, `reports/p0/coord_check.md` trên nhánh `feat/p0-coord-check-osm`):

- **Cù Lao Chàm** là đảo, nhưng bị gắn vào đất liền bên kia cửa sông. Ma trận ghi phố cổ Hội An → Cù Lao Chàm **20 phút, 9,6 km xe máy**, trong khi đường chim bay đã 22 km và thực tế phải đi cano từ bến Cửa Đại. 26,5% chặng của đảo ngắn hơn đường chim bay.
- **24 điểm trên đỉnh Bà Nà** (Cầu Vàng, Fantasy Park, chùa Linh Ứng, nhà hàng, quán cà phê) và **khách sạn Mercure** trên đỉnh bị gắn vào đường công vụ lên núi: 35 phút xe máy từ ga cáp treo chân núi, và **1 phút, 0 km** giữa hai điểm bất kỳ trên đỉnh (tất cả chung một điểm gắn). Linh Phong Bảo Tháp còn bị gắn vào một con đường khác: 72 phút. Thực tế khách đi cáp treo lên, rồi đi bộ trên đỉnh.
- **Bãi Sủng Cỏ** và **Bãi Cát Vàng** cách đường xe máy 1,3 km và 400 m. Đoạn cuối phải đi bộ.

## Cách sửa

Mỗi nơi như vậy có một **cửa ngõ**: một đầu đường bộ (một hàng có sẵn trong ma trận) cộng một chặng cố định không đi bằng xe máy, tính cho cả hai chiều. Ví dụ, đi từ phố cổ Hội An ra Cù Lao Chàm:

1. Xe máy từ phố cổ tới bến Cửa Đại. Bến không có hàng trong ma trận, nên đi qua quán gần bến nhất có đường bộ thẳng tới bến: Mate Restaurant, cách bến 2,1 km đường xe máy theo OSM, tức 5 phút. Phố cổ → Mate 13 phút, cộng 5 phút, được 18 phút.
2. Cano 20 phút, cộng 10 phút mua vé, mặc áo phao, lên tàu: 30 phút.
3. Tổng **48 phút, 25 km** (trước đây 20 phút, 9,6 km).

Quy tắc chung, với X là nơi sau cửa ngõ:

- a → X = đường bộ từ a tới đầu đường bộ + chặng cố định
- X → b = chặng cố định + đường bộ từ đầu đường bộ tới b
- X → Y, khác cửa ngõ = chặng của X + đường bộ giữa hai đầu + chặng của Y
- X → Y, cùng cửa ngõ có `inside: walk` (đỉnh Bà Nà) = đi bộ: đường chim bay × 1,3, đi 4 km/h

Dữ liệu nằm trong `BE/data/snapshots/danang-v2/transfers.json` (có nguồn). `BE/app/services/transfers.py` viết lại hàng và cột của các nơi đó **một lần, lúc nạp ma trận** (`matrix.load_matrix_doc`), nên solver, gate, `segments` của kế hoạch và audit cùng đọc một số phút. `matrix.json` không đổi. Công cụ so với OSRM (`calibrate_matrix.py`) đọc ma trận thô: `load_matrix_doc(path, transfers=False)`.

## Cửa ngõ và nguồn

| Cửa ngõ | Đầu đường bộ | Chặng cố định | Nguồn |
|---|---|---|---|
| Cáp treo Bà Nà (25 nơi) | hàng của Sun World Bà Nà Hills: ghim Google nằm ở ga chân núi, cách ga Hội An 170 m | 20 phút cáp + 10 phút từ cổng vào ga = 30 phút | mỗi lượt 15–20 phút (Vietnam Booking 2026, Sun Paradise Land 07/08/2026, hoiandaytrip); từ cổng tới ga thêm 10–20 phút (Sun Paradise Land) |
| Cano Cửa Đại – Cù Lao Chàm | bến Cửa Đại (OSM node 133589858), qua Mate Restaurant + 5 phút | 20 phút cano + 10 phút lên tàu = 30 phút | cano 15–20 phút, đảo cách bờ 18 km (VnExpress, cập nhật 14/7/2026); 10 phút lên tàu là số thiết kế, nguồn không ghi |
| Đường mòn Bãi Sủng Cỏ | hàng của chính bãi (OSRM đã dừng ở đường gần nhất) | 25 phút đi bộ | đường đi bộ ngắn nhất trên OSM (bản 24/11): 1,67 km |
| Lối bộ Bãi Cát Vàng | hàng của chính bãi | 9 phút đi bộ | OSM: 0,58 km, có bậc thang |

## Ảnh hưởng

Số phút của các chặng trong báo cáo kiểm toạ độ (trước → sau, xe máy là phần đường bộ):

| Chặng | Trước | Sau | Gồm |
|---|---|---|---|
| Phố cổ Hội An → Cù Lao Chàm | 20 phút, 9,6 km | 48 phút, 25,0 km | xe máy 18 + cano 30 |
| Cầu Rồng → Cù Lao Chàm | 64 phút | 87 phút | xe máy 57 + cano 30 |
| Đỉnh Bà Nà → Sun World Bà Nà Hills | 36 phút, 18 km | 30 phút, 5,3 km | cáp treo |
| Cầu Rồng → Cầu Vàng | 63 phút | 81 phút | xe máy 51 + cáp treo 30 |
| Cầu Vàng → Fantasy Park | 1 phút, 0 km | 17 phút, 1,1 km | đi bộ |
| Sun World → Linh Phong Bảo Tháp | 72 phút | 30 phút | cáp treo |
| Cầu Rồng → Bãi Sủng Cỏ | 71 phút | 96 phút | xe máy 71 + đi bộ 25 |
| Cầu Rồng → Bãi Cát Vàng | 26 phút | 35 phút | xe máy 26 + đi bộ 9 |

Nạp ma trận lâu thêm khoảng 0,1 giây (một lần mỗi tiến trình); 55 692 ô đổi giá trị. Các chặng khác giữ nguyên từng ô.

**Audit chuẩn** (`BE/tools/audit_plans.py`, 67 yêu cầu, 201 kế hoạch) gần như không đụng tới các nơi này: trên `main`, chỉ 6 kế hoạch có Bà Nà, và cả 6 đều dùng chính "Sun World Bà Nà Hills" (ga chân núi, hàng vốn đúng). Không kế hoạch nào có Cù Lao Chàm, điểm trên đỉnh hay hai bãi.

Sau khi sửa, vẫn 201/201 kế hoạch qua gate và đi được; không kế hoạch nào dùng chặng cano, cáp treo hay đi bộ; số ý muốn đạt giữ nguyên 96/108. Nhưng chỉ 73/201 kế hoạch giống hệt trước. Lý do: danh sách ứng viên đưa vào solver của mọi yêu cầu (570–685 điểm) có khoảng 20 nơi sau cửa ngõ (Cù Lao Chàm, Cầu Vàng, Fantasy Park, quán trên đỉnh). Số phút của chúng đổi nên mô hình CP-SAT đổi, và với cùng ngân sách tìm kiếm solver dừng ở một kế hoạch khác gần tương đương, thường chỉ đổi một quán ăn hay một bảo tàng. Kiểm tra A/B trên 7 yêu cầu (21 kế hoạch): code mới bỏ `transfers.json` cho kết quả giống hệt `main` (21/21), `main` chạy hai lần cũng giống hệt (21/21), còn có `transfers.json` thì 11/21 giống. Các cờ chất lượng đổi ít và theo cả hai chiều: sạch 25 → 27, ngày đi vòng > 1,3 lần: 36 → 26, đến muộn 14 → 11, khoảng trống dài 95 → 100, chặng dài 25 → 31 (toàn chặng đường bộ trong thành phố), thiếu bữa tối 15 → 17. Đi lại trung bình 30,4 → 31,0 phút một ngày; thời gian trả lời trung vị 5,9 → 5,6 giây.

**Audit nhắm thẳng** (11 yêu cầu, 33 kế hoạch, cùng bộ chấm của `audit_plans.py`): phải ghé Cù Lao Chàm (từ khách sạn Nam Hải, từ khách sạn Sala, không khách sạn), Cầu Vàng, Cầu Vàng + Fantasy Park, Sun World, ý muốn "cáp treo", khách sạn Mercure trên đỉnh, Bãi Sủng Cỏ, Bãi Cát Vàng, và chuyến 2 ngày có cả đảo lẫn Cầu Vàng.

- Kế hoạch của `main`, chấm bằng số phút mới: **chỉ 11/33 đi được**. 31 chặng không đủ thời gian (`ERR_TRAVEL`), ví dụ Cù Lao Chàm → Chùa Cầu cần 49 phút nhưng lịch chỉ chừa 32, Cầu Vàng → Fantasy Park cần 17 phút nhưng lịch chừa 13.
- Kế hoạch sau khi sửa: **33/33 qua gate và đi được**. Chặng dài (`Q_LONG_LEG`, trên 35 phút) tăng 31 → 42 vì giờ đã tính đúng cano và cáp treo; đi lại trung bình 69 → 81 phút một ngày.
- Ví dụ (gia đình, phải ghé Cầu Vàng và Fantasy Park): trước đây đi xe máy thẳng từ quán mì Quảng lên Cầu Vàng 61 phút, rồi sang Fantasy Park 1 phút. Giờ là quán mì Quảng → Fantasy Park 81 phút (xe máy 51 + cáp treo 30), Fantasy Park → Cầu Vàng 17 phút đi bộ.

## Hợp đồng cho app

`segments[]` của kế hoạch (`BE/app/services/response.py`):

- `mode` vẫn là `"motorbike"` cho chặng thường. Chặng vào hoặc ra một nơi sau cửa ngõ ghi các phần theo thứ tự đi, nối bằng `+`: `"motorbike+boat"`, `"boat+motorbike"`, `"cable_car"` (từ chính ga chân núi lên đỉnh), `"cable_car+motorbike"`, `"motorbike+walk"`, và `"walk"` giữa hai điểm trên đỉnh Bà Nà.
- Có thêm `transfers: [{gateway, name, mode, minutes, km}]`, ví dụ `{"gateway": "cu_lao_cham_boat", "name": "Cano Cửa Đại - Cù Lao Chàm", "mode": "boat", "minutes": 30, "km": 16.5}`. `minutes` và `km` của segment đã gồm phần này.
- App hiện chưa đọc `segments`. Khi hiện chặng đi, nên ghi "xe máy 18 phút + cano 30 phút" thay vì "xe máy 48 phút".

## Thêm hoặc sửa một cửa ngõ

- Thêm POI mới trên đỉnh Bà Nà: thêm `{poi_id, name, status, lat, lon}` vào `places` của `ba_na_cable_car`. Test `BE/tests/data/test_transfers_v2.py` báo lỗi nếu một POI active của cụm `ba_na` chưa nằm sau cáp treo, hoặc tên, toạ độ lệch `pois.json`.
- Một cửa ngõ có id không còn trong ma trận thì bị bỏ qua lúc nạp, không làm hỏng ma trận; lý do nằm ở `doc["transfers"]["skipped"]`. Test dữ liệu đòi danh sách này rỗng.
- `road_end` có ba dạng: `{"poi_id": ...}` (một POI đứng ở đó), `{"own_row": true}` (hàng của chính nơi đó, chỉ cho cửa ngõ một nơi), `{"via": [{"poi_id", "minutes", "km"}]}` (chọn đường nhanh nhất qua vài POI gần, cộng một đoạn xe máy ngắn).

## Chưa làm

- **Giờ chạy của tàu và cáp treo.** Tàu du lịch ra Cù Lao Chàm phần lớn nghỉ ngoài tháng 3–8 (VnExpress), và chạy theo lịch cố định. Cáp treo Bà Nà mở 08:00, vé ngày lên lần cuối 16:30–17:00. Hiện `hours` của Cù Lao Chàm là `00:00-23:59`, nên planner vẫn có thể xếp đảo tới 20:00. Nên làm tiếp bằng `hours.access_window` như khung đường Sơn Trà.
- **Tiền vé của chặng.** Điểm trên đỉnh Bà Nà có giá `included` (nằm trong vé Sun World) nên tính 0đ. Vì vậy kế hoạch có Cầu Vàng và Fantasy Park mà không có điểm "Sun World Bà Nà Hills" thì không bị tính vé cáp treo (mức `expensive`, 850.000đ một người). Ví dụ: kế hoạch gia đình 4 người phải ghé Cầu Vàng và Fantasy Park báo tổng 200.000đ, chỉ là tiền bữa trưa. Cù Lao Chàm (mức `cheap`, 50.000đ) cũng chưa gồm tiền cano bắt buộc, khoảng 150.000đ mỗi lượt theo ghi chú giá.
- **Chuyến không có khách sạn (open tour):** ngày bắt đầu ở điểm đầu tiên, nên nếu đảo là điểm đầu thì chặng cano chiều đi không được tính. Chặng về khách sạn cuối ngày cũng chưa được tính, với mọi điểm xuất phát.
- **Hàng của bến Cửa Đại là ước lượng** qua một quán gần bến (lệch vài phút). Dựng hàng OSRM thật cho bến cần Docker và OSRM.
- **Xếp hàng giờ cao điểm** ở cáp treo (vài phút tới vài chục phút) chưa tính.
- `BE/tools/coord_check_osm.py` (nhánh `feat/p0-coord-check-osm`) đọc `matrix.json` thô, nên vẫn báo hàng của Cù Lao Chàm sai. Đúng với hàng OSRM, nhưng planner đã đọc qua `transfers.json`.
