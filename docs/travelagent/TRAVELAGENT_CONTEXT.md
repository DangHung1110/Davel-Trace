# TravelAgent — Bối cảnh cho Claude Code

> Đọc file này trước mọi việc trong repo. Chốt 18/11/2026; mục 5, 6 (2 dòng đầu), 7, 11 cập nhật 19/11/2026
> sau khi gộp dữ liệu hai nhánh.
> Bộ tài liệu: file này (bối cảnh + kiến trúc + quy tắc) · `DATA_SPEC.md` (form dữ liệu v2.2) ·
> `DATA_AUDIT_2026-11-19.md` (rà soát dữ liệu + việc còn lại).
> Nguồn đầy đủ (do người dùng giữ): doc "TravelAgent – Kiến trúc Agent lập lịch du lịch Đà Nẵng"
> (mục 12–17 là bản chốt; mục 1–11 là lịch sử thiết kế) và doc "TravelAgent – Đánh giá audit dữ liệu POI".
> Nếu file này mâu thuẫn với `AGENTS.md`, `HANDOFF.md` hoặc `specs/001-travel-agent-mvp/`, DỪNG LẠI và hỏi người dùng.

---

## 1. Bài toán

Agent lập lịch cho du khách tự túc 1–2 ngày ở Đà Nẵng (gồm phần Quảng Nam cũ đã sáp nhập), đi xe máy.
Lịch phải đi được ngoài đời: đúng giờ mở cửa, đủ thời gian di chuyển, trong ngân sách, ăn đúng bữa,
có nghỉ, chịu được trễ và mưa, replan giữa chuyến mà không phá phần đã đi.

Mô hình toán: **OPTW** (Orienteering Problem with Time Windows) có điểm thưởng phụ thuộc thời gian `u(t)`,
chi phí chuyển tiếp phụ thuộc thứ tự `c_ij`, và trạng thái tích luỹ (năng lượng, độ no, nhiệt).

Hai luật cho toàn hệ thống:
1. Mọi điểm trong lịch phải truy về một `poi_id` trong dữ liệu.
2. Không lịch nào đến tay người dùng mà chưa qua verifier.

---

## 2. Lịch sử thảo luận (17–18/11/2026)

1. **Định nghĩa:** LLM chỉ hiểu yêu cầu và kể lại; solver + verifier quyết định tính đúng. Bài toán = OPTW.
2. **Kiến trúc đầu:** LLM orchestrator → `TripSpec` → planner → verifier → replanner; dữ liệu POI có provenance;
   4 model tự train (ETA, thời lượng ghé, sở thích two-tower, neural solver).
3. **Train vs inference:** train offline định kỳ; inference theo sự kiện; không online learning.
4. **"Núi trước hay biển trước":** thứ tự phải suy ra từ dữ liệu, không viết luật. Cần `u(t)` theo giờ,
   chi phí chuyển tiếp (tắm biển xong phải về thay đồ), trạng thái tích luỹ. Lập lịch hai tầng
   (tầng 1 khung ngày, tầng 2 điền chi tiết). Lựa chọn của người dùng → ràng buộc precedence + báo cái giá.
5. **Nguồn `u(t)`:** 4 tầng (thể loại → POI → bối cảnh → người dùng); `u(t)` là hình dạng (đỉnh = 1),
   mức hay chung là `prize`.
6. **Bản đánh giá thiết kế bên ngoài (PDF):** phần lớn đúng; đã nhận các lỗi: thời tiết đếm 2–3 lần,
   `u` chỉ chấm lúc bắt đầu, đường cong theo giờ đồng hồ, shrinkage trộn thang đo, hàm mục tiêu lệch đơn vị,
   P90 tính hai lần, Monte Carlo không tương quan, Gaussian cho thời lượng ghé, ngân sách độ trễ,
   số khung tầng 1 (73–1.045, không phải 24), mask không nhìn trước, mâu thuẫn ma trận, ML quá tay,
   OSRM không có profile xe máy.
7. **750 POI:** dùng làm danh sách để tìm, khớp sang nguồn mở; xác minh theo mức độ được dùng;
   **bỏ tính năng dị ứng** (chỉ cảnh báo + thẻ dị ứng khi người dùng nhắc).
8. **ML:** two-tower → GBDT; thời lượng ghé → bảng thống kê; neural solver yếu hơn CP-SAT ở quy mô này
   → nhánh nghiên cứu; PyVRP làm lõi heuristic; pre-trained: LLM nhỏ fine-tune cho parse,
   embedding đóng băng, TabPFN v2 cho ETA ít dữ liệu, RouteFinder chỉ để nghiên cứu.
9. **Data:** nút cổ chai là dữ liệu hành vi, không phải số POI; trạng thái là mô phỏng, không thu thập.
10. **Audit repo 18/11:** xem mục 5.
11. **Giờ và giá:** thay giá trị chính xác bằng nhóm giờ + khung an toàn, nhóm giá + khoảng giá, kèm confidence.
12. **So sánh ITINERA (EMNLP 2024) và Hao et al. (NAACL 2025):** lấy truy xuất theo sở thích từ ITINERA,
    lấy solver + unsat core từ Hao et al.; gom cụm chỉ là gợi ý mềm.
13. **Kiểm định:** P50 tất định + Monte Carlo có tương quan; truy xuất hybrid (tag, BM25, embedding, RRF).
14. **P0-a (18/11):** dựng `danang-v2` từ v1 bằng luật (thể loại, khu, nhóm giờ, giá, thời lượng, provenance), cách ly Google,
    11 giá vé tra web có URL. Phát hiện: khung giờ an toàn ban đầu chỉ đúng 50–79% (đã thu hẹp → 0,83–0,93);
    liên kết OSM v1 nối theo khoảng cách sai nhiều (chỉ 42/223 khớp tên); thời lượng ghé v1 quá dài (cầu/tượng 3–4 giờ).
15. **Giá:** đã có 3 hệ giá song song (nhóm 3 mức app đọc, `price_level` Google, giá v2) → chốt **một trường `price.tier`
    4 mức** (free/cheap/medium/expensive, + `included` cho điểm nằm trong vé cha). Không lưu số VND từng POI vì ~95% điểm
    không có số thật; vé đắt gộp vào tier; ngân sách = tổng trung điểm, cảnh báo = tổng cận trên.
16. **Giờ:** cũng gom về một trường `hours.open` + `kind` (fixed/safe_window/unknown).
17. **Lỗi chặn mới thấy:** cờ `verified` kiểu v1 loại 253–380 điểm (gồm cả 10 điểm tiêu biểu); 300 điểm chưa có ma trận →
    hôm nay chỉ 409/789 điểm thực sự vào được lịch. Bỏ cờ, thay bằng luật đủ điều kiện.
18. **Độ phủ (18/11 tối):** thêm 127 POI OSM (Hội An, Bà Nà, Mỹ Sơn, Nhà thờ Con Gà, Công viên Biển Đông) qua trình duyệt
    của người dùng; cụm vé `hoi_an_old_town`.

---

## 3. Kiến trúc chốt — luồng một yêu cầu

1. **Hiểu yêu cầu:** LLM (sau này: LLM nhỏ fine-tune) → `TripSpec` JSON đúng schema;
   trường không chắc để `null` và hỏi lại, không đoán.
2. **Truy xuất:** lọc cứng (SQL: giờ mở, đóng tạm, khu, nơi tránh) → chấm hybrid (tag, BM25, embedding) gộp bằng RRF
   → hạn ngạch theo vai trò (đủ quán mỗi bữa, chỗ nghỉ, điểm trong nhà) + MMR → bộ lọc ứng viên (GBDT) → ~25 POI.
3. **Tầng 1 – khung ngày:** xếp khối lớn vào buổi + khu (cụm mềm); mô phỏng năng lượng/độ no/nhiệt;
   branch-and-bound với cận trên rẻ.
4. **Tầng 2 – OPTW:** PyVRP (điểm tuỳ chọn có thưởng, cửa sổ thời gian, nhóm loại trừ cho bữa ăn;
   `u(t)` = bản sao POI theo khung giờ trong cùng nhóm loại trừ) hoặc CP-SAT (chứng minh tối ưu, tìm xung đột).
5. **Không có nghiệm:** mỗi ràng buộc cứng của người dùng là literal giả định trong CP-SAT → tập xung đột
   → thử các phương án nới, chỉ giữ phương án solver xác nhận khả thi → LLM diễn đạt → người dùng chọn → về bước 1.
6. **Kiểm định:** tất định với P50 + đệm 10 phút trước mỗi cửa sổ cứng; Monte Carlo 1.000 mẫu, log-normal,
   có nhân tố chung theo ngày (cả chặng đi lẫn nhịp độ nhóm); đạt khi cận dưới `p_on_time` ≥ 0,9.
   Sai → thêm ràng buộc vi phạm vào mô hình, giải lại tối đa 2 vòng → vẫn sai thì trả lịch an toàn + cảnh báo.
7. **Hiển thị:** vẽ lịch từ JSON ngay; LLM viết lời kể với placeholder `{poi:...}`, `{time:...}`, phần hiển thị điền từ JSON.

Vòng ngoài:
- **Replan:** kích hoạt theo sự kiện (GPS trễ quá đệm, đổi mưa, đóng cửa bất ngờ); khoá phần đã đi;
  giải lại tầng 1+2; phạt số thay đổi; mục tiêu p95 < 1 giây.
- **Log phản hồi:** giữ/đổi/bỏ, đánh giá kèm giờ tới, GPS (có đồng ý), **propensity** của phương án được hiển thị.

Hàm mục tiêu:
```
Tổng điểm = Σ prize_i · ū_i · (1 − s_mưa,i · p_mưa(t_i))  −  w · Σ c_ij  −  phạt(mệt, đèo tối, ...)
ū_i = trung bình u_i trên khoảng ở lại; nắng nằm trong u(t), thời tiết chỉ tính phần lệch so với bình thường
prize = xác suất đã hiệu chỉnh; w đổi phút ra điểm, tinh chỉnh trên bộ gold
```

---

## 4. Bảng quyết định

| Chủ đề | Chốt |
|---|---|
| Dị ứng | Bỏ; khi người dùng nhắc → cảnh báo + thẻ dị ứng; không lưu thông tin dị ứng |
| Vai trò LLM | Chỉ hiểu và kể; lời kể dùng placeholder |
| Solver | PyVRP (tốc độ) + CP-SAT (chứng minh, unsat core); neural solver = nghiên cứu |
| Gom cụm | Gợi ý mềm ở tầng 1, không lọc cứng |
| u(t) | Neo giờ mặt trời, phủ 24 giờ, trung bình trên khoảng ở lại |
| Thời tiết | Chỉ phần lệch so với bình thường; mưa × độ nhạy; sóng lớn/cờ cấm tắm = đóng cửa cứng |
| Kiểm định | P50 + đệm; Monte Carlo tương quan, log-normal, so cận dưới |
| Ma trận | Valhalla `motor_scooter`, tính sẵn hằng đêm cho mọi POI, theo khung giờ × thời tiết, P50 + P90 |
| Giờ, giá | Nhóm giờ + khung an toàn; nhóm giá + khoảng giá; confidence theo trường |
| Nguồn dữ liệu | Cách ly trường gốc Google (`quarantine_google.json`); khớp OSM/Overture/Wikidata **theo khoảng cách và tên** |
| Chính sách Google | `pois.json` luôn sạch; Google chỉ ở `quarantine_google.json`; `GOOGLE_POLICY` quyết lúc **chạy** (demo cho tới khi có `prize_prior`, rồi `cach_ly`) |
| Giá | Một trường `price.tier`: free / cheap (<100k) / medium (100–500k) / expensive (500k–1,2tr) / included / null |
| Giờ | Một trường `hours.open` (khung hợp lệ mọi ngày mở) + `kind` + `closed_days` |
| Cờ `verified` v1 | Bỏ; thay bằng luật đủ điều kiện (active, không base, có ma trận, có giờ) + nhãn độ tin cậy |
| Xếp hạng | `popularity.prize_prior` sạch thay `rating` Google |
| Đọc dữ liệu trong app | Qua bộ chuyển `BE/common.py::poi_view`, không đọc thẳng trường trong file |
| Model sở thích | GBDT/LightGBM + embedding đóng băng; bỏ đặc trưng `rating`/`price_level` của Google |
| Thời lượng ghé | Bảng log-normal theo thể loại × kiểu nhóm + shrinkage |
| Độ trễ | Vẽ lịch từ JSON (~1,8 s); lời kể hiện sau |

---

## 5. Hiện trạng dữ liệu (19/11/2026)

- `BE/data/snapshots/danang-v1/` trên `main`: **750 POI** đã duyệt (549 giữ / 124 loại / 77 chưa duyệt, phần lớn là
  lưu trú), `plan_tier`, ma trận xe máy `dense-v1` phủ 750 POI (OSRM `motorbike.lua`, sai số 7,8% so với VietMap).
  App vẫn chạy trên snapshot này.
- `BE/data/snapshots/danang-v2/` (format v2.3, chốt chiều 19/11): **556 POI** dùng được để xếp lịch (877 ứng viên =
  750 v1 + 127 OSM Hội An/Bà Nà/Mỹ Sơn; 321 bỏ trong `dropped.json` kèm lý do: đã loại v1, lưu trú, ít/không có
  thông tin trên Google Maps, đã đóng cửa). Mọi POI có giờ và mức giá; ma trận xe máy 556 × 556. Chi tiết:
  `DATA_AUDIT_2026-11-19.md` mục 0, `DATA_SPEC.md` mục 10–11.
- Nhánh `feat/p0-data-v2` dựng v2.1 từ một bản `danang-v1` cũ (742 POI, 29/10) — đã thay bằng v2.3.
- Mô tả 0; Wikidata 10; log người dùng thật 0; gold 30 truy vấn (`BE/eval/gold/t051_scoped_suite.json`).
- ML hiện có trên `main`: PATM (LightGBM pairwise), weather labeler, shadow LLM ranker (event classifier chỉ còn ở nhánh cũ).

---

## 6. Bản đồ refactor: module → việc cần làm

| Module | Việc |
|---|---|
| `BE/common.py` (`load_pois`) | Bộ đọc v2.2 → trường app đang đọc (bản `poi_view` cho v2.1 có trên `feat/p0-data-v2`; chuyển sang `main` và đọc `price.min_vnd/max_vnd`) |
| `BE/app/services/retrieval.py` (`load_pois_json`), `BE/app/modules/catalog/infrastructure.py`, `BE/app/routers/*` | Mọi chỗ đọc `pois.json` đi qua bộ đọc trên; vẫn đọc được v1 |
| `BE/ml/data/*` (SerpAPI) | Ngừng dùng cho dữ liệu production; `osm_join.py`, `osm_add.py`, `fetch_osm.py` mở rộng cho khớp nguồn mở |
| `BE/app/services/profile_filter.py` | Bỏ lọc dị ứng; thay bằng cảnh báo + thẻ dị ứng; giữ `must_avoid`, accessibility |
| `BE/app/services/matrix.py`, `osrm_client.py`, `BE/tools/build_poi_matrix.py` | Đã có OSRM xe máy hiệu chỉnh, phủ mọi POI v2 (126 hàng ước lượng); còn P50/P90 theo khung giờ × thời tiết |
| `BE/app/services/optimizer.py` | Giữ CP-SAT OPTW; thêm assumptions cho unsat core; thêm backend PyVRP; `u(t)` bằng bản sao khung giờ |
| `BE/app/services/validator.py`, `gate.py` | P50 + đệm; Monte Carlo tương quan; vòng lazy constraint ≤ 2 |
| `BE/app/services/repair.py` | Giữ giới hạn 2 vòng; chỉ sửa trong phạm vi ràng buộc đã kiểm chứng |
| `BE/app/services/parser.py`, `llm.py` | Ép output theo JSON schema; trường không chắc = null + câu hỏi lại |
| `BE/app/services/retrieval.py`, `rank.py`, `pool.py` | Hybrid (tag, BM25, embedding), RRF, hạn ngạch vai trò, MMR, đo recall@25 |
| `BE/app/services/trip_ctx.py`, `templates.py` | Trạng thái năng lượng/độ no/nhiệt; tầng 1 khung ngày |
| `BE/app/services/weather.py` | Phần lệch so với khí hậu; xác suất mưa theo giờ; khí hậu khi lập lịch xa |
| `BE/ml/patm/*` | Bỏ đặc trưng gốc Google; nhãn LLM judge = nhãn yếu; đo đồng ý LLM vs người trên `human_verify_200`; kiểm tra giấy phép Foursquare |
| `BE/eval/*` | Gold 30 → 100; thêm recall@25, Average Margin, Overlaps, p_on_time |

---

## 7. Đặc tả dữ liệu

- **Đích:** `DATA_SPEC.md` — bản ghi POI v2.2, từ vựng, giá = mức + khoảng VND, 15 luật + 5 cổng.
- **Dựng:** `python BE/ml/data/migrate_v2.py` (POI) rồi `python BE/tools/build_matrix_v2.py --car …` (ma trận).
- **Nguồn đầu vào** (`BE/data/sources/README.md`): `new_pois_*.json`, `osm_match.json`, `agent_web_*.json`,
  `decisions_*.json`, `human_verify_v2_*.json`, `popularity.json`.
- **Thứ tự tin nguồn:** human (có URL) → open_data / user → agent_web → inferred. Giờ: trang chính thức → OSM → nhóm giờ.
  Mô tả: Wikivoyage → Wikipedia → để trống (KHÔNG để LLM viết).

---

## 8. Quy tắc làm việc cho agent

1. Đọc `AGENTS.md`, `HANDOFF.md`, `specs/001-travel-agent-mvp/` trước. Mâu thuẫn với file này → hỏi người dùng.
2. Chạy pytest trước và sau mỗi thay đổi; không để số test pass giảm.
3. KHÔNG sửa hay xoá `BE/data/snapshots/danang-v1/`. Tạo snapshot mới có version.
4. Không dùng trường gốc Google để train hay xuất production, trừ khi người dùng chọn chính sách demo phi thương mại.
5. Không gọi SerpAPI hay API trả phí. Được dùng Overpass, Overture (DuckDB), Wikidata, Wikipedia pageviews,
   Wikivoyage, Open-Meteo — có cache cục bộ và giới hạn tốc độ.
6. Không bịa dữ liệu. Thiếu thì để trống, confidence thấp, ghi `KHÔNG XÁC ĐỊNH`.
7. Giữ hợp đồng API (`contracts/`) trừ khi được yêu cầu; nếu buộc phải đổi, ghi rõ lý do.
8. Thay đổi nhỏ, một mục đích, kèm test. Không refactor lan rộng ngoài phạm vi nhiệm vụ.
9. Hỏi người dùng trước khi: xoá bất cứ gì; thêm hơn giới hạn POI mới; đổi hợp đồng API; dùng nguồn có điều khoản không rõ.
10. Cuối mỗi phiên: báo cáo theo khung trong prompt nhiệm vụ, có số liệu và danh sách việc cần người dùng làm.

---

## 9. Thứ tự công việc

| Giai đoạn | Nội dung | Cổng ra |
|---|---|---|
| P0 – Làm sạch nền (2 tuần) | pytest baseline; schema v2; cách ly Google; khớp nguồn mở; mở rộng Hội An/Bà Nà/Sơn Trà/Hải Vân; giờ, giá, mô tả; luật kiểm tra; hàng đợi xác minh | Test xanh, 10 luật đạt, nguồn sạch |
| P1 – Nền cho ML (2 tuần) | Ma trận Valhalla; u(t) neo mặt trời; bộ phân loại POI (TF-IDF + LightGBM, weak supervision + cleanlab); bộ lọc ứng viên; gold 30 → 100 | 100 gold qua gate |
| P2 – MVP + pilot (3–4 tuần) | LLM nhỏ parse (constrained decoding); nhánh vô nghiệm; Monte Carlo verifier; hybrid retrieval; pilot 50–100 chuyến | Đo được khả thi ngoài đời |
| P3 – Học từ log (liên tục) | ETA (TabPFN → GBDT, conformal); ranker nhãn thật; tham số trạng thái; nhánh nghiên cứu solver | Model thắng baseline mới lên |

---

## 10. Thuật ngữ

- **OPTW:** chọn tập con điểm + thứ tự + giờ tới để tối đa tổng điểm trong cửa sổ thời gian và giới hạn ngày.
- **TripSpec:** JSON ràng buộc của chuyến đi (ngày, nhóm, ngân sách, sở thích, nơi tránh, precedence...).
- **u(t):** độ hấp dẫn theo giờ của một POI, 0–1, đỉnh = 1.
- **P50 / P90:** trung vị / phân vị 90 của thời gian.
- **Khung an toàn:** khoảng giờ mà gần như mọi POI cùng nhóm giờ đều mở.
- **Gate:** bộ luật kiểm định trong `gate.py` / `validator.py`.
- **Propensity:** xác suất một phương án được hiển thị; cần để đánh giá và học lại trên log.

---

## 11. Trạng thái và việc tiếp (19/11/2026)

Dữ liệu đã chốt thành `danang-v2` v2.3 (556 POI, xem `DATA_AUDIT_2026-11-19.md` mục 0): 18 luật dữ liệu xanh,
máy đã quyết mọi mục từng chờ người duyệt (luật ở `BE/ml/data/curate_v2.py`; người dùng sửa qua `decisions_*.json`).

Việc tiếp, theo thứ tự: (1) ~~duyệt form~~ (máy đã quyết); (2) chuyển bộ đọc dữ liệu (`poi_view`) sang `main` cho v2.3;
(3) dựng lại hàng ma trận của 126 POI mới bằng OSRM xe máy; (4) tạo `BE/data/priors/` (đường cong `u(t)`,
khí hậu, tham số trạng thái); (5) gold 30 → 100 trên v2.2.
