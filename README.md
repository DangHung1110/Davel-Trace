# Da Nang Local PMTiles 3D Route Simulator

Repository hiện có ba bề mặt demo dùng chung dữ liệu Đà Nẵng:

- Prototype bản đồ tĩnh ở thư mục gốc (`index.html` + `server.py`).
- FastAPI planner/platform trong `BE/`: phương án khả thi, hard gate,
  PostgreSQL code-first, shadow calibration và readiness theo component.
- Flutter mobile trong `FE/`: khung điện thoại 390×844 chạy ngay trên laptop,
  PMTiles local, lịch trình, chi tiêu, hồ sơ và planner live/offline trung thực.

Bộ test tĩnh, không framework và không cần build. Chức năng gồm:

- Render bản đồ Đà Nẵng từ `data/danang.pmtiles`, không cần VietMap API key.
- Hiển thị tòa nhà 3D từ source `protomaps/buildings`.
- Tìm theo tên POI/địa chỉ bằng VietMap Autocomplete v4, lấy tọa độ qua Place v4 và đặt kết quả làm điểm A/B.
- Nếu VietMap Search chưa truy cập được, dùng Photon/OpenStreetMap làm nguồn tìm kiếm dự phòng cho bản test.
- Chọn điểm A/B bằng tọa độ hoặc nhấp trực tiếp lên bản đồ.
- Gọi VietMap Route API v4, vẽ tuyến và mô phỏng xe chạy từ A đến B.
- Xe tự bắt đầu chạy khoảng 1,3 giây sau khi tạo tuyến; nút **Tạm dừng/Tiếp tục** dùng để điều khiển thủ công.
- Tự thử Route v4 → v3 → v1.1 để tương thích với key cũ.
- Nếu key chưa được cấp quyền Routing (ví dụ HTTP 423), dùng OSRM/OpenStreetMap để tuyến vẫn bám theo đường.
- Chỉ khi cả VietMap Routing và OSRM đều không dùng được mới tạo đường nội suy màu cam; đường cam không phải tuyến thực tế.

## Chạy thử

Do trình duyệt có thể chặn API khi mở trực tiếp bằng `file://`, hãy chạy một local server trong thư mục này:

```powershell
python server.py
```

Không dùng `python -m http.server` cho file PMTiles vì server mặc định không trả HTTP byte ranges. `server.py` trong dự án đã hỗ trợ `206 Partial Content`.

Sau đó mở `http://localhost:5500`. Bản đồ tự tải từ file local, không cần nhập API key.

## Demo mobile trên laptop

Mở terminal PowerShell thứ nhất:

```powershell
docker compose --env-file BE/.env up -d postgres
.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

Mở terminal PowerShell thứ hai:

```powershell
& '.\.flutter-sdk\bin\flutter.bat' pub get --directory FE
& '.\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

App tự căn giữa trong khung điện thoại khi chạy trên màn hình laptop. Nếu BE
chưa chạy, app vẫn mở dữ liệu demo và ghi rõ rằng lựa chọn chưa được lưu lên
server. Hướng dẫn/test đầy đủ: `specs/003-stable-planning-roadmap/quickstart.md`.
Hướng dẫn platform/PostgreSQL đầy đủ:
`specs/005-platform-foundation/quickstart.md`.

PostgreSQL local dùng host `127.0.0.1`, port `5432`, database `davel_trace`,
username `davel`; password lấy từ `BE/.env`. Compose dùng một volume chung,
image Alpine có sẵn và log rotation để không nhân dung lượng theo worktree.

Ô **Service API key** chỉ dùng cho Search/Place/Route của VietMap và có thể để trống. Khi để trống, tìm kiếm dùng Photon/OpenStreetMap và chỉ đường dùng OSRM.

## Dữ liệu bản đồ local

File `data/danang.pmtiles` được cắt từ Protomaps/OpenStreetMap build ngày 2026-08-23, bbox có vùng đệm quanh Đà Nẵng:

```powershell
.\go-pmtiles_1.31.2_Windows_x86_64\pmtiles.exe extract `
  "https://build.protomaps.com/20260823.pmtiles" `
  ".\data\danang.pmtiles" `
  --bbox=107.75,15.80,108.55,16.35 `
  --maxzoom=15
```

PMTiles chứa dữ liệu vector để render. Font và sprite hiện vẫn tải từ CDN Protomaps; muốn chạy hoàn toàn không có Internet thì cần tải thêm các asset này vào dự án. Search và routing cũng là dịch vụ online, tách biệt với bản đồ nền local.
#
