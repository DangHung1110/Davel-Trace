# TASK (Codex): tìm giờ mở cửa có nguồn cho 6 POI — CHỈ ĐỌC WEB, ghi đúng 1 file

Ghi kết quả vào `reports/p0/links/hours_codex.json` (mảng JSON). KHÔNG sửa file nào khác, không git.
Mỗi mục: {poi_id, name, hours "HH:MM-HH:MM" (nhiều khung cách bằng ", "), closed_days [Mo..Su], ticket_vnd (nếu thấy),
source (URL), quote (trích nguyên văn câu chứa giờ), checked_at "2026-11-19", confidence low|medium|high, note}.
Không đoán: không tìm được nguồn thì hours=null và ghi lý do. Nhiều nguồn lệch -> lấy khung hẹp hơn, ghi cả hai.
User-Agent chung `davel-trace-data/0.1`, không gửi thông tin cá nhân.

| poi_id | Tên | Khu |
|---|---|---|
| ChIJLeqV3_cXQjERH0Dq1Mte6_w | Son Tra Retreat - Garden Lounge & Eatery | Sơn Trà |
| ChIJSRWy6Hr3QTERiU3vuI0PbHw | Khu Du Lịch Sinh Thái Lái Thiêu | Hòa Vang (Bà Nà) |
| ChIJQWQVKr4ZQjERcafNnRyLelk | DD WONDERLAND | Đà Nẵng trung tâm |
| ChIJK4sVPc0ZQjERdGROWQ8MMg4 | Trung Tâm Giải Trí Helio | Hải Châu, Đà Nẵng |
| osm:node/7127442985 | Nhà biểu diễn nghệ thuật cổ truyền Hội An (66 Bạch Đằng) | Hội An |
| osm:way/14131302 | Công viên Ấn tượng Hội An (show Ký ức Hội An) | Hội An |
