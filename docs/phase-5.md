# Phase 5: hoàn tất planner (31/10/2026)

Nhánh `task/stable-p5-finish`, tách từ `feat/stable-p1-p4`. Tiêu chí Phase 4 đã đạt trước đó (`docs/verify-samples.md` mục 14).

| Việc | Trạng thái |
|---|---|
| Ngân sách thật: `effective_fee` (B5) | Xong |
| Build lại gold, bộ lọc eval khớp runtime (N5) | Xong |
| Siết CORS, tắt router test ở production (N6) | Xong |
| Repair trả `needs_verification` (B4) | Xong |
| Đo độ trễ trên máy deploy | Có công cụ, **chưa đo trên máy deploy** |

## 1. Ngân sách thật (B5)

Trước đây chỉ 13 POI có giá vé, còn lại `fee = 0`. Vì vậy cổng ngân sách không bao giờ trượt, `total_cost` gần như luôn bằng 0,
và điểm nào không có giá vé cũng bị ghi "miễn phí", kể cả nhà hàng.

`BE.common.effective_fee(poi)` trả số tiền một người chi ở một điểm:

| Thứ tự | Trường hợp | Giá trị |
|---|---|---|
| 1 | Có `ticket_vnd` hoặc `fee` | Giá thật |
| 2 | `beach`, `landmark`, `nature`, `park`, `viewpoint` mức Rẻ, không có vé | 0 đồng |
| 3 | Còn lại có mức giá | Rẻ 50.000, Trung bình 300.000, Đắt 700.000 |
| 4 | Không có mức giá | `None`: "giá chưa rõ", không bao giờ là miễn phí |

- Audit ghi mức Rẻ khoảng 100.000. Tài liệu này dùng 50.000 vì mức Rẻ là dưới 100.000 mỗi người, nên 50.000 mới là giữa khoảng.
- Giá tính theo người, ngân sách là của cả nhóm: chi phí = tổng giá × `travelers`. Audit không nêu điểm này, nhưng nếu không nhân
  thì nhóm 4 người vẫn "trong ngân sách" dù thực chi gấp 4 lần.
- Bộ lọc ngân sách, cổng BCS, `total_cost`, xếp hạng, lịch tiết kiệm và repair đều đọc cùng một hàm.
- Bộ giải có thêm ràng buộc cứng `max_fee` (SC-008), nên không còn dựng xong lịch rồi mới bị cổng loại.
- Lịch có `cost_estimated` và một cảnh báo khi một phần chi phí là ước lượng theo mức giá (FR-026).
- Không đủ tiền cho điểm bắt buộc thì trả lịch rỗng kèm cảnh báo, không âm thầm vượt ngân sách.

Cặp đôi, 2 người, 1 ngày:

| Ngân sách | Lịch cân bằng | Lịch tiết kiệm |
|---|---|---|
| 3.000.000 | 1.580.000 | 300.000 |
| 600.000 | 580.000 | 240.000 |
| 200.000 | 200.000 | 200.000 |
| 0 | Không xếp được, báo thiếu nhà hàng cho bữa trưa | Như bên trái |

## 2. Gold và baseline (N5)

Gold cũ chỉ có 5 POI, nên mọi con số so sánh đã lỗi thời.

- `approach_b.filter_pois` gọi đúng `retrieval.retrieve` của planner, nên eval và app chọn từ cùng một danh sách.
- Gold đi qua các điểm bắt buộc trước, rồi tới 40 điểm gần nhất. Điểm nào làm vượt ngân sách hoặc phá luật trong ngày (mỗi loại một
  điểm, không hai điểm cùng loại liền nhau) thì bị bỏ qua, bằng chính các hàm của cổng kiểm.
- Truy vấn có thêm `travelers`, `activities` và hồ sơ người dùng như một request thật. Hồ sơ chỉ áp cho lần chạy hybrid.
- Điểm bắt buộc được chọn trong số điểm vừa khung giờ của truy vấn.
- Bộ giải của eval tăng ngân sách từ 1,5 lên 8 đơn vị. Với 80 ứng viên, 1 luồng: mức 1,5 chỉ giải được 9/27, mức 3 được 24/27, mức 5 được
  25/27, mức 8 được 27/27.

Kết quả trên 541 POI, 30 truy vấn, 27 truy vấn khả thi (`BE/eval/gold/t053_baselines.json`):

| Tiêu chí | Mục tiêu | Chỉ theo khoảng cách | Hybrid | Đạt |
|---|---|---|---|---|
| SC-005 | Ít nhất 90% qua cổng kiểm | 100% | 100% | Đạt |
| SC-006 | 0 vi phạm giờ mở cửa | 0 | 0 | Đạt |
| SC-007 | 0 chồng giờ, 0 thiếu đường đi | 0 | 0 | Đạt |
| SC-008 | 0 vi phạm ngân sách (nay đã có giá thật) | 0 | 0 | Đạt |
| SC-009 | Hybrid gấp 1,10 lần theo rating | 4,498 | 4,576 (gấp 1,017) | **Chưa đạt** |
| SC-010 | Khôi phục được ít nhất 80%, giữ 100% điểm đã đi | | 27/27, giữ 100% (mục 7) | Đạt |

- **SC-009:** rating đã điều chỉnh gần như nằm trong khoảng 4,0–4,9, và lịch chỉ theo khoảng cách cũng được 4,5, nên gấp 1,10 lần thì gần như
  không thể đạt. Cần đổi thước đo, ví dụ thêm độ nổi tiếng hoặc mức khớp sở thích, thay vì chỉnh để qua.
- **SC-010:** số 23/27 đo lần đầu là đo trên truy vấn không có hồ sơ, trong khi lịch có hồ sơ thì replan luôn thất bại (mục 7). Sửa lỗi đó rồi đo đúng
  với hồ sơ được 18/27. 9 lần còn lại do mưa bỏ nhà hàng trưa ngoài trời (6), mưa bỏ điểm bắt buộc (2), và nhà hàng có hai ca (1). Sửa nốt thì được
  27/27. Phép đo này chỉ thử một sự cố: trời mưa sau điểm đầu tiên.
- **Mong muốn của người dùng:** hybrid đáp ứng 18/28 hoạt động được yêu cầu. Phần còn lại bị nới với cảnh báo, nhiều truy vấn chỉ có khung giờ nửa ngày.
- **LLM-only:** bỏ qua vì máy không có LLM chạy local. Không có số nào bị suy đoán.
- **Model chuyển tiếp:** các số trên dùng quy tắc dự phòng vì máy này thiếu libomp cho lightgbm. Máy có libomp có thể cho số khác một chút.

## 3. CORS và router (N6)

- API nhận trình duyệt từ các origin trong `CORS_ORIGINS`. Ngoài production còn nhận mọi cổng của `localhost` và `127.0.0.1`. Chỉ cho phép
  `GET`, `POST` và header `Content-Type`.
- `APP_ENV=production` tắt `/v1/review`, `/v1/repair`, `/v1/accept`, vì chỉ trang test local dùng các router này.
- **Khi deploy phải đặt cả hai biến**, nếu không app web sẽ bị trình duyệt chặn.

## 4. Repair (B4)

`POST /v1/repair` trả thêm khối `retrieval` giống `POST /v1/itinerary`: danh sách cần xác minh và số điểm bị loại theo từng lý do (FR-013, FR-024).

## 5. Độ trễ

`python BE/tools/bench_latency.py --snapshot BE/data/snapshots/danang-v1` chạy 7 kịch bản, mỗi request 3 lịch. Trên máy 12 nhân, 14 request:
trung vị 5,62 giây, p95 5,77 giây, tối đa 6,27 giây, không lịch nào lỗi. Đạt mục tiêu p95 dưới 8 giây, nhưng **vẫn phải chạy lại trên máy deploy**.

## 6. Còn lại

- Đo độ trễ trên máy deploy.
- SC-009: đổi thước đo.
- Repair (`/v1/repair`, chỉ dùng ở trang test local) chưa hỗ trợ lịch nhiều ngày: trả nguyên lịch kèm `note`.
- Cầu Rồng chưa vào lịch mặc định. Lịch có hồ sơ thường không có bữa tối.
- Rút mẫu blind mới từ 541 POI để người kiểm độc lập (`docs/verify-samples.md` mục 12).

## 7. Lịch 2 ngày (FR-020)

Trước đây yêu cầu 2 ngày vẫn chỉ ra lịch 1 ngày, vì phần lập lịch không đọc `days`. `BE/app/services/multiday.py` giải từng ngày một rồi gộp thành
một lịch. Lịch 1 ngày đi thẳng vào bộ giải, dạng trả về không đổi.

| Nội dung | Cách làm |
|---|---|
| Không lặp điểm | Ngày sau loại các điểm ngày trước đã dùng |
| Ngân sách | Mỗi ngày được tiêu phần chia đều của số tiền còn lại. Không đủ thì thử lại với toàn bộ số còn lại |
| Điểm bắt buộc | Chia đều cho các ngày, vì mỗi ngày chỉ có một điểm mỗi loại. Nếu không được thì xếp hết vào ngày đầu |
| Mong muốn hoạt động | Ngày sau chỉ phải đáp ứng những gì ngày trước chưa đáp ứng |
| Cổng kiểm | Luật trong ngày chạy riêng từng ngày; ngân sách và điểm bắt buộc tính cả chuyến; thiếu ngày hoặc lặp điểm thì trượt `HCS` |
| Xếp lại khi có sự cố | Chỉ xếp lại một ngày (`day`, mặc định ngày đầu còn điểm chưa đi); các ngày khác giữ nguyên |

Phần trả về: mỗi phần tử `activities` và `segments` có `day`, và có thêm `days` tóm tắt từng ngày (`specs/001-travel-agent-mvp/contracts/api.md`).

**Kết quả** trên 9 truy vấn cả ngày đầu tiên của bộ gold, hỏi lại với 2 ngày: 9/9 qua cổng kiểm, 9/9 đủ hai ngày, không lặp điểm, không vượt ngân sách, trung bình
5,83 điểm mỗi ngày, đáp ứng 7/9 mong muốn. Độ trễ 14 request, mỗi request 3 lịch, máy 12 nhân: trung vị 10,9 giây, p95 11,3 giây (mục tiêu của spec
là 30 giây).

Khi không đủ tiền cho cả hai ngày, lịch trả về `passed: false` và cảnh báo "chi xep duoc 1/2 ngay", không âm thầm bỏ ngày.

**Lỗi cũ phát hiện khi làm phần này**, đều đã sửa và có test:

- **Replan luôn thất bại với lịch có hồ sơ người dùng, kể cả lịch 1 ngày.** Cổng kiểm không thấy loại hình nên không thấy bữa trưa, và bộ giải không biết luật
  bữa trưa, nghỉ trưa. Giờ replan kiểm cả ngày, tính cả các điểm đã đi. Trễ quá 13:00 mà chưa ăn trưa thì không còn làm hỏng cả ngày.
- Trời mưa làm bỏ luôn nhà hàng trưa ngoài trời: giờ tìm nhà hàng trong nhà thay thế, không có thì giữ nhà hàng cũ.
- Trời mưa hoặc mệt không còn tự bỏ điểm bắt buộc. Người dùng chủ động bỏ hoặc địa điểm đóng cửa thì vẫn bỏ được.
- Nhà hàng có hai ca mở cửa: replan trước đây chỉ đọc ca đầu.
- Điểm đã đi được tính vào ngân sách khi replan.
- Danh sách 80 ứng viên giữ cả các điểm vượt phần tiền của ngày, làm mất chỗ của quán rẻ, nên lịch ngân sách thấp không xếp được bữa trưa.

**Giới hạn:** dự báo thời tiết chưa theo ngày, nên ngày 2 dùng cùng dự báo với ngày 1. Giờ mở cửa cũng chưa theo thứ trong tuần. Repair chưa hỗ trợ
nhiều ngày.
