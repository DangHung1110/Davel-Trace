# Backend (FastAPI)

Travel-agent API (`/v1/*` per `specs/001-travel-agent-mvp/contracts/api.md`).
Mọi lệnh dưới đã chạy thật trên máy này (2026-09-28, Python 3.11, Windows).

## 1. Cài deps

```powershell
python -m pip install -r BE/requirements.txt
```

Gồm: fastapi, uvicorn, ortools, lightgbm, pydantic, pytest, httpx.

Management MVP còn dùng SQLAlchemy 2.x và Alembic. ORM models là nguồn schema
(code-first); không tạo hay sửa bảng bằng tay.

## 2. Env (không commit secret)

```powershell
copy BE\.env.example BE\.env
```

Mặc định chạy ngay không cần sửa: `LLM_PROVIDER=local`
(Ollama `http://localhost:11434`, demo day). Test env mới cần key
(`LLM_API_KEY` qua env/BE/.env — KHÔNG commit).

## 3. Chạy BE

Khởi tạo hoặc nâng cấp schema trước khi chạy API:

```powershell
& '.\.venv\Scripts\python.exe' -m alembic -c BE\alembic.ini upgrade head
& '.\.venv\Scripts\python.exe' -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

Nếu Python đã nằm trong `PATH`, có thể dùng lệnh ngắn:

```powershell
python -m uvicorn BE.app.main:app --port 8000
```

Kiểm tra (đã verify thật):

```powershell
curl.exe http://localhost:8000/v1/health
# {"status":"ok","snapshot":"danang-v1"}

curl.exe -X POST http://localhost:8000/v1/expenses `
  -H "Content-Type: application/json" `
  -d "@body.json"   # {"trip_id":"t1","label":"Mi Quang","amount":120000,"kind":"food"}
# -> 201 entry; GET /v1/expenses/summary?trip_id=t1 -> budget/spent/left/alert
```

Lưu ý: `POST /v1/parse` cần LLM (Ollama local hoặc API key);
không LLM thì endpoint trả lỗi transport rõ ràng, không crash.
`POST /v1/itinerary` cần snapshot `data/snapshots/danang-v1/`
(lane A, đủ lanes merge mới có).

## 4. SQLite và DBeaver

Mặc định backend dùng SQLite tại:

```text
sqlite:///BE/data/davel_trace.db
```

Trong DBeaver, tạo connection **SQLite** và chọn file tuyệt đối
`<repo>\BE\data\davel_trace.db`. Không nhập host, port, user hay password.
Nếu muốn dùng database khác, đặt `DATABASE_URL` trong `BE/.env`, rồi chạy
`alembic upgrade head` với cùng biến môi trường trước khi khởi động API.

Kiểm tra migration trên database trắng:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest BE\tests\integration\test_migrations.py -q
```

## 5. Test

```powershell
& '.\.venv\Scripts\python.exe' -m pytest BE\tests -q
```

Unit chạy trực tiếp cũng được: `python BE/tests/unit/test_x.py`.
