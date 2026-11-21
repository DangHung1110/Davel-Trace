> **ĐÃ THAY THẾ** bởi `PROMPT_P0C_FINALIZE.md` (18/11, 22:00). Giữ lại để tham khảo.

# Prompt cho Claude Code — P0-b (tiếp sau P0-a ngày 18/11/2026)

Dán nguyên khối dưới đây vào Claude Code, chạy ở gốc repo `Davel-Trace`.

---

Đọc theo thứ tự: `AGENTS.md`, `docs/travelagent/TRAVELAGENT_CONTEXT.md` (đặc biệt mục 7, 8, 11),
`BE/data/snapshots/danang-v2/README.md`, `reports/p0/P0_report.md`. Nếu có mâu thuẫn, dừng và hỏi tôi.

Tham số: `GIOI_HAN_POI_MOI = 150`, `CHINH_SACH_GOOGLE = demo_phi_thuong_mai` (giữ như build hiện tại).

Luật: không sửa `BE/data/snapshots/danang-v1/`; không gọi SerpAPI/API trả phí; không bịa dữ liệu (thiếu → null + confidence thấp);
mọi thay đổi dữ liệu đi qua `BE/ml/data/migrate_v2.py` (không sửa tay `danang-v2/pois.json`); chạy
`python -m pytest BE/tests -q` trước và sau; số test pass không được giảm. Làm trên nhánh `feat/p0b-data`, commit nhỏ, message tiếng Anh.

Việc, theo thứ tự (dừng sau mỗi việc và báo cáo ngắn):

1. **Ingest xác minh của người.** Đọc mọi `BE/data/sources/human_verify_v2_*.json`
   (`{items:[{poi_id, hours, ticket_vnd, evidence_url, verified_by:"human", checked_at}]}` — xuất từ `reports/p0/11_verify_queue.html`).
   Trong `migrate_v2.py`: nguồn này ưu tiên cao nhất cho giờ và giá, `verified_by=human`, confidence 0.9; thiếu `evidence_url` → hạ `user` 0.7.
   Thêm test: một mục human thắng mọi nguồn khác; mục thiếu URL không thành `human`.
2. **Dữ liệu mở.** Chạy `python BE/ml/data/fetch_open_data.py all` (máy này có mạng). Báo: số `osm_match`, số POI có Wikidata,
   phân bố lượt xem. Rebuild v2. Kiểm tra lại 10 luật.
3. **Độ phủ Hội An / Bà Nà.** Từ `BE/data/sources/osm_gap_candidates.json`, đề xuất ≤ 40 POI (ưu tiên: phố cổ Hội An và các điểm trong phố cổ,
   quán ăn/cà phê có tên rõ ở `hoi_an` và quanh chân Bà Nà). **Đưa danh sách cho tôi duyệt trước khi thêm.** Sau khi duyệt:
   thêm qua một file nguồn mới (`BE/data/sources/new_pois_*.json`) mà migrate đọc, rồi mở rộng ma trận bằng `BE/tools/expand_poi_matrix.py`
   (cần OSRM/Valhalla cục bộ — nếu không có, dừng và báo).
4. **Optimizer nhiều khung giờ.** `BE.common.parse_hours` chỉ trả khung đầu tiên → nhà hàng mở trưa + tối chỉ được xếp trưa.
   Cho optimizer nhận mọi khung trong `opening_hours` (khoảng tuỳ chọn / bản sao theo khung, chỉ chọn một). Giữ hành vi cũ khi chỉ có 1 khung.
   Test: POI `11:00-14:00, 17:00-22:00` được xếp lúc 18:00 khi trip là 16:00–21:00.
5. **Báo cáo** `reports/p0/P0b_report.md`: số liệu trước/sau, cổng `P0_GATE=1` còn fail gì, việc tôi cần làm.

Hỏi tôi trước khi: xoá bất cứ gì; thêm > 40 POI; đổi hợp đồng API trong `specs/001-travel-agent-mvp/contracts/`; đổi `SNAPSHOT_DIR` mặc định.
