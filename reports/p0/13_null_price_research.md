# Tra cứu giá/giờ cho POI `price.tier = null` — 19/11/2026

Phạm vi: 28 POI không phải lưu trú có `price.tier = null` sau P0-c. Công cụ: WebSearch + WebFetch (không dùng Google Maps).
Chỉ ghi giá trị khi đã mở URL và đọc được nguyên văn → `BE/data/sources/agent_web_2026-11-19.json` (`verified_by = agent_web`).

## Kết quả: 28 → còn 13 `null`

| POI | Kết quả | Nguồn / lý do |
|---|---|---|
| Kim Sơn, Mộc Sơn, Thổ Sơn | **free**, 07:00–17:30 | vietnambooking 23/01/2026: chỉ Thủy Sơn thu 40.000đ, "các ngọn khác … không thu phí vào cổng" |
| Làng đá mỹ nghệ Non Nước | **free** (giờ: "sunrise to sunset" → để trống) | gtrip.vn 13/11/2026 |
| Precious Heritage Art Gallery Museum (Hội An) | **free**, 08:00–20:00 | localvietnam, cập nhật 13/10/2025 |
| Công viên Đất nung Thanh Hà | **cheap** (50.000đ NL / 30.000đ TE) | sunparadiseland 15/08/2026 |
| Chùa Non Nước, Thái Sơn, Phổ Đà Sơn, Long Hoa, Tam Tôn, Lâm Tỳ Ni Viên; Bãi tắm Non Nước, Public Beach Access, Khu Dừng Chân | **free** (`inferred`, conf 0.7) | luật "nơi công cộng"; trước bị chặn vì luật cũ coi mọi điểm ≤ 800 m quanh Thủy Sơn là "trong cụm có vé" — nay chỉ cổng Thủy Sơn (`requires_ticket_of`) |

## Còn `null` (13) — không tìm được nguồn đáng tin

| POI | Ghi nhận | Đề xuất |
|---|---|---|
| Khu DL Sinh thái Thủy Vân Sơn (Hòa Hiệp Bắc) | znews 17/4/2024: UBND phường **cưỡng chế tháo dỡ** công trình xây trái phép, lấn 8.200 m² rừng; không rõ còn đón khách | **chuyển `review`** (nghi ngừng hoạt động) |
| Bảo tàng Y học Cổ truyền Hội An (46 Nguyễn Thái Học) | mở 15/3/2019 (baovanhoa); vé phố cổ 120.000đ (khách NN) / 80.000đ (khách VN) bao 5 phiếu (vietnamtourism, 7/11/2026) nhưng **không xác nhận** bảo tàng này nhận phiếu | Q5: cân nhắc thêm vào cụm `hoi_an_old_town` (→ `included`) |
| Bảo tàng Văn hóa Phật giáo (tầng 2 chánh điện chùa Quán Thế Âm) | danangfantasticity (2016) không ghi giờ/vé; một blog nói chùa miễn phí 06:00–18:00 nhưng trang mở ra không có câu này | cần người kiểm |
| Non Nước Stone Carving Memory Museum | danangfantasticity 13/09/2024: chỉ địa chỉ R1-R12 Trường Sa; không có giờ/vé | cần người kiểm (hotline trên trang) |
| VỌC Glamping | mia.vn ghi "745.000đ/người (2025)" nhưng không rõ giá đó thuộc VỌC | không ghi (nguồn mơ hồ) |
| Suối Rạng (Sơn Trà), Bến Nam Yên, KDL Nam Ô, Hồ bơi Thanh Khê, Nhà bia Chứng tích Núi Ghềnh, Nhà lưu niệm Mẹ Nhu, Art Gallery, TASY Studio | không có trang nào nêu giá/giờ cho đúng địa điểm (Nam Ô: chỉ "rạn Nam Ô" chung chung; Mẹ Nhu: baodanang chỉ mô tả di tích) | cần người kiểm hoặc chuyển `review` (Art Gallery / TASY Studio là tên chung, có thể không phải điểm tham quan) |
