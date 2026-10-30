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

## 6. Kết quả nhóm A (đã làm)

Tool `BE/ml/data/normalize_fields.py` áp các luật tất định lên `pois.json`. Mọi luật là hàm thuần của
dữ liệu có sẵn: không gọi nguồn ngoài, không đoán giá trị. Chạy lại không đổi gì thêm. Test
`test_normalize_fields.py` fail nếu snapshot còn dòng chưa chuẩn hoá.

| Luật | 742 POI | 410 verified |
|---|---|---|
| `fee` ← `ticket_vnd` | 13 | 7 |
| `price_level` suy từ `price_band` (rẻ 1, trung bình 2, đắt 3) | sửa 17 dòng lệch, 466 → `null` | 13, 239 → `null` |
| Giờ "suy luận" → `hours_source: inferred` | 10, bỏ 1 (Biển Rạng Sơn Trà) | 8, bỏ 1 |
| Các ca trong ngày từ web/OSM gộp vào một phần tử | 2 | 2 |
| Thời lượng tính theo `cat` thay vì loại gốc của Google | 85 | 18 |

Một số thời lượng sau khi sửa:

- Bảo tàng Chăm 200 → 90 phút.
- Bãi Biển Thiên Đường 200 → 120 phút, khớp đúng con số người duyệt đề xuất.
- Cầu Trần Thị Lý 200 → 45 phút.
- Đình làng Hải Châu 240 → 54 phút.

Planner:

- **Đọc giờ** (`BE/common.open_windows`):
  - Khung qua nửa đêm được kéo sang ngày hôm sau.
  - Mỗi ca trong ngày là một khung riêng, và optimizer chọn một trong các khung.
  - Các biến thể theo ngày trong tuần được lấy giao, tức chỉ giữ giờ mở ở mọi biến thể.
- **POI thiếu giờ** không còn bị coi là mở suốt chuyến. Planner dùng **khung an toàn đo từ dữ liệu**: các
  khung giờ mà ≥ 90% POI cùng nhóm (có giờ từ nguồn thật) đang mở.

  | Nhóm | Khung an toàn |
  |---|---|
  | Tham quan (gộp 7 loại, n=89) | 09:00–17:00 |
  | Cà phê | 07:30–19:30 |
  | Spa | 10:00–19:30 |
  | Quán ăn | 17:00–21:00 |
  | Bar | 19:30–23:45 |
  | Chợ | không có khung nào đạt 90% (chợ sáng lẫn chợ đêm) → **không xếp** cho tới khi có giờ thật |

  Lệnh `normalize_fields.py --safe-hours` in lại bảng này, và test fail nếu bảng trong code lệch khỏi dữ
  liệu. Optimizer, replan và repair cùng đọc bảng này. Dữ liệu thì vẫn để trống giờ.
- **Mức giá `null`** được coi là mức trung bình (`UNKNOWN_PRICE_LEVEL = 2`), nên thứ hạng không đổi so
  với trước. Retrieval gắn nhãn "gia chua xac minh".
- Các bước crawl (`fetch_serpapi`, `osm_add`, `manual_add`) và `enrich_tags` không còn ghi số 2 giả hay giờ
  suy luận dưới nhãn "web".

E2E trên 9 kịch bản (trước → sau):

- Mọi plan đều pass, và không điểm dừng nào nằm ngoài giờ mở cửa.
- Kịch bản bar buổi tối: mong muốn đạt 2/3 → **3/3**.
- Chi phí vé bắt đầu xuất hiện (3D Art 140k, Mỹ thuật 20k); trước đó luôn là 0.
- p50 vẫn 5.9s.

Còn lại cho người (không tự động hoá được):

- 4 POI Google có các biến thể giờ không giao nhau, nên planner không xếp được: The South Coffee, Nhà thờ
  Giáo xứ An Hải, Nhà thờ Gia Phước, The Craftsman Cocktail Bar.
- Biển Rạng Sơn Trà đã bị bỏ giờ suy luận, nên cần giờ thật. Chợ Non Nước chưa có giờ nên chưa xếp được.
- Vịnh Sơn Trà và View Ngắm Bình Minh Sơn Trà: chính ghi chú nói đường lên chỉ mở 07:30–18:30, nhưng lại
  được điền 24/7.
- Thời lượng theo luật vẫn chỉ là ước lượng (`dur_confidence: low`), ví dụ shop đặc sản 90 phút, du thuyền
  240 phút.
- 2 POI verified chưa biết có vé hay không (Non Nuoc Stone Carving Memory Museum, Đà Sơn tâm linh), nên
  planner vẫn coi là miễn phí.
- Luật auto của Cường so thời lượng với trung vị của nhóm, nên khi thời lượng thay đổi, kết quả cũng đổi.
  Chạy lại thử: cờ "thời lượng bất thường" giảm từ 23 xuống 4, nhưng sẽ có **7 POI chưa verify tự qua**
  (du thuyền, lớp nấu ăn, thuyền thúng...). Tôi không bật cờ verify cho chúng.

## 7. Tầng 1: đối chiếu OSM (đã làm)

Tool `BE/ml/data/osm_crosscheck.py` ghi kết quả ra `osm_crosscheck.json` và `OSM_CROSSCHECK.md` trong snapshot.
Tool không sửa `pois.json` và không đụng cờ `verified`. Chạy mất 4 giây trên extract OSM ngày 28/10/2026, gồm
9.265 đối tượng có tên.

Luật ghép:

- Đo khoảng cách tới **hình học** của đối tượng OSM, tối đa 150 m. Bãi biển là một đường dài, nên đo tới
  tâm sẽ sai.
- Tên được bỏ dấu, bỏ từ chung ("bãi biển", "beach") và bỏ phần địa chỉ phía sau ("- 58 Ông Ích Đường").
- Hai tên phải trùng hẳn, hoặc chung ≥ 2 chữ theo **đúng thứ tự**, trong đó có ít nhất một chữ riêng (không
  phải địa danh, tên món hay từ chỉ loại). Nhờ vậy:
  - "Trà Sơn Quán" ≠ "Son Tra Viewpoint" (khác thứ tự);
  - "Bãi tắm Sao Biển" ≠ "Nhà thờ Đức Mẹ Sao Biển" (chỉ chung một chữ);
  - "Mỳ Quảng Quê Xưa" ≠ "My Quang Restaurant" (chỉ chung tên món).
- Loại hình: tag chung chung (`tourism=attraction`, `shop=*`) chỉ được dùng để xác nhận, không bao giờ tạo
  mâu thuẫn. Khi tag cụ thể mâu thuẫn với loại hình của POI thì chính phép ghép đáng nghi, nên "tồn tại"
  vẫn chỉ được tính là một nguồn.
- POI vốn lấy từ OSM được ghi `same_source`: không tự xác nhận chính mình.

Kết quả trên 410 POI verified (6 POI lấy từ OSM được tính riêng):

| Trường | Xác nhận | Mâu thuẫn | Một nguồn |
|---|---|---|---|
| Tồn tại, vị trí | 102 | 0 | 302 |
| Loại hình | 97 | 4 | 303 |
| Giờ | 15 | 8 | 369 (thêm 8 thiếu, 1 chỉ OSM có) |

OSM phủ được **47% nhóm tham quan** (37/79) nhưng chỉ **18% quán xá** (53/301 nhà hàng, cà phê, bar, spa).

**Độ tin, đo trên 48 dòng có nhãn người** (`SPOT_CHECK.md`):

- 12 dòng được OSM xác nhận tồn tại và loại hình: **0 dòng sai ở hai trường này**. 2 trong số đó người
  đánh "Sai", nhưng vì thời lượng và trùng lặp, là những thứ OSM không kiểm.
- 3 lỗi loại hình người tìm thấy đều **không** được OSM xác nhận, nên luật "≥ 2 nguồn" sẽ không cho chúng
  qua.
- Độ phủ trên các dòng đúng: 11/38 (29%).
- Mẫu còn nhỏ: với 0/12 dòng sai, cận trên của khoảng tin cậy 95% vẫn khoảng 24%. Gate thật vẫn cần mẫu 50
  POI có 2 người duyệt.

Những điểm mới cần người xử lý (đầy đủ trong `OSM_CROSSCHECK.md`):

- **Loại hình:**
  - Bãi Sủng Cỏ và Bãi Tắm Non Nước đang gắn `attraction`, nhưng OSM ghi là bãi biển.
  - Lagoon Rooftop (bar hay nhà hàng) và Cucina Luca (nhà hàng hay cà phê) lệch nhẹ.
- **Trùng lặp:**
  - Bãi Tắm Non Nước và Bãi biển Non Nước là cùng một bãi, và cả hai đều đã verify.
  - Cổng Chùa Linh Ứng là một phần của Chùa Linh Ứng.
  - Chùa Không Tên có thể trùng Khu Văn hoá Tâm linh Đà Sơn.
- **Giờ lệch quá 30 phút (8 POI):**
  - Maia Beach Bar: dữ liệu ghi 07:00–01:00, OSM ghi 16:00–23:00.
  - Bảo tàng 3D Art: dữ liệu ghi đóng cửa 18:00, OSM ghi 22:00.
- **Ngày nghỉ mà dữ liệu của mình không có:** theo OSM, Bảo tàng Hồ Chí Minh nghỉ thứ Hai và thứ Sáu.
- **Giờ chỉ OSM có:** The Craftsman Cocktail Bar (OSM: 18:00–02:00). Đây là một trong 4 POI planner chưa
  xếp được.

Kết luận: OSM là nguồn thứ hai đáng tin, vì không có lần xác nhận sai nào trong mẫu. Nhưng OSM chỉ phủ khoảng
một phần tư số POI verified: tốt với nhóm tham quan, yếu với quán xá. Quán xá cần một nguồn thứ hai khác
(VietMap Place hoặc Google), và việc đó cần bạn duyệt chi phí.

## 8. Tool duyệt, ingest và đo độ chính xác (đã làm)

### Trang duyệt `FE/verify_review.html`

Dựng bằng `BE/tools/build_verify_page.py`, phát triển tiếp từ tool của Cường. Định dạng export cũ vẫn giữ, chỉ
thêm trường mới.

- **289 dòng, chia hai nhóm:**
  - **33 POI đã verify nhưng bị gắn cờ, đưa lên đầu.** Các POI này đang được xếp vào lịch, nhưng OSM hoặc
    luật dữ liệu báo có vấn đề: lệch loại hình, lệch giờ, trùng, giờ suy luận, thiếu giờ, chưa biết có vé,
    hoặc có thể không phải điểm đến.
  - **256 dòng hàng đợi:** đã bỏ 76 lodging. Nhóm tham quan được đưa lên trước.
- **Lý do của hàng đợi được chấm lại trên dữ liệu hiện tại.** File queue cũ chỉ quyết định POI nào cần người
  duyệt. Sau bước chuẩn hoá, cờ "thời lượng bất thường" giảm từ 23 xuống 4.
- **Mỗi thẻ có khối đối chiếu OSM:** trạng thái từng trường, đối tượng khớp, link OSM, giờ và ngày nghỉ theo OSM.
- **Có ô sửa:** giờ, loại hình, thời lượng, giá vé, mức giá. Ô nào sai định dạng thì bị tô đỏ và chặn xuất file.
  Trên trang cũng hiện khung giờ an toàn mà planner dùng khi POI thiếu giờ.
- **Hash không còn phụ thuộc hệ điều hành:** hash được tính trên JSON đã chuẩn hoá. Mỗi dòng xuất ra có
  `row_hash`.

### Ingest `BE/ml/data/ingest_verdicts.py`

Mặc định chạy thử, không ghi gì. Khi dùng `--apply`:

- **"Đúng":** bật `verified`, ghi nguồn `human-review-v1`, và áp các giá trị đã sửa (nguồn `human`).
- **"LOẠI":** tắt `verified`. Luật auto của Cường sẽ không bao giờ tự cho POI đó qua lại (`human_rejected`).
- **Từ chối cả dòng, không áp một nửa,** khi:
  - sai định dạng hoặc thiếu tên người duyệt;
  - dòng đến từ trang mẫu;
  - `row_hash` lệch với dữ liệu hiện tại, tức dữ liệu đã đổi sau khi tạo trang.
- **Hai người khác ý về "Đúng/LOẠI":** không áp, chỉ báo cáo. Nếu cùng ý nhưng nhập giá trị khác nhau cho một
  trường thì bỏ trường đó.
- **Chạy lại không đổi gì.** Mọi dòng đã áp được ghi vào `review_log.jsonl`.
- Nên ingest file của mọi người duyệt trong **cùng một lần chạy**.

### Mẫu đo độ chính xác `FE/verify_sample.html` + `BE/ml/data/verify_precision.py`

- Mẫu gồm 80 POI rút ngẫu nhiên, phân tầng theo loại hình, từ 362 POI do máy tự verify (seed 20261030).
- **Duyệt kiểu mù:** trang không hiện lý do của máy hay kết quả OSM. Người duyệt chấm "Đúng" hoặc "Sai", và
  tick trường bị sai.
- Tool chấm điểm tính:
  - precision của từng người;
  - **precision chặt**: chỉ tính đúng khi mọi người chấm đều nói "Đúng";
  - khoảng tin cậy Wilson và hệ số đồng thuận Cohen's κ;
  - các trường hay sai nhất.
- **Vì sao 80 mà không phải 50:** với cổng ≥ 95% và cận dưới ≥ 90%, mẫu 50 không được sai dòng nào (sai 1 dòng
  thì cận dưới còn 89.5%). Số lỗi tối đa vẫn qua cổng theo cỡ mẫu:

  | Cỡ mẫu | 50 | 60 | 80 | 100 |
  |---|---|---|---|---|
  | Số lỗi tối đa | 0 | 1 | 2 | 4 |

### Quy trình cho người duyệt

1. Mở `FE/verify_review.html` (bấm đúp là mở, không cần mạng). Duyệt nhóm "đã verified, cần xem lại" trước,
   rồi đến hàng đợi. Nhập tên, rồi bấm **Xuất JSONL**.
2. Hai người mở `FE/verify_sample.html` và chấm **riêng**, mỗi người xuất một file.
3. Người phụ trách chạy:
   - `python BE/ml/data/ingest_verdicts.py --snapshot BE/data/snapshots/danang-v1 <các file review>`, xem báo
     cáo, rồi chạy lại với `--apply`.
   - `python BE/ml/data/verify_precision.py --snapshot BE/data/snapshots/danang-v1 <2 file mẫu>`.
4. Nếu precision chặt không qua cổng: không tắt cả đợt auto, mà tắt có chọn lọc các dòng chỉ có một nguồn
   hoặc đang mâu thuẫn.

Tool cần Python 3.10 trở lên. `python3` mặc định của macOS là 3.9.

### Nguồn thứ hai cho quán xá: đã thử VietMap, không dùng được

Thử 50 request VietMap Search v4 trên quán xá đã verify:

| Nhóm | Số quán | Ghép được (tên khớp, ≤ 150 m) | Toạ độ trùng Google (< 1 m) | Còn lại |
|---|---|---|---|---|
| Chưa có OSM xác nhận | 40 | 19 | 13 | lệch 2–12 m |
| OSM đã xác nhận (đối chứng) | 10 | 2 | 2 | – |

VietMap chỉ có tên, địa chỉ và mã loại; không có giờ hay rating. Quan trọng hơn, toạ độ gần như sao y Google:
13/21 trùng tới dưới 1 m, phần còn lại lệch không quá 12 m. Như vậy VietMap không phải nguồn độc lập; dùng nó
để "xác nhận" sẽ chỉ là Google tự xác nhận chính mình. **Kết luận: không chạy đủ 700 request.** Quán xá vẫn
cần người duyệt, qua trang review và mẫu đo precision. Repo chỉ ghi số liệu tổng hợp, không lưu câu trả lời
thô của VietMap.

### "Rating ảo": chưa làm được, cần key

Cách sửa (trung bình Bayes theo số review) đã mô tả ở mục 4, nhưng cần số review, mà số này chỉ có từ Google:

- `.env` hiện chỉ có `VIETMAP_API_KEY`, chưa có `SERPAPI_KEY`.
- Gói miễn phí của SerpApi cho 250 lượt search mỗi tháng. Mỗi lượt search trả về khoảng 20 quán kèm số review,
  nên chạy lại kế hoạch query cũ (khoảng 30–60 lượt) là phủ được phần lớn POI. Tra từng POI theo `place_id` thì
  tốn 410 lượt, vượt quota miễn phí.

## 9. Gợi ý tra Google Maps cho 33 POI cần xem lại (30/10/2026)

Claude đã tra Google Maps cho 33 POI đã verify nhưng bị gắn cờ, và 2 POI trùng của chúng trong hàng đợi. Nguồn tra
là trang địa điểm mở bằng `place_id`. Kết quả nằm trong `BE/data/snapshots/danang-v1/review_drafts.jsonl`
(35 dòng) và hiện ngay trên thẻ của trang duyệt. Mỗi thẻ có:

- gợi ý Đúng, LOẠI hoặc Bỏ qua kèm lý do;
- bằng chứng Google: tên, rating, số đánh giá, loại, giờ theo từng ngày, trạng thái đóng cửa;
- các giá trị nên sửa, đã được điền sẵn vào ô sửa.

**Gợi ý không tự áp dụng.** Người duyệt vẫn phải bấm nút; dòng xuất ra ghi thêm `draft_by` để biết đã có gợi ý.

| Gợi ý | Số POI | Ví dụ |
|---|---|---|
| Đúng | 23 | phần lớn khớp Google; OSM cũ (Maia Beach Bar, Ông Minh, 3D Art); 3 bãi sửa loại hình thành `beach`; Trình cà phê đóng 23:00 |
| LOẠI | 10 | Đình Hồng Phước **đóng vĩnh viễn**; Shop Hoa Tươi **không còn trên Google**; The South Coffee **đã đổi tên** thành Little HaNoi; 2 nhà thờ giáo xứ chỉ có giờ lễ; 4 bản trùng (Đà Sơn ×2, Non Nước, Cổng Chùa Linh Ứng); Khu Dừng Chân |
| Bỏ qua (bạn quyết) | 2 | shop đặc sản "shop online" có cửa hàng thật; Quán Hải sản Tân Trà Beach bị Google xếp loại "Điểm thu hút" |

Ngoài ra, trên mỗi thẻ:

- Khối OSM giờ hiện tag OSM thật, kèm tên phụ đã khớp (ví dụ "Chùa Không Tên"), thay cho danh sách loại hình suy ra.
- Ô giờ nhận cả dấu gạch dài khi dán từ Google Maps ("09:00–18:00").

## 10. Gợi ý tra Google Maps cho 254 POI trong hàng đợi (30/10/2026)

Mục 9 mới có gợi ý cho 33 POI cần xem lại. Đợt này phủ nốt 254 POI trong hàng đợi. Giờ cả 289 thẻ trên
`FE/verify_review.html` đều có gợi ý, nằm trong `review_drafts.jsonl` (35 dòng cũ + 254 dòng mới).

Cách tra:

- **180 POI có `place_id`**: mở thẳng trang địa điểm, giống mục 9.
- **74 POI từ OSM hoặc nhập tay** (không có `place_id`): tìm theo tên quanh tọa độ POI. Một kết quả được tính là
  khớp khi tên trùng hoặc chứa tên kia, và cách POI không quá 300 m. Khi Google trả về danh sách, chỉ tính tên trùng
  hẳn: "Chùa An Phước" không được khớp với "Chùa Phước An".
- Mỗi dòng ghi lại bằng chứng: tên, rating, số đánh giá, loại hình, giờ từng ngày, trạng thái; với POI tìm theo tên
  thì thêm khoảng cách và danh sách kết quả.

| Gợi ý | Số POI | Gồm |
|---|---|---|
| Đúng | 166 | điền sẵn giờ cho 21 POI (giờ thiếu hoặc khác Google), sửa loại hình 4 POI (Chùa Nam Sơn, Cầu Sông Hàn, Cầu Thuận Phước → `landmark`; SAY Beer → `bar`) |
| LOẠI | 48 | xem bảng dưới |
| Bỏ qua (bạn quyết) | 40 | xem bảng dưới |

Các gợi ý LOẠI:

| Lý do | Số | POI |
|---|---|---|
| Đóng cửa | 5 | vĩnh viễn: DA NANG DOWNTOWN, GREEN COFFEE. Tạm thời: Chùa Phước Lộc, Blues Q Coffee, New World Spa |
| Google đã gỡ listing | 1 | Chợ Đêm An Thượng: mã cũ không mở ra địa điểm nào; tìm theo tên chỉ ra khu phố và một nhà hàng |
| Trùng | 10 | Ba Na Hills, Núi Bà Nà (trùng Sun World Bà Nà Hills); Đèo Hải Vân, Núi Hải Vân (trùng Hải Vân Quan); bản OSM của nhà thờ Phú Thượng và Tùng Sơn; Non Nuoc Beach; một bản Viet Nam's Delights; Chùa Làng Thanh Khê bản 0 đánh giá; thuyền thúng "rừng dừa hội an" |
| Tên OSM chung chung | 8 | Public beach, Small waterfall, Art Gallery, Gần núi thần tài, To Quoc Ghi Cong, Lưu Niệm - Đặc Sản, Mart Souvenir, 노니판매점 |
| Không phải điểm tham quan | 4 | 2 am thờ bên đường; Public Beach Access; Cầu Tiên Sơn (cầu giao thông) |
| Google xếp không phải điểm đến | 3 | ANGEL LOUNGE, Maju (quán bar tiếp viên nữ); RAIN MUSIC BOX (cho thuê thiết bị karaoke) |
| Quán, dịch vụ dưới 5 đánh giá | 15 | 13 quán/spa 5,0★ từ 1–4 lượt, Bến Du Thuyền Sông Hàn, TASY STUDIO (cửa hàng tranh, bị gắn loại bảo tàng) |
| Quán OSM không có trên Google | 1 | Gio coffee |
| Nhà thờ chỉ có giờ lễ | 1 | Nhà thờ Giáo xứ An Thượng (cùng cách xử lý như mục 9) |

Các gợi ý Bỏ qua, chia theo việc cần làm:

| Cần gì | Số | POI |
|---|---|---|
| Nhóm quyết chính sách | 11 | 6 phòng karaoke (có gợi ý karaoke cho khách du lịch không); 4 điểm nằm trong khu Sun World Bà Nà (Đỉnh Bà Nà, Linh Phong Bảo Tháp, Thác Tóc Tiên, Thai Market): gộp vào Sun World hay giữ riêng; VinWonders Nam Hội An nằm ngoài khung Đà Nẵng |
| Điền thứ Google Maps không có | 6 | giá vé: Sun World Bà Nà Hills, VỌC Glamping, Nhà bia Núi Ghềnh. Giờ: phố đi bộ Bạch Đằng, Son Tra Viewpoint (thực ra là quán cà phê, đã điền sẵn `cafe`). Tọa độ: Smile Goods lệch 4,8 km |
| Chỉ có trên OSM, Google không có | 12 | 6 núi nhỏ, Suối Ngọc, Chùa An Phước, chùa Sư Nữ, nhà thờ An Ngãi Tây, đài tưởng niệm chuyến bay 229, Làng chiếu Cẩm Nê |
| Chưa đủ bằng chứng | 11 | Kim Sơn, Mộc Sơn, Thổ Sơn (núi nhỏ cạnh Thủy Sơn); Núi Thần Tài (điểm thật là công viên suối khoáng); có thể trùng: KDL Sinh thái Nam Ô, Quảng trường Liên Chiểu; Tuyet Pham Cooking Class (0 đánh giá); Fishing Village, Chợ Miếu Bông, Himawari, Non La |

Quy tắc về giờ:

- Giờ được điền khi POI chưa có giờ, hoặc giờ đang có khác Google.
- Google ghi "mở cả ngày" thì chỉ điền `00:00-23:59` cho landmark, park, nature, beach và viewpoint. Với quán, spa
  và dịch vụ, 24/24 thường là giá trị mặc định chủ quán để lại, nên không điền và planner dùng giờ an toàn của nhóm.
- Ô giờ chỉ có một khung dùng cho mọi ngày; dấu phẩy trong ô nghĩa là nhiều ca trong cùng một ngày. Nơi có giờ khác
  nhau theo ngày được điền khung chung của mọi ngày, ví dụ VinWonders điền 09:00–18:00 dù T7, CN mở tới 19:00. Trang
  duyệt và ingest đều báo sai khi các ca trong một ngày chồng nhau (vd. "07:00-17:30, 07:00-17:00").
- Ô giờ không ghi được ngày nghỉ. Ngày Google ghi nghỉ bị bỏ ra và được nêu trong ghi chú. Chợ Khái Tây nghỉ T2–T4
  nên không điền giờ.
- Giờ qua đêm vô lý của điểm tham quan bị bỏ (Hải Vân Quan, CN 07:00–05:30).
- Cầu Sông Hàn: Google ghi 08:00–20:00, nhưng cầu công cộng thì điền cả ngày.

Phụ phẩm của đợt tra:

- Đã có số đánh giá Google cho 212 POI trong hàng đợi (ô `google.reviews` của từng dòng nháp).
- Trong 73 POI rating 5,0, có 32 POI dưới 20 đánh giá. Đây đúng là vấn đề "rating ảo" Cường nêu.
- Số đánh giá mới có cho POI trong hàng đợi, chưa có cho 410 POI đã verify, nên việc crawl lại số review (mục 8)
  vẫn cần làm.
