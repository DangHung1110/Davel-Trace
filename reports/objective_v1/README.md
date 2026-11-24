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

## Chạy lại

```bash
# <data> = thư mục data thầy v2 (teacher_*.jsonl), <ids> = test_ids.json của bộ lọc v2
python reports/objective_v1/scripts/eval_objective.py <repo> <data> <ids> out_legacy.jsonl legacy 2 120
python reports/objective_v1/scripts/eval_objective.py <repo> <data> <ids> out_v1.jsonl v1 2 120
python reports/objective_v1/scripts/eval_objective.py <repo> <data> <ids> out_v1_savings.jsonl v1:savings 2 30
python reports/objective_v1/scripts/analyze_objective.py <repo> out_legacy.jsonl out_v1.jsonl
python reports/objective_v1/scripts/eval_gold.py <repo> gold_v1.jsonl v1 2
```
