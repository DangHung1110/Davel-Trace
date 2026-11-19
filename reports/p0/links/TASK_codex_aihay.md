# TASK (Codex): kiểm chứng gợi ý của AI-Hay — CHỈ ĐỌC WEB, ghi đúng 1 file

Đầu vào: `reports/p0/links/aihay_rows.json` (56 dòng: poi_id, verdict ĐÚNG/SAI/KHÔNG RÕ, hours_src, ticket_src, links).
AI-Hay là LLM: KHÔNG tin câu trả lời, chỉ tin trang nguồn bạn tự mở và đọc được câu nói rõ giờ/vé.

Việc:
1. Mọi dòng có `links`: mở link, trích nguyên văn câu về giờ/vé của ĐÚNG địa điểm đó.
2. Dòng SAI/ĐÚNG không có link — ưu tiên các điểm dưới đây, tự tìm nguồn (trang chính thức / cổng du lịch / báo):
   - osm:node/5286977425 Núi Thần Tài (ta: 06:00-17:30; AI-Hay: 08:30-17:30)
   - Ngũ Hành Sơn + Thổ Sơn + Kim Sơn + Mộc Sơn (ta: 07:00-17:30; AI-Hay: 07:00-17:00)
   - Mikazuki Water Park 365, Sun World Bà Nà Hills, VinWonders Nam Hội An, Ký ức Hội An
   - Giờ mở/đóng bán đảo Sơn Trà theo mùa (AI-Hay: 07:30-18:30 tháng 3-9, 07:30-17:30 tháng 10-2) — tìm văn bản/nguồn chính thức.
3. Ghi `reports/p0/links/aihay_verified.json`: mảng {poi_id, name, claim_aihay, page_says_hours, page_says_ticket,
   quote, source, published_or_updated, agrees_with_ours (true/false/null), our_value, note}.
Không đoán, không sửa file khác, không git. UA `davel-trace-data/0.1`, không gửi thông tin cá nhân.
