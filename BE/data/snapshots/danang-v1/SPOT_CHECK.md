# SPOT-CHECK snapshot v1 — HƯỚNG DẪN CHO AGENT NGOÀI (đọc kỹ trước khi làm)
# File này + pois.json (cùng thư mục, join theo `name`) là đủ để làm, không cần repo/code.

## 1. Bối cảnh
# - pois.json: 329 POI Đà Nẵng crawl từ Google/SerpApi. Mỗi POI có các field:
#   poi_id, name, type (nhãn Google tiếng Việt THÔ, chưa chuẩn hóa), opening_hours (list string,
#   [] = thiếu dữ liệu), price_level (1-4), rating (None = thiếu), fee, verified (hiện toàn false),
#   visit_min {p25,p50,p75} (phút, nguồn xem dur_source: "category_rule" = suy từ nhóm type, chưa kiểm người),
#   weather_sensitive, intensity, lat/lon, tags.
# - File này: 49 dòng mẫu = 15% random (seed=42) + các outlier (dur_p50 lệch >60% median nhóm type).
#   Mỗi dòng đã rút gọn field cần kiểm, cú pháp:
#   - [ ] TÊN | Type | hours=[...] | price=N | rating=R | dur_p50=X (median_cat=Y) | indoor/outdoor=? => Dung/Sai/Ghi_chu:
#   Ánh xạ: hours=opening_hours, price=price_level, dur_p50=visit_min.p50, median_cat=trung vị p50 của nhóm type.

## 2. Việc cần làm TRÊN MỖI DÒNG (3 thao tác, sửa trực tiếp vào dòng)
#  (a) Điền indoor/outdoor: I = chủ yếu trong nhà (quán ăn, cafe, chợ có mái, bảo tàng),
#      O = chủ yếu ngoài trời (bãi biển, thắng cảnh, chợ trời), B = cả hai (khu phức hợp nhà + sân),
#      ? = không chắc từ tên+type (chỉ dùng khi thật sự không đoán được).
#      Được phép ghi ? — đừng đoán mò.
#  (b) Kết luận sau `=>`: ghi `Dung` nếu type + hours + dur_p50 đều hợp lý; ghi `Sai: ...`
#      kèm sửa cụ thể nếu có gì sai (vd `Sai type (cửa hàng điện nước, không phải Chợ); dur nên 30' không phải 90'`).
#      Kiểm 4 điểm: type có đúng bản chất POI không | hours có hợp lý/không (ghi `giờ thiếu` nếu []) |
#      dur_p50 ở từng ấy phút có hợp lý không (so median_cat để tham chiếu, POI cụ thể được quyền lệch) |
#      rating có ảo không (vd 5.0 tuyệt đối cho tiệm tạp hóa thì ghi nghi).
#  (c) Tick `- [ ]` thành `- [x]` khi xong dòng đó.
#  Ví dụ dòng hoàn thành:
#  - [x] ... | indoor/outdoor=I => Sai type (cửa hàng điện nước, không phải Chợ); dur nên 30'; rating 5.0 nghi ít review

## 3. Quy tắc (bắt buộc)
#  - KHÔNG bịa dữ liệu: thiếu thì ghi `giờ thiếu` / `thiếu rating` / `?`, không tự tra Google nhồi vào.
#  - Đừng "sửa" các default hàng loạt đã biết: price_level=2 khắp file, fee=0, verified=false,
#    weather_sensitive=false là giá trị crawl thô — chỉ flag khi vô lý lộ liễu ở dòng cụ thể.
#  - Type là nhãn thô: được đề xuất tên chuẩn (vd `Chợ` -> `cửa hàng`), nhưng verdict Dung/Sai
#    đánh theo bản chất đúng/sai, không trừ điểm vì hoa/thường/dấu câu.
#  - Ưu tiên sức cho ~10 dòng lạ (chợ, bãi biển, đình, bảo tàng, hours=[]) — quán cafe/nhà hàng
#    lặp lại làm nhanh: type đúng + dur 45-72' hợp lý + I là tick được.
#  - Output = CHÍNH FILE NÀY đã điền xong 49 dòng (giữ nguyên thứ tự dòng, không thêm/bớt dòng).

## 4. Dữ liệu này chảy đi đâu (để hiểu vì sao cần cẩn thận)
#  - dur_p50 đã duyệt -> thời lượng optimizer + cổng giờ-kết-thúc (lịch sai giờ về là do số này sai).
#  - I/O -> train bộ gán nhạy-cảm-thời-tiết M4 + cổng weather của validator (mưa -> đổi POI indoor) + câu giải thích.
#  - verdict -> bật cờ verified, mở cổng chống-hallucination FAR (hiện snapshot verified=0 nên planner từ chối hết).

# --- 49 DÒNG CẦN LÀM (15% random seed=42 + outliers p50 lech >60% median category) ---

- [x] CỬA HÀNG ĐIỆN NƯỚC HUY HIỀN | Chợ | hours=['05:00-21:00', '05:00-22:00'] | price=2 | rating=5 | dur_p50=90 (median_cat=75.0) | indoor/outdoor=- => LOẠI khỏi snapshot (không phải điểm du lịch — quyết audit 2026-09-29).
- [x] Xanh House | Nhà hàng | hours=['09:00-21:00'] | price=2 | rating=4.4 | dur_p50=60 (median_cat=60) | indoor/outdoor=I => Dung (chưa rõ loại hình nhà hàng cụ thể).
- [x] Hải sản My Hanh Seafood | Nhà hàng hải sản | hours=['09:00-23:00'] | price=2 | rating=4.7 | dur_p50=72 (median_cat=72) | indoor/outdoor=I => Dung (duration có thể tầm 60–90').
- [x] The Cups Coffee Roastery | Quán cà phê | hours=['06:30-23:00'] | price=2 | rating=4.7 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Tiệm Hoa & Nắng - WiWi Coffee | Quán cà phê | hours=['06:00-22:00'] | price=2 | rating=4.7 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] HỨA cafe | Quán cà phê | hours=['06:30-22:00'] | price=2 | rating=4.4 | dur_p50=45 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Quán Tuấn Núi (Heo bản - Gà đen) | Nhà hàng | hours=['10:00-23:00'] | price=2 | rating=4.3 | dur_p50=60 (median_cat=60) | indoor/outdoor=I => Dung
- [x] Korea BBQ House | Nhà hàng thịt bò Hàn Quốc | hours=['10:30-23:00', '10:30-23:30'] | price=2 | rating=4.8 | dur_p50=72 (median_cat=72) | indoor/outdoor=I => Dung
- [x] Đà Sơn tâm linh | Bảo tàng | hours=[] | price=2 | rating=3.7 | dur_p50=90 (median_cat=90) | indoor/outdoor=B => Sai: tên "tâm linh", không rõ có phải bảo tàng không; giữ unverified; Đây la chua, co the co indoor la ngoi chua va outdoor la san chua.
- [x] Nhà Hàng La Luna | Nhà hàng | hours=['10:00-21:00'] | price=2 | rating=4.2 | dur_p50=60 (median_cat=60) | indoor/outdoor=I => Dung
- [x] Chợ hải sản tươi sống biển Thanh Khê | Chợ | hours=['00:00-06:30, 14:30-00:00'] | price=2 | rating=4.2 | dur_p50=75 (median_cat=75.0) | indoor/outdoor=? => Dung
- [x] Ghềnh Bàng | Thắng cảnh | hours=[] | price=2 | rating=4.5 | dur_p50=54 (median_cat=54) | indoor/outdoor=O => Sai: 54' quá ngắn (đi bộ đường rừng xuống ghềnh); nên ~90–120'
- [x] XÓM MỚI GARDEN | Nhà hàng Việt Nam | hours=['10:00-22:00'] | price=2 | rating=4.9 | dur_p50=72 (median_cat=72) | indoor/outdoor=I => Dung
- [x] Gyu Sachi - Nhà hàng nướng Nhật Ngưu Hạnh | Nhà hàng Nhật Bản | hours=['10:30-14:00, 16:30-22:30', '10:30-22:30'] | price=2 | rating=4.7 | dur_p50=72 (median_cat=72.0) | indoor/outdoor=I => Dung
- [x] Madame Son | Nhà hàng | hours=['17:00-22:00'] | price=2 | rating=4.8 | dur_p50=72 (median_cat=60) | indoor/outdoor=I => Dung
- [x] Moss Coffee Shop 2 | Quán cà phê | hours=['06:30-22:15'] | price=2 | rating=4.6 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Lữ Cafe & Bar | Quán cà phê | hours=['07:30-21:30'] | price=2 | rating=4.7 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Bãi Biển Thiên Đường | Điểm thu hút khách du lịch | hours=[] | price=2 | rating=4.3 | dur_p50=200 (median_cat=200) | indoor/outdoor=O => Sai type (phải là Bãi biển); 200' quá dài, nên ~120'; nghi trùng bãi Thanh Khê
- [x] Chợ Khuê Mỹ | Chợ | hours=['05:00-19:00'] | price=2 | rating=4.3 | dur_p50=75 (median_cat=75.0) | indoor/outdoor=I => Dung
- [x] Nhà hàng LoCo | Nhà hàng hải sản | hours=['10:30-22:00'] | price=2 | rating=4.8 | dur_p50=72 (median_cat=72) | indoor/outdoor=I => Dung
- [x] Quán Hải sản Tân Trà Beach | Điểm thu hút khách du lịch | hours=[] | price=2 | rating=4.4 | dur_p50=200 (median_cat=200) | indoor/outdoor=I => Sai type (là quán ăn, không phải Điểm thu hút); 200' quá dài, nên ~72'
- [x] KITE COFFEE & SOUVENIRS | Quán cà phê | hours=['07:30-22:00'] | price=2 | rating=4.7 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Bãi biển Sơn Trà | Điểm thu hút khách du lịch | hours=[] | price=2 | rating=4.8 | dur_p50=240 (median_cat=200) | indoor/outdoor=O => Sai: nghi trùng "Son Tra Beach" (cách 99m, cần gộp); 240' quá dài
- [x] Trà Quán Góc Nhà Tụi Mình | Cửa hàng trà truyền thống | hours=['09:00-22:00'] | price=2 | rating=4.7 | dur_p50=90 (median_cat=90) | indoor/outdoor=I => Sai: dur 90' như cửa hàng; quán trà nên ~60'
- [x] Bãi Cát Vàng | Bãi biển | hours=[] | price=2 | rating=4 | dur_p50=120 (median_cat=120) | indoor/outdoor=O => Dung
- [x] Chợ đêm Helio - B. Night Market | Chợ đêm | hours=['17:00-23:00'] | price=2 | rating=4.1 | dur_p50=75 (median_cat=75.0) | indoor/outdoor=O => Dung
- [x] ChuAn cafe | Quán cà phê | hours=['07:00-18:00'] | price=2 | rating=4.9 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Nhà hàng NHÀ BẾP CHỢ HÀN | Nhà hàng Việt Nam | hours=['09:00-22:00'] | price=2 | rating=4.7 | dur_p50=72 (median_cat=72) | indoor/outdoor=I => Dung
- [x] Nhà Hàng Hồ Xanh - Hồ Xanh Restaurant | Nhà hàng | hours=['09:00-22:30'] | price=2 | rating=3.9 | dur_p50=60 (median_cat=60) | indoor/outdoor=I => Dung
- [x] CaFe Mộc Gia | Quán cà phê | hours=['06:00-22:00'] | price=2 | rating=4.5 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Nhà hàng chay Shanti Vegan Đà Nẵng | Nhà hàng | hours=['10:00-14:00, 16:00-21:00'] | price=2 | rating=4.9 | dur_p50=72 (median_cat=60) | indoor/outdoor=I => Dung
- [x] WONDERLUST - Coffee & Souvenir | Quán cà phê | hours=['08:00-19:30'] | price=2 | rating=4.5 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] La’s Cafe | Quán cà phê | hours=['06:30-22:00'] | price=2 | rating=4.5 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Đình làng Hải Châu | Điểm thu hút khách du lịch | hours=[] | price=2 | rating=4.5 | dur_p50=240 (median_cat=200) | indoor/outdoor=B => Sai: 240' cho một đình làng; nên ~30'
- [x] Koko House - Nhà Hàng Thịt Nướng Hàn Quốc | Nhà hàng Hàn Quốc | hours=['11:00-14:00, 17:00-22:00'] | price=2 | rating=4.9 | dur_p50=72 (median_cat=72.0) | indoor/outdoor=I => Dung
- [x] House Coffee | Quán cà phê | hours=['06:00-22:30'] | price=2 | rating=4.9 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Ibasho Coffee | Quán cà phê | hours=['07:00-22:00'] | price=2 | rating=4.2 | dur_p50=45 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Chợ Non Nước | Chợ | hours=[] | price=2 | rating=4.4 | dur_p50=75 (median_cat=75.0) | indoor/outdoor=I => Dung
- [x] Voọc Souvenir Coffee | Quán cà phê | hours=['06:00-22:30'] | price=2 | rating=4.1 | dur_p50=45 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] My Casa | Nhà hàng ý | hours=['11:00-22:00'] | price=2 | rating=4.6 | dur_p50=72 (median_cat=72.0) | indoor/outdoor=I => Dung
- [x] Khu Dừng Chân | Điểm thu hút khách du lịch | hours=[] | price=2 | rating=4.3 | dur_p50=200 (median_cat=200) | indoor/outdoor=B => Sai: khu nghỉ chân cạnh Ngũ Hành Sơn, không phải điểm tham quan riêng (xem xét loại/gộp)
- [x] Khu Căn cứ Cách mạng K20 | Bảo tàng chiến tranh | hours=['08:00-11:00, 13:30-16:30'] | price=2 | rating=4.4 | dur_p50=90 (median_cat=90.0) | indoor/outdoor=B => Dung
- [x] 3 Cây Lộc Restaurant | Nhà hàng Việt Nam | hours=['08:00-23:00'] | price=2 | rating=3.9 | dur_p50=60 (median_cat=72) | indoor/outdoor=I => Dung
- [x] D.coffee | Quán cà phê | hours=['06:00-22:30'] | price=2 | rating=4.5 | dur_p50=54 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Nhà Hàng Nhà Bếp Khuê Mỹ | Nhà hàng Việt Nam | hours=['10:00-22:00'] | price=2 | rating=4.7 | dur_p50=72 (median_cat=72) | indoor/outdoor=I => Dung
- [x] Di tích Đình Hồng Phước | Bảo tàng chiến tranh | hours=[] | price=2 | rating=None | dur_p50=90 (median_cat=90.0) | indoor/outdoor=B => Sai type (đình mà gắn "Bảo tàng chiến tranh"); 90' quá dài, nên ~30'
- [x] BigHome coffee 24/7 | Quán cà phê | hours=[] | price=2 | rating=4.3 | dur_p50=45 (median_cat=54.0) | indoor/outdoor=I => Dung
- [x] Chợ Hoà Mỹ | Chợ | hours=[] | price=2 | rating=4.5 | dur_p50=90 (median_cat=75.0) | indoor/outdoor=I => Sai: 90' quá dài cho chợ dân sinh
- [x] Chợ Thanh Vinh | Chợ nông sản | hours=['05:00-18:00'] | price=2 | rating=3.9 | dur_p50=75 (median_cat=75.0) | indoor/outdoor=? => Dung