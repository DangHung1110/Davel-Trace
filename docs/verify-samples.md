# Mẫu dữ liệu verify: 1 POI đã verify và các POI chưa hoàn chỉnh

Ngày: 29/10/2026. Nhánh: `task/stable-p4-verify-data`. Dữ liệu: `BE/data/snapshots/danang-v1/pois.json`
(410 POI `verified=true`: 362 `auto-verify-v1`, 48 `spotcheck-v1`). Đọc kèm `docs/verify-proposal.md`.

Mọi con số dưới đây đếm trực tiếp trên `pois.json`. Mục "planner thấy" là giá trị planner thực sự dùng
(`rank.py`, `profiles.py`, `optimizer.py`, `BE/common.py`).

## 1. 410 POI verified đang thiếu trường nào

| Trường | Planner dùng để | Tình trạng trong 410 POI |
|---|---|---|
| `opening_hours` | khung giờ được ghé | 406 có, **4 trống** (planner coi là mở suốt chuyến). 354 chỉ có một nguồn là Google crawl. 9 POI có giờ là **suy luận**, không phải dữ liệu (8 trong số đó là 24/7). |
| `fee` (vé vào cửa) | ngân sách, hồ sơ tiết kiệm | **0 cho cả 410 POI**. 7 POI có `ticket_vnd` > 0 (bảo tàng 20–140k, Mikazuki 350k) nhưng planner chỉ đọc `fee`, nên coi là miễn phí. |
| `price_level` (1–3) | khớp mức chi tiêu, phạt giá ở hồ sơ tiết kiệm, đặc trưng của model PATM | **239/410 (58%) là số 2 mặc định** của bước crawl (`fetch_serpapi.py:184`), không có bằng chứng giá. Cả 48 spa đều thuộc nhóm này. |
| `rating` | điểm xếp hạng (trọng số 0.22), điểm hồ sơ | 401 có, 9 null. **Số lượt review: 0/410**, crawl không lưu và raw crawl không còn trong repo. 51 POI có rating ≥ 4.9. |
| `visit_min` | thời lượng ghé | **408/410 là luật theo loại** (`dur_confidence: low`). Cây cầu 200 phút, tiệm hoa 90 phút. |
| Loại hình, tồn tại | ô bữa ăn, mong muốn | 5 POI có tag hoặc tên đáng ngờ ("Văn phòng công ty", "shop online", "điện hoa"), cần người xem. Ít nhất 2 trong số đó không phải điểm đến cho khách (mục 3.5). |

Về giờ mở cửa, dữ liệu có hai lỗi đọc trong code (dữ liệu đúng, planner hiểu sai):

- **Khung qua nửa đêm.** `parse_hours("19:30-03:00")` trả về (1170, 180). Optimizer yêu cầu giờ bắt đầu
  cộng thời lượng ≤ giờ đóng (`optimizer.py:243`), nên khung này không bao giờ thỏa. 74 POI verified bị
  ảnh hưởng, trong đó có **40/47 bar**: planner không bao giờ xếp được chúng.
- **Chỉ đọc khung đầu tiên.** Với "10:30-14:00, 17:30-20:45", planner chỉ thấy ca trưa. Có 30 POI verified
  mà planner thấy đóng cửa sớm hơn giờ đóng muộn nhất trong dữ liệu.
- Ngoài ra, bước crawl gộp giờ của 7 ngày thành một chuỗi và bỏ ngày nghỉ (`fetch_serpapi.parse_hours`),
  nên planner không biết thứ Hai bảo tàng có đóng cửa hay không.

Về nguồn: theo trường `verified_by`, 362 POI được bật bằng luật tự động `spotcheck_v2` (chỉ kiểm cấu trúc).
Phần làm tay có commit là giờ cho 96 POI (`hours_web.json`) và giá vé cho 33 POI (`price_web.json`). Nếu
410 POI đều đã được người xem, nên ghi lại đúng nguồn `verified_by`, để sau này còn đo được độ chính xác.

## 2. Một POI đã verify: Bảo tàng Điêu khắc Chăm Đà Nẵng

Đây là POI có nhiều bằng chứng nhất: giờ có nguồn web, giá vé có 2 nguồn, và OSM khớp tên.

```json
{
  "poi_id": "ChIJLWoAs80ZQjERLKHDYD-ZymI",
  "name": "Bảo tàng Điêu khắc Chăm Đà Nẵng",
  "cat": "museum",
  "lat": 16.0603007, "lon": 108.2232677,
  "opening_hours": ["07:00-17:00"],
  "web_evidence": {"hours_web": "07:00-17:00"},
  "visit_min": {"p25": 140, "p50": 200, "p75": 280},
  "dur_source": "category_rule", "dur_confidence": "low",
  "fee": 0,
  "ticket_vnd": 60000,
  "ticket_note": "NL 60k; ĐN thường trú+SV 20k; miễn phí <16t và 3 lễ/năm",
  "price_sources": ["https://hoiandriver.com/...", "https://www.vietnamairlines.com/..."],
  "price_level": 2,
  "smart_tags": {"ticket": true, "price_band": "cheap"},
  "rating": 4.2,
  "osm_evidence": {"osm": "node/4259583469", "dist_m": 123.9, "name": null},
  "must_go": true,
  "source": "serpapi/google-maps",
  "verified": true, "verified_by": "auto-verify-v1", "verified_at": "2026-10-29"
}
```

| Trường | Giá trị | Nguồn | Mức tin | Planner thấy |
|---|---|---|---|---|
| Tồn tại, vị trí | 16.0603, 108.2233 | Google + OSM (`tourism=museum`, cùng tên, cách 7.7m khi ghép lại) | **confirmed** (2 nguồn) | đúng |
| Loại hình | museum | type Google + tag OSM | **confirmed** | đúng |
| Giờ | 07:00–17:00 | Google + web | **confirmed** | đúng |
| Vé | 60.000đ | 2 trang web | **confirmed** | **0đ** (planner đọc `fee`) |
| Mức giá | `price_level` 2, `price_band` cheap | mâu thuẫn nhau | **conflict** | 2 (trung bình) |
| Thời lượng | 200 phút | luật theo loại | **assumed** | 3 giờ 20 cho một bảo tàng |
| Rating | 4.2 | Google, không có số review | single | 4.2 |

Nhận xét: ngay cả POI tốt nhất cũng có 3 trường planner đang dùng sai. `osm_evidence` có sẵn trong dữ liệu
trỏ vào một node không tên cách 124m; lần ghép lại mới tìm được đúng đối tượng.

## 3. Các POI chưa hoàn chỉnh (cả 8 đều đang `verified=true`)

**3.1 Nhà Hàng Hải Sản - Ơ Kìa** (`auto-verify-v1`): giá mặc định, rating không kiểm được.

```json
{"cat": "restaurant", "opening_hours": ["06:00-23:00"], "price_level": 2, "price_note": null,
 "smart_tags": {"price_band": null}, "rating": 4.8,
 "osm_evidence": {"osm": "node/4430018990", "dist_m": 34.4, "hours": "24/7", "name": null}}
```

- `price_level` 2 là giá trị mặc định, không có khoảng giá nào.
- Rating 4.8 không có số review, nên không phân biệt được 4.8 từ 5 lượt hay từ 2.000 lượt.
- `osm_evidence` ghi "24/7" nhưng lấy từ một node **không tên** cách 34m, nên không phải bằng chứng.

**3.2 Biển Rạng Sơn Trà** (`auto-verify-v1`): nhầm thực thể khi điền giờ.

```json
{"cat": "restaurant", "type": "Nhà hàng Việt Nam", "tags": ["Nhà hàng Việt Nam", "Văn phòng công ty", "Nhà hàng cơm"],
 "opening_hours": ["00:00-23:59"], "hours_source": "web",
 "hours_web": "suy luận: bãi tự nhiên hoang sơ, không vé/giờ"}
```

- Đây là nhà hàng, nhưng bước điền giờ hiểu nhầm thành bãi biển và suy ra mở 24/7.
- Planner có thể xếp bữa tối lúc 23:00 ở đây.
- Mọi giá trị "suy luận" phải mang mức `assumed`, không được tính là đã verify.

**3.3 Mikazuki Water Park 365** (`auto-verify-v1`): có giá vé, nhưng planner coi là miễn phí.

```json
{"cat": "attraction", "opening_hours": ["09:00-19:00"], "fee": 0, "ticket_vnd": 350000, "rating": null}
```

Hồ sơ "tiết kiệm" còn cộng thưởng miễn phí cho POI này. Rating null vì nguồn là `manual+web`.

**3.4 Chợ Non Nước** (`spotcheck-v1`, người duyệt): đúng chỗ, nhưng thiếu giờ.

```json
{"cat": "market", "opening_hours": [], "visit_min": {"p50": 75}, "rating": 4.5}
```

- OSM xác nhận tồn tại (`amenity=marketplace`, cùng tên, cách 28m).
- Thiếu giờ, nên planner coi chợ mở suốt chuyến, kể cả 21:00.
- Ví dụ này cho thấy người duyệt bấm "Đúng" mà không có giờ. Đây là lý do cần ô nhập giờ (đề xuất 6.2).

**3.5 Shop Hoa Tươi Quận Ngũ Hành Sơn | Điện Hoa Đà Nẵng** (`auto-verify-v1`): không phải điểm đến.

```json
{"cat": "market", "type": "Chợ hoa", "tags": ["Chợ hoa", "Văn phòng công ty"],
 "opening_hours": ["04:00-23:30"], "visit_min": {"p50": 90}}
```

Đây là dịch vụ giao hoa, nhưng planner có thể đưa khách tới đây 90 phút. "Đặc Sản Ngon Đà Nẵng - Đặc Sản
Làm Quà shop online" cũng thuộc loại này.

**3.6 Cầu Trần Thị Lý** (`auto-verify-v1`): thời lượng vô lý.

```json
{"cat": "attraction", "opening_hours": ["00:00-23:59"], "visit_min": {"p50": 200}, "rating": null, "source": "osm/overpass"}
```

Planner sẽ cho khách đứng ở cây cầu 3 giờ 20 phút. "Cầu vượt đi bộ Mikazuki" là 240 phút.

**3.7 Spa Nặn Mụn - Không Sưng Liên Chiểu Lu's House Beauty & Academy** (`auto-verify-v1`): rating đáng
ngờ, giá mặc định.

```json
{"cat": "spa", "rating": 4.9, "price_level": 2, "price_note": null, "opening_hours": ["09:00-20:00"]}
```

- Đây là cơ sở nặn mụn và dạy nghề, khó coi là điểm thư giãn cho khách du lịch.
- 22/48 spa verified có rating 4.9. Đây đúng kiểu "vài lượt vote là lên 5 sao" mà Cường nói.

**3.8 Vấn Cocktail Bar** (`auto-verify-v1`): dữ liệu đúng, nhưng planner hiểu sai.

```json
{"cat": "bar", "opening_hours": ["19:00-02:00"], "rating": 4.9, "price_level": 2}
```

Khung qua nửa đêm, nên planner không bao giờ xếp được quán này (mục 1).

## 4. Về các ý trong tin nhắn với Cường

**"Có thể xóa `price_level` luôn."** Đồng ý là giá trị hiện tại không đáng tin: 58% là mặc định. Nhưng
không nên xóa ngay, vì 3 chỗ đang đọc nó:

- `rank.py` khớp với mức chi tiêu người dùng chọn;
- `profiles.py` phạt giá ở hồ sơ tiết kiệm;
- model PATM (`scorer.py:91`) dùng chênh lệch `price_level` làm đặc trưng. Xóa thì phải train lại.

Đề xuất thay thế:

- Lưu **sự thật** là khoảng giá VND cho mỗi người, kèm nguồn: `price_vnd: {low, high, source}`. Hiện đang có
  dạng chữ trong `price_note` của 253 POI.
- `price_level` và `price_band` thành giá trị **suy ra** bằng ngưỡng trong config. **Không có giá thì để
  `null`**, không để số 2.
- `rank.py` và `scorer.py` đã chịu được `null`. `profiles.py` hiện coi `null` là mức rẻ nhất (1), nên cần
  chốt cách xử lý ở hồ sơ tiết kiệm.

**"Set ngưỡng expensive trên 2–3 triệu."** Ngưỡng hiện tại tính theo giá giữa khoảng, mỗi người:

- rẻ < 100k;
- trung bình 100–500k;
- đắt > 500k.

Trên các POI verified có khoảng giá:

| Loại | Số POI | Giá giữa (median) | Cao nhất |
|---|---|---|---|
| Quán ăn | 54 | 150k | 550k |
| Cà phê | 70 | 50k | 300k |
| Bar | 31 | 250k | ~1 triệu ("Trên 1 Tr ₫") |

Với ngưỡng 2–3 triệu mỗi người, **không POI verified nào là "đắt"**; chỉ khách sạn vượt mức đó, mà khách
sạn không vào lịch. Nếu ý là 2–3 triệu cho **cả chuyến**, thì đó là ngưỡng của ngân sách chuyến, không phải
nhãn của POI. Planner đã có `budget` riêng cho việc này. Cần chốt lại hai bên đang nói ngưỡng nào.

**"Rating ảo, 3–4 vote là lên 5 sao."** Cách sửa chuẩn là rating có trọng số theo số review (trung bình
Bayes):

```
rating_adj = (n × R + m × C) / (n + m)
n = số review, R = rating Google, C = rating trung bình của loại đó, m ≈ 50
```

Ví dụ với C = 4.4 và m = 50:

| n | R | rating_adj |
|---|---|---|
| 4 | 5.0 | (20 + 220) / 54 = **4.44** |
| 2.000 | 4.6 | **4.60** |

Công thức này tự động và chính xác 100% khi đã có `n`. Nhưng hiện **không có `n` cho POI nào**, nên cần
crawl lại. Kết quả search của SerpApi có sẵn số review; gói miễn phí cho 250 lượt mỗi tháng. Bước này cần
duyệt key và quota.

**"Giờ không có thì làm tay: lọc phần thiếu rồi lên Google Maps check."** Làm tay được, nhưng cần ghi lại
nguồn và mức tin, và không được suy luận (ví dụ 3.2). Cách tự động hoá:

- Lấy giờ **theo từng ngày** từ Google (SerpApi / Places) và so với `opening_hours` của OSM.
- Hai nguồn khớp thì `confirmed`. Lệch thì đưa người xử lý.
- Chỉ có một nguồn thì `single`. Không có nguồn nào thì dùng **khung an toàn theo loại** kèm cảnh báo, thay
  vì coi là mở suốt chuyến.

## 5. Tự động chính xác được tới đâu

| Nhóm | Việc | Chính xác | Cần gì |
|---|---|---|---|
| **A. Biến đổi tất định** (làm ngay, không cần nguồn mới) | `fee` ← `ticket_vnd` (7 POI); `price_level` mặc định 2 → `null` (239); sửa đọc giờ qua nửa đêm và nhiều ca (74 + 30 POI); "suy luận" → `assumed`; trần thời lượng theo loại con (cầu, đình, tiệm, chợ) | 100%, kiểm bằng test | chỉ code |
| **B. Đối chiếu nguồn** | tồn tại, vị trí, loại hình (OSM + Google types); giờ (Google theo ngày + OSM); số review | đo bằng mẫu, gate ≥ 95% | OSM (đã có); crawl lại Google (cần quota) |
| **C. Người** | mâu thuẫn giữa nguồn; thời lượng ngoài trần; giá vé điểm tham quan không có nguồn; loại "không phải điểm đến" | | trang duyệt có ô sửa giờ, giá, loại, thời lượng |

Nhóm A chiếm phần lớn lỗi planner thấy trong mục 3, và không cần gọi thêm dịch vụ ngoài nào.
