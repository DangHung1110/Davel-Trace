# Rà soát dữ liệu và luồng — 19/11/2026

Phạm vi: toàn bộ dữ liệu của repo (`main` @ 916886f) và nhánh `feat/p0-data-v2` @ 2f36a0e, đối chiếu với
kiến trúc chốt (doc "TravelAgent – Kiến trúc Agent…", mục 12 và 17). Kết quả: snapshot `danang-v2`
format v2.2 trên nền `main`, đặc tả ở `DATA_SPEC.md`.

## 0. Chốt chiều 19/11 — v2.3, con số cuối

Người dùng: *"giá không cần chính xác, nếu không đủ thông tin trên Google Maps thì bỏ; máy làm được gì thì xử lý
hết, thống nhất data, cho con số cuối cùng"*. Mọi mục form `review_v22.html` từng hỏi người được máy quyết bằng
luật (`BE/ml/data/curate_v2.py`, đặc tả mục 10–11 của `DATA_SPEC.md`).

| | Số POI |
|---|---|
| Ứng viên (750 v1 + 127 OSM) | 877 |
| **Giữ trong `pois.json`** | **556** |
| — tham quan / ăn / cà phê nghỉ / bar-đêm / spa | 186 / 149 / 111 / 57 / 53 |
| — trung tâm / Sơn Trà–Mỹ Khê / Hội An / Hải Vân–Liên Chiểu / Ngũ Hành Sơn / Bà Nà | 186 / 165 / 95 / 57 / 33 / 20 |
| — giờ có nguồn / khung an toàn theo nhóm | 112 / 444 |
| — giá có nguồn / ước lượng theo nhóm | 38 / 518 |
| Bỏ (`dropped.json`) | 321 |
| — đã loại khi duyệt v1 / lưu trú / Núi Sơn Trà (review) | 136 / 76 / 1 |
| — dưới 30 đánh giá Google / không tìm thấy / đã đóng cửa / Google không có giờ | 77 / 17 / 6 / 6 |
| — giờ lệch mọi nhóm / trùng | 1 / 1 |

Đã làm thêm so với buổi sáng:

- **Tra Google Maps 126 POI OSM** (Hội An, Bà Nà, Mỹ Sơn) trong trình duyệt: 108 khớp, 18 không tìm thấy; phát hiện
  6 nơi đã đóng (Café Sputnik, Lapin, Summer Beach, Bánh mì Thuý, Nhà biểu diễn nghệ thuật cổ truyền, Bảo tàng
  Hội An đang tạm đóng). Kết quả ở `BE/data/sources/google_maps_check_2026-11-19.json`, chỉ để quyết giữ/bỏ.
- **Không còn giờ `unknown` và giá `null`**: nhóm giờ `co_ve` 09:00–16:00 (khớp 26/29 bộ giờ Google), `su_kien_toi`
  cho show tối; giờ du thuyền sông Hàn, Cù Lao Chàm tra web; giá bảo tàng / điểm có vé lấy khoảng theo nhóm.
- **Chọn lại nhóm giờ** cho 8 POI được giữ có khung nhóm lệch hẳn giờ Google (vd. Mì Quảng Nhung chỉ bán 06:00–10:00 →
  nhóm ăn sáng).
- **10 tên làm sạch**, 4 cặp nghi trùng xác định là hai nơi khác nhau, Núi Sơn Trà bỏ.
- **`time_budget` theo `dwell`**: 139 POI mang tag "thời lượng" cũ của v1 mâu thuẫn thời gian ghé (vd. Nhà Vọng
  Cảnh 30 phút ghi "cả ngày"); nay luôn suy từ `dwell.p50` (91 quick, 462 half_day, 3 full_day).
- Bỏ khỏi repo: form `review_v22.html`, `build_review_page.py`, 6 báo cáo duyệt cũ trong `reports/p0/`.
- Ma trận xe máy 556 × 556 (2,5 MB, không thiếu cặp). Test: 19 luật dữ liệu + 13 test luật lọc xanh.

Các mục 1–7 dưới đây là rà soát buổi sáng (v2.2), giữ để tra cứu.

## Tóm tắt

- **Dữ liệu đang tách làm hai dòng.** `feat/p0-data-v2` dựng v2.1 từ một bản `danang-v1` cũ (742 POI, 29/10).
  `main` đã có `danang-v1` mới hơn (750 POI, đã duyệt từng điểm, ma trận xe máy hiệu chỉnh). Vì thế v2.1
  thiếu 8 POI và giữ lại 132 POI mà `main` đã loại.
- **v2.2 gộp hai dòng**: nền `main` + phần tốt của v2.1 (126 POI OSM Hội An/Bà Nà/Mỹ Sơn, giá/giờ có URL,
  luật phân loại, form duyệt). 876 POI, 663 điểm dừng active.
- **Format thống nhất**: mỗi khái niệm một trường; giá có khoảng VND thật thay vì nằm trong chữ; bỏ 4 tag trùng
  nghĩa; thêm `on_request`, `audience`, `provenance.status`; 0 giá trị Google trong `pois.json`.
- **Ma trận xe máy phủ cả 876 POI** (6,4 MB thay cho ma trận ô tô 48 MB). 126 hàng mới là ước lượng, sai số 5,8%.
- **Kiểm tra**: 15 luật cấu trúc xanh (47 test). Còn 5 cổng P0 chờ người duyệt bằng `reports/p0/review_v22.html`.

## 1. Hai dòng dữ liệu

```
main ──92aeeb5 (29/10)──────── 164 commit ─────────────── 916886f (main)
          │                    danang-v1: 750 POI, duyệt 549 giữ / 124 loại,
          │                    plan_tier, giờ theo thứ, ma trận xe máy 750 POI
          └── feat/p0-data-v2: danang-v1 cũ 742 POI → danang-v2 v2.1 (869 POI)
```

Ví dụ thật: "Nhà hàng MIKADO" là trung tâm tiệc cưới. Lần duyệt trên `main` (30/10) đã loại nó ("phục vụ tiệc
đặt trước, không phải nơi khách du lịch ghé ăn"). Trong v2.1 nó vẫn `active`, thể loại `restaurant`, nên planner
có thể xếp nó làm bữa tối. Trong v2.2 nó là `excluded`, lý do "trung tâm tiệc cưới, hội nghị — không phải nơi
khách ghé ăn", `provenance.status.source = review_v1`.

Những gì v2.1 bỏ sót vì dựng từ bản cũ:

| | v2.1 | v2.2 |
|---|---|---|
| POI tay của `main` (Cầu Tình Yêu, Cá Chép Hóa Rồng, Nhà thờ Con Gà, Bãi tắm Phạm Văn Đồng, Bánh Xèo Bà Dưỡng, Hải Sản Bé Mặn, Sky36, New Golden Pine Club) | không có | có |
| POI `main` đã loại (trùng hoặc nằm trong điểm khác 33, tên chung/chỉ có trên OSM 21, ít bằng chứng 17, karaoke 15, đã đóng cửa 11, tiệc cưới 4, nhà thờ chỉ có giờ lễ 4…) | 113 `active` + 19 `review` | 132 `excluded`, có lý do |
| Ma trận | OSRM **ô tô**, 784 POI | OSRM **xe máy** hiệu chỉnh (VietMap, sai số 7,8%) + 126 hàng ước lượng |
| `TRAVELAGENT_CONTEXT.md` mục 5 | mô tả bản cũ ("OSRM driving phủ 498/742") | cập nhật |

Lưu ý: mục 14.1 của doc kiến trúc ("742 POI", "ma trận phủ 498/742") cũng lấy số từ bản cũ này.

Danh sách từng POI đổi trạng thái giữa v2.1 và v2.2, kèm lý do: `DATA_AUDIT_2026-11-19_status_changes.csv`.

## 2. Luồng mới cần dữ liệu gì

| Bước (kiến trúc 12.2) | Cần | Có trong v2.2 | Còn thiếu |
|---|---|---|---|
| 1. Hiểu yêu cầu → TripSpec | câu nói + TripSpec đúng để fine-tune/đo | — | bộ câu ↔ TripSpec; gold mới có 30 truy vấn |
| 2. Truy xuất | lọc cứng: trạng thái, giờ, khu, nơi tránh | `status`, `hours`, `zone`, `role`, `on_request` | — |
| | khớp tag, BM25, embedding | tag đủ cho 876 POI; tên | mô tả 0/876 (Wikivoyage/Wikidata) |
| | hạn ngạch vai trò, bộ lọc ứng viên | `role`, `tags.indoor`; mỗi khu đủ vai trò (luật 10) | nhãn cho bộ lọc GBDT (sinh bằng CP-SAT) |
| 3. Tầng 1 khung ngày | khu, cụm mềm, gắng sức | `zone`, `cluster_id`, `alt_group`, `tags.effort` | tham số trạng thái (năng lượng, độ no, nhiệt) |
| 4. Tầng 2 OPTW | cửa sổ giờ, thời lượng, giá, ma trận, `u(t)` | giờ 152 có nguồn / 622 khung an toàn / 102 không biết; dwell p25-p50-p75; khoảng giá 788/876; ma trận xe máy 876; `time_profile` | đường cong `u(t)` (`BE/data/priors/time_profiles.json`); ma trận theo khung giờ |
| 5. Kiểm định | P50 + đệm, Monte Carlo log-normal | phút ma trận ≈ P50; `dwell` cho `sigma_log` | P90 theo khung giờ × mưa (cần log GPS) |
| 6. Hiển thị | tên sạch, tên tiếng Anh | `name`, `name_en` 108 | 12 tên cần làm sạch |
| Replan | log GPS, thời tiết | — | pilot |

## 3. Đã làm trong v2.2

- **Nền đúng**: đọc `danang-v1` của `main` (không sửa). Trạng thái lấy từ lần duyệt v1 (121 loại), `plan_tier`
  (`excluded` → loại 11; `wish_only` → `tags.on_request`; `main`/`local` → `popularity.audience`), rồi luật v2,
  rồi quyết định của người dùng (luôn thắng).
- **Giá**: `{tier, min_vnd, max_vnd, note}`. 788 POI có khoảng; `tier` luôn suy ra từ khoảng nên đổi ngưỡng (Q1)
  chỉ cần build lại.
- **Giờ**: thứ tự nguồn rõ ràng; giờ đọc từ Google Maps (`claude-google-maps*`, `hours_by_day`) vào quarantine;
  45 điểm trong khu có vé bị cắt theo giờ cổng (vd. Chùa Cầu theo giờ vé phố cổ 07:30–21:00).
- **Tag**: bỏ `space` (trùng `indoor`), `rain_protection` (luôn `unknown`), `exposure_source`, `wind_exposure`
  (không ai đọc); `time_budget` thành một giá trị; 126 POI mới có tag theo trung vị thể loại (trước: trống);
  21 POI bỏ `good_times` mâu thuẫn với giờ có nguồn (vd. quán lẩu chỉ mở tối bị gắn "morning").
- **OSM**: chỉ nhận khớp khi tên khớp — loại 7 cặp sai (vd. "H Coffee" ↔ "Alo Coffee", "La Bonne Café" ↔
  "Làng Bích họa"); 355 POI có liên kết OSM (v2.1: 315); `name_en` từ OSM cho 108 POI.
- **Google**: `review_count`, giờ/giá đọc từ Google Maps, `visit_min` kiểu Google, ghi chú duyệt có số sao/số đánh giá
  → `quarantine_google.json` (749 POI). Lý do loại được viết lại ngắn, không còn số liệu Google.
- **Ma trận** (`BE/tools/build_matrix_v2.py`): 750 POI cũ giữ nguyên hàng xe máy; 126 POI mới ước lượng bằng
  `phút = 0,56 + 1,86 × km đường ô tô`, khớp trên 527 POI và đo trên 130 POI để riêng: sai số trung bình 5,8%,
  trung vị 1 phút. Ví dụ: Cầu Rồng → Chùa Cầu 29,6 km, 59 phút; Chùa Cầu → Mỹ Sơn 37,2 km, 75 phút.
- **Build tất định**: chạy hai lần ra cùng byte.

## 4. Kiểm tra

`python -m pytest BE/tests/data -q` → 15 luật cấu trúc xanh (mười luật của mục 17.3 + 5 luật giữ format thống nhất).

Cổng P0 (`P0_GATE=1`), hiện còn:

| Cổng | Còn | Ai làm |
|---|---|---|
| G3 điểm tiêu biểu có giờ `fixed` + giá có nguồn (miễn phí / trong vé cha không cần nguồn giá) | 23 / 33 | người kiểm giờ/giá (form, mục "Tiêu biểu") |
| G4 không còn `review` | 1 (Núi Sơn Trà) | người dùng chọn |
| G5 tên sạch | 12 | duyệt bảng tên |
| G6 mọi điểm dừng có giờ và giá | 23 không giờ, 6 không giá (chủ yếu lớp nấu ăn, khu vui chơi có vé) | tra trang chính thức |
| G7 điểm có vé có giá kèm URL | 16 | tra trang chính thức |

## 5. Giữ và bỏ

Giữ (đều có code hoặc test đọc): `BE/data/snapshots/danang-v1/*` (app đang chạy trên đó; đóng băng),
`data/snapshots/danang-v1/` (7 POI cho test), `data/danang.pmtiles` (bản đồ FE), `BE/eval/gold/*`,
`BE/eval/human/plan_review_v1.json` (nhãn người), `BE/ml/patm/*` (ranker, train lại bằng nhãn người).

Không mang từ `feat/p0-data-v2` sang (vẫn còn trên nhánh đó và trong lịch sử git):

| File | Lý do |
|---|---|
| `danang-v2/matrix.json` (ô tô, 48 MB) | thay bằng ma trận xe máy 6,4 MB; blob `4500c04` dùng lại khi build ước lượng |
| `danang-v2/archive_fields.json` (1,7 MB), `matrix_ref.json` | trùng với `danang-v1` + lịch sử git; không ai đọc |
| `danang-v1/*` bản cũ (742 POI, ma trận ô tô, ~30 trang/đáp án duyệt cũ) | `main` đã có bản mới; các file duyệt cũ `main` đã xoá ngày 02/11 (712a67d) |
| `sources/osm_gap_candidates.json` | 742 ứng viên build không đọc; sinh lại bằng `fetch_open_data.py osm` |
| `DATA_SPEC_v2_1.md`, `DATA_FIX_PLAN.md`, `PROMPT_P0*.md` | thay bằng `DATA_SPEC.md` + file này |
| `reports/p0` bản v2.1, `reports/audit_*`, `reports/data_audit_20261118.md` | số liệu của bản cũ; báo cáo mới sinh lại mỗi lần build |
| `BE/eval/gold/gold_v2.json` | dựng bằng planner của nhánh cũ; dựng lại khi app đọc được v2.2 |
| `BE/data/exports/danang-v2/*.csv` | sinh lại mỗi lần build; `main` gitignore `BE/data/exports/` |

Bỏ khi app chuyển hẳn sang v2: `danang-v1/review_drafts.jsonl`, `auto_verify_queue.jsonl` cùng các tool duyệt v1
(`build_verify_page.py`, `spotcheck_v2.py`) — form v2.2 và `11_verify_queue.html` thay chúng.

Code của `feat/p0-data-v2` chưa mang sang: bộ đọc `poi_view`, CP-SAT nhiều khung giờ, luật đủ điều kiện. Chúng sửa
planner bản cũ; cần chuyển lại lên `main` và đọc `price.min_vnd/max_vnd` của v2.2.

## 6. Việc tiếp theo

1. ~~**Người dùng**: mở `reports/p0/review_v22.html`~~ — đã do máy quyết chiều 19/11 (mục 0). Trước đây: trả lời Q1–Q7, duyệt 12 tên, 1 POI review, 4 cặp nghi trùng,
   6 giá chưa biết, 23 điểm tiêu biểu, 26 điểm vé phố cổ → Xuất JSON → `ingest_review.py` → `migrate_v2.py`.
   Form cũ `review_v21.html` vẫn dùng được (ingest nhận cả hai), quyết định áp theo `poi_id`.
2. Chuyển bộ đọc v2.2 vào `main` để planner chạy thử trên `danang-v2` (gold 30 truy vấn, so với v1).
3. Dựng hàng ma trận chính xác cho 126 POI mới bằng OSRM xe máy (`BE/tools/osrm/build_osrm.sh`).
4. `BE/data/priors/`: đường cong `u(t)` cho 12 `time_profile`, khí hậu theo tháng × giờ, tham số trạng thái.
5. `fetch_open_data.py popularity` với `WIKIMEDIA_UA` có liên hệ thật (Wikidata hiện mới có 10 POI).

## 7. Giới hạn

- Giờ: chỉ 152/876 có nguồn; 622 là khung an toàn theo nhóm (đúng ~85–90% theo hiệu chỉnh của v2.1).
- Giá: 624/663 điểm dừng là ước lượng theo thể loại (`inferred`, confidence 0,4).
- Thời lượng ghé: 820 POI theo bảng loại điểm; 5 người xác nhận; cần log pilot để hiệu chỉnh.
- Quyết định loại của lần duyệt v1 dựa một phần vào Google Maps (số đánh giá, "đã đóng cửa"); giữ quyết định,
  còn số liệu gốc nằm trong quarantine.
- 126 hàng ma trận mới là ước lượng; sai số lớn hơn ở đường đèo và đường làng (p90 14,6%).
