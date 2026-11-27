# Kiểm toạ độ Google bằng OpenStreetMap (P0, 26/11/2026)

- **Dữ liệu kiểm:** `danang-v2` trên `main` 707f084 (1029 POI, 916 active).
- **OSM:** Geofabrik `vietnam-latest`, dữ liệu tới 24/11/2026 (md5 `31c3d46b…`, đúng file đã dùng dựng ma trận ngày 25/11), cắt theo khung ma trận `107.85,15.72,108.55,16.3`.
- **Script:** [`BE/tools/coord_check_osm.py`](../../BE/tools/coord_check_osm.py). Script chỉ đọc: **không sửa `pois.json`, không dựng lại ma trận**.
- **Chi tiết từng POI:** [`coord_check.csv`](coord_check.csv), mỗi POI một dòng, có link bản đồ.

## Kết luận ngắn

- Đã kiểm **613 POI active** có toạ độ chưa từng đối chiếu: 596 lấy từ Google, 17 nhập tay. 65 POI đã bị loại (excluded) cũng có trong CSV nhưng không tính vào các số dưới đây.
- **Ở những chỗ OSM có dữ liệu, toạ độ Google đúng.** 197 POI (32%) tìm thấy trong OSM và cách nhau không quá 100 m: trung vị 4 m, 90% dưới 31 m.
- **Chỉ 9 POI lệch với OSM hơn 100 m.** Xem từng cái thì phần lớn không phải lỗi: quán có nhiều chi nhánh, hoặc OSM vẽ một chỗ khác của cùng khu. **Còn 2 điểm nghi sai thật**, cần người xem ảnh vệ tinh: Nhà thờ Phú Thượng (lệch 517 m) và Quán Hải sản Bà Tám (cách 430 m con đường ghi trong nguồn).
- **Lỗi lớn nhất nằm ở ma trận, không ở toạ độ.** OSRM gắn Cù Lao Chàm (một hòn đảo) vào đất liền. Vì vậy ma trận ghi phố cổ Hội An ↔ Cù Lao Chàm là **20 phút, 9,6 km xe máy** (cả hai chiều), trong khi đường chim bay đã 22 km và thực tế phải đi tàu.
- **Không thấy toạ độ kiểu "tâm thành phố".** Không POI nào nằm đúng tâm một địa danh OSM. Chỉ có 2 cặp trùng điểm: 2 khách sạn, và 1 tour nhập tay đặt đúng toạ độ Sơn Trà Marina.
- **Giới hạn:** **407 POI (66%) không có trong OSM** (phần lớn là quán cà phê, nhà hàng, spa, bar), nên OSM không kiểm được. Riêng 62 POI có địa chỉ trong tên hoặc trong ghi chú nguồn: 55 nằm cách đúng con đường đó dưới 60 m.

## Một ví dụ

**"Hải Sản Đà Nẵng Bé Biển"** (toạ độ Google):

1. Bỏ dấu và các chữ chung ("hải sản", "Đà Nẵng"), còn lại "Bé Biển".
2. OSM có nhà hàng "Bé Bien" (`amenity=restaurant`) cách ghim **11 m**.
3. Cùng tên, cùng loại, rất gần, nên kết quả là **ok**.

**"Nhà thờ Phú Thượng"**: OSM có "nhà thờ Phú Thượng", cùng tên, cùng loại (nơi thờ tự), nhưng cách **517 m**. Vì vậy điểm này bị đánh **off**, đưa vào P1.

## Cách làm

1. **Tìm cùng một nơi trong OSM** (10 896 vật có tên):
   - Tên được bỏ dấu, bỏ chữ chung (quán, nhà hàng, cà phê, Đà Nẵng…). Loại của vật OSM không được trái loại của POI (quán cà phê không khớp khách sạn).
   - **Xác nhận** (≤ 100 m): khớp tên lỏng. Ví dụ tên này nằm trong tên kia ("Àla Cafe" / "Àla Cafe Roaster"), gõ sai 1 chữ ("Oani" / "Aoni"), viết liền ("Levenin" / "Le Vénin").
   - **Nghi lệch** (> 100 m): khớp tên chặt.
     - Dấu thanh phải giống: "Phước Tường" khác "Phước Tượng".
     - Tên đường, phường và số nhà bị bỏ trước khi so: "PNJ Liên Chiểu" chỉ còn "PNJ".
     - Tìm trong 300 m, rồi 1 km, rồi cả vùng. Ra cả vùng thì phải trùng ít nhất 2 chữ thật.
     - Quán hay khách sạn trùng tên ở xa thường chỉ là chi nhánh khác, nên được xếp `ambiguous` chứ không phải `off`.
   - Khoảng cách đo tới hình của vật OSM: 0 m nếu ghim nằm trong toà nhà hay công viên.
2. **Kiểm thêm, không cần OSM có nơi đó:**
   - Địa chỉ trong tên hoặc trong ghi chú nguồn (trang giá, trang giờ), so với chính con đường đó. Địa chỉ cũng dùng để phân xử khi OSM có một nơi trùng tên ở xa.
   - Khoảng cách tới đường xe máy gần nhất (OSRM gắn ghim vào đường đó).
   - Hàng của POI trong ma trận: đường đi không thể ngắn hơn đường chim bay.
   - Nhiều POI chung một điểm.
3. **Tự kiểm bộ so khớp:** chạy trên 303 POI vốn lấy toạ độ từ OSM. Có 298 tìm đúng vật của chính nó, 4 khớp vật khác cách dưới 100 m, 1 không thấy. Test: [`BE/tests/unit/test_coord_check_osm.py`](../../BE/tests/unit/test_coord_check_osm.py).

## Số liệu theo vùng và loại (POI active)

Ý nghĩa các cột kết quả:

- `ok`: khớp OSM trong 100 m.
- `check`: lệch 100–300 m.
- `off`: lệch hơn 300 m.
- `ambiguous`: chỉ trùng tên với chuỗi hoặc chi nhánh ở xa.
- `no_osm`: OSM không có nơi này.

Ý nghĩa các cột P (mức ưu tiên xem lại):

- P1: gần như chắc có vấn đề.
- P2: nên xem.
- P3: OSM không kiểm được, xem bằng mắt khi có thời gian.

| vùng | ok | check | off | ambiguous | no_osm | P1 | P2 | P3 | tổng |
|---|---|---|---|---|---|---|---|---|---|
| trung_tam | 69 | 1 | 0 | 2 | 153 | 1 | 4 | 30 | 225 |
| son_tra_my_khe | 83 | 0 | 2 | 1 | 118 | 0 | 4 | 24 | 204 |
| hai_van_lien_chieu | 11 | 0 | 0 | 0 | 87 | 0 | 1 | 17 | 98 |
| ngu_hanh_son | 28 | 0 | 0 | 0 | 35 | 0 | 1 | 13 | 63 |
| hoi_an | 5 | 0 | 0 | 0 | 9 | 1 | 1 | 9 | 14 |
| ba_na_tay | 1 | 1 | 2 | 0 | 5 | 2 | 2 | 2 | 9 |
| **tổng** | **197** | **2** | **4** | **3** | **407** | **4** | **13** | **95** | **613** |

| loại | ok | check | off | ambiguous | no_osm | P1 | P2 | P3 | tổng |
|---|---|---|---|---|---|---|---|---|---|
| restaurant | 34 | 0 | 0 | 1 | 74 | 1 | 1 | 0 | 109 |
| cafe | 19 | 0 | 1 | 2 | 85 | 0 | 2 | 0 | 107 |
| lodging | 44 | 1 | 0 | 0 | 30 | 0 | 3 | 0 | 75 |
| wellness | 7 | 0 | 1 | 0 | 67 | 0 | 0 | 0 | 75 |
| nightlife | 17 | 0 | 0 | 0 | 54 | 0 | 1 | 0 | 71 |
| religious | 25 | 1 | 1 | 0 | 27 | 1 | 1 | 27 | 54 |
| day_market | 13 | 0 | 0 | 0 | 17 | 0 | 0 | 17 | 30 |
| outdoor_landmark | 13 | 0 | 0 | 0 | 16 | 0 | 0 | 16 | 29 |
| paid_attraction | 7 | 0 | 1 | 0 | 21 | 2 | 2 | 20 | 29 |
| beach | 7 | 0 | 0 | 0 | 10 | 0 | 2 | 10 | 17 |
| viewpoint | 3 | 0 | 0 | 0 | 4 | 0 | 1 | 3 | 7 |
| museum_indoor | 6 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 7 |
| night_market | 2 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 3 |
| **tổng** | **197** | **2** | **4** | **3** | **407** | **4** | **13** | **95** | **613** |

Theo nguồn toạ độ:

- Google, 596 POI: ok 187, check 2, off 4, ambiguous 3, no_osm 400.
- Nhập tay, 17 POI: ok 10, no_osm 7.

## 10 trường hợp lệch nhất (đã xem từng cái)

Ở cột link:

- **G**: trang Google Maps của nơi đó.
- **ghim**: toạ độ đang có trong dữ liệu.
- **OSM**: vật OSM khớp với nó.
- **2 điểm**: mở cả ghim và vật OSM trên cùng một bản đồ.

| # | POI | lệch | nhận định | link |
|---|---|---|---|---|
| 1 | Trung Nguyên Legend Café (Sơn Trà) | 5,7 km tới "Trung Nguyên Legend" ở trung tâm | chuỗi, OSM là chi nhánh khác → **giữ** (P2, chỉ cần xác nhận có chi nhánh Sơn Trà) | [G](https://www.google.com/maps/place/?q=place_id:ChIJJS-cJ58XQjERxgFIfN6CjJ0) · [ghim](https://www.openstreetmap.org/?mlat=16.103292&mlon=108.25765#map=18/16.103292/108.25765) · [OSM](https://www.openstreetmap.org/node/729406850) |
| 2 | Sun World Bà Nà Hills | 5,6 km tới khu vui chơi OSM | ghim Google nằm ở khu ga cáp treo chân núi (cách nhà ga cáp treo 169 m, phòng vé 236 m, điểm dừng "Bãi đỗ xe Bà Nà Hills" 377 m). OSM vẽ khu trên đỉnh. Ghim này đúng là chỗ đi xe tới → **giữ** (script để P1) | [G](https://www.google.com/maps/place/?q=place_id:ChIJyUQ4aw72QTERCXl5YV-4U1w) · [ghim](https://www.openstreetmap.org/?mlat=16.026563&mlon=108.032812#map=18/16.026563/108.032812) · [OSM](https://www.openstreetmap.org/way/359114064) |
| 3 | Gyu Sachi | 3,7 km tới "Gyu Sachi" | nguồn giá ghi "54–56 Quang Trung", ghim cách đường Quang Trung 8 m → OSM là cơ sở khác → **giữ** (script tự bỏ khỏi danh sách) | [G](https://www.google.com/maps/place/?q=place_id:ChIJJSd-naoZQjERheTI-IEkRrc) · [ghim](https://www.openstreetmap.org/?mlat=16.075055&mlon=108.22075#map=18/16.075055/108.22075) · [OSM](https://www.openstreetmap.org/node/12836656107) |
| 4 | Highlands | 926 m tới "Highlands Coffee" | chuỗi (OSM gắn thẻ `brand`) → **giữ** | [G](https://www.google.com/maps/place/?q=place_id:ChIJ55nxA9MZQjERNOaUcyvyXxg) · [ghim](https://www.openstreetmap.org/?mlat=16.065478&mlon=108.194781#map=18/16.065478/108.194781) · [OSM](https://www.openstreetmap.org/node/6520986631) |
| 5 | M'healthy spa | 844 m tới "M'Healthy - Nails & Spa" | trang chính ghi 52 Hoàng Kế Viêm, ghim cách đường đó 13 m. OSM là cơ sở ở 7/14 Lưu Quang Thuận → **giữ** | [G](https://www.google.com/maps/place/?q=place_id:ChIJmwtSJxYXQjERqyw4BIsIRV4) · [ghim](https://www.openstreetmap.org/?mlat=16.048425&mlon=108.242608#map=18/16.048425/108.242608) · [OSM](https://www.openstreetmap.org/node/12378143501) |
| 6 | **Nhà thờ Phú Thượng** | 517 m tới "nhà thờ Phú Thượng" | cùng tên, cùng loại. OSM không có toà nhà nhà thờ ở cả hai điểm. Điểm OSM chỉ là một chấm, được gắn tên đường tránh Nam Hải Vân – Túy Loan, nên có thể chính OSM sai → **xem ảnh vệ tinh (P1)** | [G](https://www.google.com/maps/place/?q=place_id:ChIJY3yT3IweQjERnbDRpKk8b3A) · [2 điểm](https://www.openstreetmap.org/directions?route=16.050763%2C108.103519%3B16.046395%2C108.105258) |
| 7 | **Quán Hải sản Bà Tám** | cách đường 2 Tháng 9 430 m | nguồn giá ghi "K126/2 đường 2 Tháng 9". "Bà Tám" là tên rất phổ biến, nên ghim có thể là một quán khác cùng tên → **xem (P1)** | [G](https://www.google.com/maps/place/?q=place_id:ChIJUahp7dYZQjERa6ryX2z_stg) · [ghim](https://www.openstreetmap.org/?mlat=16.049758&mlon=108.218113#map=18/16.049758/108.218113) |
| 8 | The Hideout café | 427 m tới "Hideout Cafe" | Foody ghi 95 Đỗ Bá. Ghim cách đường gần hơn trong hai đường Đỗ Bá / Nguyễn Văn Thoại 125 m → **xem (P2)** | [G](https://www.google.com/maps/place/?q=place_id:ChIJKbpWc6IXQjERMZMSscftz9I) · [2 điểm](https://www.openstreetmap.org/directions?route=16.053405%2C108.240431%3B16.050788%2C108.243369) |
| 9 | Seahorse (khách sạn) | 236 m tới hostel "Seahorse" | có thể là 2 cơ sở khác nhau → **xem (P2)** | [G](https://www.google.com/maps/place/?q=place_id:ChIJEa410zMYQjER3f11TKinbkU) · [2 điểm](https://www.openstreetmap.org/directions?route=16.069096%2C108.22291%3B16.067802%2C108.224662) |
| 10 | Nhà thờ cổ Tùng Sơn | 202 m tới "nhà thờ Tùng Sơn" | điểm OSM cùng kiểu với Phú Thượng (một chấm, gắn tên đường tránh) → **xem (P2)** | [G](https://www.google.com/maps/place/?q=place_id:ChIJs4dg5vceQjERJQ5D9ATvWhU) · [2 điểm](https://www.openstreetmap.org/directions?route=16.062535%2C108.096007%3B16.060964%2C108.096969) |

## Danh sách đề xuất xem lại

### P1: 4 POI

- **Nhà thờ Phú Thượng**: xem ảnh vệ tinh, chọn ghim Google hay điểm OSM (mục 6 ở bảng trên).
- **Quán Hải sản Bà Tám**: xem Google Maps / Street View. Quán ở K126/2 đường 2 Tháng 9 hay ở chỗ ghim hiện tại (mục 7)?
- **Cù Lao Chàm** (nhập tay, OSM xác nhận ghim nằm trên đảo): toạ độ không sai, **ma trận sai**.
  - Ghim cách đường xe máy gần nhất 870 m, nên OSRM gắn nó vào đất liền.
  - 26,5% chặng của nó (tới các điểm cách hơn 2 km) ngắn hơn đường chim bay.
  - Cần biểu diễn chặng tàu: điểm đặt ở bến tàu, cộng thời gian tàu.
  - Cho tới lúc sửa, kế hoạch có thể xếp đảo như một chặng xe máy 20 phút.
  - [ghim](https://www.openstreetmap.org/?mlat=15.950859&mlon=108.52272#map=14/15.950859/108.52272)
- **Sun World Bà Nà Hills**: đề xuất **giữ** (mục 2). Script vẫn để P1 vì nó không tự biết đâu là lối vào.

### P2: 13 POI

- **The Hideout café, Seahorse, Nhà thờ cổ Tùng Sơn**: mục 8–10 ở bảng trên.
- **Trung Nguyên Legend Café**: chỉ cần xác nhận có chi nhánh ở Sơn Trà (mục 1).
- **Hotel Hồng Phúc 2 và Khách Sạn Rose**: hai khách sạn cách nhau 2,4 m, nên có thể một ghim là ghim đoán. [ghim](https://www.openstreetmap.org/?mlat=16.07299&mlon=108.188215#map=19/16.07299/108.188215)
- **Sơn Trà Marina và Tour lặn ngắm san hô (bến CT15)**: tour nhập tay đang dùng đúng toạ độ của Marina. Cần xác nhận bến CT15 có ở Marina không. [ghim](https://www.openstreetmap.org/?mlat=16.096837&mlon=108.26696#map=18/16.096837/108.26696)
- **Vive Océane**: địa chỉ 5 Trường Sa là của cả khu Hyatt. Ghim nằm ở bãi biển, cách đường Trường Sa 226 m, có lẽ vẫn đúng.
- **Điểm xa đường xe máy.** Ma trận tính phút tới con đường gần nhất, không phải lối vào thật:
  - **Bãi Sủng Cỏ**: cách 1,3 km, phải đi thuyền hoặc đi bộ.
  - **Đỉnh Bà Nà**: cách 367 m, phải lên bằng cáp treo. Ma trận ghi Đỉnh Bà Nà → Sun World Bà Nà Hills là 36 phút, 18 km xe máy.
  - **Bãi Cát Vàng**: cách 401 m.
  - **VinWonders Nam Hội An**: cách 215 m. Khu này rộng, có lẽ ổn.

### P3: 95 địa điểm tham quan hoặc chợ mà OSM không có

Gồm 27 nơi thờ tự, 20 điểm có vé, 17 chợ, 16 cảnh quan, 10 bãi biển và các loại khác. OSM không kiểm được nhóm này, chỉ xem được bằng mắt. Lọc `review = P3` trong CSV. Cột `why` ghi tên gần giống gần nhất nếu có.

### Phụ: 13 liên kết `ext_ids.osm` cũ nối nhầm sang nơi khác

Các liên kết này lấy từ `BE/data/sources/osm_match.json` (ngày 20/11, khớp tên kiểu `difflib` ≥ 0,6 trong 120 m). Danh sách:

- TGT Beach Hotel → "Lucia beach hotel"
- CẬU CẢ → "Mắt kính Điện Biên Phủ" (một tiệm kính)
- Wind Garden Coffee → "Cloud Garden Cafe"
- Holiday Beach Hotel → "Holiday Beach Club"
- H Coffee → "Alo Coffee"
- P Coffee → "Tigon Coffee"
- L Stand Coffee and Tea → "D.coffee"
- Lá sen Spa → "Lee Spa"
- Elites Hotel → "The Legend Hotel"
- NYX Sky Lounge → "Sophie Mixology"
- Sound Cafe → "Spanda Yoga Café"
- Lounge Beach bar → "4U Restaurant"
- Ngụ coffee → "MatBien Coffee"

Hiện **không có dữ liệu nào lấy qua các liên kết này** (giờ, món, wikidata đều không dùng). Dù vậy nên xoá để lần nhập dữ liệu OSM sau không kéo nhầm.

Cột `prev_osm_link` / `prev_link_same` trong CSV có đủ 23 trường hợp liên kết cũ khác kết quả mới: 13 cái ở trên, và 10 cái khác.

- 5 cái là cùng nơi nhưng khác vật OSM: Động Âm Phủ, Hồ Hòa Trung, Sandy Beach Non Nuoc Resort, Chùa Linh Ứng – Bà Nà, The Ocean Villas.
- 5 cái đáng ngờ:
  - Lagoon Rooftop → "Duy Tịnh Rooftop Bar"
  - Thuyền Thúng Tượng Thúy → "Hoi An Basket Boat"
  - Nhà Hàng Chay Phúc An → "…Thúp An"
  - Cửa hàng Đặc Sản Đà Nẵng Làm Quà → "Dac San Da Nang"
  - Sun World Bà Nà Hills → bảng thông tin "Failyland of Ba Na Hills"

## Giới hạn

- OSM không phải chuẩn đúng. Hai nhà thờ ở trên có thể là OSM sai.
- Lệch dưới 100 m (ghim sang toà nhà bên cạnh) thì không bắt được, nhưng gần như không đổi số phút xe máy.
- 66% POI không có trong OSM. Với nhóm này, "không thấy" không có nghĩa là "đúng".
- Ngưỡng so tên được chỉnh trên chính dữ liệu này: test ghi lại các ví dụ đúng và sai. OSM thêm quán thì chạy lại script.

## Sửa thế nào sau khi duyệt

- `decisions_*.json` hiện chỉ đổi được tên, trạng thái và loại, **không đổi được toạ độ**. Muốn sửa toạ độ phải thêm một loại file nguồn cho `BE/ml/data/migrate_v2.py` đọc. Ví dụ `location_fix_*.json`, mỗi dòng gồm `lat`, `lon` và URL bằng chứng.
- Sau đó dựng lại các hàng ma trận của những POI đã sửa. Việc này cần Docker và OSRM, như lần dựng ngày 25/11.
- Chạy lại kiểm tra (khoảng 8 giây):

  ```bash
  python BE/tools/coord_check_osm.py --pbf <danang.osm.pbf> --validate --print-md
  ```
