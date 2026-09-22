# Feature Specification: Personalized Travel Agent MVP

**Feature Branch**: `001-travel-agent-mvp`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "Personalized Travel Agent là hệ thống lập kế hoạch du lịch cá nhân hóa cho Đà Nẵng: nhận yêu cầu tự nhiên bằng tiếng Việt, gợi ý POI/quán ăn, tối ưu thứ tự hoạt động theo sở thích (không chỉ đường ngắn nhất), kiểm tra tính khả thi, giải thích quyết định, cập nhật lịch khi đổi yêu cầu hoặc gặp sự cố, quản lý chi tiêu trong app, hiển thị trên ứng dụng di động Flutter."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tạo itinerary cơ bản (Priority: P1)

Khách du lịch cá nhân/cặp đôi nhập thành phố, thời gian, ngân sách và sở thích;
hệ thống hiển thị itinerary gồm POI, quán ăn, khung giờ, phương tiện và lý do.

**Why this priority**: Luồng giá trị cốt lõi — không có là không có sản phẩm.

**Independent Test**: Nhập prompt cố định; kiểm tra output đủ trường bắt buộc,
không trùng thời gian, đúng thứ tự.

**Acceptance Scenarios**:

1. **Given** người dùng nhập thành phố, thời gian, ngân sách và sở thích, **When** hệ thống xử lý xong, **Then** itinerary phải có POI, giờ bắt đầu/kết thúc từng hoạt động, thời gian di chuyển, chi phí ước tính và lý do lựa chọn.
2. **Given** prompt thiếu thông tin cần thiết (thành phố hoặc thời gian), **When** hệ thống xử lý, **Then** hệ thống phải hỏi lại đúng chỗ thiếu hoặc ghi rõ giả định đã dùng.

---

### User Story 2 - Gợi ý POI và quán ăn phù hợp ngữ cảnh (Priority: P1)

Người dùng yêu cầu địa điểm theo preference ("yên tĩnh", "hợp hẹn hò", "gần biển");
hệ thống trả về danh sách có điểm phù hợp, khoảng cách, giờ mở cửa và lý do.

**Why this priority**: Đề xuất đúng gu là khác biệt chính so với bản đồ thông thường.

**Independent Test**: Yêu cầu "quán yên tĩnh hẹn hò gần biển"; kiểm tra kết quả
khớp loại món, không gian, ngân sách, khoảng cách.

**Acceptance Scenarios**:

1. **Given** người dùng yêu cầu quán yên tĩnh để hẹn hò gần biển, **When** hệ thống tìm kiếm, **Then** kết quả phải chứa địa điểm phù hợp loại món, không gian, ngân sách và khoảng cách, kèm lý do.
2. **Given** không có POI nào thỏa ràng buộc cứng, **When** hệ thống tìm kiếm, **Then** hệ thống phải nới sở thích mềm (không tự bỏ ràng buộc cứng) và báo rõ đã nới gì.

---

### User Story 3 - Ưu tiên thứ tự hoạt động theo sở thích (Priority: P1)

Người dùng nói "leo núi rồi đi biển rồi đi ăn"; hệ thống ưu tiên hiking → beach →
restaurant khi khả thi, thay vì chọn điểm gần nhất.

**Why this priority**: Luận điểm trung tâm của sản phẩm (tổng giá trị > đường ngắn nhất).

**Independent Test**: Cùng tập POI, so lịch hệ thống sinh với lịch "đường ngắn nhất";
lịch hệ thống phải giữ thứ tự ưu tiên khi khả thi.

**Acceptance Scenarios**:

1. **Given** người dùng thích vận động trước khi thư giãn và cả hiking lẫn beach đều khả thi, **When** hệ thống lập lịch, **Then** hiking phải xếp trước beach, hoặc giải thích rõ nếu không thể.
2. **Given** thứ tự ưu tiên vi phạm giờ mở cửa hoặc ngân sách, **When** hệ thống lập lịch, **Then** hệ thống phải giữ ràng buộc cứng, đổi thứ tự và giải thích lý do.

---

### User Story 4 - Chọn trong nhiều phương án đã chấm điểm (Priority: P1)

Thay vì 1 lịch duy nhất, hệ thống trình 2–3 phương án (Tiết kiệm / Cân bằng /
Trải nghiệm) kèm điểm số và khác biệt; người dùng chọn 1 để chốt.

**Why this priority**: Biến mâu thuẫn sở thích thành lựa chọn tường minh; tăng tin tưởng.

**Independent Test**: Với cùng 1 yêu cầu, kiểm tra hệ thống sinh ≥2 phương án khả thi
có điểm và lý do khác biệt.

**Acceptance Scenarios**:

1. **Given** yêu cầu có thể đáp ứng nhiều cách, **When** hệ thống lập lịch, **Then** phải trình ≥2 phương án, mỗi phương án có tổng tiền, tổng giờ đi, điểm hợp gu và lý do khác biệt.
2. **Given** người dùng chọn 1 phương án, **When** xác nhận, **Then** phương án đó thành lịch chính, các phương án khác được lưu để so sánh.

---

### User Story 5 - Quản lý chi tiêu trong chuyến đi (Priority: P1)

Ngân sách đặt lúc lập lịch thành hạn mức; người dùng ghi chi thực tế (ăn/vé/xe);
app báo số còn lại, cảnh báo 80%/100%, và dùng tiền còn lại cho lần xếp lại sau.

**Why this priority**: Ngân sách chỉ có nghĩa khi theo dõi được thực tế.

**Independent Test**: Đặt budget 3 triệu, ghi 3 khoản chi; kiểm tra số còn lại và
cảnh báo đúng ngưỡng.

**Acceptance Scenarios**:

1. **Given** trip có ngân sách 3 triệu, **When** người dùng ghi chi 2.5 triệu, **Then** app phải báo còn 500 nghìn và cảnh báo đã dùng 83%.
2. **Given** chi thực tế vượt dự toán buổi sáng, **When** xếp lại buổi chiều, **Then** ràng buộc ngân sách còn lại phải siết theo số thực tế.

---

### User Story 6 - Lịch tính đến thời tiết (Priority: P1)

Hệ thống tự lấy nhiệt độ + xác suất mưa Đà Nẵng theo giờ; xếp hoạt động ngoài trời
tránh nắng/mưa gắt và giải thích ("38°C nên đi biển sáng sớm").

**Why this priority**: Thời tiết là nguyên nhân hàng đầu làm lịch vỡ ngoài đời.

**Independent Test**: Giả lập mưa 80% buổi chiều; kiểm tra hoạt động ngoài trời
chiều được đổi sang trong nhà + có giải thích.

**Acceptance Scenarios**:

1. **Given** dự báo mưa >70% trúng khung hoạt động ngoài trời, **When** hệ thống lập/cập nhật lịch, **Then** phải đề xuất phương án trong nhà thay thế và nêu lý do thời tiết.
2. **Given** mất mạng không lấy được dự báo mới, **When** hệ thống lập lịch, **Then** phải dùng bản cache gần nhất và ghi rõ giờ lấy dữ liệu.

---

### User Story 7 - Giải thích quyết định (Priority: P2)

Mọi lựa chọn POI/thứ tự đều có lý do, phân biệt đâu là dữ liệu thật, đâu là suy luận.

**Why this priority**: Giải thích tạo niềm tin; là cơ sở kiểm chứng.

**Independent Test**: Với 1 lịch mẫu, kiểm tra mỗi quyết định có ≥1 lý do gắn bằng
chứng từ input hoặc dữ liệu.

**Acceptance Scenarios**:

1. **Given** 1 itinerary đã sinh, **When** người dùng xem lý do, **Then** mỗi quyết định phải có lý do, phân biệt fact và inference, ghi rõ dữ liệu nào chưa chắc chắn.
2. **Given** giờ mở cửa/rating/giá chưa xác minh, **When** hệ thống giải thích, **Then** KHÔNG được trình bày chúng như sự thật.

---

### User Story 8 - Thay đổi lịch trình giữa chừng (Priority: P2)

Người dùng nói "tôi mệt, bỏ hiking" hoặc "trời mưa, tìm chỗ trong nhà"; hệ thống
giữ phần đã hoàn thành, xếp lại phần còn lại trước giờ kết thúc.

**Why this priority**: Đời thực luôn đổi; làm lại từ đầu là trải nghiệm tệ.

**Independent Test**: Lịch mẫu 5 hoạt động, hoàn thành 2, đổi yêu cầu; kiểm tra
2 hoạt động đầu giữ nguyên, phần còn lại xếp lại hợp lệ.

**Acceptance Scenarios**:

1. **Given** 1 phần itinerary đã hoàn thành, **When** người dùng đổi preference hoặc gặp sự cố, **Then** hệ thống phải giữ hoạt động đã xong, bỏ cái không còn phù hợp, xếp lại phần còn lại trước giờ kết thúc.
2. **Given** yêu cầu mới xung đột ràng buộc cũ, **When** xử lý, **Then** hệ thống phải hỏi ưu tiên thay vì tự bỏ ràng buộc cứng.

---

### User Story 9 - Đánh giá itinerary (Priority: P2)

Researcher/developer chạy benchmark: hệ thống trả metric từng chiều (khả thi,
sở thích, đường đi, phục hồi) để so sánh các phiên bản với nhau và với baseline
đường-ngắn-nhất.

**Why this priority**: Không đo được thì không biết bản nào tốt hơn.

**Independent Test**: Chạy evaluator trên 5 lịch mẫu (đúng/sai lẫn lộn); kiểm tra
lịch sai bị rớt cổng khả thi, lịch đúng được chấm điểm đầy đủ.

**Acceptance Scenarios**:

1. **Given** 1 itinerary và 1 yêu cầu, **When** chạy đánh giá, **Then** phải trả kết quả đạt/rớt từng ràng buộc cứng trước, rồi mới chấm điểm chất lượng mềm.
2. **Given** 2 itinerary cùng yêu cầu ("hiking → beach" vs "beach → hiking"), **When** so sánh, **Then** hệ thống phải xếp hạng đúng theo độ hợp sở thích, không chỉ theo độ dài đường.

---

### Edge Cases

- Prompt thiếu thành phố → hỏi lại thành phố/vị trí hiện tại.
- Prompt thiếu thời gian → hỏi hoặc dùng giả định hiển thị rõ.
- Người dùng chọn A = B → báo trùng, yêu cầu chọn lại.
- Không có POI phù hợp → nới sở thích mềm, không tự bỏ ràng buộc cứng.
- POI đóng cửa → loại hoặc đề xuất khung giờ khác.
- Không đủ thời gian di chuyển → đánh dấu infeasible + đề xuất bỏ/thay POI.
- Vượt ngân sách → đề xuất lịch rẻ hơn hoặc báo cần tăng ngân sách.
- Nguồn dữ liệu ngoài lỗi/timeout → thử lại giới hạn, rồi dùng cache hoặc báo lỗi.
- Mất mạng → dùng snapshot/cache, gắn nhãn không realtime.
- POI chưa xác minh → không đưa vào lịch chính.
- Trời mưa → ưu tiên trong nhà hoặc hỏi user.
- User mệt → giảm cường độ, thêm nghỉ.
- Đổi yêu cầu khi đang đi → giữ đã hoàn thành, replan phần còn lại.
- Preference xung đột → xác định ràng buộc cứng, hỏi ưu tiên hoặc đưa 2 phương án.
- Thiếu giờ mở cửa → gắn uncertainty, không dùng như fact.
- POI đã đi rồi → trừ điểm đề xuất (trừ khi must-visit); penalty mờ dần theo thời gian.
- User mới → onboarding 5 câu, không phạt lịch sử.
- Nhóm đông → must-avoid của bất kỳ ai thành luật chung.

## Requirements *(mandatory)*

### Functional Requirements

**Input và parsing**

- **FR-001**: Khi người dùng nhập yêu cầu tự nhiên, hệ thống PHẢI trích xuất thành trip state có cấu trúc.
- **FR-002**: Trip state PHẢI gồm thành phố, điểm bắt đầu, ngày, giờ, số người, ngân sách, phương tiện.
- **FR-003**: Hệ thống PHẢI trích xuất preference hoạt động, đồ ăn, không gian, nhịp độ, thể lực, mức đông, thứ tự hoạt động.
- **FR-004**: Hệ thống PHẢI phân biệt ràng buộc cứng, sở thích mềm, giả định và điểm chưa chắc chắn.
- **FR-005**: Khi thiếu thông tin cần thiết, hệ thống PHẢI hỏi lại hoặc ghi rõ giả định.
- **FR-006**: Hệ thống KHÔNG ĐƯỢC tự biến sở thích mềm thành ràng buộc cứng nếu user chưa yêu cầu.

**POI và restaurant recommendation**

- **FR-007**: Khi user yêu cầu địa điểm, hệ thống PHẢI tìm POI khớp loại hoạt động, vị trí, giờ mở cửa, ngân sách, preference.
- **FR-008**: Mỗi POI PHẢI có tên, loại, vị trí, điểm phù hợp, giờ mở cửa (nếu có), lý do đề xuất.
- **FR-009**: Hệ thống PHẢI loại hoặc hạ điểm POI vi phạm ràng buộc cứng.
- **FR-010**: Hệ thống PHẢI chấm điểm POI theo cả thuộc tính địa điểm và ngữ cảnh itinerary.
- **FR-011**: Hệ thống PHẢI chấm điểm chuyển tiếp giữa 2 hoạt động (ví dụ hiking → beach).
- **FR-012**: Hệ thống PHẢI cho phép đánh đổi giữa độ hợp gu và chi phí đường đi.
- **FR-013**: Hệ thống PHẢI gắn nhãn uncertainty cho dữ liệu chưa xác minh.

**Lập lịch**

- **FR-014**: Hệ thống PHẢI chọn POI và sắp theo thứ tự thời gian.
- **FR-015**: Hệ thống PHẢI kiểm tra giờ mở cửa POI.
- **FR-016**: Hệ thống PHẢI kiểm tra đủ thời gian di chuyển giữa 2 POI.
- **FR-017**: Hệ thống PHẢI kiểm tra ngân sách tổng.
- **FR-018**: Hệ thống PHẢI tính giờ tham quan, ăn, nghỉ, di chuyển.
- **FR-019**: Hệ thống PHẢI hãm lịch quá dày khi vượt ngưỡng thời lượng/thể lực.
- **FR-020**: MVP PHẢI hỗ trợ tối thiểu 1 ngày, tối đa 2 ngày.
- **FR-021**: Hệ thống PHẢI hiển thị tổng giờ đi, tổng tiền, các ràng buộc đã đáp ứng.
- **FR-022**: Khi không có lịch khả thi, hệ thống PHẢI trả lý do + đề xuất nới sở thích mềm.

**Giải thích**

- **FR-023**: Hệ thống PHẢI giải thích lý do chọn POI và thứ tự.
- **FR-024**: Mỗi lý do PHẢI phân biệt fact từ dữ liệu và inference từ preference.
- **FR-025**: Hệ thống KHÔNG ĐƯỢC trình bày assumption như fact.
- **FR-026**: Hệ thống PHẢI ghi rõ khi giờ mở cửa/rating/giá không chắc chắn.

**Replanning động**

- **FR-027**: Hệ thống PHẢI lưu giờ hiện tại, vị trí hiện tại, đã xong, đã hủy, còn lại.
- **FR-028**: Khi user thêm/bớt/đổi preference, hệ thống PHẢI cập nhật trip state.
- **FR-029**: Khi có sự cố, hệ thống PHẢI xếp lại phần chưa hoàn thành.
- **FR-030**: Hệ thống PHẢI giữ hoạt động đã hoàn thành.
- **FR-031**: Hệ thống PHẢI cố giữ các ràng buộc cứng còn hiệu lực.
- **FR-032**: Hệ thống PHẢI giảm thay đổi không cần thiết so với lịch cũ.
- **FR-033**: Hệ thống PHẢI hiển thị phần nào giữ/bỏ/thay/sắp lại.
- **FR-034**: Hệ thống PHẢI báo khi không đáp ứng đồng thời các yêu cầu.

**Đánh giá**

- **FR-035**: Hệ thống PHẢI có validator kiểm tra thực thể, thời gian, giờ mở cửa, ngân sách, khả thi đường đi.
- **FR-036**: Hệ thống PHẢI tính Preference Satisfaction.
- **FR-037**: Hệ thống PHẢI tính Activity Order Accuracy hoặc Preference-aware Regret.
- **FR-038**: Hệ thống PHẢI tính Route Efficiency và Time Utilization.
- **FR-039**: Hệ thống PHẢI hỗ trợ đánh giá pairwise giữa 2 itinerary.
- **FR-040**: Hệ thống PHẢI đánh giá dynamic recovery sau sự cố.

**Nhiều phương án**

- **FR-041**: Hệ thống PHẢI sinh ≥2 phương án khả thi khi có thể.
- **FR-042**: Mỗi phương án PHẢI kèm điểm số + lý do khác biệt.
- **FR-043**: Người dùng PHẢI xác nhận trước khi chốt phương án.

**Lịch sử đã đi**

- **FR-044**: Hệ thống PHẢI lưu lịch sử đã đi (POI + thời gian + rating).
- **FR-045**: POI đã đi PHẢI bị trừ điểm đề xuất trừ khi nằm trong must-visit.
- **FR-046**: Penalty PHẢI mờ dần theo thời gian.

**Hành vi user**

- **FR-047**: Mọi thay đổi gu PHẢI ghi state_delta + version itinerary.
- **FR-048**: Must-avoid của bất kỳ thành viên nào PHẢI thành ràng buộc cứng chung.
- **FR-049**: Chuyến công tác PHẢI tắt penalty điểm đã đi.
- **FR-050**: User mới PHẢI qua onboarding 5 câu trước khi gợi ý.

### Key Entities *(include if feature involves data)*

- **User**: id, ngôn ngữ, nhóm người, mục đích chuyến đi, sở thích dài hạn/hiện tại, thể lực, ngân sách, phương tiện, lịch sử đã đi + feedback.
- **TripRequest**: origin, city, date, giờ bắt đầu/kết thúc, số người, ngân sách, phương tiện, must-visit, avoid, activities, food/order preferences.
- **POI**: id, tên, loại, tọa độ, giờ mở cửa, duration, giá, rating, tags, intensity, ambience, weather sensitivity, nguồn, freshness.
- **Restaurant**: thuộc tính POI + cuisine, price range, crowd, dietary tags, reservation, meal availability.
- **RouteSegment**: POI đi/đến, phương tiện, khoảng cách, duration, nguồn, confidence, timestamp.
- **Activity**: POI, loại, giờ bắt đầu/kết thúc, intensity, duration, nghỉ trước/sau.
- **Itinerary**: id, activities có thứ tự, segments, tổng tiền/khoảng cách/giờ đi, constraint status, preference score, explanation, version.
- **DynamicEvent**: loại, thời gian, nguồn, activity ảnh hưởng, constraint mới, mức độ, cách xử lý.
- **Expense**: trip id, khoản chi, số tiền, thời điểm, loại; liên kết ngân sách trip.
- **WeatherSnapshot**: thời điểm lấy, nhiệt độ, xác suất mưa theo giờ, nguồn.
- **EvaluationRecord**: input, itinerary sinh ra, baseline, kết quả khả thi, điểm preference/route/recovery, nhãn pairwise (nếu có).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ≥95% yêu cầu mẫu được trích xuất thành trip state đúng định dạng.
- **SC-002**: ≥85% ràng buộc cứng trong yêu cầu được nhận diện đúng.
- **SC-003**: POI gợi ý đạt Recall@10 ≥70% trên tập kiểm tra.
- **SC-004**: Điểm transition đúng thứ tự ưu tiên ≥70% cặp kiểm tra.
- **SC-005**: ≥90% task khả thi cho ra lịch qua được cổng kiểm tra.
- **SC-006**: Vi phạm giờ mở cửa = 0 trên task có đủ dữ liệu.
- **SC-007**: Không trùng giờ hoạt động, không thiếu thời gian di chuyển.
- **SC-008**: Vi phạm ngân sách = 0 khi ngân sách là ràng buộc cứng.
- **SC-009**: Điểm hợp gu của hệ thống cao hơn baseline đường-ngắn-nhất ≥10%.
- **SC-010**: Phục hồi sau sự cố thành công ≥80%, giữ 100% hoạt động đã xong.
- **SC-011**: Xếp lại xong trong 15 giây; lịch đầy đủ trong 30 giây.
- **SC-012**: ≥90% lời giải thích có bằng chứng từ input/dữ liệu; không claim thiếu căn cứ.
- **SC-013**: Ngân sách hiển thị khớp chi thực tế đã ghi (sai số do giá ước tính được ghi rõ).
- **SC-014**: 100% hoạt động đã hoàn thành được giữ nguyên sau replanning.
- **SC-015**: Replanning hoàn thành trong 15 giây.
- **SC-016**: Hiển thị ít nhất 1 lý do cho mỗi thay đổi trong replan.
- **SC-017**: Khi không đáp ứng được ràng buộc, trả lỗi có cấu trúc (không crash).
- **SC-018**: ≥90% explanation chứa ít nhất 1 evidence từ input hoặc data source.
- **SC-019**: Không claim địa điểm mở cửa nếu không có dữ liệu xác minh.

## Assumptions

- MVP 1 thành phố (Đà Nẵng), tối đa 2 ngày; user xác nhận giờ bắt đầu/kết thúc.
- POI data via Google Places API (legal, ~$3.40 cho 200 POIs); bổ sung thủ công các field API thiếu (visit_duration, intensity, ambience).
- Routing: OSRM snapshot matrix (không dùng VietMap — free, deterministic, offline).
- Sở thích mềm được nới khi vô nghiệm; ràng buộc cứng không tự nới.
- LLM không phải nguồn sự thật duy nhất; validator chịu trách nhiệm cuối.
- User có mạng khi cần search/routing; mất mạng dùng cache/snapshot kèm nhãn.
- Mobile (Flutter) là FE chính; BE deploy free tier (Render/Fly.io); local dev trên MacBook.
- Dynamic replanning là feature thật (không phải demo-only); demo dùng mock GPS thay GPS thật, interface giống hệt.
- Không booking/thanh toán thật; key qua `.env`.
- Ngôn ngữ: tiếng Việt trước, tiếng Anh sau (khi ổn định).
- Benchmark tự động không bắt buộc hỏi clarification; app thực tế được hỏi lại.
- Thuộc tính cảm tính ("yên tĩnh", "hợp hẹn hò") là suy luận từ review, luôn gắn uncertainty.
- Đi công tác tắt phạt điểm đã đi; user mới onboarding trước khi gợi ý.
