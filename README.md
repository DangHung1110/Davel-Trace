# Davel Trace

## Repository layout

- `FE/`: Flutter mobile app cho hồ sơ, chuyến đi/lịch thủ công, map và chi tiêu.
- `BE/`: FastAPI + SQLAlchemy/Alembic management API.
- Root prototype: the original local PMTiles 3D route simulator used to validate map data and routing.

Development is integrated through the `dev` branch. Feature work should branch from `dev` and follow Conventional Commits in English.

## Management MVP

Phần app hoàn chỉnh trước AI gồm:

- nhiều hồ sơ local, một hồ sơ đang hoạt động, không yêu cầu đăng nhập;
- chuyến Đà Nẵng tối đa hai ngày và lịch hoạt động thủ công có reorder/cảnh báo chồng giờ;
- chi tiêu gắn trực tiếp với chuyến đi, tổng hợp theo nhóm và cảnh báo 80%/100%;
- POI snapshot dùng chung, map PMTiles hiện có, OSRM và fallback được gắn nhãn trung thực;
- SQLite code-first qua SQLAlchemy models và Alembic migrations, mở trực tiếp bằng DBeaver.

AI planner, booking/payment, OCR hóa đơn và đồng bộ đa thiết bị chưa thuộc MVP. Boundary `PlannerPort` giữ AI tách khỏi dữ liệu itinerary chính thức để có thể bổ sung sau mà không phá các module quản lý.

Chạy backend từ repository root:

```powershell
& '.\.venv\Scripts\python.exe' -m alembic -c BE\alembic.ini upgrade head
& '.\.venv\Scripts\python.exe' -m uvicorn BE.app.main:app --reload --host 127.0.0.1 --port 8000
```

Chạy Flutter trên Chrome trong khung điện thoại từ `FE/`:

```powershell
flutter pub get
flutter run -d chrome --web-port 5501 `
  --dart-define=DAVEL_API_BASE_URL=http://127.0.0.1:8000
```

Xem hướng dẫn chi tiết tại `BE/README.md` và `FE/README.md`.

## Da Nang Local PMTiles 3D Route Simulator

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
