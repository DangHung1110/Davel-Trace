# Feature Specification: Giá theo khoản, tổng tiền chuyến đi đúng và chuyển luật cứng thành mềm

**Feature Branch**: `feat/019-pricing-soft-rules` (spec id `019-pricing-soft-rules`; trước đây đánh số 002, đổi 21/11 vì số 002 đã dùng ở nhánh `feat/002-trip-management-mvp`)

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Thêm 1 feat về tiền: vé nhiều mức, phí bắt buộc, đếm khoản chưa biết; tổng tiền đúng theo số người; dùng giá cho train model (giữ cả giá ước lượng, chỉ gắn cờ). Bỏ luật cứng, chỉ giữ sở thích người dùng đặt."

Nền dữ liệu: snapshot `danang-v2` v2.1 (PR #25). Hiện trạng và lỗ hổng: `docs/travelagent/DATA_FIX_PLAN.md` mục 4b.

## Bối cảnh (hiện trạng phải thay)

- Mỗi điểm chỉ có **một mức giá** (`price.tier`). Tổng tiền = cộng điểm giữa của mức (rẻ 50k, trung bình 250k, đắt 850k) cho mỗi điểm.
- Vé theo đối tượng (người lớn / trẻ em / người địa phương / hạng ghế) và phí bắt buộc (gửi xe, thang máy, thuyền, cano) chỉ nằm trong ghi chú chữ; 34 điểm đang ở tình trạng này.
- Điểm chưa rõ giá được cộng **0**: tổng tiền luôn thấp hơn thực tế mà không báo.
- Tổng tiền **không nhân số người** dù yêu cầu có "2 người".
- Vé chung (phố cổ Hội An, 31 điểm "included") tính 0 ở điểm con nhưng **không ai cộng vé cha** khi lịch không có điểm cha.
- Bộ xếp lịch có nhiều luật cứng tự đặt (1 nhà hàng/bữa, giới hạn cà phê, mỗi loại tối đa 1/ngày, không 2 điểm cùng loại liền nhau, bữa trưa bắt buộc, nghỉ trưa, 1 lớp nấu ăn/ngày). Vi phạm bất kỳ luật nào làm lịch "hỏng", kể cả khi khách không quan tâm.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tổng tiền chuyến đi đáng tin (Priority: P1)

Khách nhập số người và ngân sách; lịch trả về tổng tiền cho **cả nhóm**, nói rõ phần nào là giá có nguồn,
phần nào ước lượng và bao nhiêu khoản chưa rõ giá — không bao giờ ngầm coi khoản chưa rõ là 0đ.

**Why this priority**: Ngân sách là ràng buộc khách đặt; tổng sai thì cảnh báo vượt ngân sách vô nghĩa.

**Independent Test**: Lịch cố định 1 ngày cho 2 người lớn gồm 1 điểm vé, 1 hội quán Hội An (vé chung), 1 điểm chưa rõ giá;
kiểm tra tổng = 2 × vé + 1 lần vé chung × 2 người, và có dòng "1 khoản chưa rõ giá".

**Acceptance Scenarios**:

1. **Given** lịch cho 2 người lớn, **When** tính tổng, **Then** mọi khoản tính theo người được nhân 2; khoản tính theo nhóm/xe tính theo số nhóm/xe.
2. **Given** lịch có 3 hội quán cùng vé chung phố cổ nhưng không có điểm "vé phố cổ", **When** tính tổng, **Then** vé phố cổ được cộng đúng 1 lần mỗi người.
3. **Given** lịch có điểm chưa rõ giá, **When** hiển thị tổng, **Then** hiện dạng khoảng "X–Y đ + N khoản chưa rõ giá", không hiện một con số chắc chắn.
4. **Given** khoảng tổng tiền chồng lên ngân sách (cận dưới ≤ ngân sách < cận trên), **When** kiểm tra ngân sách, **Then** lịch vẫn hợp lệ nhưng có cảnh báo "có thể vượt ngân sách".

---

### User Story 2 - Thấy đúng giá cho mình (Priority: P1)

Khách thấy từng khoản của điểm: vé người lớn/trẻ em/người địa phương, hạng vé, phí bắt buộc, khoản tuỳ chọn.

**Why this priority**: Bà Nà 1.000.000 (ngoại tỉnh) vs 650.000 (người Đà Nẵng) vs 500.000 (18–25 tuổi) — một con số chung sai với gần như mọi khách.

**Independent Test**: Điểm Bà Nà với nhóm 2 người lớn ngoại tỉnh + 1 trẻ 1,2 m; kiểm tra tổng dùng đúng giá từng đối tượng
và liệt kê khoản tuỳ chọn (buffet) riêng, không cộng vào tổng.

**Acceptance Scenarios**:

1. **Given** điểm có nhiều mức vé, **When** khách khai là người địa phương, **Then** dùng giá địa phương.
2. **Given** điểm có phí bắt buộc theo xe (gửi xe), **When** tính tổng, **Then** cộng theo số xe (mặc định suy từ số người, nói rõ giả định).
3. **Given** khoản tuỳ chọn (VIP, buffet, thuyền thúng ở điểm không bắt buộc), **When** hiển thị, **Then** liệt kê riêng, không cộng vào tổng trừ khi khách chọn.
4. **Given** điểm chỉ có mức giá (chưa có khoản chi tiết), **When** tính tổng, **Then** dùng giá ước lượng theo mức và đánh dấu "ước lượng".

---

### User Story 3 - Lịch theo sở thích của khách, không theo luật tự đặt (Priority: P2)

Chỉ những gì là **điều kiện thực tế** hoặc **khách tự đặt** mới làm lịch không hợp lệ; các luật "lịch đẹp" thành điểm trừ.

**Why this priority**: Khách muốn 2 quán cà phê hay ăn trưa lúc 14h là quyền của khách; luật cứng tự đặt đang loại những lịch đó.

**Independent Test**: Khách yêu cầu "đi 3 quán cà phê"; lịch phải có 3 quán (bị trừ điểm mềm, không bị loại).

**Acceptance Scenarios**:

1. **Given** lịch vi phạm một luật mềm, **When** chấm, **Then** lịch vẫn hợp lệ, điểm bị trừ và giải thích nêu luật đó.
2. **Given** lịch vi phạm điều kiện thực tế (ngoài giờ mở cửa, khung đường Sơn Trà, không kịp di chuyển, trùng giờ, quá giờ về), **When** kiểm tra, **Then** lịch không hợp lệ.
3. **Given** khách đặt sở thích (ngân sách, điểm bắt buộc, loại hoạt động, nhịp đi, chỉ gợi ý lớp nấu ăn khi chọn ẩm thực/văn hoá), **When** xếp lịch, **Then** sở thích đó là ràng buộc cứng.
4. **Given** hai lịch cùng hợp lệ, **When** so sánh, **Then** lịch ít điểm trừ mềm hơn được ưu tiên khi các yếu tố khác ngang nhau.

---

### User Story 4 - Dữ liệu tiền cho model (Priority: P2)

Bộ dữ liệu xuất cho train có cột tiền dạng số phẳng, **giữ cả giá ước lượng** và gắn cờ, không lọc bỏ.

**Why this priority**: 648/745 điểm có giá ước lượng; bỏ đi là mất gần hết thông tin tiền. Giá ước lượng vẫn đúng chiều tương đối.

**Independent Test**: Xuất `poi_features.csv`; kiểm tra mọi điểm đang dùng có cột tiền, và cột cờ phân biệt nguồn/ước lượng.

**Acceptance Scenarios**:

1. **Given** điểm chỉ có giá ước lượng, **When** xuất, **Then** vẫn có giá trị số và cờ `price_known = 0`.
2. **Given** điểm có khoản chi tiết, **When** xuất, **Then** có tổng bắt buộc cho 1 người lớn, tỉ lệ giá trẻ em, có/không phí bắt buộc, có/không giá địa phương, tổng khoản tuỳ chọn.

---

### Edge Cases

- Khách không nói số người → dùng mặc định hiện có (2 người lớn) và **nói rõ giả định**.
- Không nói có trẻ em / người địa phương → coi là người lớn ngoại tỉnh; nói rõ giả định.
- Giá ghi bằng USD → quy đổi theo tỉ giá cố định trong cấu hình, ghi tỉ giá đã dùng.
- Khoản theo nhóm cố định (thuyền thúng 2 người/thúng) với số người lẻ → làm tròn lên.
- Vé chung + điểm cha cũng nằm trong lịch → không cộng hai lần.
- Giá theo ngày (cuối tuần, lễ) → ngoài phạm vi; dùng giá ngày thường và ghi chú nếu nguồn có nêu.
- Tất cả điểm trong lịch đều chưa rõ giá → không hiện tổng 0đ; hiện "chưa đủ thông tin giá".
- Lịch chỉ khả thi khi vi phạm nhiều luật mềm → vẫn trả lịch, kèm danh sách điểm trừ.

## Requirements *(mandatory)*

### Functional Requirements

**Dữ liệu giá**

- **FR-001**: Mỗi điểm PHẢI có thể mang danh sách **khoản tiền** (price items): tên khoản, số tiền, đối tượng áp dụng (người lớn / trẻ em / người địa phương / hạng), đơn vị tính (mỗi người / mỗi nhóm N người / mỗi xe / mỗi lượt), bắt buộc hay tuỳ chọn, nguồn.
- **FR-002**: Mức giá tóm tắt hiện có PHẢI được giữ và suy ra từ khoản bắt buộc cho 1 người lớn khi có khoản chi tiết (tương thích ngược).
- **FR-003**: Điểm chưa có khoản chi tiết PHẢI tiếp tục dùng mức giá ước lượng, gắn nhãn "ước lượng".
- **FR-004**: Mọi khoản tiền PHẢI đi qua file nguồn + bước dựng snapshot hiện có; không sửa tay snapshot (DATA_FIX_PLAN mục 5).

**Tính tổng tiền**

- **FR-005**: Tổng tiền PHẢI tính cho cả nhóm theo thành phần nhóm (số người lớn, trẻ em, người địa phương), nhân đúng đơn vị tính của từng khoản.
- **FR-006**: Vé chung (điểm con có vé cha) PHẢI được cộng đúng 1 lần mỗi người cho cả lịch, dù có hay không có điểm cha.
- **FR-007**: Khoản chưa rõ giá KHÔNG ĐƯỢC tính là 0; tổng PHẢI có cận dưới, cận trên và số khoản chưa rõ.
- **FR-008**: Kiểm tra ngân sách PHẢI dùng khoảng tổng: vượt khi cận dưới > ngân sách; cảnh báo khi ngân sách nằm trong khoảng.
- **FR-009**: Khoản tuỳ chọn PHẢI hiển thị riêng và chỉ cộng khi khách chọn.
- **FR-010**: Mọi giả định (số người, đối tượng, tỉ giá, số xe) PHẢI được nêu trong phần giải thích (FR-025 của spec 001: không trình bày giả định như fact).
- **FR-011**: Bảng chi phí PHẢI tách theo loại khớp sổ chi tiêu hiện có (ăn / vé / di chuyển / khác) để so dự kiến với thực chi.

**Luật cứng → mềm**

- **FR-012**: Chỉ các nhóm sau là ràng buộc cứng: (a) điều kiện thực tế — giờ mở cửa (gồm suất đặt trước, khung đường bán đảo Sơn Trà), thời gian di chuyển, giờ kết thúc ngày, không trùng giờ, điểm phải đủ dữ liệu xếp lịch; (b) sở thích khách đặt — ngân sách, điểm bắt buộc, loại hoạt động, nhịp đi, chỉ gợi ý trải nghiệm đặt trước khi chọn ẩm thực/văn hoá.
- **FR-013**: Các luật sau PHẢI chuyển thành điểm trừ mềm: 1 nhà hàng mỗi bữa, giới hạn quán cà phê, mỗi loại điểm tối đa 1/ngày, không 2 điểm cùng loại liền nhau, bữa trưa bắt buộc, nghỉ trưa sau bữa trưa, tối đa 1 trải nghiệm đặt trước mỗi ngày.
- **FR-014**: Khi khách nêu rõ mong muốn trái một luật mềm (vd. "3 quán cà phê"), luật mềm đó PHẢI không trừ điểm cho chuyến đó.
- **FR-015**: Giải thích lịch PHẢI nêu các điểm trừ mềm đã chấp nhận và lý do.
- **FR-016**: Trọng số điểm trừ mềm PHẢI nằm trong cấu hình, không viết cứng rải rác.

**Dữ liệu cho model**

- **FR-017**: Bộ đặc trưng xuất cho train PHẢI có cột tiền dạng số cho **mọi** điểm đang dùng, gồm cả giá ước lượng.
- **FR-018**: PHẢI có cột cờ phân biệt giá có nguồn / ước lượng (`price_known`) và có thể kèm trọng số mềm; KHÔNG lọc bỏ dòng ước lượng.
- **FR-019**: PHẢI có cột: tổng bắt buộc 1 người lớn, tỉ lệ giá trẻ em, có phí bắt buộc, có giá địa phương, tổng khoản tuỳ chọn.

### Key Entities

- **Khoản tiền (Price item)**: một khoản phải/có thể trả tại điểm — số tiền, đối tượng, đơn vị tính, bắt buộc/tuỳ chọn, nguồn, độ tin cậy.
- **Thành phần nhóm (Party)**: số người lớn, trẻ em (theo chiều cao/tuổi nếu nguồn phân biệt), người địa phương, số xe.
- **Bảng chi phí (Cost breakdown)**: tổng cận dưới/cận trên, danh sách khoản đã cộng, khoản chưa rõ, khoản tuỳ chọn, giả định, nhóm theo loại chi tiêu.
- **Luật mềm (Soft rule)**: tên, trọng số, điều kiện miễn trừ theo sở thích khách.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% lịch có số người > 1 có tổng tiền nhân đúng thành phần nhóm (test bộ lịch mẫu).
- **SC-002**: 100% lịch có điểm vé chung cộng vé cha đúng 1 lần/người.
- **SC-003**: 0 lịch hiển thị tổng như con số chắc chắn khi còn khoản chưa rõ giá.
- **SC-004**: ≥ 30 điểm hay vào lịch (tham quan có vé, điểm tiêu biểu) có khoản chi tiết có nguồn, gồm 34 điểm hiện ghi nhiều mức/phí trong ghi chú.
- **SC-005**: Trên bộ lịch mẫu, tỉ lệ lịch hợp lệ không giảm; số lịch bị loại chỉ vì luật "lịch đẹp" về 0.
- **SC-006**: Yêu cầu nêu rõ mong muốn trái luật mềm (≥ 5 kịch bản mẫu) được đáp ứng 100%.
- **SC-007**: File đặc trưng xuất có cột tiền cho 100% điểm đang dùng (không còn ô trống do thiếu nguồn).

## Assumptions

- Mặc định 2 người lớn ngoại tỉnh, không trẻ em, 1 xe máy/2 người khi khách không nói (nêu rõ giả định).
- Tỉ giá cố định 25.000 đ/USD, đặt trong cấu hình.
- Giá ước lượng theo mức giữ nguyên bảng hiện tại (rẻ 50k, trung bình 250k, đắt 850k) cho tới khi có dữ liệu thực chi hiệu chỉnh.
- Thu thập khoản chi tiết đi theo quy trình hiện có: đọc trang nguồn, không dùng Google, không để LLM đoán số.
- Phiên này không đổi hợp đồng API công khai; nếu bảng chi phí cần trường mới trong response, sẽ hỏi trước (DATA_FIX_PLAN mục 5).

## Out of Scope

- Giá theo ngày/mùa/lễ, khuyến mãi, mua vé online.
- Chi phí lưu trú và vé máy bay.
- Học trọng số luật mềm từ log (sau pilot).
