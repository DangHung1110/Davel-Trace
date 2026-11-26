# Hàm mục tiêu v1 so với legacy (24/11/2026)

Với trọng số cuối của nhánh `feat/planner-objective-v1`, v1 giữ nguyên tỉ lệ có lịch, gate và bữa trưa ở mọi bộ đo, chạy xe ít hơn và đa dạng hơn ở profile balanced; cái giá là thời gian giải tăng 15–35%.

Thiết lập chung: cùng cap 40, cùng ngân sách CP-SAT (`deterministic_time` 5), 2 tiến trình song song. Request giữ riêng: 120 id đầu của `test_ids.json` (bộ lọc v2, chưa dùng để train). "Legacy" là `main` với luật gu CATEGORY_CAP / NO_CONSECUTIVE đã mềm, các luật còn lại cứng (`DAVEL_OBJECTIVE=legacy`).

## Balanced, 120 request giữ riêng (`compare_heldout.json`)

| Chỉ số | Legacy | v1 |
|---|---|---|
| Có lịch / qua gate | 120/120 / 120/120 | 120/120 / 120/120 |
| Bữa trưa đúng khung | 49/49 | 49/49 |
| Phút chạy xe, trung vị / trung bình | 57 / 52,1 | 35,5 / 38,1 |
| Chặng dài nhất, trung bình (phút) | 30,9 | 24,0 |
| Đổi zone, trung bình | 1,65 | 1,06 |
| Số nhóm khác nhau mỗi lịch | 4,31 | 4,39 |
| Lịch có từ 2 điểm cùng nhóm | 32 | 28 |
| Lịch có 2 bãi biển | 3 | 3 |
| Số điểm mỗi lịch | 5,48 | 5,60 |
| Lịch vượt trần nhịp của template | 0 (cứng) | 15, đều vượt 1 điểm |
| POI khác nhau / tỉ trọng top-20 | 103 / 0,733 | 110 / 0,728 |
| Thời gian giải trung vị (giây) | 8,5 | 9,9 |

## Gold 30 (`compare_gold.json`)

| Chỉ số | Legacy | v1 |
|---|---|---|
| Có lịch / qua gate | 29/30 / 29/29 | 29/30 / 29/29 (q21 không có lịch ở cả hai) |
| Bữa trưa đúng khung | 10/10 | 10/10 |
| Phút chạy xe, trung vị | 60 | 44 |
| Chặng dài nhất, trung bình | 41,6 | 28,3 |
| Đổi zone | 1,59 | 1,03 |
| Lịch có từ 2 điểm cùng nhóm | 8 | 7 |
| Thời gian giải trung vị (giây) | 5,3 | 7,1 |

## Hai profile còn lại, 30 request (`compare_profile_*.json`)

| Chỉ số | Savings legacy → v1 | Experience legacy → v1 |
|---|---|---|
| Có lịch / gate / bữa trưa | 30/30 / 30/30 / 14/14 → giữ nguyên | 30/30 / 30/30 / 14/14 → giữ nguyên |
| Phút chạy xe, trung vị | 32 → 28 | 52,5 → 41,5 |
| Đổi zone | 1,53 → 1,20 | 1,30 → 1,00 |
| Lịch có từ 2 điểm cùng nhóm | 8 → 15 | 5 → 4 |
| Số điểm mỗi lịch | 5,7 → 5,8 | 5,53 → 5,43 |
| Thời gian giải trung vị (giây) | 11,3 → 11,7 | 10,0 → 12,0 |

Savings lặp nhiều hơn: 13/15 lịch lặp là nhóm phố–công trình (Cầu Rồng + phố du lịch), loại điểm dừng ngắn, miễn phí, β thấp (0,5). Có một lỗi data đi kèm: Quốc Tự Tam Thai (chùa) đang được xếp vào nhóm phố–công trình.

## Trọng số đã chỉnh trong quá trình đo

| Lần đo | Thấy gì | Chỉnh |
|---|---|---|
| Bản đầu (`compare_heldout_first_weights.json`) | Chợ Hàn + Chợ Cồn cùng ngày ở 17/120; 28/120 lịch vượt trần nhịp | β chợ 1,0 → 2,0; κ → 0,6 / 1,2 / 2,0 |
| Gom luật về một chỗ | cạnh q_ij của legacy đã trừ phút chạy xe (`EDGE_TRAVEL_WEIGHT`), bỏ đi thì phải dồn vào T9 | τ 0,0083 → 0,014 |
| Sau khi gom | hai bảo tàng cùng ngày ở 9/120 | β lịch sử–văn hoá 1,0 → 1,5 |
| Savings | điểm miễn phí đều gần U: 6,1 điểm, 17/30 lịch lặp, chạy xe 32 → 49 | savings: τ 0,045 (mức cạnh cũ của nó), `pace_scale` 2, `repeat_scale` 1,5 |

`compare_heldout_trial.json`: bản thử trước khi gom luật (cạnh vẫn trừ phút chạy xe, τ 0,0083). Vẫn là chỉnh tay; bước sau là học trọng số (`docs/travelagent/OBJECTIVE_V1.md`).

## Bước 1: T11 điểm trùng, bữa tối, nhịp, ngân sách giải (24–25/11, `compare_dedup_*.json`)

Từ 25/11 v1 là mặc định (`DAVEL_OBJECTIVE=legacy` để so). Đo trên `main` sau PR #29–#37 (snapshot 1.029 POI, nhãn món `tags.dishes`), legacy và v1 cùng data.

Phát hiện sau lần đo đầu: v1 phạt chạy xe mạnh hơn nên gom điểm sát nhau và chọn nhiều cặp "một chỗ hai tên" hơn legacy (Hải Vân Quan + Đèo Hải Vân 2 → 9 lịch, Chợ Hàn + Chợ Cồn 0 → 5, mì Quảng hai lần 2 → 6). Đọc từng lịch còn thấy ngày qua buổi tối thiếu bữa tối và CP-SAT dừng ở lời giải kém. Đã sửa:

- **T11** (`objective.duplicate_counts`, `dup_*` trong `v1.json`): 2,0U điểm thứ hai của một `alt_group`; 2,0U điểm "dạo cả khu" + điểm trong khu (`requires_ticket_of`); 1,5U chợ ban ngày thứ hai (food tour 0,1U); 0,5U bữa thứ hai cùng món (nhãn `tags.dishes`, không có thì suy từ tên; "món chay" không tính). Đếm trên cả ngày. Mềm; cứng khi ở `strict_rules`.
- **Greedy hint** bỏ qua điểm trùng (`_hint_dup_kinds`).
- **Bữa tối** 0,8 → 1,2U. **T8 đếm điểm tham quan**: bữa trưa và tối không tính nhịp, quán thứ ba trở đi và bữa sáng có tính (`objective.paced_stops`); một khung bữa chỉ giữ chỗ khi ngày còn ~90 phút để ăn.
- **Ngân sách CP-SAT của v1 × 1,6** (`search_scale`, 5 → 8 đơn vị): ở 5 đơn vị một ngày khách tiết kiệm kém tối ưu 32% (3 quán ăn).
- **Data** (`decisions_zfinal_20261124_dedup.json`): `alt_group` Hải Vân, Phố cổ + Phố đi bộ phố cổ; gộp Bãi tắm Nguyễn Thần Hiến → Bãi biển Non Nước, Bãi Biển Thiên Đường → Bãi Tắm Thanh Khê; Quốc Tự Tam Thai là chùa; Khu ẩm thực Chợ Cồn là chỗ ăn. `migrate_v2` tính lại loại điểm khi quyết định đổi category. `must_visit` trỏ tới bản ghi đã gộp được chuyển sang bản ghi giữ lại (`BE.common.merged_into`, router và eval).
- **Replan** gán nhóm / zone / khoá T11 như lần lập đầu.

| Bộ | Legacy → v1 | Có lịch / gate / bữa trưa | Chạy xe trung vị (phút) | Trùng: món / chợ / cùng chỗ / khu (số lịch) | Lặp nhóm | Thời gian giải trung vị (s) |
|---|---|---|---|---|---|---|
| Held-out 120 | | 120 / 120 / 49 → giữ nguyên | 55,5 → 26 | 5/1/2/1 → 2/0/0/0 | 36 → 37 | 17,7 → 18,1 |
| Gold 30 | | 29 / 29 / 10 → giữ nguyên | 59 → 24 | 0/0/1/1 → 0/0/0/0 | 9 → 10 | 9,8 → 11,7 |
| Savings 30 | | 30 / 30 / 14 → giữ nguyên | 32,5 → 27 | 2/0/1/0 → 0/0/0/0 | 9 → 14 | 18,9 → 19,9 |
| Experience 30 | | 30 / 30 / 14 → giữ nguyên | 53,5 → 41,5 | 3/0/1/14 → 2/0/0/0 | 4 → 4 | 14,9 → 26,5 |

Ngày đi qua buổi tối có ăn tối (legacy → v1): held-out 26/26 → 24/26, savings 8/8 → 6/8, experience 7/8 → 6/8. Các ngày thiếu đều có lý do: 6 khách với ngân sách 500 nghìn, `must_visit` Phố cổ Hội An tới 19:51, ngày kết thúc ở chợ đêm (ăn ở chợ). Hai bữa cách nhau dưới 2,5 giờ: held-out 0 → 3, gold 0 → 1.

`pytest` đầy đủ: ở cả hai chế độ chỉ lỗi 28 test có sẵn trên `main` + 4 test ngoài phạm vi (`test_groq`: máy đặt `GROQ_API_KEY`; 2 `test_migrations`: cần Postgres local; `test_replan_window`: lỗi trên `origin/main`).

Còn mở: experience giải chậm hơn 78% (ngân sách × 1,6; 26/11 hạ về × 1,2 sau khi sửa mô hình và lời giải mồi, xem `latency_p95.md`); savings lặp nhóm 9 → 14 (cầu + phố du lịch, β phố 0,5); vài ngày đặt quán thứ hai lệch giờ khi khách ghi thích món đó (điểm gu cao) — để bước học trọng số; CP-SAT vẫn có thể dừng ở lời giải kém ở ngân sách giới hạn — gợi ý lời giải tốt hơn (pointer, bước 5).

## Chạy lại

```bash
# <data> = thư mục data thầy v2 (teacher_*.jsonl), <ids> = test_ids.json của bộ lọc v2
python reports/objective_v1/scripts/eval_objective.py <repo> <data> <ids> out_legacy.jsonl legacy 2 120
python reports/objective_v1/scripts/eval_objective.py <repo> <data> <ids> out_v1.jsonl v1 2 120
python reports/objective_v1/scripts/eval_objective.py <repo> <data> <ids> out_v1_savings.jsonl v1:savings 2 30
python reports/objective_v1/scripts/analyze_objective.py <repo> out_legacy.jsonl out_v1.jsonl
python reports/objective_v1/scripts/eval_gold.py <repo> gold_v1.jsonl v1 2
# đếm điểm trùng có sẵn trong analyze_objective.py (plans_with_duplicates)
```
