# Backend (FastAPI + PostgreSQL)

FastAPI phục vụ planner hiện có và nền tảng quản lý. PostgreSQL 16 là kho dữ
liệu authoritative; SQLite cũ chỉ còn là nguồn import/compatibility ở
`demo|test`, không được chọn trong production.

## 1. Cấu hình

Từ repo root:

```powershell
Copy-Item BE\.env.example BE\.env
.\.venv\Scripts\python.exe -m pip install -r BE\requirements.txt
```

Đổi `POSTGRES_PASSWORD` và phần password tương ứng trong `DATABASE_URL`.
`BE/.env` đã được gitignore và không được commit.

## 2. PostgreSQL bằng Docker, không làm phình máy

```powershell
docker compose --env-file BE/.env up -d postgres
docker compose --env-file BE/.env ps
```

Compose cố định project name `davel-trace-dev`, dùng chung đúng một named
volume giữa các worktree, chỉ pull image `postgres:16-alpine` khi thiếu và
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
Port: 5432 (hoặc POSTGRES_PORT trong BE/.env)
Database: davel_trace
Username: davel
Password: giá trị POSTGRES_PASSWORD local
```

Các bảng nền tảng: `alembic_version`, `acceptance_records`,
`shadow_observations`, `import_runs`, `seed_runs`. Nhấn Test Connection rồi
Finish; không cần mở trực tiếp file SQLite nữa.

## 5. Import, seed, backup và restore proof

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

## 6. Test

```powershell
.\.venv\Scripts\python.exe -m pytest BE\tests -q
```

Chi tiết end-to-end và Git Bash: `specs/005-platform-foundation/quickstart.md`.
