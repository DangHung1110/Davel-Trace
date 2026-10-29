# Backend (FastAPI)

Travel-agent API (`/v1/*` per `specs/001-travel-agent-mvp/contracts/api.md`).
Mọi lệnh dưới đã chạy thật trên máy này (2026-09-28, Python 3.11, Windows).

## 1. Cài deps

```powershell
python -m pip install -r BE/requirements.txt
```

Gồm: fastapi, uvicorn, ortools, lightgbm, pydantic, pytest, httpx.

## 2. Env (không commit secret)

```powershell
copy BE\.env.example BE\.env
```

Mặc định chạy ngay không cần sửa: `LLM_PROVIDER=local`
(Ollama `http://localhost:11434`, demo day). Test env mới cần key
(`LLM_API_KEY` qua env/BE/.env — KHÔNG commit).

## 3. Chạy BE

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

## Accepted-plan database (code first)

Không cần PostgreSQL/MySQL cho demo hiện tại. Lần đầu người dùng chốt phương
án, backend tự tạo SQLite tại:

```text
BE/data/accepted_plans.db
```

DBeaver: **New Connection → SQLite → Path** trỏ vào file trên. Hai bảng chính
là `acceptance_records` và `shadow_observations`. Có thể đổi đường dẫn bằng
`ACCEPTANCE_DB_PATH`; file database runtime đã được gitignore.

API evidence:

- `GET /v1/acceptances?trip_id=...`
- `GET /v1/acceptances/{id}`
- `POST /v1/shadow/evaluate`
- `GET /v1/planning/readiness`

Shadow judge mặc định tắt (`SHADOW_JUDGE_RATE=0`) và không bao giờ thay thứ tự
deterministic hoặc vượt hard gate. Tỉ lệ canary hợp lệ tối đa là `0.10`.

## 4. Test

```powershell
.\.venv\Scripts\python.exe -m pytest BE/tests -q
```

Unit chạy trực tiếp cũng được: `python BE/tests/unit/test_x.py`.
