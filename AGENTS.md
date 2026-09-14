# AGENTS.md — Davel-Trace

> Hiến pháp cho mọi agent và thành viên làm việc trong repo này.
> Mọi thay đổi file này phải qua PR và được review.

## 1. Project overview

Bản test tĩnh mô phỏng route 3D Đà Nẵng trên nền PMTiles local.
Không framework, không cần build.

- **Frontend:** `index.html` — render bản đồ Đà Nẵng từ `data/danang.pmtiles`,
  nhà 3D từ source `protomaps/buildings`, tìm kiếm (VietMap Autocomplete/Place v4,
  fallback Photon/OpenStreetMap), vẽ route (VietMap Route v4, fallback OSRM,
  cuối cùng mới nội suy đường cam — đường cam KHÔNG phải route thật).
- **Backend:** `server.py` — Python stdlib, static server có hỗ trợ
  HTTP byte-range (`206 Partial Content`) cho PMTiles. Không dependency ngoài.
- Nhánh `dev` đang tách workspace BE/FE (`BE/README.md`, `FE/README.md`).

## 2. Lệnh chuẩn (PowerShell)

```powershell
python server.py            # chạy local server, mặc định http://127.0.0.1:5500
python server.py --port 8080
```

- KHÔNG dùng `python -m http.server` cho PMTiles (thiếu byte-range).
- Không commit code khi chưa đọc `README.md`.

## 3. Quy trình Git (bắt buộc)

- Nhánh tích hợp: `dev`. Nhánh ổn định: `main`.
- Mọi việc làm trên nhánh riêng (`feat/...`, `fix/...`, `chore/...`), xong mở PR vào `dev`.
- **CẤM push trực tiếp lên `main` / `dev`. CẤM force-push. CẤM xóa nhánh remote.**
- Commit bước nhỏ, message tiếng Anh prefix rõ (`feat:`, `fix:`, `chore:`, `docs:`).
- Trước khi chạy agent task lớn: tạo checkpoint
  `git commit -am "wip: checkpoint before agent run"` và `git push`.
- File `data/danang.pmtiles` (~11MB) và `go-pmtiles_*/pmtiles.exe`
  đang tracked có chủ đích — KHÔNG xóa, KHÔNG đưa vào `.gitignore`.

## 4. Spec-driven workflow

Dùng Spec Kit (`/speckit.*`) cho mọi feature/fix không tầm thường:

1. `/speckit.specify` — spec WHAT/WHY, không chi tiết HOW
2. `/speckit.clarify` (nếu còn điểm mờ) → `/speckit.plan` → `/speckit.checklist`
3. `/speckit.tasks` → `/speckit.analyze` (read-only, sửa ở nguồn nếu báo lỗi)
4. `/speckit.implement` → `/speckit.converge` (lặp tới khi Converged)

## 5. Definition of Done

Task chỉ coi là xong khi đủ TẤT CẢ:

- [ ] Code chạy được bằng lệnh mục 2, không lỗi console nghiêm trọng
- [ ] Không phá vỡ tính năng cũ (mở map, search A/B, vẽ route, play/pause xe)
- [ ] Không thêm dependency mới nếu chưa được duyệt trong spec/plan
- [ ] Không commit secret/API key (VietMap key để trống hoặc qua `.env`, không hardcode)
- [ ] Commit + push lên nhánh task, mở PR vào `dev` với mô tả spec/thay đổi/test
