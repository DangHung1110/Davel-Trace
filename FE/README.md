# Flutter mobile — Davel Trace

UI uses the coastal reference from Stitch project `11832778903374325952`, adapted
to a softer mint/slate palette and the app's four real destinations. Rare account
recovery and expense filters are disclosed on demand; expense edit/delete share a
menu and route playback uses one play/pause control. Existing flows stay available.

For the web debug demo keep FastAPI running on the configured `API_BASE_URL`. The
map iframe prefers `/v1/maps/danang.pmtiles`, which supports byte-range responses;
Flutter's debug asset server serves the full file and cannot supply suitable ranges.
The packaged asset remains a fallback for range-capable static hosting. The map
keeps one iframe across GPS fixes, reports retryable load errors, and explains fixes
outside the local Da Nang coverage instead of following them into an empty region.
Native Flutter continues using its existing OSM tile provider.

Map checks: `node --test tool/map_location_bridge.test.cjs`; with app/backend running,
`node tool/map_browser_smoke.cjs` runs a separate headless Chromium with synthetic
GPS fixes and writes `build/ui-review/map-browser-390.png`. No device GPS is read.

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

## Trang tĩnh của planner

Flutter là frontend demo chính. Các trang tĩnh dưới đây vẫn là công cụ kiểm tra API
nhanh của planner, không cần build: chạy `python server.py` từ repo root rồi mở
`http://127.0.0.1:5500/FE/<page>`.

- `test_harness.html`: text thành plans, rồi review, repair và "Chot plan".
- `onboard.html`: hồ sơ onboarding (ba archetype hoặc tùy chỉnh), giữ trong localStorage.

Các trang review được sinh ra và không commit:

```bash
python BE/tools/build_plan_review.py --reuse        # plan_review.html: 24 plans, blind human review
python BE/tools/build_verify_page.py --mode review  # verify_review.html
python BE/tools/build_verify_page.py --mode sample  # verify_sample.html
python BE/tools/build_review_report.py              # verify_result.html
```
