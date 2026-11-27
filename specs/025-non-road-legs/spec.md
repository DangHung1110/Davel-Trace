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

## Tiền vé của điểm cha và tiền chặng (làm ngày 27/11, nhánh `fix/transfer-fares`)

Có những điểm phải trả tiền **ngoài giá của chính nó** mới tới được:

- **Vé của điểm cha.** 24 điểm trên đỉnh Bà Nà (Cầu Vàng, Fantasy Park, quán ăn, cà phê) nằm trong vé Sun World Bà Nà Hills, vé này gồm cả cáp treo. Tương tự, 23 nhà cổ, hội quán, bảo tàng nằm trong vé phố cổ Hội An, và 5 động, chùa nằm trong vé Ngũ Hành Sơn (Thủy Sơn). Dữ liệu ghi quan hệ này bằng `requires_ticket_of`; các điểm tham quan con có giá `included`, tức 0đ.
- **Tiền chặng.** Ra Cù Lao Chàm phải đi cano từ bến Cửa Đại.

Trước đây planner chỉ cộng giá của từng điểm. Kế hoạch có Cầu Vàng mà không có điểm "Sun World Bà Nà Hills" vì thế không trả vé nào, và Cù Lao Chàm chỉ tốn 50.000đ.

**Cách tính bây giờ.** Một công thức (`BE.common.fee_breakdown`) dùng chung cho bộ giải, cổng `BCS` và `total_cost`:

1. Mỗi điểm trả giá của chính nó, như trước.
2. Vé của điểm cha trả **một lần cho cả chuyến**, dù có mấy điểm con. Không trả nếu chính điểm cha có trong lịch, vì giá của nó đã là vé đó. Nguồn giá của Sun World ghi vé dùng được 3 ngày liên tiếp.
3. Tiền chặng trả **mỗi ngày có ghé**: một lượt cano khứ hồi trong ngày.

Ví dụ thật (audit nhắm thẳng): gia đình 4 người, xuất phát từ khách sạn Sala, phải ghé Cầu Vàng và Fantasy Park, ngân sách 3 triệu. Lịch "tiết kiệm" có 6 điểm: Làng Bích họa, Công viên APEC, Cầu Rồng, mì Quảng Cô Sáu, Fantasy Park, Cầu Vàng.

- Trước: báo **200.000đ**, tức chỉ tiền mì Quảng của 4 người.
- Tiền thật: 4 × (850.000đ vé Sun World + 50.000đ mì Quảng) = **3.600.000đ**, vượt ngân sách.
- Sau: với 3 triệu, planner trả lịch rỗng kèm cảnh báo "ngan sach khong du cho cac diem bat buoc" (riêng tiền vé đã 3,4 triệu). Với 6 triệu, planner xếp đúng 6 điểm đó, báo 3.600.000đ và ghi rõ khoản "Sun World Bà Nà Hills: 850.000đ/người × 4 (cho Fantasy Park, Cầu Vàng)".

| Khoản | Giá một người planner dùng | Nguồn |
|---|---|---|
| Vé Sun World (24 điểm trên đỉnh Bà Nà) | 850.000đ, giá của POI Sun World (mức `expensive`) | nguồn giá của POI: 1.000.000đ khách ngoại tỉnh, 650.000đ khách Đà Nẵng, 500.000đ tuổi 18–25 |
| Vé phố cổ Hội An (23 điểm) | 250.000đ (mức `medium`) | 120.000đ khách nước ngoài, 80.000đ khách Việt |
| Vé Ngũ Hành Sơn (5 điểm) | 50.000đ (mức `cheap`) | 40.000đ |
| Cano Cửa Đại – Cù Lao Chàm | 260.000đ, khứ hồi trong ngày | VnExpress cập nhật 14/7/2026: vé ở bến 350.000đ = 260.000đ tiền cano + 70.000đ phí tham quan + 20.000đ phí môi trường, an ninh; phí tham quan đã nằm trong giá của chính Cù Lao Chàm. Vietnambooking (29/8/2026) ghi cano "khứ hồi trong ngày". Nắng Trip ghi 150.000đ, không ngày, không rõ một chiều hay khứ hồi. |

Vé của ba điểm cha tính theo giá của chính điểm cha khi nó là một điểm trong lịch (giữa mức giá), để hai cách đi cùng một chỗ tốn cùng một tiền. Vì vậy vé phố cổ Hội An đang tính cao gấp đôi giá thật (xem "Chưa làm").

**Code.**

- `transfers.json`: mỗi cửa ngõ có `fare`. Cano: `{"vnd": 260000, "per": "visit", "verified_by": "agent_web", "sources": [...]}`. Cáp treo: `{"ticket_of": "<Sun World>"}`, nghĩa là tiền cáp treo là vé Sun World và được tính qua `requires_ticket_of`. Đi bộ không có `fare`.
- Lúc nạp POI (`view_pois`), mỗi điểm nhận `access_fees`: vé của điểm cha (`kind: "ticket"`, `per: "trip"`) và tiền chặng (`kind: "transfer"`, `per: "visit"`). 53 điểm của danang-v2 có khoản này. Gate đọc nó qua `_gate_view`.
- Bộ giải: `StubPOI.access`. Ràng buộc ngân sách thêm một biến "phải trả" cho mỗi khoản: có điểm cần khoản đó mà điểm cha không nằm trong ngày thì phải trả. Lời giải mồi (`_greedy_hint`) giữ tiền vé cho điểm bắt buộc.
- Chuyến nhiều ngày: vé mua ở ngày trước không tính lại ở ngày sau (`paid_access`); cano tính lại mỗi ngày. Ngày 1 có Cầu Vàng (đã mua vé Sun World) thì điểm "Sun World Bà Nà Hills" ở ngày 2 tốn 0đ: chỉ điểm bán vé cho điểm khác (`sells_ticket`) được miễn, một quán ăn quay lại vẫn tính tiền.
- Replan `/v1/replan`: vé và cano mà điểm đã đi mua rồi thì phần còn lại của ngày không trả lại. Repair, bộ lọc ngân sách của retrieval, điểm xếp hạng giá (`rank`) và điểm của hồ sơ tiết kiệm đọc `visit_fee`: giá của điểm cộng tiền để tới được nó. Cầu Vàng không còn được gọi là "miễn phí".
- Audit (`BE/tools/audit_plans.py`) tự tính tiền từ dữ liệu thô (`requires_ticket_of` và `transfers.json`), không gọi code của app, nên một lỗi chung của bộ giải và gate vẫn lộ ra.

**Đo.** Kế hoạch cũ chấm bằng luật tiền mới (cùng bộ chấm, `--report-only`):

- Audit nhắm thẳng (15 yêu cầu, 45 kế hoạch; 11 yêu cầu ở trên thêm 4: gia đình 6 triệu, Chùa Cầu, động Huyền Không, Cù Lao Chàm một người 300k): trước **34/45** kế hoạch báo thiếu tiền, **8** thật ra vượt ngân sách; trung bình báo 713.000đ trong khi tiền thật 1.756.000đ. Vé bị bỏ sót: phố cổ Hội An 24 lần, Sun World 20, Ngũ Hành Sơn 3, cộng cano của mọi kế hoạch có đảo. Sau: 0 báo thiếu, 0 vượt ngân sách. 6 lịch rỗng là hai yêu cầu không đủ tiền thật: gia đình 4 người 3 triệu cho Bà Nà, và một người 300k cho Cù Lao Chàm (riêng cano và vé đảo đã 310.000đ).
- Audit chuẩn (`BE/tools/audit_plans.py`, 67 yêu cầu, 201 kế hoạch): trước **70/201** kế hoạch báo thiếu tiền và **16** thật ra vượt ngân sách. Gần như toàn bộ là vé phố cổ Hội An (132 lượt điểm con không trả vé, cộng 2 lượt Ngũ Hành Sơn), nhiều nhất ở hồ sơ trải nghiệm vì nó hay chọn hội quán, nhà cổ; không kế hoạch chuẩn nào có điểm trên đỉnh Bà Nà hay đảo. Ví dụ T04 (4 bạn, tối muộn, 3 triệu): báo 2.800.000đ, tiền thật 3.800.000đ. Sau: 0 báo thiếu, 0 vượt ngân sách, 201/201 qua gate và đi được, ý muốn đạt giữ nguyên 96/108. 52 kế hoạch trả vé phố cổ, 1 kế hoạch trả vé Ngũ Hành Sơn. Chi phí trung bình một kế hoạch: báo 1.004.000đ, tiền thật 1.216.000đ, sau 1.146.000đ (planner chọn lại điểm khi đã thấy vé).
- Lịch đổi: 64/201 kế hoạch giống hệt, 103/201 cùng tập điểm, 76/201 đổi tổng tiền. Mô hình CP-SAT đổi ở mọi yêu cầu có điểm con trong danh sách ứng viên (thêm biến "phải trả"), và điểm xếp hạng giá của các điểm con đổi, nên solver dừng ở lịch khác. Các cờ chất lượng đổi theo cả hai chiều: sạch 27 → 25 (chấm bằng bộ chấm cũ ở lần trước), khoảng trống dài 100 → 90, chặng dài 31 → 27, đến muộn 11 → 14, về sớm 9 → 12; đi lại trung bình 31,0 → 30,1 phút một ngày.
- Thời gian trả lời (mỗi bên một lần chạy, không xen kẽ, nên chỉ để biết không chậm đi rõ rệt): một ngày trung vị 6,0 → 5,4 giây, p95 9,3 → 8,3; hai ngày trung vị 10,8 → 11,0.

## Hợp đồng cho app

`segments[]` của kế hoạch (`BE/app/services/response.py`):

- `mode` vẫn là `"motorbike"` cho chặng thường. Chặng vào hoặc ra một nơi sau cửa ngõ ghi các phần theo thứ tự đi, nối bằng `+`: `"motorbike+boat"`, `"boat+motorbike"`, `"cable_car"` (từ chính ga chân núi lên đỉnh), `"cable_car+motorbike"`, `"motorbike+walk"`, và `"walk"` giữa hai điểm trên đỉnh Bà Nà.
- Có thêm `transfers: [{gateway, name, mode, minutes, km}]`, ví dụ `{"gateway": "cu_lao_cham_boat", "name": "Cano Cửa Đại - Cù Lao Chàm", "mode": "boat", "minutes": 30, "km": 16.5}`. `minutes` và `km` của segment đã gồm phần này.
- App hiện chưa đọc `segments`. Khi hiện chặng đi, nên ghi "xe máy 18 phút + cano 30 phút" thay vì "xe máy 48 phút".

Tiền (`plan_totals`):

- `total_cost` đã gồm vé của điểm cha và tiền chặng.
- Khi có khoản như vậy, plan có thêm `access_fees: [{key, kind, per, name, vnd_per_person, travelers, vnd, for, estimate, day?}]`, ví dụ `{"key": "ChIJyUQ4aw72QTERCXl5YV-4U1w", "kind": "ticket", "per": "trip", "name": "Sun World Bà Nà Hills", "vnd_per_person": 850000, "travelers": 4, "vnd": 3400000, "for": [<Fantasy Park>, <Cầu Vàng>], "estimate": false}`. `kind` là `"ticket"` (vé điểm cha) hoặc `"transfer"` (tiền chặng); `for` là các điểm cần khoản đó; `day` có ở chuyến nhiều ngày. Không có khoản nào thì không có trường này.
- App hiện chỉ đọc `total_cost`. Khi hiện chi phí, nên ghi thêm một dòng cho mỗi khoản, ví dụ "Vé Sun World Bà Nà Hills 850.000đ × 4 (cho Cầu Vàng, Fantasy Park)", để khách hiểu vì sao tổng cao hơn giá các điểm cộng lại.

## Gộp với nhánh khác

- `fix/transfer-fares` nằm trên `fix/non-road-legs`, nên gộp sau nhánh đó.
- `feat/single-poi-value` (chưa gộp) xung đột ở `BE/app/services/profiles.py` (import, `_score`, phần tính điểm nút). Khi giải: giữ cấu trúc `value_svc.score` của nhánh kia, giữ `paid=paid` cho `_score` (đường legacy), và trong `BE/app/services/value.py` đổi `effective_fee(poi)` ở `place_features` và `explain` thành `visit_fee(poi, paid_access(trip))`. Nếu không, dưới objective v1 hồ sơ tiết kiệm lại coi Cầu Vàng, nhà cổ Hội An là "miễn phí" và cộng điểm thưởng miễn phí, dù tiền vé vẫn bị tính.

## Thêm hoặc sửa một cửa ngõ

- Thêm POI mới trên đỉnh Bà Nà: thêm `{poi_id, name, status, lat, lon}` vào `places` của `ba_na_cable_car`. Test `BE/tests/data/test_transfers_v2.py` báo lỗi nếu một POI active của cụm `ba_na` chưa nằm sau cáp treo, hoặc tên, toạ độ lệch `pois.json`.
- Một cửa ngõ có id không còn trong ma trận thì bị bỏ qua lúc nạp, không làm hỏng ma trận; lý do nằm ở `doc["transfers"]["skipped"]`. Test dữ liệu đòi danh sách này rỗng.
- `road_end` có ba dạng: `{"poi_id": ...}` (một POI đứng ở đó), `{"own_row": true}` (hàng của chính nơi đó, chỉ cho cửa ngõ một nơi), `{"via": [{"poi_id", "minutes", "km"}]}` (chọn đường nhanh nhất qua vài POI gần, cộng một đoạn xe máy ngắn).

## Chưa làm

- **Giờ chạy của tàu và cáp treo.** Tàu du lịch ra Cù Lao Chàm phần lớn nghỉ ngoài tháng 3–8 (VnExpress), và chạy theo lịch cố định. Cáp treo Bà Nà mở 08:00, vé ngày lên lần cuối 16:30–17:00. Hiện `hours` của Cù Lao Chàm là `00:00-23:59`, nên planner vẫn có thể xếp đảo tới 20:00. Nên làm tiếp bằng `hours.access_window` như khung đường Sơn Trà.
- **Giá vé theo mức, không theo số tiền có nguồn.** `effective_fee` lấy giữa mức giá, nên vé phố cổ Hội An tính 250.000đ (nguồn: 120.000đ khách nước ngoài, 80.000đ khách Việt) và vé Sun World 850.000đ (nguồn: 1.000.000đ khách ngoại tỉnh). Sửa ở `effective_fee` sẽ đổi giá của mọi điểm, nên để việc riêng.
- **Vé trẻ em** (Sun World, nửa giá cano cho trẻ 1–8 tuổi) chưa mô hình hoá: mọi giá là giá người lớn.
- **Replan của app** (`planning_lifecycle`) lập lại phần còn lại mà không có các điểm đã đi. Nếu sáng đã lên Bà Nà (vé đã mua, khách tự ghi chi tiêu) và phần còn lại vẫn có một điểm trên đỉnh, vé bị tính lần nữa. Chỉ `/v1/replan` (`services/replan.py`) biết vé đã mua.
- **Khách sạn Mercure trên đỉnh làm điểm xuất phát:** lượt cáp treo xuống và lên lại không bị tính tiền (khoản gắn với điểm, không gắn với chặng).
- **Chuyến 2 ngày rải `must_visit`** (Cầu Vàng ngày 1, Fantasy Park ngày 2) vẫn có thể xảy ra: vé chỉ tính một lần (đúng với vé 3 ngày), nhưng khách phải lên núi hai lần.
- Mức giá (`price_level`) của điểm con vẫn là 1 (rẻ) khi chấm hợp mức chi tiêu; chỉ số tiền đã đúng.
- **Chuyến không có khách sạn (open tour):** ngày bắt đầu ở điểm đầu tiên, nên nếu đảo là điểm đầu thì chặng cano chiều đi không được tính. Trên `main`, chặng về khách sạn cuối ngày cũng chưa được tính. Nhánh `fix/return-leg-to-base` (chưa gộp) thêm chặng này; nó đọc cùng ma trận, nên khi gộp cả hai, chặng về từ đảo sẽ tự gồm cano.
- **Hàng của bến Cửa Đại là ước lượng** qua một quán gần bến (lệch vài phút). Dựng hàng OSRM thật cho bến cần Docker và OSRM.
- **Xếp hàng giờ cao điểm** ở cáp treo (vài phút tới vài chục phút) chưa tính.
- `BE/tools/coord_check_osm.py` (nhánh `feat/p0-coord-check-osm`) đọc `matrix.json` thô, nên vẫn báo hàng của Cù Lao Chàm sai. Đúng với hàng OSRM, nhưng planner đã đọc qua `transfers.json`.
