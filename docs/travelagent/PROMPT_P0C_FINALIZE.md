# Prompt cho Claude Code — P0-c: hoàn thiện dữ liệu `danang-v2.1`

Dán nguyên khối dưới đây vào Claude Code, chạy ở gốc repo `Davel-Trace`, trên nhánh `feat/p0-data-v2` (đã commit WP0).

---

Bạn là kỹ sư dữ liệu + backend của dự án TravelAgent (Davel-Trace). Đọc theo thứ tự, trước khi sửa gì:

1. `AGENTS.md`
2. `docs/travelagent/TRAVELAGENT_CONTEXT.md` — bối cảnh, kiến trúc, quyết định, quy tắc (mục 8 là luật làm việc)
3. `docs/travelagent/DATA_SPEC_v2_1.md` — form dữ liệu ĐÍCH (bắt buộc)
4. `docs/travelagent/DATA_FIX_PLAN.md` — các gói việc WP1–WP12, nghiệm thu từng gói
5. `reports/p0/P0_report.md` — những gì đã làm, số liệu
6. Code: `BE/ml/data/v2_rules.py`, `BE/ml/data/migrate_v2.py`, `BE/common.py`, `BE/app/services/retrieval.py`,
   `BE/app/services/optimizer.py`, `BE/tests/data/test_snapshot_v2.py`

Nếu tài liệu mâu thuẫn nhau hoặc mâu thuẫn với code: DỪNG và hỏi tôi, nêu rõ chỗ mâu thuẫn.

## Quyết định đã chốt (từ `DATA_FIX_PLAN.md` mục 1)

Q1 = <điền hoặc để mặc định> · Q2 = <...> · Q3 = <...> · Q4/Q5 = <file quyết định nếu có> · Q6 = <...>

## Luật

- Không sửa/xoá `BE/data/snapshots/danang-v1/`. Không sửa tay `danang-v2/pois.json` — mọi thay đổi qua `migrate_v2.py` + file trong `BE/data/sources/`.
- Không gọi SerpAPI/API trả phí; không bịa dữ liệu (không biết → `null` + confidence thấp).
- Chạy `python -m pytest BE/tests -q` trước khi bắt đầu và sau mỗi gói; số test pass không được giảm.
  Thêm test cho mọi hành vi mới. Chạy cả `P0_GATE=1 python -m pytest BE/tests/data -q -k gate` để báo cổng.
- Mỗi gói = một hoặc vài commit nhỏ, message tiếng Anh (`feat(data): ...`, `refactor: ...`, `test: ...`).
- Không đổi hợp đồng API trong `specs/001-travel-agent-mvp/contracts/`; không đổi `SNAPSHOT_DIR` mặc định — hỏi tôi trước.
- Không xoá file; cần bỏ thì chuyển vào `_to_delete/` và báo.

## Việc — làm lần lượt, dừng báo cáo sau mỗi gói

1. **WP1** bộ chuyển `poi_view` + `migrate_v2.py` ghi schema v2.1 + `archive_fields.json` + luật 11 (danh sách trắng khoá).
   Nghiệm thu: toàn bộ test xanh với v1 và với `SNAPSHOT_DIR=BE/data/snapshots/danang-v2`.
2. **WP2** giá → `price.tier` (bảng 4 mức trong `BE/common.py`, vé cha tính 1 lần, bỏ `price_level` khỏi ranking).
3. **WP3** giờ → `hours.open` + `kind`; optimizer nhận nhiều khung giờ (test 18:00 cho quán `11:00-14:00, 17:00-22:00`).
4. **WP4** bỏ cờ `verified`; luật đủ điều kiện trong `retrieval`; nhãn độ tin cậy trong response.
5. **WP5** tên sạch (đưa bảng đề xuất cho tôi duyệt TRƯỚC khi áp), gom `tags`, đổi `time_budget`, soát `weather_sensitive`.
6. **WP6** `prize_prior` (signature + prior thể loại + Wikidata/Wikipedia khi có); ranker dùng nó thay `rating`;
   kiểm tra gold với `GOOGLE_POLICY=cach_ly`.
7. **WP7** ma trận: nếu `curl -s 127.0.0.1:5000` không trả lời OSRM thì DỪNG và nhắc tôi bật OSRM; nếu có, chạy
   `BE/tools/expand_poi_matrix.py` theo lô ≤ 100, ghi theo Q2.
8. **WP8–WP10** khi tôi đã đặt file `human_verify_v2_*.json` / `decisions_*.json` / đã chạy `fetch_open_data.py`:
   viết bước ingest, áp, báo số liệu. Nếu file chưa có: bỏ qua, ghi vào báo cáo.
9. **WP11** dựng lại gold trên v2.1, so sánh với v1 (KHÔNG đổi `SNAPSHOT_DIR` mặc định).
10. **WP12** dựng lại exports; viết `reports/p0/P0_final.md`.

## Báo cáo sau mỗi gói (ngắn)

- Đã làm gì (file, hàm), test trước/sau (pass/fail), cổng G1–G5 (xanh/đỏ, còn bao nhiêu mục).
- Số liệu thay đổi (vd. POI xếp được vào lịch: 409 → ?).
- Việc cần tôi làm / quyết định cần tôi chốt.
- Cuối cùng một khối JSON:
  `{"wp": "...", "tests": {"passed": n, "failed": n}, "gates": {"G1": "...", ...}, "eligible_pois": n, "todo_for_user": [...]}`

Hỏi tôi trước khi: xoá bất cứ gì; thêm > 40 POI; đổi hợp đồng API; đổi `SNAPSHOT_DIR`; dùng nguồn dữ liệu có điều khoản không rõ.
