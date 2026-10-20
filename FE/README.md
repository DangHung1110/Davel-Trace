# Davel Trace Mobile

Flutter Management MVP theo hệ thiết kế Stitch **Sơn Trà Breeze**: teal `#006A6A`, amber `#D97706`, nền slate sáng, thẻ bo tròn Material 3 và typography Be Vietnam Pro. App quản lý hồ sơ local, chuyến đi, lịch thủ công và chi tiêu; AI planner được để sau qua boundary riêng và không ghi trực tiếp vào itinerary.

## Chạy trên laptop trong khung mobile

Chạy backend trước tại port 8000, sau đó từ `FE/`:

```powershell
flutter pub get
flutter run -d chrome --web-port 5501 `
  --dart-define=DAVEL_API_BASE_URL=http://127.0.0.1:8000
```

Git Bash dùng cú pháp sau (không dùng `$env:` hoặc `&` của PowerShell):

```bash
flutter pub get
flutter run -d chrome --web-port 5501 \
  --dart-define=DAVEL_API_BASE_URL=http://127.0.0.1:8000
```

UI tự giới hạn ở chiều rộng **390 px** (cao tối đa 844 px) trên màn hình lớn, nên Chrome hiển thị như một điện thoại ngay trên laptop. Có thể mở DevTools → Toggle device toolbar nếu muốn mô phỏng kích thước máy cụ thể.

Nếu Flutter chưa có trong PATH, thay `flutter` bằng đường dẫn đầy đủ đến `flutter.bat`. Trong Git Bash, ví dụ:

```bash
"/c/path/to/flutter/bin/flutter.bat" run -d chrome --web-port 5501 \
  --dart-define=DAVEL_API_BASE_URL=http://127.0.0.1:8000
```

## Map và routing

- Flutter Web dùng `web/data/danang.pmtiles`, MapLibre và buildings 3D.
- Marker lấy từ activity đã lưu, không còn hard-code demo trip.
- Map ưu tiên OSRM. Nếu OSRM không dùng được, UI/backend gắn nhãn tuyến dự phòng; đường thẳng không được mô tả như route thật.
- Từ chối quyền vị trí không chặn xem map/lịch.
- Native hiện giữ OSM raster fallback; PMTiles local đầy đủ được kiểm tra trên Flutter Web/laptop.

## Kiểm tra

```powershell
flutter analyze
flutter test
flutter build web --dart-define=DAVEL_API_BASE_URL=http://127.0.0.1:8000
```
