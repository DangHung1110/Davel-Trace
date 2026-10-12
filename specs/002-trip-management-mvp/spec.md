# Feature Specification: Trip Management MVP

**Feature Branch**: `feat/002-trip-management-mvp`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Hoàn thiện ứng dụng MVP trước khi thêm AI, tập trung vào quản lý người dùng, chuyến đi, lịch trình thủ công, bản đồ và chi tiêu; dữ liệu phải được lưu bền vững và có thể kiểm tra bằng công cụ quản trị cơ sở dữ liệu."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quản lý hồ sơ cá nhân (Priority: P1)

Người dùng tạo và cập nhật hồ sơ du lịch cá nhân gồm tên hiển thị, ngôn ngữ, nhịp độ, thể lực, mức chi tiêu, sở thích ăn uống và điều cần tránh. Ứng dụng nhớ hồ sơ đang hoạt động sau khi đóng và mở lại.

**Why this priority**: Hồ sơ là chủ thể sở hữu chuyến đi và chi tiêu, đồng thời tạo dữ liệu đầu vào ổn định cho AI ở giai đoạn sau.

**Independent Test**: Tạo một hồ sơ, sửa ít nhất hai thuộc tính, đóng và mở lại hệ thống; hồ sơ đã sửa vẫn còn và được chọn làm hồ sơ hoạt động.

**Acceptance Scenarios**:

1. **Given** chưa có hồ sơ, **When** người dùng nhập dữ liệu hợp lệ và lưu, **Then** hệ thống tạo hồ sơ và chọn hồ sơ đó làm hồ sơ hoạt động.
2. **Given** đã có hồ sơ, **When** người dùng sửa sở thích hoặc thông tin hiển thị, **Then** thay đổi được lưu và xuất hiện lại sau khi khởi động lại.
3. **Given** hồ sơ đang sở hữu chuyến đi, **When** người dùng yêu cầu xóa hồ sơ, **Then** hệ thống cảnh báo tác động và chỉ xóa sau khi xác nhận rõ ràng.

---

### User Story 2 - Quản lý chuyến đi và lịch thủ công (Priority: P1)

Người dùng tạo chuyến đi Đà Nẵng, đặt thời gian và ngân sách, rồi tự thêm, sửa, xóa và sắp xếp các hoạt động. Một hoạt động có thể tham chiếu POI trong catalog hoặc là địa điểm tùy chỉnh.

**Why this priority**: Đây là luồng sử dụng chính giúp ứng dụng hữu ích ngay cả khi chưa có AI lập lịch.

**Independent Test**: Tạo chuyến đi một ngày, thêm ba hoạt động, đổi thứ tự và sửa thời gian; lịch cuối cùng giữ đúng thứ tự và dữ liệu sau khi mở lại.

**Acceptance Scenarios**:

1. **Given** có hồ sơ hoạt động, **When** người dùng tạo chuyến đi với ngày, giờ và ngân sách hợp lệ, **Then** chuyến đi xuất hiện trong danh sách của hồ sơ đó.
2. **Given** có chuyến đi nháp, **When** người dùng thêm POI hoặc địa điểm tùy chỉnh vào lịch, **Then** hoạt động lưu tên, tọa độ, thời gian dự kiến và nguồn tạo thủ công.
3. **Given** lịch có nhiều hoạt động, **When** người dùng đổi thứ tự hoặc thời gian, **Then** hệ thống lưu thứ tự mới và cảnh báo nếu các khung giờ chồng lấn.
4. **Given** chuyến đi chưa bắt đầu, **When** người dùng xóa chuyến đi và xác nhận, **Then** chuyến đi cùng dữ liệu phụ thuộc bị xóa khỏi danh sách.

---

### User Story 3 - Theo dõi ngân sách và chi tiêu (Priority: P1)

Người dùng ghi lại, sửa và xóa các khoản chi theo chuyến đi; ứng dụng hiển thị tổng đã chi, số còn lại, phân bổ theo danh mục và cảnh báo khi đạt 80% hoặc 100% ngân sách.

**Why this priority**: Quản lý chi tiêu là giá trị chính của management MVP và dữ liệu số dư sẽ được AI dùng làm ràng buộc sau này.

**Independent Test**: Với chuyến đi có ngân sách 3.000.000 đồng, thêm, sửa và xóa nhiều khoản chi; tổng tiền, số còn lại, danh mục và cảnh báo luôn khớp phép tính độc lập.

**Acceptance Scenarios**:

1. **Given** chuyến đi có ngân sách 3.000.000 đồng, **When** người dùng ghi tổng chi 2.500.000 đồng, **Then** hệ thống hiển thị còn 500.000 đồng và cảnh báo đã vượt ngưỡng 80%.
2. **Given** đã có một khoản chi, **When** người dùng sửa số tiền hoặc danh mục, **Then** tổng hợp được tính lại ngay và không đếm trùng khoản cũ.
3. **Given** tổng chi đạt hoặc vượt ngân sách, **When** mở màn hình chi tiêu, **Then** hệ thống hiển thị cảnh báo 100% và số còn lại có thể âm khi vượt ngân sách.
4. **Given** chuyến đi không có khoản chi, **When** mở màn hình chi tiêu, **Then** hệ thống hiển thị trạng thái trống cùng ngân sách đầy đủ còn lại.

---

### User Story 4 - Xem lịch trên bản đồ và tuyến đường (Priority: P2)

Người dùng xem các hoạt động của chuyến đi trên bản đồ Đà Nẵng, xem vị trí hiện tại khi cấp quyền, và yêu cầu tuyến đường bám theo đường thực giữa các điểm theo thứ tự lịch.

**Why this priority**: Bản đồ giúp lịch thủ công trở nên trực quan và tái sử dụng tài sản PMTiles/OSRM hiện có mà không phụ thuộc AI.

**Independent Test**: Mở một chuyến đi có ba điểm, kiểm tra marker theo đúng thứ tự và yêu cầu tuyến; tuyến hiển thị theo thứ tự hoạt động, hoặc hệ thống báo rõ khi dịch vụ tuyến không khả dụng.

**Acceptance Scenarios**:

1. **Given** chuyến đi có hoạt động với tọa độ hợp lệ, **When** người dùng mở bản đồ, **Then** hệ thống hiển thị các marker theo thứ tự hoạt động trên bản đồ Đà Nẵng.
2. **Given** có ít nhất hai điểm, **When** người dùng yêu cầu chỉ đường, **Then** hệ thống hiển thị tuyến từ dịch vụ routing và phân biệt rõ với đường dự phòng không phải tuyến thật.
3. **Given** người dùng từ chối quyền vị trí, **When** mở bản đồ, **Then** lịch và tuyến vẫn xem được nhưng không hiển thị vị trí hiện tại.
4. **Given** dịch vụ tìm đường không truy cập được, **When** người dùng yêu cầu tuyến, **Then** hệ thống giữ lịch hiện tại, hiển thị lỗi có thể thử lại và không trình bày đường nội suy như tuyến thật.

---

### User Story 5 - Khôi phục phiên làm việc và xử lý lỗi (Priority: P2)

Người dùng tiếp tục sử dụng dữ liệu quản lý đã lưu sau khi ứng dụng hoặc backend khởi động lại; các trạng thái tải, trống và lỗi đều có hướng dẫn rõ ràng thay vì làm mất dữ liệu đang xem.

**Why this priority**: Persistence và khả năng phục hồi biến bản demo giao diện thành ứng dụng quản lý có thể sử dụng thực tế.

**Independent Test**: Tạo hồ sơ, chuyến đi, hoạt động và chi tiêu; khởi động lại toàn bộ ứng dụng/backend rồi xác nhận toàn bộ dữ liệu và quan hệ vẫn còn.

**Acceptance Scenarios**:

1. **Given** đã có dữ liệu hợp lệ, **When** backend khởi động lại, **Then** hồ sơ, chuyến đi, hoạt động và chi tiêu vẫn được tải lại đầy đủ.
2. **Given** yêu cầu mạng thất bại, **When** người dùng đang xem dữ liệu đã tải, **Then** hệ thống giữ dữ liệu hiện có, báo lỗi và cho phép thử lại.
3. **Given** không có dữ liệu cho một màn hình, **When** người dùng mở màn hình đó, **Then** hệ thống hiển thị trạng thái trống và hành động tiếp theo phù hợp.

### Edge Cases

- Tên hồ sơ hoặc tên chuyến đi chỉ chứa khoảng trắng.
- Ngày kết thúc trước ngày bắt đầu hoặc giờ kết thúc trước giờ bắt đầu trong cùng ngày.
- Ngân sách bằng 0, khoản chi bằng 0, khoản chi âm hoặc số tiền vượt phạm vi hợp lệ.
- Hai hoạt động chồng lấn thời gian hoặc có cùng thứ tự.
- POI snapshot được cập nhật hoặc POI bị thiếu sau khi hoạt động đã được lưu.
- Địa điểm tùy chỉnh thiếu tọa độ hoặc tọa độ nằm ngoài phạm vi hợp lệ.
- Xóa hồ sơ/chuyến đi khi đang có dữ liệu phụ thuộc.
- Yêu cầu vị trí bị từ chối, bị thu hồi hoặc không được hỗ trợ trên thiết bị.
- OSRM, ảnh từ xa hoặc API quản lý bị timeout/mất mạng.
- Hai thao tác cập nhật cùng một bản ghi dựa trên phiên bản cũ.
- Cơ sở dữ liệu mới chưa có bảng hoặc migration bị dừng giữa chừng.

## Requirements *(mandatory)*

### Functional Requirements

**Hồ sơ người dùng**

- **FR-001**: Hệ thống PHẢI cho phép tạo, đọc, cập nhật và xóa hồ sơ người dùng cục bộ.
- **FR-002**: Hồ sơ PHẢI lưu tên hiển thị, ngôn ngữ, loại nhóm, mục đích chuyến đi, mức chi tiêu, nhịp độ, thể lực, sở thích ăn uống và điều cần tránh.
- **FR-003**: Hệ thống PHẢI duy trì đúng một hồ sơ hoạt động trên mỗi phiên thiết bị và khôi phục lựa chọn đó khi mở lại.
- **FR-004**: Hệ thống PHẢI yêu cầu xác nhận trước khi xóa hồ sơ có dữ liệu phụ thuộc và PHẢI mô tả dữ liệu sẽ bị xóa.

**Chuyến đi và lịch thủ công**

- **FR-005**: Hệ thống PHẢI cho phép tạo, đọc, cập nhật và xóa chuyến đi thuộc một hồ sơ.
- **FR-006**: Chuyến đi PHẢI lưu tên, thành phố, ngày bắt đầu/kết thúc, giờ bắt đầu/kết thúc, số người, ngân sách, phương tiện và trạng thái.
- **FR-007**: Management MVP PHẢI giới hạn chuyến đi tại Đà Nẵng và tối đa hai ngày.
- **FR-008**: Hệ thống PHẢI cho phép thêm, sửa, xóa và sắp xếp hoạt động thủ công trong chuyến đi.
- **FR-009**: Hoạt động PHẢI hỗ trợ cả POI catalog và địa điểm tùy chỉnh; khi đã lưu, tên và tọa độ hiển thị PHẢI không phụ thuộc vào lần cập nhật catalog sau đó.
- **FR-010**: Hệ thống PHẢI cảnh báo khung giờ chồng lấn nhưng không tự ý thay đổi lịch thủ công của người dùng.
- **FR-011**: Mỗi thay đổi lịch PHẢI tăng phiên bản itinerary và ghi nguồn hoạt động là `manual`; nguồn `ai` được dành cho tích hợp sau này.

**Chi tiêu**

- **FR-012**: Hệ thống PHẢI cho phép tạo, đọc, cập nhật và xóa khoản chi thuộc một chuyến đi.
- **FR-013**: Khoản chi PHẢI lưu nhãn, số tiền nguyên theo VND, thời điểm và danh mục `food`, `ticket`, `transport` hoặc `other`.
- **FR-014**: Hệ thống PHẢI tính tổng đã chi, số còn lại và tổng theo danh mục từ dữ liệu khoản chi hiện tại.
- **FR-015**: Hệ thống PHẢI cảnh báo khi tổng chi đạt ít nhất 80% và khi đạt ít nhất 100% ngân sách.
- **FR-016**: Khoản chi PHẢI liên kết với chuyến đi thay vì một phiên bản itinerary để dữ liệu không mất khi lịch được tạo lại sau này.

**Bản đồ, POI và tuyến đường**

- **FR-017**: Hệ thống PHẢI tiếp tục sử dụng bản đồ PMTiles Đà Nẵng hiện có và không được xóa tài sản bản đồ đang tracked.
- **FR-018**: Hệ thống PHẢI hiển thị marker hoạt động theo thứ tự lịch và hỗ trợ xem chi tiết địa điểm.
- **FR-019**: Hệ thống PHẢI dùng dữ liệu POI như catalog dùng chung, độc lập với AI, và giữ định danh POI ổn định trong một phiên bản snapshot.
- **FR-020**: Hệ thống PHẢI dùng tuyến từ dịch vụ routing khi khả dụng; đường dự phòng không PHẢI route thật và PHẢI được gắn nhãn rõ.
- **FR-021**: Từ chối quyền vị trí KHÔNG ĐƯỢC chặn việc xem lịch, POI hoặc tuyến đường.

**Persistence và API**

- **FR-022**: Hồ sơ, chuyến đi, itinerary, hoạt động và chi tiêu PHẢI được lưu bền vững qua các lần khởi động lại.
- **FR-023**: Hệ thống PHẢI có lịch sử migration có thể tái tạo schema trên một cơ sở dữ liệu mới mà không chỉnh bảng thủ công.
- **FR-024**: Tất cả thao tác ghi PHẢI được kiểm tra tính hợp lệ và trả lỗi có cấu trúc, không để dữ liệu một phần sau lỗi.
- **FR-025**: Cập nhật bản ghi PHẢI phát hiện phiên bản cũ và từ chối ghi đè im lặng khi có xung đột.
- **FR-026**: Giao diện PHẢI có trạng thái loading, empty, error và retry cho mọi dữ liệu tải bất đồng bộ.
- **FR-027**: Hệ thống PHẢI giữ ranh giới planner độc lập để AI sau này chỉ tạo proposal; proposal không được ghi đè lịch chính nếu người dùng chưa xác nhận.

### Key Entities

- **UserProfile**: Chủ sở hữu dữ liệu quản lý; gồm thông tin hiển thị, thuộc tính du lịch và preferences có cấu trúc.
- **Trip**: Chuyến đi của một hồ sơ; sở hữu ngân sách, khoảng thời gian, trạng thái và các itinerary version.
- **Itinerary**: Một phiên bản lịch có thứ tự của chuyến đi; có nguồn `manual` hoặc `ai`, trạng thái draft/active/archived và số version.
- **Activity**: Một mục có thời gian trong itinerary; tham chiếu POI tùy chọn và lưu snapshot tên/tọa độ để giữ lịch sử.
- **Expense**: Khoản chi thuộc trực tiếp một Trip; không phụ thuộc phiên bản itinerary.
- **POI**: Catalog địa điểm Đà Nẵng có định danh ổn định, provenance và phiên bản snapshot; dùng chung cho map, lịch thủ công và AI sau này.
- **RouteSegment**: Tuyến giữa hai hoạt động, gồm nguồn, khoảng cách, thời lượng và thời điểm lấy dữ liệu.
- **PlannerProposal**: Dữ liệu đề xuất tạm thời dành cho tích hợp AI sau này; chỉ trở thành itinerary khi người dùng xác nhận.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Người dùng mới có thể tạo hồ sơ và chuyến đi thủ công đầu tiên trong tối đa 3 phút.
- **SC-002**: 100% hồ sơ, chuyến đi, hoạt động và khoản chi đã lưu hợp lệ còn tồn tại sau khi khởi động lại ứng dụng và backend.
- **SC-003**: Tổng chi, số còn lại, cảnh báo ngưỡng và tổng theo danh mục khớp chính xác với phép tính độc lập cho toàn bộ bộ test ngân sách.
- **SC-004**: 100% thao tác tạo/sửa/xóa bị lỗi không để lại bản ghi một phần hoặc quan hệ mồ côi.
- **SC-005**: Người dùng có thể thêm, sửa, xóa và đổi thứ tự ba hoạt động mà không cần AI và nhìn thấy kết quả cập nhật trong tối đa 2 giây ở môi trường local.
- **SC-006**: Khi có mạng, tuyến cho lịch tối đa 10 điểm được hiển thị hoặc trả lỗi có thể thử lại trong tối đa 10 giây.
- **SC-007**: Khi không có mạng hoặc không cấp quyền vị trí, 100% dữ liệu quản lý đã lưu vẫn xem được và ứng dụng không crash.
- **SC-008**: Tất cả màn hình quản lý đều có trạng thái loading, empty và error có hành động tiếp theo rõ ràng.
- **SC-009**: Toàn bộ luồng map/search A-B/route/play-pause của prototype hiện có vẫn chạy sau khi management MVP được thêm.
- **SC-010**: Một cơ sở dữ liệu mới có thể được khởi tạo hoàn toàn từ lịch sử migration và có thể kiểm tra bằng công cụ quản trị cơ sở dữ liệu phổ biến.

## Assumptions

- Management MVP sử dụng hồ sơ cục bộ và không bao gồm đăng ký, mật khẩu, đăng nhập từ xa hoặc phân quyền nhiều vai trò.
- AI parsing, recommendation, automatic itinerary generation, weather replan và evaluator không thuộc phạm vi feature này; các branch AI hiện có được giữ nguyên.
- Đà Nẵng là thành phố duy nhất và mỗi chuyến đi dài tối đa hai ngày.
- Đơn vị tiền là VND và lưu dưới dạng số nguyên, không xử lý thanh toán thật.
- POI snapshot hiện có là catalog dùng chung; trường AI-specific có thể trống mà không chặn lịch thủ công.
- Routing cần mạng nếu không có cache; bản đồ nền PMTiles phải tiếp tục xem được bằng tài sản local.
- Booking, payment, receipt OCR, social sharing, multi-device sync, push notification và multi-city nằm ngoài phạm vi.
- Một người sử dụng ứng dụng demo tại một thời điểm; xung đột cập nhật vẫn được phát hiện bằng version để chuẩn bị cho client thực.
