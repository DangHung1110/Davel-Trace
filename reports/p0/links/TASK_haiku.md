# Nhiệm vụ (pane Haiku) — đọc link dẫn chứng, CHỈ ĐỌC + ghi 1 file

Đọc `reports/p0/links/urls.json`. Với mỗi URL **KHÔNG** thuộc `nangtrip.com` (nangtrip do pane chính đọc):

1. Dùng WebFetch đọc **toàn bộ** trang, kể cả phần "Câu hỏi thường gặp"/FAQ dạng accordion (nội dung thường có sẵn trong HTML; hãy yêu cầu WebFetch trích nguyên văn cả các câu trả lời FAQ).
2. Trích **nguyên văn** (không suy đoán) các thông tin về: giờ mở cửa (kể cả theo mùa, ngày đóng cửa), giá vé theo đối tượng (người lớn/trẻ em/khách VN/khách nước ngoài), phí bắt buộc khác (gửi xe, cano, cáp treo…), các khu/điểm con được nhắc tới (tên + mô tả ngắn + giờ/giá nếu có), địa chỉ, ngày cập nhật bài viết.
3. Ghi chú nếu trang nói về **địa điểm khác** với tên POI (ví dụ trang về Đà Lạt cho một POI ở Đà Nẵng).

Ghi kết quả vào **một** file `reports/p0/links/digest_haiku.json`:

```json
[{"poi_id": "...", "name": "...", "url": "...", "fetched": true,
  "page_updated": "YYYY-MM-DD hoặc null", "same_place": true,
  "hours": ["nguyên văn ..."], "closed": ["..."],
  "prices": [{"audience": "người lớn VN", "vnd": 60000, "quote": "nguyên văn"}],
  "mandatory_fees": [{"what": "gửi xe", "vnd": 10000, "quote": "..."}],
  "sub_places": [{"name": "...", "desc": "...", "hours": null, "price": null}],
  "faq": [{"q": "...", "a": "nguyên văn rút gọn"}],
  "notes": "..."}]
```

Không sửa file nào khác, không git. Trang lỗi/không mở được → `fetched: false` + lý do trong `notes`. Xong thì in một dòng `DONE digest_haiku.json <số mục>`.
