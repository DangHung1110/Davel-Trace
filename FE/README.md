# Flutter mobile — Davel Trace

Ứng dụng mobile chính của dự án, theo phong cách **Sơn Trà Breeze**: teal
`#006A6A`, amber `#D97706`, nền trắng/slate, Material 3 bo tròn và ít màu.

Luồng demo đã nối:

- lịch trình quản lý và các phương án planner;
- chốt phương án live vào PostgreSQL backend;
- PMTiles Đà Nẵng, route/location và cảnh báo fallback;
- chi tiêu/ngân sách;
- hồ sơ du khách;
- seeded/stale/live state được gắn nhãn rõ ràng.

Trên desktop, app tự nằm trong khung điện thoại logic 390×844. Trên viewport
mobile, app dùng toàn màn hình.

## Chạy trên laptop

Project dùng Flutter stable 3.47.5. Trên máy phát triển hiện tại, `.flutter-sdk`
trỏ đến SDK dùng chung ở `D:\ToolCache\flutter-3.47.5\flutter`; không copy SDK
vào từng worktree. Chỉ cần Chrome để demo web, chưa cần Android emulator hay
điện thoại thật.

Từ repo root (PowerShell):

```powershell
& '.\.flutter-sdk\bin\flutter.bat' pub get --directory FE
& '.\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Git Bash:

```bash
./.flutter-sdk/bin/flutter.bat run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Không dùng cú pháp PowerShell `$env:...` hoặc `&` trong Git Bash.

## Kiểm tra

```powershell
& '.\.flutter-sdk\bin\flutter.bat' analyze FE
Push-Location FE
& '..\.flutter-sdk\bin\flutter.bat' test
& '..\.flutter-sdk\bin\flutter.bat' build web --release
Pop-Location
```

`FE/onboard.html` và `FE/test_harness.html` vẫn là công cụ kiểm tra API nhanh;
Flutter là frontend demo chính.
