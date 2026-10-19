# Davel Trace Management API

FastAPI backend cho Management MVP: hồ sơ local, chuyến đi Đà Nẵng tối đa hai ngày, lịch thủ công, chi tiêu, POI catalog và route preview.

## Database decision

MVP dùng **SQLite + SQLAlchemy 2 + Alembic code-first** theo project Constitution. PostgreSQL/MySQL chưa được quy định; đổi sang một trong hai cần amendment/PR riêng. ORM models là nguồn schema, còn Alembic revisions là đường tạo/cập nhật DB chính thức.

Database mặc định được sinh tại `BE/data/davel_trace.db`. DBeaver mở file này bằng driver SQLite; không cần host, port, username hay password.

## Setup (PowerShell)

Từ repository root:

```powershell
py -3.11 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r BE\requirements.txt
& '.\.venv\Scripts\python.exe' -m alembic -c BE\alembic.ini upgrade head
& '.\.venv\Scripts\python.exe' -m uvicorn BE.app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: `http://127.0.0.1:8000/docs`
Health: `http://127.0.0.1:8000/v1/health`

## Setup (Git Bash)

```bash
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r BE/requirements.txt
./.venv/Scripts/python.exe -m alembic -c BE/alembic.ini upgrade head
./.venv/Scripts/python.exe -m uvicorn BE.app.main:app --reload --host 127.0.0.1 --port 8000
```

## DBeaver

1. Chạy `alembic upgrade head` ít nhất một lần.
2. Trong DBeaver chọn **New Database Connection → SQLite**.
3. Database file: đường dẫn tuyệt đối tới `BE/data/davel_trace.db`.
4. Test Connection → Finish.

Các bảng chính: `user_profiles`, `device_state`, `trips`, `itineraries`, `activities`, `expenses`, `route_segments`, `alembic_version`.

## Environment

Copy `.env.example` thành `.env` nếu muốn override. App không tự đọc `.env`; đặt biến trong shell hoặc dùng tool runner của IDE.

- `DAVEL_DATABASE_URL`: mặc định SQLite file trong repo.
- `DAVEL_POI_SNAPSHOT`: đường dẫn snapshot POI JSON.
- `DAVEL_OSRM_BASE_URL`: mặc định public OSRM demo.
- `DAVEL_ROUTE_TIMEOUT_SECONDS`: mặc định 10 giây.
- `DAVEL_CORS_ORIGINS`: danh sách origin cố định; localhost/127.0.0.1 với port bất kỳ cũng được phép cho Flutter dev server.

## Test

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
```

Không commit file `.db`, `.env` hay API key.
