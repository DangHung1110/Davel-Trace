# Nhiệm vụ (pane Codex): tìm toạ độ 3 điểm Sơn Trà. Chỉ đọc, ghi đúng 1 file

Cần toạ độ (lat, lon, WGS84) cho:

1. **Bãi Đá Đen** (còn gọi Bãi Obama), bán đảo Sơn Trà, Đà Nẵng
2. **Bãi Rạng**, bán đảo Sơn Trà (phường Thọ Quang cũ)
3. **Hồ Xanh**, bán đảo Sơn Trà (hồ nước xanh trên đường lên Chùa Linh Ứng, khu Bãi Bụt)

## Cách tìm

Thử theo thứ tự:

1. **OSM Overpass**, bbox `16.08,108.18,16.16,108.35`, tìm theo `name~` (không phân biệt hoa thường; thử cả không dấu). Endpoint: overpass-api.de, overpass.kumi.systems, overpass.private.coffee. User-Agent chung chung (`davel-trace-data/0.1`), KHÔNG gửi email.
2. **Nominatim**.
3. **Trang web có toạ độ dạng số**, ví dụ toạ độ ghi trong bài, hoặc link Google Maps có `@lat,lon` hay `!3d…!4d…` trong HTML của bài viết.

Yêu cầu với kết quả:

- Không đoán. Toạ độ phải có nguồn (OSM id hoặc URL trang có số).
- Kiểm tra kết quả nằm trong bbox trên.
- So khoảng cách với các điểm đã có trong `BE/data/snapshots/danang-v2/pois.json` để biết có trùng không, ví dụ "Biển Rạng Sơn Trà" (restaurant) hay "Nhà Hàng Hồ Xanh".

## Ghi kết quả

Ghi vào `reports/p0/links/geo_codex.json`:

```json
[{"name": "Bãi Đá Đen", "lat": 0.0, "lon": 0.0, "source": "osm:node/… | URL", "quote": "…",
  "confidence": "high|medium|low", "nearest_existing": {"poi_id": "…", "name": "…", "dist_m": 0}}]
```

Không tìm được thì ghi `lat: null` kèm lý do. Không sửa file nào khác, không chạy git. Xong in `DONE geo_codex.json`.
