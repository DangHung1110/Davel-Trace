# Đề xuất verify POI chính xác (Phase 4)

Ngày: 29/10/2026. Nhánh: `task/stable-p4-verify-data` (P1–P3 + dữ liệu verify của
`exp/full-audit`). Bổ sung cho `docs/verify-criteria.md`, không thay thế nó.

## 1. Verify để làm gì

Planner chỉ được xếp POI có `verified=true` (cổng FAR). Mỗi trường POI đi thẳng vào
lịch, nên dữ liệu crawl sai thì lịch sai:

| Trường | Planner dùng để | Sai thì |
|---|---|---|
| Toạ độ | thời gian di chuyển (matrix) | dẫn khách tới chỗ khác |
| Giờ mở cửa | khung giờ được ghé | **thiếu giờ = planner coi mở suốt chuyến** (`optimizer.poi_window`) |
| Loại hình (`cat`) | bữa trưa, template, mong muốn ("bảo tàng") | quán ăn lọt vào ô tham quan |
| Thời lượng (`visit_min`) | độ dài mỗi điểm, giờ về | lịch tràn giờ hoặc trống |
| Trùng lặp | 3 phương án phải khác nhau | "khác nhau" nhưng cùng một chỗ |

## 2. Hiện trạng đo được

**Đợt auto của `exp/full-audit`.** `spotcheck_v2` (chỉ kiểm cấu trúc) đã bật 362 POI.
Tổng hiện có 410 verified (362 `auto-verify-v1` + 48 `spotcheck-v1`).

**Planner trên dữ liệu này.** Chạy 7 kịch bản, 3 hồ sơ mỗi kịch bản: mọi mong muốn đều
đạt, mọi plan đều pass, p50 5.9s. **Khoảng 85% POI xuất hiện trong plan là POI auto.**
Chất lượng lịch vì vậy phụ thuộc trực tiếp vào độ chính xác của đợt auto.

**Độ chính xác của luật auto.** Cách đo: chạy luật auto trên 48 dòng đã có nhãn người
(`SPOT_CHECK.md`).

| | Người: Đúng | Người: Sai |
|---|---|---|
| auto_pass | 34 | **5** |
| queue | 4 | 5 |

- Precision của auto_pass là **34/39 = 87%** (khoảng tin cậy Wilson 95%: 73–94%).
  Mẫu có cố ý thêm outlier, nên con số này có thể bi quan; dù vậy cận dưới vẫn dưới 90%.
- Luật **bỏ lọt 5/10 lỗi** người đã bắt:
  - sai loại hình (bãi biển gắn nhãn "điểm tham quan");
  - trùng lặp khác ngôn ngữ ("Bãi biển Sơn Trà" và "Son Tra Beach", cách nhau 99m);
  - thời lượng vô lý (đình làng 240 phút, chợ dân sinh 90 phút);
  - không phải điểm tham quan riêng ("Khu Dừng Chân").
- Nhận định: kiểm cấu trúc không thay được kiểm **bản chất** và **thời lượng**.

**Nguồn thứ hai.**
- `osm_evidence` có sẵn chỉ xác nhận 31/362 POI auto (gần và cùng tên). Có 53 dòng
  ghép nhầm với node gần nhất nhưng khác tên.
- Ghép lại từ đầu với file OSM Việt Nam đầy đủ (8,358 đối tượng có tên trong bbox; khớp
  tên bỏ dấu, nhiều biến thể tên, bán kính 150m): **265/742 POI (36%)**.
  - Nhóm tham quan: landmark 54/85, nature 11/16, museum 9/15, market 31/49, attraction 33/87.
  - Nhóm quán xá: restaurant 38/128, cafe 21/108, spa 6/77, bar 12/69.
  - Giờ mở cửa so được 37 cặp.

## 3. Nguyên tắc

1. **Verify theo từng trường, không chỉ một cờ chung.** Ví dụ
   `verification = {exists, location, category, hours, duration}`, mỗi trường có một
   mức: `confirmed` (≥2 nguồn độc lập đồng ý), `single`, `conflict`, `assumed`.
   `verified=true` chỉ là kết quả tổng hợp: exists, location, category đạt `confirmed`
   và hours không phải `conflict`.
2. **Tự động = đồng thuận ≥2 nguồn độc lập.** Một nguồn thì chưa được xác nhận. Hai
   nguồn mâu thuẫn thì đưa người xử lý, kèm bằng chứng hai nguồn hiển thị cạnh nhau.
3. **Đo trước khi tin.** Mỗi đợt auto lấy 50 POI ngẫu nhiên, phân tầng theo category,
   cho 2 người duyệt độc lập (đo đồng thuận Cohen's κ). Chỉ bật đợt đó khi precision
   ≥ 95% **và** cận dưới khoảng tin cậy ≥ 90%.
4. **Planner dùng được mức tin.** Trường `assumed`/`single` vẫn dùng được, nhưng phải
   kèm cảnh báo và ràng buộc an toàn, không được im lặng.

## 4. Pipeline `auto-verify-v2`

| Tầng | Việc | Trạng thái |
|---|---|---|
| 0. Cấu trúc | `spotcheck_v2` A1–A7 | có sẵn |
| 1. Đối chiếu chéo | OSM local (miễn phí, đã có extract), Wikidata cho địa danh; **VietMap Place/Search** cho quán xá (cần key, khoảng 700 request, xem ToS); làm mới Google để có `business_status`, số review, giờ | OSM đã chạy thử được |
| 2. Người | chỉ xử lý `conflict` và `single` của nhóm tham quan; trang duyệt có ô sửa giờ, loại hình, thời lượng | cần sửa trang |
| 3. Đo và gate | mẫu ngẫu nhiên 50 POI, 2 người, precision/κ | chưa có |

Luật ghép nguồn:
- tên bỏ dấu, dùng mọi biến thể (`name`, `name:vi`, `name:en`, `alt_name`);
- tách từ loại hình phổ biến (bãi biển/beach, chùa/pagoda);
- đo khoảng cách tới **hình học** của đối tượng (bãi biển dài đo tới đường bờ), không đo
  tới tâm;
- tag OSM (`tourism=museum`, `natural=beach`, `amenity=place_of_worship`...) ánh xạ
  sang `cat` làm nguồn thứ hai cho loại hình.

## 5. Từng trường tự động được tới đâu

| Trường | Tự động? | Cách | Còn cần người |
|---|---|---|---|
| Toạ độ trong vùng, định dạng | Có, 100% | tầng 0 | không |
| Tồn tại + vị trí | Có, khi có nguồn 2 | OSM (36%; tham quan 50–65%) + VietMap/Google cho quán xá | POI chỉ có 1 nguồn |
| Loại hình | Phần lớn | tag OSM + type Google | conflict |
| Giờ mở cửa | Một phần | Google/VietMap; OSM chỉ 37 cặp | phần còn lại, hoặc dùng mặc định an toàn (mục 6.2) |
| Thời lượng | **Không** verify bằng nguồn được | prior theo loại (`duration_prior.json`) + trần theo loại (đình ≤ 45 phút, chợ dân sinh ≤ 60 phút) | outlier |
| Giá vé | Ít nguồn | trang chính thức (danangfantasticity), người | phần lớn |

Kết luận: **không có cách tự động nào chính xác 100%**. Nhưng có thể tự động hoá phần
lớn với **độ chính xác đo được**: đồng thuận ≥2 nguồn, người chỉ xử lý phần mâu thuẫn,
và gate bằng mẫu ngẫu nhiên. Độ phủ của VietMap/Google cho quán xá **chưa đo được**:
cần thử 50 POI trước khi cam kết con số.

## 6. Việc sửa trước khi giao người duyệt

1. **`queue_hash` phụ thuộc hệ điều hành.** Trang hiện tại được dựng trên Windows (CRLF)
   nên hash là `83541d50`; dựng lại trên macOS/Linux (LF) ra `551c8101` dù dữ liệu y hệt.
   Cần hash trên nội dung đã chuẩn hoá (các dòng JSON đã parse), không hash byte thô.
2. **Thiếu giờ chiếm 239/332 dòng.** Cần thêm ô nhập giờ; bấm "Đúng" mà không kèm giờ
   thì POI giữ `verified=false`. Song song, sửa planner để POI thiếu giờ dùng **khung an
   toàn theo loại** (ví dụ đình/chùa 07:00–17:00), có cảnh báo, thay vì coi như mở suốt chuyến.
3. **Bỏ 76 lodging khỏi hàng đợi.** Retrieval đã loại lodging, nên duyệt chúng là công thừa
   (23% hàng đợi).
4. **Thứ tự ưu tiên:** landmark (62), attraction (56), nature (14), park (8), museum (7),
   beach (5), viewpoint (1). Bar/spa đã có 47/48 POI từ đợt auto.
5. **Bbox → vùng phục vụ.** Từ 1/7/2025 Quảng Nam đã nhập vào TP Đà Nẵng, nên "nằm trong
   Đà Nẵng" phải bao gồm cả Hội An. VinWonders Nam Hội An (15.789N) đang bị `fail` oan.
   Matrix Phase 3 đã phủ tới 15.65N.
6. **Tool ingest verdict** (`verify_verdicts_*.jsonl` → `pois.json`, ghi `verified_by`,
   người duyệt, thời điểm, ghi chú, có kiểm hash): chưa có.
7. **Soát mẫu 362 POI auto:** 50 POI ngẫu nhiên phân tầng, theo mục 3.3.

## 7. Thứ tự làm đề xuất

1. Sửa mục 6.1–6.6, rồi giao trang duyệt cho người (khoảng 2 giờ công với 256 dòng sau
   khi bỏ lodging).
2. Đưa đối chiếu OSM (tầng 1) thành tool và chạy trên toàn bộ 742 POI (miễn phí).
3. Thử VietMap Place cho 50 quán xá để đo độ phủ, rồi quyết định có chạy đủ 700 request
   không.
4. Lấy mẫu 50 POI auto để đo precision. Nếu dưới gate thì hạ cờ có chọn lọc (chỉ những
   dòng `single`/`conflict`), không hạ toàn bộ.
