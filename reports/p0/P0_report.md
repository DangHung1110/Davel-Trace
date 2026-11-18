# Báo cáo P0 – Làm sạch dữ liệu (`danang-v2`) — 2026-11-18

Người làm: Claude (phiên cloud, truy cập repo qua thư mục kết nối). Chưa commit — xem "Việc bạn cần làm".

## 1. Kết quả chính

| Hạng mục | v1 | v2 |
|---|---|---|
| POI | 742 (metadata ghi 745) | 742, metadata khớp |
| Trạng thái | — | active 718 · review 20 · excluded 4 |
| POI có giờ dùng được (trường app đọc) | 499 | 660 |
| POI active (không tính lưu trú) thiếu giờ | 243 | 6 (đều là điểm "phải tra": Hải Vân Quan, Cù Lao Chàm…) |
| Giá: band app đọc được | 13 | 280 (+151 `free_entry`) |
| Giá vé tra web có URL (agent_web) | 13 (không ghi nguồn rõ) | 28 POI |
| Liên kết OSM (POI gốc Google) | 223 (nối chỉ theo khoảng cách) | 42 (khoảng cách ≤ 60 m **và** tên khớp); + 78 POI gốc OSM |
| Thời lượng ghé (`visit_min`) | rule v1: cầu/tượng đài/điểm ngắm 150–240 phút | bảng v2 theo 28 loại điểm; 38 POI người dùng đã xác nhận giữ nguyên |
| Test | 808 pass | 838 pass, 0 fail |

**Thử lịch (7 truy vấn gold, cùng solver, `deterministic_time=4`)**: v1 6/7 qua gate (q05 không ra lịch), trung bình 4,0 điểm/lịch; v2 7/7 qua gate,
trung bình 6,4 điểm/lịch (do thời lượng ghé hợp lý hơn), ít mục "giá chưa xác minh" hơn. Đây là thử nhanh, chưa phải đánh giá.

## 2. Đã thay đổi gì

**Dữ liệu (mới, không đụng v1)**
- `BE/data/snapshots/danang-v2/` — `pois.json`, `quarantine_google.json`, `matrix_ref.json`, `README.md` (đặc tả trường).
- `BE/data/exports/danang-v2/` — `poi_features.csv` (đặc trưng sạch cho ranker / pruner / u(t)),
  `poi_classifier_weak.csv` (742 nhãn yếu; 645 dòng nhãn luật khớp nhãn chỉ-từ-tên; 91 dòng dựa loại Google → đánh dấu `label_uses_google_type`).
- `BE/data/sources/agent_web_2026-11-18.json` — 11 mục giá vé/giờ tra web có URL (Bà Nà, Ngũ Hành Sơn, Động Âm Phủ, Cù Lao Chàm,
  Rừng dừa Bảy Mẫu, du thuyền sông Hàn ×2, Suối Hoa, Hải Vân Quan, VinWonders Nam Hội An, Jolie Cooking Class).

**Code**
- `BE/ml/data/v2_rules.py` — luật thuần (phân loại, vùng, nhóm giờ, giao giờ theo ngày, parse giá, band, dwell).
- `BE/ml/data/migrate_v2.py` — dựng v2 + exports + báo cáo + hàng đợi xác minh.
- `BE/ml/data/fetch_open_data.py` — lấy OSM (Overpass) + Wikidata/pageviews **khi có mạng** (VM này chỉ ra được pypi).
- `BE/common.py` — thêm `matrix_path()` (đi theo `matrix_ref.json`); `matrix.py`, `routers/itinerary.py`, `routers/evaluate.py`,
  `snapshot.load_matrix` dùng nó. Hành vi với v1 không đổi.
- `BE/app/services/retrieval.py` — POI `role=base` (lưu trú) và `status=excluded` không vào ứng viên (trừ khi là must-visit). v1 không có các trường này nên không đổi.
- Test mới: `BE/tests/unit/test_v2_rules.py`, `BE/tests/data/test_snapshot_v2.py` (10 luật + 2 luật cổng P0).

**Quyết định đã tự đưa ra (bạn có thể đảo lại)**
1. Đổi tên thể loại `pagoda` → `religious` (gồm cả nhà thờ, đình, đền).
2. Thêm nhóm giờ `cua_hang` (cửa hàng đặc sản/lưu niệm) tách khỏi `cho_ngay`; thu hẹp khung an toàn theo đo đạc (mục 3).
3. Chính sách Google khi build: `demo_phi_thuong_mai` (vì ranking còn đọc `rating`). Exports luôn sạch.
4. Loại (excluded) 4 POI: 3 quán có tiếp viên, 1 phòng khám thẩm mỹ. 20 POI để `review` (tên chung chung, đỉnh núi OSM không có đường lên, Ba Na Hills trùng Sun World…).
5. Giới hạn đường lên bán đảo Sơn Trà (07:30–17:30, nguồn ghi trong `access_note` v1) chỉ áp cho POI **trên bán đảo**
   (v1 gán nhầm cho cả Chợ đêm Sơn Trà, Cầu Tiên Sơn, spa ở Thanh Khê).

## 3. Phát hiện đáng chú ý

- **Bảng nhóm giờ ban đầu (tôi viết) sai khá nhiều**: đo trên giờ Google v1, khung an toàn chỉ đúng 50–79% với cafe/bar/spa/chợ.
  Sau khi thu hẹp: 0,83–0,93. Nghĩa là giờ suy luận **không bao giờ** an toàn tuyệt đối → luôn cần nhãn "nên kiểm tra giờ" + bước kiểm định.
- **Nối OSM chỉ theo khoảng cách là nguy hiểm**: trong 223 liên kết v1 chỉ 42 có tên khớp (56 phần tử OSM không có tên). Lần thử đầu dùng giờ OSM của liên kết sai (House Coffee ↔ The Pizza Company, mở 10:00) làm truy vấn gold q01 không ra lịch.
- **Thời lượng ghé v1 quá dài** cho điểm ngắn (cầu, tượng, điểm ngắm 3–4 giờ) → solver chọn ít điểm.
- **Độ phủ vùng**: `hoi_an` (17 POI) và `ba_na_tay` (21 POI) **không có quán ăn/cà phê nào** → lịch Hội An/Bà Nà sẽ thiếu bữa. Phố cổ Hội An chưa có trong dữ liệu.
- 6 cặp nghi trùng (`04_duplicate_candidates.csv`), vd. "Chùa Làng Thanh Khê" ×2, "Nhà thờ Phú Thượng" ×2, "Đèo Hải Vân"/"Hải Vân Quan".

## 4. Còn thiếu (cổng P0 chưa đạt)

`P0_GATE=1 python -m pytest BE/tests/data -k gate` hiện **fail 2 luật** — đúng như dự kiến:
1. `paid_attraction` thiếu `ticket_vnd` + URL: còn ~25 mục (`07_ticket_checklist.csv`) — chủ yếu 14 lớp nấu ăn (đang dùng ước lượng US$29–40), các khu sinh thái nhỏ.
2. `hoi_an`, `ba_na_tay` thiếu vai trò meal/rest → cần mở rộng POI (bước 5 của prompt P0, cần mạng: `fetch_open_data.py osm` tạo danh sách ứng viên; thêm POI mới còn cần hàng ma trận).

## 5. Việc bạn cần làm

1. **Xem diff và commit** trên nhánh riêng (tôi không chạy git để tránh khoá `.git`):
   `git checkout -b feat/p0-data-v2 && git add BE reports && git commit -m "feat(data): danang-v2 snapshot, rules, exports, P0 reports"`.
2. Chạy toàn bộ test trên máy bạn: `python -m pytest BE/tests -q` (gồm `test_baselines.py` VM không chạy kịp).
3. Trên máy có mạng: `python BE/ml/data/fetch_open_data.py all` rồi `python BE/ml/data/migrate_v2.py` (thêm liên kết OSM, Wikidata, lượt xem Wikipedia).
4. Mở `reports/p0/11_verify_queue.html`, kiểm 30–50 dòng đầu (giờ/giá + URL), bấm "Xuất JSON", lưu vào `BE/data/sources/` (bước ingest file này là việc tiếp theo cho Claude Code).
5. Quyết định: giữ `demo_phi_thuong_mai` hay chuyển `cach_ly`; duyệt danh sách `03_status_review.csv` và `04_duplicate_candidates.csv`.

## 6. Báo cáo kèm theo

`00_baseline.md` · `01_migration_summary.json` · `02_category_changes.csv` (178 dòng) · `03_status_review.csv` ·
`04_duplicate_candidates.csv` · `05_archetype_vs_google.csv` · `07_ticket_checklist.csv` · `11_verify_queue.csv/.html` (150 dòng).

```json
{"p0_status": "partial", "tests": {"passed": 838, "failed": 0, "not_run": "test_baselines.py (VM time limit)"},
 "pois": 742, "active": 718, "review": 20, "excluded": 4,
 "hours_usable": 660, "price_band_legacy": 280, "free_entry": 151, "agent_web_prices": 28,
 "osm_links_name_checked": 42, "gate_failures": ["paid_attraction ticket evidence (~25)", "hoi_an/ba_na_tay meal+rest"],
 "google_policy_in_build": "demo_phi_thuong_mai", "network_steps_pending": ["osm match", "wikidata/pageviews", "coverage expansion"]}
```

## 7. Bổ sung độ phủ (18/11, tối)

Lấy từ OpenStreetMap qua Overpass bằng trình duyệt trên máy bạn (máy ảo không ra mạng), lưu ở
`BE/data/sources/new_pois_osm_2026-11-18.json` (127 POI, có mã kiểm lỗi chép cho từng dòng — 127/127 khớp).
`migrate_v2.py` đọc file này; v1 không đổi. Danh sách: `reports/p0/08_new_pois.csv`.

| Khu | Trước | Sau |
|---|---|---|
| Hội An | 16 điểm tham quan, 0 quán ăn, 0 cà phê | 56 tham quan, 43 quán ăn, 18 cà phê, 5 bar |
| Bà Nà – Hòa Vang | 19 tham quan, 0 quán ăn, 0 cà phê | 21 tham quan, 13 quán ăn, 4 cà phê |
| Đà Nẵng | thiếu Nhà thờ Chính tòa (Con Gà), Công viên Biển Đông | đã thêm |

- Điểm mới tiêu biểu: Phố cổ Hội An (điểm cha, vé 80–120k), Chùa Cầu, các hội quán, nhà cổ Tấn Ký/Phùng Hưng/Đức An…,
  Chợ đêm Hội An, làng gốm Thanh Hà, làng mộc Kim Bồng, làng rau Trà Quế, bãi biển Cửa Đại, show Ký ức Hội An,
  Thánh địa Mỹ Sơn, Cầu Vàng, nhà thờ Saint Denis (Bà Nà).
- Cụm mới `hoi_an_old_town`: 18 điểm dùng chung vé phố cổ (danh sách là ước đoán theo vị trí — cần người xác nhận;
  giới hạn 5 phiếu/vé chưa mô hình hoá). Quán ăn trên đỉnh Bà Nà gắn `requires_ticket_of` = Sun World (phải có vé mới vào), giá bữa tính riêng.
- Giờ: 66/127 điểm có giờ OSM đọc theo từng ngày; 4 quán nghỉ 1 ngày/tuần được ghi `closed_days` (lịch hiện chưa xét thứ).
  60 điểm không có giờ OSM dùng khung an toàn theo nhóm.
- Thiếu trong OSM nên chưa thêm: bãi biển An Bàng (chỉ có quán cùng tên), Cầu Tình Yêu, tượng Cá chép hoá rồng.
  Sun Wheel/Asia Park bỏ qua vì đang tạm đóng (ghi chú trong `manual_pois.json`).

**Hệ quả còn lại:** 300 điểm (173 cũ + 127 mới) chưa có hàng ma trận → chưa vào lịch được cho tới khi tính lại ma trận.
POI mới mang `verified=false` như quy ước `osm_add.py`, nên còn bị loại khỏi lịch chính cho tới khi bỏ cờ `verified` kiểu cũ (mục 2 trong danh sách việc).
Cổng P0 "mỗi khu đủ vai trò" giờ **đạt**; cổng "vé có bằng chứng" vẫn trượt (chờ đổi sang tag giá 4 mức).
