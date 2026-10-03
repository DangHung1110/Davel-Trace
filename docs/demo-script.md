# Demo video script (target: full local, đủ 3 lanes merge)

Chuẩn bị: snapshot `data/snapshots/danang-v1/` (lane A), BE chạy
(`python -m uvicorn BE.app.main:app --port 8000`), Ollama `qwen3:14b`
(nếu có; không thì parse dùng API key test env). Mỗi bước ghi màn hình.

## Scene 1 — Sức khỏe hệ thống (15s)

`GET /v1/health` → `{"status":"ok","snapshot":"danang-v1"}`.
Lời dẫn: "BE + snapshot Đà Nẵng sẵn sàng, chạy offline hoàn toàn."

## Scene 2 — Parse tiếng Việt (30s)

`POST /v1/parse` body `{"text": "cuối tuần đi Đà Nẵng 2 người 3 triệu
thích biển", "user_id": "u1"}` → TripRequest (city, budget, activities).
Rồi gửi `"đi chơi 2 người"` → `needs_clarification: ["city"]`.
Lời dẫn: "Thiếu thành phố thì hỏi lại, không đoán bừa."

## Scene 3 — Multi-plan + select (60s)

`POST /v1/itinerary` với trip S2 → 3 plans (savings/balanced/
experience) kèm tiền/điểm/lý do khác biệt. `POST /v1/itinerary/select`
`{"itinerary_id": "<balanced>"}` → `{"active_id": ...}`.
Lời dẫn: "Ba phương án, chốt một — hai cái còn lại để so sánh."

## Scene 4 — GPS mock + rain replan (60s)

Replay `data/gps/demo_day.json` (Sơn Trà → Mỹ Khê, 6 điểm).
Tới 13:30 trigger `rain/high` → replan: completed giữ nguyên,
điểm outdoor còn lại đổi vào nhà + lý do "mưa 80%".
Lời dẫn: "Trời mưa giữa đường — đã xong thì giữ, còn lại xếp lại."

## Scene 5 — Budget alerts (30s)

`POST /v1/expenses` 3 khoản (1.5M + 400k + 600k = 2.5M/3M) →
summary còn 500k + alert `80%`.
Lời dẫn: "Chi vượt là báo ngay, tiền còn lại siết lịch chiều."

## Fallback khi venue mất mạng

Quay sẵn full-local (BE + Ollama + snapshot trên máy); mở video nếu
wifi chết. Warm-up BE + Ollama trước giờ demo 5 phút.
