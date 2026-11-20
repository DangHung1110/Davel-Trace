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

## Vòng 1c — 19/11 tối

- **Hồ Xanh Sơn Trà**: thêm từ OSM `way/140401174` (natural=water, Nominatim; `reports/p0/links/geo_codex.json`, tin cậy cao).
  - Toạ độ là tâm mặt hồ, không phải lối vào.
  - Chưa có nguồn về vé/giờ → `free` + khung giờ an toàn theo luật nơi công cộng (inferred), không đoán thêm.
- **Bãi Rạng Sơn Trà**: thêm `manual:son-tra-bai-rang` (toạ độ worldplaces, tin cậy trung bình).
  - 09:00–18:00, không vé, gửi xe bắt buộc ~10.000đ, chòi ~300.000đ/6 người (thông tin người dùng, `verified_by=user`).
  - Cách KDL Sinh thái Suối Rạng ~166 m: giữ 2 điểm riêng, cùng `cluster_id = bai_rang`.
- **Bãi Đá Đen**: đổi tên thành "Bãi Đá Đen Sơn Trà". Bỏ alias "Bãi Obama" vì trên OSM "Obama" trỏ bãi khác cách ~9 km.
- **Kết quả**: 875 POI (831 active, 44 excluded, 0 review); ma trận 792, 0 ô lỗi; gate P0 22/22 xanh.
- **Giờ cho điểm `unknown`** (Codex t15, `reports/p0/links/hours_codex.json` → `agent_web_2026-11-19c.json`; nguồn lệch thì lấy giao khung hẹp):

  | Điểm | Giờ | Ghi chú |
  |---|---|---|
  | Son Tra Retreat | 10:00–21:00 | giao thêm khung bán đảo 07:30–17:30 |
  | KDL Sinh thái Lái Thiêu | 07:30–17:00 | vé 100.000đ |
  | DD Wonderland | 09:00–21:00 | — |
  | Ký ức Hội An | 17:00–21:30, nghỉ thứ Ba | show 20:00–21:00, vé ECO 600.000đ |

  - Helio và Nhà biểu diễn 66 Bạch Đằng: tạm ngưng hoặc chuyển chỗ → giữ `unknown`, có ghi chú.
  - `migrate_v2`: agent_web nay mang được `closed_days`; agent_web thắng new_pois theo từng khoá.

## Kiểm chứng chéo bằng AI-Hay — 19/11 khuya

- **Cách làm:** hỏi AI-Hay (ai-hay.vn, ẩn danh, qua Edge + `orca computer`) 9 lượt cho 57 điểm của `final_review.html`. Kết quả ở `reports/p0/links/aihay_rows.json`.
  - AI-Hay là LLM: chỉ dùng như gợi ý.
  - Codex (t15) mở trang nguồn để kiểm (`aihay_verified.json`).
- **Kết quả AI-Hay:** 5 ĐÚNG, 13 SAI, 38 KHÔNG RÕ. Chỉ 16/56 dòng có link; nhiều dòng "SAI" không có link. Lượt đầu còn nhầm Chợ đêm An Thượng là "ở Hội An".
- **Codex mở trang nguồn:** 8 khớp, 4 lệch, 44 chưa đủ nguồn.
- **Đã sửa theo nguồn (vào `agent_web_2026-11-19c.json`, `human_verify_v2_20261119_fix.json`):**

  | Điểm | Trước | Sau | Nguồn / ghi chú |
  |---|---|---|---|
  | Núi Thần Tài | 06:00-17:30 (suy luận) | **08:30-17:30**, vé 490.000đ | danangfantasticity 22/01/2026 |
  | Ngũ Hành Sơn | đến 17:30 | **07:00-17:00** | — |
  | Cây Đa Ngàn Năm | 24h | **07:30-17:30** | giờ tuyến bán đảo theo mùa, lấy khung hẹp |
  | Bãi Rạng | 9:00-18:00 | **09:00-17:30** | 9-18 là giờ dịch vụ lặn (locatravel); giao với khung bán đảo; `verified_by=user` (trước ghi nhầm human) |

- **Lỗi phát hiện:** khung giờ bán đảo chỉ áp cho điểm có `access_note` từ v1, nên điểm mới (Bãi Rạng, Bãi Đá Đen, Hồ Xanh…) không được áp.
  - Hồ Xanh (gần Sơn Trà Marina, chân bán đảo) và Bãi Đá Đen (đường ven biển Hoàng Sa): chưa có nguồn nói chúng thuộc tuyến kiểm soát, nên giữ nguyên.
  - Ghi vào P1: hợp đồng giờ theo mùa + phạm vi tuyến.
- **Trang chốt cuối:** mỗi dòng giờ hiện thêm "AI-Hay: …" và "Codex mở trang: khớp/LỆCH" kèm link, để người duyệt bấm nhanh.

## Chốt cuối — 20/11

File xuất: `reports/p0/final_review_20261120.json` (Claude ghi theo tin nhắn người dùng; ingest → `decisions_zfinal_20261120.json`, `human_verify_v2_20261120_zfinal.json`; số liệu vé ở `agent_web_2026-11-20.json`).

- **A, B:** người dùng giữ mặc định → Helio, Nhà biểu diễn 66 Bạch Đằng loại; 13 lớp nấu ăn giữ active; VỌC giữ paid_attraction; Bãi Rạng tách 2 điểm; lưu trú giữ nguyên. 12 giá trị mục B đồng ý hết.
- **C — 7 dòng AI-Hay báo sai, người dùng tự kiểm kèm link** (verified_by = human):

| Điểm | Kết quả | Nguồn |
|---|---|---|
| Hồ Xanh Sơn Trà | 24h, miễn phí | daivietourist.vn |
| Công viên Ấn tượng (Ký ức Hội An) | giữ 17:00-21:30, nghỉ thứ Ba; show 20:00 ~60'; ECO 600k quầy (online 520-540k), HIGH 750k, VIP 1,2tr | hoianit.com |
| Rừng Dừa Bảy Mẫu (+ 2 điểm cùng cụm, agent_web) | 07:30-18:30; cổng 30k; thúng 150k/2 người/45' | mia.vn |
| Ngũ Hành Sơn → **Ngũ Hành Sơn (Thủy Sơn)** | 40k + thang máy 15k/lượt + Âm Phủ 20k; **Kim Sơn, Thổ Sơn gộp vào** (excluded) | nangtrip.com |
| Tour lặn ngắm san hô Sơn Trà (bến CT15) | **điểm mới** `manual:son-tra-tour-lan-ct15` tại pin Sơn Trà Marina; suất 08:00-14:45, 120' → 08:00-16:45; NL 450k, trẻ 1-6t 250k | oktrip.vn; toạ độ tixgo.vn/node/3822 |
| DD Wonderland | **giữ nguyên** — xem dưới | |

- **Không làm theo nguyên văn / Claude tự quyết thêm:**
  - "DD Wonderland": link người dùng (mytour) nói về **Công viên Châu Á / Da Nang Downtown** — nơi khác (OSM way/667422708), và đã **dừng hoạt động từ 3/9/2025** (TTXVN 5/8/2025; chưa có tin mở lại tới 10/2026). Không thêm điểm; DD Wonderland (khu vui chơi trẻ em) giữ giá trị cũ.
  - Điểm Google "Dịch Vụ Cano … Lặn Biển" (gần Bãi Rạng) là cơ sở lặn khác bến CT15 → loại, thay bằng điểm mới đúng bến thay vì chỉ đổi tên.
  - Hòn Thủy Sơn loại vì trùng "Ngũ Hành Sơn (Thủy Sơn)" (~100 m).
- Codex (t15) kiểm 2 tra cứu: `reports/p0/links/final2_codex.json`.
- Kết quả: 876 POI (826 active, 50 excluded), ma trận 793 (0 ô thiếu), giờ do người kiểm 30/50.

## Tuyến kiểm soát bán đảo Sơn Trà — 20/11

Nguồn: VietnamPlus + Tuổi Trẻ (17/08/2026), VnEconomy + VietNamNet (15–16/09/2025). Ba tuyến: Tiên Sa–Suối Ôm–Đỉnh Bàn Cờ (**đang tạm dừng sau bão**, 17/08/2026); Yết Kiêu–Đỉnh Bàn Cờ–Bãi Bắc (đoạn Bàn Cờ→Bãi Bắc một chiều); Ngã ba Bãi Bắc–Cây Đa (chỉ đi bộ). Giờ 07:30–18:30 (tháng 3–9) / 07:30–17:30 (tháng 10–2).

- **Mùa:** mùa đi đẹp nhất là tháng 3–9, nhưng dữ liệu giữ **07:30–17:30 quanh năm** vì mốc này đúng ở cả hai mùa (mùa hè chỉ sớm 1 tiếng); chọn 18:30 sẽ sai cho khách đi tháng 10–2.
- **Code:** `migrate_v2.py` đọc `BE/data/sources/access_route_*.json` (on_route/off_route; điểm không có thì giữ luật cũ) và **cắt cả giờ do người kiểm/quyết định theo khung đường** (`clip_to_access`). Trước đây giờ người kiểm ghi đè khung đường: Bán đảo Sơn Trà, Mũi Nghê (24h), Đỉnh Bàn Cờ (→19:00), Hải đăng Tiên Sa (→18:00) nay về 07:30–17:30. Cây Đa ghi rõ on_route.
- **Mũi Nghê → excluded:** "cấm tuyệt đối các tuyến trekking tự phát xuống Hục Lỡ, Mũi Nghê, Bãi Đá Đen" (VietNamNet).
- **Phân loại từng điểm (Codex t15, `reports/p0/links/sontra_route_codex.json` → `access_route_son_tra_20261120b.json`):** 3 trên tuyến (Đỉnh Bàn Cờ, Nhà Vọng Cảnh, Cây Đa), 35 ngoài tuyến, 8 chưa rõ. Căn cứ: trạm ở nút Hoàng Sa gần ngã ba Bãi Bắc (danangportal); 'resort, Bảo tàng Đồng Đình, chùa Linh Ứng' ở chân núi ngoài vùng kiểm soát (VnExpress 6/11/2019) + hình học đường OSM. Là suy luận, không phải bản đồ ranh pháp lý.
  - 9 điểm ngoài tuyến được bỏ khung đường (trước đây áp theo toạ độ): chùa Linh Ứng 06:30-17:30, Son Tra Retreat 10:00-21:00, Sơn Trà Marina, Bãi biển/Vịnh Sơn Trà, các điểm ngắm cảnh trên đường Hoàng Sa, Sơn Trà Tịnh Viên.
  - Chưa rõ, giữ luật cũ: Ghềnh Bàng (24h; báo Văn Hoá 2026 cảnh báo không tự ý tiếp cận), Hải đăng Tiên Sa, Radar Sơn Trà 1 và Núi Sơn Trà (cổng private trên OSM), Nhất Lâm Thủy Trang Trà, Đài tưởng niệm 229, The Long Bar InterContinental.
  - Bãi Đá Đen Sơn Trà (người dùng thêm) trùng tên với điểm cấm trekking trong VietNamNet — cần người dùng xác nhận; Codex coi 'Bãi Đá' (Obama) là bãi khác, ngoài tuyến.
- Kết quả: 876 POI (825 active, 51 excluded).
- **Người dùng chốt 20/11:** loại 5 điểm bị cấm/không được tự ý tiếp cận — Mũi Nghê, Hải đăng Tiên Sa, Ghềnh Bàng, Bãi Đá Đen Sơn Trà, Bãi Đá (Bãi Obama) (`decisions_zfinal_20261120b.json`). Kết quả: 876 POI (821 active, 55 excluded).

## Giờ chùa / hội quán có nguồn — 20/11

Codex (t15) đọc web cho 80 điểm tôn giáo đang dùng khung ước lượng 08:00-11:00, 14:00-16:00 (`reports/p0/links/religious_codex.json`, không dùng Google):
- **19 điểm có giờ tham quan có nguồn → `fixed`** (`agent_web_2026-11-20b.json`), ví dụ Sơn Trà Tịnh Viên 06:30-18:00, Chùa Tam Bảo 06:00-21:00, Chùa Bát Nhã 06:00-20:30, 5 hội quán Hội An 07:00/08:00-16:00/17:00. Nguồn lệch → lấy khung hẹp.
- 19 nhà thờ chỉ có giờ lễ (không phải giờ tham quan) → giữ `safe_window`.
- 42 điểm không có nguồn đọc được → giữ `safe_window`.
- Giờ ngoài lưu trú: fixed 175 → 194, safe_window 557 → 538, unknown 13 (lớp nấu ăn).

## Trải nghiệm theo suất (`by_booking`) + giờ ngoài trời/chợ/spa/nightlife — 20/11

**Hợp đồng mới (người dùng duyệt):** `hours.kind = by_booking` (`DATA_SPEC_v2_1.md`).
- `open` = các suất đặt được; `dwell` = độ dài suất → solver chỉ đặt trọn một suất (dùng cơ chế nhiều khung giờ sẵn có).
- `retrieval.py`: chỉ gợi ý khi khách chọn ẩm thực/nấu ăn/văn hoá/trải nghiệm/workshop (hoặc must-visit); nhãn "can dat truoc (theo suat)".
- `optimizer.py`: tối đa 1 trải nghiệm theo suất mỗi ngày (ràng buộc cứng).
- Nguồn: `BE/data/sources/booking_*.json` → `migrate_v2.apply_booking`. Test: `BE/tests/unit/test_by_booking.py`.
- Dữ liệu (Codex đọc trang lớp/đặt chỗ, `reports/p0/links/cooking_sessions_codex.json`): 4/13 lớp có suất ghi rõ → by_booking (Family Kitchen, Apron Up, Sunny Bánh Mì & Coffee, Thuận Tình Island). 2 lớp Jolie ghi giờ dạng "09:00 / 15:00 · 13:00 / 19:00" — chưa rõ cặp bắt đầu/kết thúc nên chưa áp; 7 lớp không có lịch → giữ unknown.
- **Chưa làm:** bỏ bữa ăn liền kề sau lớp nấu ăn (cần sửa luật bữa trưa bắt buộc trong solver).

**Giờ có nguồn (Codex: OSM + web, không Google):** ngoài trời/chợ 10/69, spa/nightlife 30/158 → `agent_web_2026-11-20c.json` (Nón Spa bỏ: nguồn mâu thuẫn ngày nghỉ). Còn lại không có nguồn đọc được → giữ `safe_window`.

Giờ ngoài lưu trú: fixed 234, safe_window 498, by_booking 4, unknown 9.
