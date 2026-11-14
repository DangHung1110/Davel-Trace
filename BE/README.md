# Backend (FastAPI + PostgreSQL)

FastAPI phục vụ planner hiện có và nền tảng quản lý. PostgreSQL 16 là kho dữ
liệu authoritative; SQLite cũ chỉ còn là nguồn import/compatibility ở
`demo|test`, không được chọn trong production.

## 1. Cấu hình

Từ repo root:

```powershell
if (!(Test-Path BE\.env)) { Copy-Item BE\.env.example BE\.env }
.\.venv\Scripts\python.exe -m pip install -r BE\requirements.txt
```

Đổi `POSTGRES_PASSWORD` và phần password tương ứng trong `DATABASE_URL`.
`BE/.env` đã được gitignore và không được commit.

## Cấu hình Gemini cho trợ lý lập lịch

Planner deterministic không cần LLM. Khi `LLM_PROVIDER=disabled`, API lập lịch,
chọn phương án và lịch sử vẫn hoạt động đầy đủ; chỉ interpretation/explanation AI
không khả dụng.

Gemini Plus/Google AI Pro trong ứng dụng Gemini và quota của Gemini Developer API
là hai sản phẩm riêng. Tài khoản Plus không tự cấp API quota cho backend. Để bật
Gemini:

1. Mở [Google AI Studio](https://aistudio.google.com/app/apikey) và tạo Gemini API key.
2. Sao chép `BE/.env.example` thành file ignored `BE/.env` nếu chưa có.
3. Điền cấu hình sau; không đặt key trong Dart, source code, commit hoặc ảnh chụp log:

   ```dotenv
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_key_from_ai_studio
   LLM_MODEL=gemini-3.1-flash-lite
   LLM_PARSE_ENABLED=true
   LLM_EXPLANATION_ENABLED=true
   LLM_SHADOW_ENABLED=false
   ```

4. Khởi động lại backend và kiểm tra `GET /v1/ai/readiness`. Response chỉ hiển thị
   provider/model/capability, tuyệt đối không trả key.

Backend gọi REST compatibility endpoint chính thức của Gemini bằng Python stdlib,
không thêm SDK và không dùng tài khoản/token ChatGPT. Nếu model trên không còn có
trong project AI Studio của bạn, chỉ cần đổi `LLM_MODEL`; không cần migration dữ liệu.

Tài liệu chính thức: [API quickstart](https://ai.google.dev/gemini-api/docs/get-started),
[billing](https://ai.google.dev/gemini-api/docs/billing),
[pricing/free tier](https://ai.google.dev/gemini-api/docs/pricing), và
[OpenAI-compatible REST](https://ai.google.dev/gemini-api/docs/openai).

Với provider hosted, UI phải thông báo nội dung được gửi ra ngoài và người dùng có
thể bỏ qua AI để nhập trường có cấu trúc. Raw prompt/output không được lưu mặc định.

## 2. PostgreSQL bằng Docker, không làm phình máy

```powershell
docker compose --env-file BE/.env up -d postgres
docker compose --env-file BE/.env ps
```

Compose mặc định dùng project `davel-trace-dev`; `COMPOSE_PROJECT_NAME` trong
env có thể chọn một project/volume local riêng. Bản Task 012 trên máy này dùng
`davel-trace-task012-demo`, cổng `5437`. Các worktree dùng cùng project sẽ dùng
chung named volume; đổi port không tạo lại password trong volume cũ.
Compose chỉ pull image `postgres:16-alpine` khi thiếu và
giới hạn log ở 3 file × 10 MB. Không có application image/build cache.

```powershell
# Dừng container, giữ nguyên database
docker compose --env-file BE/.env down

# Xem dung lượng; không tự động prune tài nguyên của project khác
docker system df
```

Chỉ dùng `docker compose --env-file BE/.env down -v` khi thật sự muốn xóa toàn
bộ database local và tạo lại từ đầu. Lệnh này phá hủy dữ liệu nên không nằm
trong luồng chạy/test tự động.

## 3. Code-first migrations và chạy API

```powershell
.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini current
.\.venv\Scripts\python.exe -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

Không dùng `Base.metadata.create_all()` trong runtime. Mọi thay đổi schema đi
qua Alembic revision được review. Kiểm tra:

```powershell
curl.exe -i http://127.0.0.1:8000/v1/health
curl.exe -i http://127.0.0.1:8000/v1/ready
```

`health` là liveness. `ready` kiểm tra PostgreSQL, Alembic head, catalog và
ghi rõ AI/OSRM là optional/degraded thay vì làm core app chết.

## 4. DBeaver

New Database Connection → PostgreSQL:

```text
Host: 127.0.0.1
Port: 5437 (hoặc POSTGRES_PORT trong BE/.env)
Database: davel_trace
Username: davel
Password: giá trị POSTGRES_PASSWORD local
```

Các bảng nền tảng: `alembic_version`, `acceptance_records`,
`shadow_observations`, `import_runs`, `seed_runs`. Identity ở revision
`006_001` thêm `accounts`, `role_assignments`, `identity_sessions`,
`one_time_actions`, `export_requests` và audit events. Các cột password/token
chỉ chứa hash. Nhấn Test Connection rồi Finish; không cần mở SQLite.

## 5. Demo đăng ký và đăng nhập

Trong `BE/.env`, bật hộp thư local chỉ cho demo:

```text
IDENTITY_DEV_OUTBOX_ENABLED=true
```

Production mode từ chối cấu hình này. Khởi động API bằng lệnh mục 3, sau đó
Flutter có thể đăng ký, lấy mã xác thực qua màn hình “hộp thư phát triển”, đăng
nhập, quản lý phiên, khôi phục mật khẩu, export và yêu cầu xóa tài khoản. Không
có mã nào được ghi vào log hoặc database dạng plaintext.

## 6. Import, seed, backup và restore proof

```powershell
# Import SQLite cũ, chạy lặp lại không nhân bản bản ghi
.\.venv\Scripts\python.exe -m BE.scripts.import_acceptance_sqlite --source BE\data\accepted_plans.db

# Seed chỉ chạy ở APP_MODE=demo hoặc test
.\.venv\Scripts\python.exe -m BE.scripts.seed_demo `
  --dataset data\snapshots\danang-v1\pois.json `
  --name danang-foundation --version danang-v1

# Reset đúng marker của seed trên (không xóa bảng/domain record khác)
.\.venv\Scripts\python.exe -m BE.scripts.seed_demo `
  --dataset data\snapshots\danang-v1\pois.json `
  --name danang-foundation --version danang-v1 --reset

# Backup ra ngoài repo; script tự dùng pg_dump trong Docker nếu máy không có pg_dump
.\.venv\Scripts\python.exe -m BE.scripts.backup_database --output D:\Backups\davel_trace.dump

# Restore vào DB tạm, so revision/count/ID đại diện, rồi tự drop DB tạm
.\.venv\Scripts\python.exe -m BE.scripts.restore_verify `
  --archive D:\Backups\davel_trace.dump `
  --manifest D:\Backups\davel_trace.dump.json
```

Không đặt archive trong repo hoặc Docker volume. Manifest không chứa password.

## 7. Test

```powershell
.\.venv\Scripts\python.exe -m pytest BE\tests -q
```

Chi tiết identity: `specs/006-identity-access/quickstart.md`.
