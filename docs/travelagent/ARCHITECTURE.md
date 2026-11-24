# Davel — Kiến trúc mới (toàn luồng)

Cập nhật 24/11/2026. Doc gốc có sơ đồ: "Davel — Kiến trúc mới (toàn luồng)" trên claude.ai. Hàm mục tiêu chi tiết: `OBJECTIVE_V1.md`. Bối cảnh và quyết định cũ: `TRAVELAGENT_CONTEXT.md`, `ARCHITECTURE_BACKLOG.md`.

Hệ thống gồm **một đường đi của request (10 bước)** và **hai vòng học**: vòng offline train bộ lọc, pointer và trọng số hàm mục tiêu; vòng online cập nhật sở thích, thời gian ở và thời gian đi từ log của user. Model tự train chỉ nằm ở bước 4–7 và trong trọng số của bước 8; còn lại là luật, solver hoặc LLM có sẵn.

## 1. Luồng một request

| # | Thành phần | Đầu vào → đầu ra | Mục đích | Loại | Trạng thái |
|---|---|---|---|---|---|
| 1 | App (Flutter) | câu nói + onboarding → text + profile | thu yêu cầu | giao diện | có; hồ sơ user đang truyền sai (bug) |
| 2 | `parser.py` | câu tiếng Việt → trip JSON (hard / soft / assumptions / uncertainties) | tách điều bắt buộc khỏi điều thích; thiếu thì hỏi | LLM có sẵn | có |
| 3 | `retrieval.py` | trip + 1.009 POI → khoảng 590 ứng viên | bỏ điểm không thể đi | luật cứng | có |
| 4 | `rank.py` + bandit | ứng viên + profile + thời tiết + w_user → điểm v_i | gu chung + gu riêng, tính ở một chỗ | luật + model online | ranker có; bandit chưa |
| 5 | thời gian ở + `matrix.py` | POI → d_i (p50, p75); ma trận OSRM → m_ij | thời lượng sát thực tế; tính cả chặng từ khách sạn | model online + ma trận | prior 31 loại; hệ số giờ chỉ để kiểm (A4) |
| 6 | `_cap_candidates` (sau này bộ lọc học) | 590 → 40 ứng viên + sàn must_visit, hoạt động đã nêu, quán ăn | thu nhỏ bài toán | luật → model offline | top-40 ở v1; LightGBM khi thắng top-40 |
| 7 | gợi ý lời giải | 40 ứng viên → thứ tự gợi ý (`AddHint`) | CP-SAT tìm lời giải nhanh hơn | greedy → model offline | greedy hint có; pointer để sau |
| 8 | `optimizer.py`, `profiles.py` | ứng viên, d_i, m_ij, ràng buộc, trọng số w → lịch | chọn và xếp điểm tối đa J | solver | v1 sau cờ `DAVEL_OBJECTIVE=v1` |
| 9 | `pool.py`, `gate.py` | 3 lịch (3 bộ trọng số theo profile) → lịch đã kiểm | gate chốt bữa trưa và luật cứng; luật gu chỉ ghi số liệu | luật | có |
| 10 | `response.py` + app | lịch → hiển thị, chạy chuyến, replan, ghi log | | giao diện | thiếu log giờ đến/rời, lý do bỏ, đánh giá |

Chuyến 2 ngày: `multiday.py` chạy bước 6–9 cho từng ngày. Replan (`replan.py`, `state.py`): giữ phần đã đi, giải lại phần còn lại với cùng hàm mục tiêu.

## 2. Các model

| Model | Loại | Học từ | Khi nào | Đánh giá | Trạng thái |
|---|---|---|---|---|---|
| Trọng số hàm mục tiêu | logistic theo cặp + perceptron, 11 hệ số | cặp LLM chấm, lịch mẫu công bố, cặp người chấm | offline | test tự động; khớp cặp người giữ riêng | v1 đặt tay, đã vào code |
| Bộ lọc ứng viên | LightGBM | lời giải CP-SAT thầy | offline | recall@40, điểm lịch, thời gian | bản thử recall@40 0,964 (chưa vào nhánh này) |
| Pointer | Transformer + pointer attention | thứ tự ghé của thầy | offline | top-1/top-3, tốc độ so với greedy hint | chưa |
| Bandit sở thích | Bayesian logistic + Thompson | sửa / chọn / bỏ lịch | online | regret trên user giả lập; pilot | chưa; cùng đặc trưng với w |
| Thời gian ở | Bayes log-normal theo POI | check-in / check-out | online | sai số trên 45 POI đã xác nhận | prior có |
| Hệ số giờ đi lại | Bayes theo cặp zone × khung giờ | thời gian đi thật | online | sai số giờ đến | prior thiết kế |
| Parser, LLM judge | LLM có sẵn | — | — | 30 câu gold; tỉ lệ tự mâu thuẫn | có |
| PATM | LightGBM cặp chuyển tiếp | 1.770 cặp v5 | đã train | ablation T10 | đang chạy |

## 3. Hàm mục tiêu và sổ luật

```
J = Σ v_i x_i + w_state·S − T3 lặp nhóm − T4 liền kề cùng nhóm + T5 bữa đúng giờ
    − T6 bữa dồn + T7 nghỉ trưa − T8 vượt nhịp − T9 chạy xe/đổi vùng + T10 PATM
```

Chi tiết từng số hạng, trọng số và cách mã hoá: `OBJECTIVE_V1.md`.

**Mỗi luật chỉ ở một chỗ.** `BE/app/services/rules.py` là sổ luật duy nhất; gate, `soft_rules`, `objective`, `scorer` đọc từ đó:

| Lớp | Luật | Ở đâu |
|---|---|---|
| physical | FAR, VROH, B3 | ràng buộc CP-SAT + gate cứng |
| user | PROFILE_SAFE, BCS, ETB, LUNCH, must_visit / avoid | ràng buộc CP-SAT + gate cứng (LUNCH nằm trong HCS) |
| taste | A1, CAFE_CAP, CATEGORY_CAP, NO_CONSECUTIVE, NO_ADJACENT_FOOD, REST_FOLLOWS_LUNCH | v1: số hạng T3–T7, gate chỉ báo cáo; cứng lại khi có trong `strict_rules` |
| quality | F1, TIME_FIT, DINNER | chỉ báo cáo |
| edge | A2, B1, B2, E2 | legacy: phạt trên cạnh q_ij; v1: T6, T4, T3, T2 lo, cạnh chỉ còn điểm PATM |

## 4. Vòng học offline

1. Chốt hàm mục tiêu (v1 xong).
2. Học trọng số w: cặp sinh từ hai vector w lệch nhau + 459 cặp có sẵn; LLM chấm hai chiều (giao thức `ranker.py`), bỏ cặp tự mâu thuẫn; 30–50 lịch mẫu công bố → perceptron; chọn bộ thắng test tự động.
3. Sinh data thầy (`gen_teacher_data.py`): 10.000–20.000 bài, thầy mạnh hơn production (cap 40, nhiều thời gian giải hơn).
4. Train bộ lọc, train pointer; bật qua cờ sau khi qua gate 100%, recall, tốc độ.
5. Lặp lại khi đổi w, POI hoặc ma trận.

## 5. Vòng học online

| Sự kiện | Ghi gì | Model |
|---|---|---|
| Hiện 1–3 lịch | lịch nào, propensity | bandit |
| Chọn 1 lịch / sửa lịch | cặp: lịch chọn hoặc sau sửa tốt hơn | bandit |
| Check-in / check-out | thời gian ở thật | thời gian ở |
| Đến điểm kế | thời gian đi thật | hệ số giờ |
| Bỏ điểm, đánh giá sau chuyến | tín hiệu yếu / điểm hài lòng | bandit; replan |

Ngày đầu chỉ dùng prior. Thêm bảng sự kiện đụng API và migration nên cần duyệt thiết kế trước.

## 6. Trạng thái data (24/11)

| Bước | Đã có | Ước lượng / yếu | Còn thiếu | Máy tự sinh |
|---|---|---|---|---|
| 1 App | — | hồ sơ user (bug) | điểm xuất phát, khu vực muốn đi | — |
| 2 Parser | LLM | — | bộ câu kiểm parser | — |
| 3 Lọc cứng | POI danang-v2 | giờ mở 342 có nguồn / 498 ước lượng; giá ~11% có nguồn | — | — |
| 4 Điểm POI | nhãn POI 918/918 | độ nổi tiếng 33 mức | từ khoá món ăn; w_user (cần log) | — |
| 5 Thời gian | ma trận 1.009 × 1.009 | bảng thời gian ở 31 loại; hệ số giờ | — | — |
| 6 Cắt 40 | poi_features 42 cột | — | — | data thầy |
| 8 CP-SAT | PATM 1.770 cặp; khí hậu, dự báo | trọng số v1 (tay); u(t) 12 đường | — | — |
| 10 App, log | bảng hiện / chọn / chi tiêu | — | giờ đến và rời; lý do bỏ, đánh giá | — |
| Offline w | — | — | 100–200 cặp người; 30–50 lịch mẫu | 1.000–2.000 cặp LLM |
| Online | — | chi tiêu thật (bảng có, 0 dòng) | check-in/out, thời gian đi, chọn/sửa/bỏ | — |

Thứ tự thu tay: giờ mở và giá của POI hay vào lịch (100 POI = 96% lượt xuất hiện trong 1.703 lịch đã sinh), rồi lịch mẫu, bộ câu kiểm parser, từ khoá món ăn. Mọi giá trị có link nguồn; không dùng trường Google; thiếu thì ghi KHÔNG XÁC ĐỊNH.

## 7. Lộ trình

1. **Hàm mục tiêu v1 trong code** — xong (nhánh `feat/planner-objective-v1`). Qua: test cả hai chế độ, đo trước/sau (`reports/objective_v1/`).
2. Module thời gian ở + thiết kế log (song song). Qua: sai số trên 45 POI không tệ hơn bảng; duyệt thiết kế log.
3. Học trọng số w. Qua: thắng v1 trên test và chỉ số.
4. Data thầy lớn, bộ lọc, pointer. Qua: recall@40 ≥ 0,95; pointer nhanh hơn greedy hint; gate 100%.
5. Bandit + log trong app; user giả lập. Qua: regret giảm.
6. Pilot 10–20 chuyến thật.

## 8. Ngoài phạm vi và rủi ro

Ngoài phạm vi: đèo Hải Vân/Sơn Trà ban đêm (chưa gắn cờ cung qua đèo), tối ưu chung nhiều ngày, dị ứng, đặt vé/khách sạn.

| Rủi ro | Xử lý |
|---|---|
| CP-SAT chậm hơn khi thêm số hạng | cap 40, pointer hint, gộp biến |
| Trọng số học từ LLM lệch | hỏi hai chiều, kéo về v1, kiểm 30 cặp người |
| Data thầy cũ khi đổi w | chốt w trước, sinh lại data |
| Không có user thật cho phần online | user giả lập + pilot; trình bày là phần mở rộng |
