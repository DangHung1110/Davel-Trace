# Flutter mobile — Davel Trace

Live foreground GPS, camera following and device test instructions:
[`live GPS quickstart`](../specs/014-live-gps/quickstart.md).

Google sign-in and real SMTP recovery setup:
[`identity providers quickstart`](../specs/013-identity-providers/quickstart.md).

Ứng dụng mobile chính của dự án, theo phong cách **Sơn Trà Breeze**: teal
`#006A6A`, amber `#D97706`, nền trắng/slate, Material 3 bo tròn và ít màu.

Điều hướng: **Chuyến đi** (danh sách → lịch từng ngày → màn lập lịch riêng),
**Bản đồ**, **Chi tiêu**, **Tài khoản**. Email đăng nhập, bảo mật và **Đăng xuất**
nằm ở Tài khoản. **Sở thích du lịch** là mặc định cho chuyến mới, tách khỏi danh
tính đăng nhập. Editor và trang bảo mật cũng dùng chung khung mobile trên desktop.
Font Be Vietnam Pro được đóng gói trong app; giấy phép ở `assets/fonts/OFL.txt`.
Kịch bản kiểm tra UI: [`015 UI/UX quickstart`](../specs/015-ui-ux/quickstart.md).

Luồng demo đã nối:

- đăng ký, xác thực email demo, đăng nhập, refresh và quản lý phiên;
- khôi phục mật khẩu, export và yêu cầu xóa tài khoản;
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
Push-Location FE
& '..\.flutter-sdk\bin\flutter.bat' pub get
& '..\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
Pop-Location
```

Git Bash:

```bash
cd FE
../.flutter-sdk/bin/flutter.bat run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
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
