# Duyệt vòng 1 (review_v21_20261119.json) — 19/11/2026

Đầu vào: export của người dùng (`BE/data/sources/review_v21_20261119.json`), ảnh #6–#11 và ghi chú trong tin nhắn.
Đã đọc 32 link: các trang nangtrip do pane chính đọc, 19 trang còn lại do pane Haiku đọc (`reports/p0/links/digest_haiku.json`).

## Nguồn sinh ra (đọc bởi `migrate_v2.py`, file sau ghi đè file trước)

| File | Nội dung |
|---|---|
| `decisions_review_20261119.json` | ingest tự động từ export: tên, trạng thái, trùng, vé phố cổ |
| `decisions_user_notes_20261119.json` | ảnh #6–#11 → excluded; gộp/tách/đổi tên; ghi chú vé phố cổ + phí bắt buộc |
| `human_verify_v2_20261119.json` | giờ/giá người dùng điền (giờ chữ tự do đã chuẩn hoá: `7h30 – 21h00`, `24/7`, `thứ Hai đến thứ Bảy`→ đóng CN) |
| `human_verify_v2_20261119_fix.json` | sửa sau khi đọc link: VỌC (link Đà Lạt → bỏ), 3D Art (giờ lệch → 09:00-18:00) |
| `agent_web_2026-11-19b.json` | giờ/giá Claude đọc từ link cho điểm mới/tách |
| `new_pois_manual_2026-11-19.json` | 3 điểm mới (2 Hội An `manual:*`, Bãi biển Tiên Sa OSM) |

## Kết quả

- 872 POI · active 828 · excluded 43 · review 1 (VỌC Glamping). Ma trận 789 điểm, 0 ô lỗi (OSRM local).
- **Xóa (ảnh):** Viet Nam's Delights ×2, Chùa Làng Thanh Khê ×2, Banh Mi Phuong, Quán ăn cô phưởng, Bến Nam Yên, KDL Nam Ô, Hồ bơi Thanh Khê, Non Nước Stone Carving Memory Museum, Nhà bia Núi Ghềnh, Nhà lưu niệm Mẹ Nhu, Art Gallery, TASY Studio.
- **Gộp:** Chùa Linh Ứng Sơn Trà ← tượng Quan Thế Âm Bồ Tát + Cổng chùa Linh Ứng (bỏ "Bãi Bụt" khỏi tên).
- **Tách:**
  - Bán đảo Sơn Trà → excluded (khu chung). Điểm con: Linh Ứng, Bàn Cờ, Cây Đa Ngàn Năm (đổi tên), Mũi Nghê, Hải đăng, Bãi biển Tiên Sa (mới, 25k gồm gửi xe), Nhất Lâm Thủy Trang Trà (10k).
  - "Phố đi bộ - chợ đêm Bạch Đằng" → **Phố đi bộ Bạch Đằng** (free, 15:00–24:00). Chợ đêm An Thượng là điểm riêng (Ngũ Hành Sơn, 18:00–23:00).
  - Đèo Hải Vân (free) ≠ Hải Vân Quan (~70k), ghi "đi đèo thì đề xuất ghé Hải Vân Quan".
- **Hội An:**
  - 18 điểm dùng vé chung phố cổ + 3 điểm "xác nhận tại quầy" (Bảo tàng Hội An, Văn Miếu, Nhà biểu diễn) → `included`. Ghi chú vé 80k/120k; 4 bảo tàng chỉ dùng được vé 120k.
  - Nhóm miễn phí giữ `free`.
  - Thêm: *Phố đi bộ phố cổ Hội An (tường vàng, thả hoa đăng)* và *Hát Bài Chòi ven sông Hoài* (Vườn tượng An Hội, 19h, xem miễn phí, thẻ 20k).
- Núi Thần Tài → **Công viên Suối khoáng nóng Núi Thần Tài** (paid, 480k → medium).

## Điểm KHÔNG làm theo ghi chú / cần bạn xem lại

1. **Chùa Quán Thế Âm (48 Sư Vạn Hạnh, Ngũ Hành Sơn)**: ghi chú đề nghị đổi tên thành Chùa Linh Ứng, nhưng tôi **giữ tên cũ**.
   - Chính link chilldanang bạn đưa ghi đúng địa chỉ này là Chùa Quán Thế Âm. Bảo tàng Văn hóa Phật giáo nằm trong chùa này.
   - Chùa Linh Ứng có tượng Quan Âm 67m nằm ở Sơn Trà (Bãi Bụt), cách khoảng 13 km.
   - Chùa này chỉ nhận giờ 06:30–17:30 và giá free.
2. **VỌC Glamping**: link là Thung Lũng Vàng (Đà Lạt). Tôi bỏ giờ/giá đã nhập, chuyển `review`. Chưa tìm được nguồn đúng địa điểm.
3. **Bảo tàng 3D Art**: bạn nhập 09:00–22:00, nhưng ghi chú và widget nangtrip đều ghi đóng 18:00. Tôi lấy 09:00–18:00.
4. **Bảo tàng Y học Cổ truyền**: chọn `cheap`, nhưng điểm này thuộc vé phố cổ nên để `included`. Đóng cửa ngày 12 và 27 hằng tháng chỉ ghi trong `price.note` vì schema chưa có ngày ngoại lệ (P1).
5. **Bánh Mì Phượng**: xóa theo ảnh #7, dù đây là quán nổi tiếng. Muốn giữ thì đổi `status` trong `decisions_user_notes_20261119.json`.
6. **Thủy Vân Sơn**:
   - Đã nhận free 07:00–18:00 từ Foody. Foody tự cảnh báo "hơn 3 tháng chưa có tương tác".
   - znews 4/2024 có tin cưỡng chế tháo dỡ khu này. Tình trạng hoạt động hiện tại chưa xác nhận.
7. **Cù Lao Chàm** để `cheap` theo vé 70k. Phí bắt buộc (cano khoảng 150k hoặc tàu gỗ 50k) chỉ ghi trong `price.note`, vì hợp đồng giá chưa có "phí bắt buộc".

## Còn thiếu (cần ở kiến trúc mới)

- Bãi Đá Đen, Bãi Rạng, Hồ Xanh (Sơn Trà) chưa thêm: chưa có toạ độ đáng tin, Overpass/Nominatim lỗi lúc chạy.
- Giờ theo mùa (Hải đăng 07:30–18:30 tháng 3–9), ngày đóng cửa trong tháng, suất diễn: chưa có trường riêng (Opening-hours contract P1).
- Loại vé phố cổ 80k/120k và số ô 2/3 điểm: chưa mô hình hoá (Ticket contract P1). Hiện chỉ có `requires_ticket_of` + `price.note`.

## Test

- Bộ test nhanh (`pytest BE/tests`, trừ `test_baselines.py`): 879 passed, 8 skipped. Mất 19 phút vì CP-SAT timeout, lỗi có sẵn từ trước.
- Gate dữ liệu `P0_GATE=1`: 20/22 xanh, đã gồm rule 12 (tên), G1, G2, G5.
- Còn đỏ:
  - **G3**: Hải Vân Quan đã có vé 70.000đ (nghị quyết HĐND Huế, khamphahue) nhưng không nguồn nào nêu giờ mở cửa.
  - **G4**: VỌC Glamping đang `review`.

## Vòng 1b — 19/11 tối (theo phản hồi người dùng)

- **Chùa Quán Thế Âm (Ngũ Hành Sơn) và Chùa Linh Ứng Sơn Trà**: người dùng xác nhận là 2 chùa khác nhau. Giữ cả 2 và ghi chú phân biệt.
- **VỌC Glamping** → active, `expensive`, mở 24/24 (nghiencamtrai 12/10/2025).
  - Gói qua đêm 695.000–795.000đ/người, 183 Nam Cao, Hòa Khánh Nam.
  - Vẫn để `paid_attraction`. Bản chất là chỗ ở qua đêm; có thể chuyển `lodging` nếu muốn.
- **Thủy Vân Sơn** → excluded (người dùng xóa).
- **Hải Vân Quan**: vé 70.000đ, 07:00–17:30 (vnexpress 1/6/2026). Hải Vân Quan và Đèo Hải Vân cùng `cluster_id = hai_van` (gợi ý đi cùng, không phải ràng buộc).
- **Bãi Đá Đen (Bãi Obama)**: thêm `manual:son-tra-bai-da-den`.
  - Toạ độ lấy từ nangtrip. Miễn phí; có thể mất khoảng 10k gửi xe.
- **Bãi Rạng, Hồ Xanh**: chưa thêm vì chưa có toạ độ có nguồn.
  - Pane Codex (t18) đang tìm, chờ người duyệt lệnh đọc web.
- **Kết quả**:
  - 873 POI: 829 active, 44 excluded, 0 review. Ma trận 790 điểm, 0 ô lỗi.
  - **Gate P0 xanh hết** (rule 1–12, G1–G5).
