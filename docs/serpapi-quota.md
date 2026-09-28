# SerpApi quota math + setup (T003b-SCRIPT, lane A)

Free plan: 250 searches/month. Hard cap trong code: **240** (buffer 10).

## Query plan (vừa khít quota)

- 6 categories × 5 districts = **30 searches** (1 page/query, ~20 results,
  `hl=vi gl=vn type=search`):
  categories: nhà hàng, quán cà phê, khu du lịch, bảo tàng, bãi biển, chợ;
  districts: Hải Châu, Sơn Trà, Ngũ Hành Sơn, Liên Chiểu, Thanh Khê.
- Details cho place_id MỚI (search payload đã có rating/hours cho nhiều
  chỗ — details chỉ lấp lỗ hổng): **≤200**.
- **Thực tế bulk 2026-09-28: 30 searches + 20 details lỗi (endpoint sai,
  đã bỏ) = 50/240.** Search-only từ đó: 333 place_ids → lọc bbox Đà Nẵng
  (loại 4: Hội An/QN/geocode lỗi) → **329 POIs** (core đủ 327, hours 68%,
  rating 97%, coords 100%). File: `BE/data/snapshots/danang-v1/pois.json`.

## Lấy key (5 phút, chưa làm — KHÔNG bulk khi chưa có key)

1. https://serpapi.com/manage-api-key → Sign up → copy key.
2. Thêm vào `BE/.env` (KHÔNG commit):
   ```
   SERPAPI_KEY=...paste...
   ```
   (Nhờ lane C thêm dòng placeholder vào `BE/.env.example` ở phase-PR —
   lane A không đụng file lane C.)
3. Chạy thử 10 trước (verify details endpoint + schema):
   ```
   python BE/ml/data/fetch_serpapi.py --raw data/snapshots/danang-full-tmp/ --max-queries 2
   ```
   `--max-queries 2` ≈ 2 searches + ~40 details ≈ 42 quota.
4. Bulk khi orchestrator duyệt (key đã có + test-10 đạt).

## Verify details endpoint

`details_params()` trong script dùng `engine=google_maps` + place_id —
đối chiếu https://serpapi.com/google-maps-api ở lần test-10, sửa 1 chỗ
nếu sai (mock selftest không phụ thuộc vào nó).
