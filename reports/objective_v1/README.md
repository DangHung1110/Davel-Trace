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

Còn mở: experience giải chậm hơn 78% (ngân sách × 1,6); savings lặp nhóm 9 → 14 (cầu + phố du lịch, β phố 0,5); vài ngày đặt quán thứ hai lệch giờ khi khách ghi thích món đó (điểm gu cao) — để bước học trọng số; CP-SAT vẫn có thể dừng ở lời giải kém ở ngân sách giới hạn — gợi ý lời giải tốt hơn (pointer, bước 5).

## Bước 4: một hàm điểm POI cho T1 (26/11, `compare_value_*.json`)

T1 nay là một hàm (`BE/app/services/value.py`) cho cả ba profile; ba profile chỉ khác ở khối `value` của `v1.json` (`OBJECTIVE_V1.md` §5 "T1"). Trọng số là các số cũ trong code, nên balanced và experience cho ra v_i y hệt. Savings đổi ba chỗ: `avg_leg` ra khỏi v_i (T9 đã tính chạy xe; `avg_leg` chỉ còn xếp hạng ở bước cắt 40), gu ăn / lean nhân với giá trị cao nhất thay vì trị tuyệt đối lớn nhất (quán đắt nhất), và bỏ `price_level` (bản sao của `fee` trên danang-v2, mục dưới). Đo từ `git archive` của `main` 707f084 và của nhánh `feat/single-poi-value` (df161c9; bench đo ở f4923c3, trước khi bỏ `price_level`), cùng máy 12 nhân; bench chạy xen kẽ, 2 lượt mỗi bên. Trong `compare_value_gold_*.json` (viết bởi `analyze_objective.py`) khoá `legacy` là `main`, `v1` là nhánh; `compare_value_audit.json` ghi `before` / `after`.

| Bộ đo | Chỉ số | Trước | Sau |
|---|---|---|---|
| Audit 67 request × 3 lịch | lịch rỗng / trượt gate / đi được | 0 / 0 / 201 | 0 / 0 / 201 |
| | lịch y hệt: savings / balanced / experience | — | 3 / 67 / 67 (savings: 39 chỉ dời giờ hoặc đổi thứ tự, 25 đổi điểm) |
| | Jaccard 3 lịch một request: trung bình / lớn nhất / cặp > 0,6 / router phải thay | 0,085 / 0,455 / 0 / 0 | 0,085 / 0,455 / 0 / 0 |
| | savings: chạy xe mỗi ngày / chi phí mỗi lịch / lịch thiếu bữa tối | 19,6 phút / 394k / 11 | 20,9 phút / 407k / 8 |
| Gold 30 | có lịch / qua gate (cả 3 profile) | 29 / 29 | 29 / 29 |
| | lịch y hệt: savings / balanced / experience | — | 5 / 30 / 30 (savings: 14 đổi điểm) |
| | savings: chạy xe trung vị / POI khác nhau / tỉ trọng top-20 | 16 phút / 52 / 0,796 | 18 phút / 58 / 0,756 |
| | tổng thời gian giải: savings / balanced / experience | 136 / 106 / 146 s | 139 / 101 / 143 s |
| Bench (`bench_latency.py`, 21 request, ở f4923c3) | trung vị / p95 | 4,15 và 4,14 / 9,29 và 8,93 s | 4,13 và 4,12 / 8,16 và 8,30 s |

Ví dụ (audit T12, cặp đôi 08:00–20:00, ngân sách 600 nghìn): savings trước có 6 điểm, xong lúc 16:40, không ăn tối; sau có 7 điểm, ăn tối Mỳ Quảng Cô Sáu 50k/người lúc 18:23, tổng 200k. Ngân sách dưới 1 triệu tính tiền gấp đôi, nên với `avg_leg` bị trừ thêm, quán 50k có giá trị âm và bữa tối không đáng đi. Lịch savings thiếu bữa tối: 11 → 8.

Savings giải chậm hơn chút: ở audit có J, 2/60 ngày thêm chạy hết ngân sách tìm kiếm (giá trị các điểm miễn phí phẳng hơn khi bỏ `avg_leg`); tổng thời gian giải gold +2%; bench không chậm đi: trung vị bằng, p95 giảm 0,6–1,1 giây (có thể vì gu ăn nay tính một lần mỗi POI thay vì mỗi lần xếp hạng; chưa đo riêng). Lời giải thích của từng điểm nay nói đúng lý do solver chọn, ví dụ "re (50k/nguoi), bua trua" thay cho "gio an, trong nha, do nang" của `rank.py`.

**Đã thử và bỏ: xếp ứng viên theo v_i.** Nếu `build_plan` sắp ứng viên theo v_i thay vì giữ thứ tự router đưa vào, mô hình CP-SAT không đổi, chỉ đổi thứ tự nút. Đo trên cùng 60 request 1 ngày có ghi J (`scripts/audit_capture.py`):

| | Giữ thứ tự cũ (bản commit) | Xếp theo v_i |
|---|---|---|
| Lịch balanced / experience khác `main` (audit 67) | 0 / 0 | 26 / 40 (24 / 39 đổi điểm) |
| J so với `main`: balanced cao hơn / thấp hơn | bằng | 3 / 10 (trung bình −0,14%) |
| J so với `main`: experience cao hơn / thấp hơn | bằng | 7 / 3 (Bà Nà +291%, M07 −24%) |
| Ngày experience chạy hết ngân sách | 20 | 23 |
| Tổng thời gian audit / bench trung vị | 355 s / 4,1 s | 378 s / 5,6 s |

Thứ tự nút chỉ đổi đường tìm kiếm của CP-SAT (ở 60 request này, 49/180 lần giải của `main` dừng vì hết ngân sách), nên được và mất may rủi, kèm chậm hơn. Giữ thứ tự cũ; `rank.py` vì vậy vẫn quyết thứ tự nút (không vào J). Ca Bà Nà +291% cho thấy CP-SAT đôi khi kẹt ở lời giải kém với thứ tự cũ: việc của gợi ý lời giải (pointer, bước 7), không của T1.

`pytest` đầy đủ: 1528 qua; 19 lỗi + 11 error đều có sẵn do môi trường (Google OAuth, `DATABASE_URL`/Postgres, 2 test ranh giới Flutter).

### Ba câu hỏi về trọng số T1, chốt theo số đo (26/11)

60 request 1 ngày của audit, mỗi request chỉ chạy một profile (`scripts/audit_profile.py`), có ghi J. Bỏ `cap_avg_leg` không đổi hàm mục tiêu và U bằng nhau ở cả 60 ngày, nên J so thẳng được; các thử khác đổi hàm mục tiêu nên so bằng lịch.

| Thử | Kết quả | Chốt |
|---|---|---|
| Savings bỏ `cap_avg_leg` (bước cắt 40) | 60/60 ngày đổi điểm; J thấp hơn ở 53/60 (trung bình −13,6%); hết ngân sách tìm kiếm 12 → 24; chạy xe 20,6 → 25 phút/ngày; ngày có bữa tối 54 → 44 | giữ |
| Savings bỏ `price_level` | 42 y hệt, 10 chỉ dời giờ, 8 đổi điểm; chi phí −1%; chạy xe +0,8 phút/ngày | bỏ (df161c9; code thật trùng 60/60 lịch với phép thử): trên danang-v2 mức giá suy ra một-một từ hạng giá, đúng nguồn của `fee` |
| Savings bỏ `free_outdoor` | 40/60 đổi điểm; điểm biển / thiên nhiên / chợ 60 → 38 | giữ: đó là gu "thiên nhiên/chợ" của savings, không phải chi phí |
| Savings và experience dùng khối `value` của balanced | experience ra đúng bộ điểm của balanced ở 36/60 (Jaccard với balanced 0,03 → 0,85, 52/60 vượt trần 0,6); savings 402 nghìn → 1,05 triệu một lịch | không học một T1 chung; trọng số T1 riêng học từ cặp chấm có nói rõ khách (`OBJECTIVE_V1.md` §7) |

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

Bước 4 (mỗi lệnh chạy trong một bản `git archive`, `<before>` và `<after>`):

```bash
python BE/tools/audit_plans.py --out audit.json --flags audit_flags.json
python reports/objective_v1/scripts/compare_audit.py <before>/audit.json <before>/audit_flags.json <after>/audit.json <after>/audit_flags.json compare_value_audit.json
python reports/objective_v1/scripts/eval_gold.py <repo> gold_savings.jsonl v1:savings 2
python reports/objective_v1/scripts/audit_capture.py <repo> --only T,W,M,D,E --out cap.json --flags cap_flags.json
python BE/tools/bench_latency.py --snapshot BE/data/snapshots/danang-v2 --rounds 3
# một profile với một biến thể trọng số (bản sao v1.json đã sửa), J ghi trên từng lịch
python reports/objective_v1/scripts/audit_profile.py <repo> savings v1_variant.json savings_variant.json
```
