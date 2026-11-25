# Hàm mục tiêu v1 — luật gu chuyển vào hàm mục tiêu (24/11/2026)

Bản này thay các luật cứng kiểu "gu" bằng số hạng trong hàm mục tiêu của CP-SAT. Ràng buộc cứng chỉ còn những gì vật lý không cho phép và những gì user tự nói. Mặc định từ 25/11/2026 (sau bước 1, người dùng duyệt); `DAVEL_OBJECTIVE=legacy` quay về luật cứng cũ để chạy A/B.

Liên quan: `TRAVELAGENT_CONTEXT.md` §3 (hàm mục tiêu đã chốt: Σ prize · ū − w·Σc_ij − phạt), `ARCHITECTURE_BACKLOG.md` A1, A2, A4.

## 1. Ba lớp

| Lớp | Gồm | Ở đâu |
|---|---|---|
| Vật lý | giờ mở cửa (VROH), đi kịp theo ma trận (B3), không chồng giờ (TCS), POI đã xác minh (FAR), tối đa 1 suất đặt chỗ | ràng buộc CP-SAT + gate cứng |
| User nói | must_visit, avoid, ngân sách (BCS), giờ về (ETB), hoạt động đã nêu, profile_safe, cấm/giới hạn của template user chọn, **bữa trưa của ngày đi qua giờ trưa (LUNCH)**, `strict_rules` | ràng buộc CP-SAT + gate cứng |
| Gu | đa dạng, bữa ăn, nghỉ trưa, nhịp, chạy xe, đổi vùng | số hạng trong J; gate chỉ báo cáo |

User muốn giữ một luật gu cứng thì ghi nó vào `trip["strict_rules"]`: `CATEGORY_CAP`, `NO_CONSECUTIVE`, `CAFE_CAP`, `A1`, `NO_ADJACENT_FOOD`, `REST_FOLLOWS_LUNCH`. `DAVEL_TASTE_RULES=hard` giữ cứng tất cả (để chạy A/B).

## 2. Công thức

```
J =  Σ v_i x_i                         T1 giá trị: điểm ranker (như cũ)
   + w_state · S                       T2 trạng thái theo giờ (trip_ctx, như cũ)
   − Σ_g β_g Σ_{k≥2} ρ_k y_gk          T3 lặp nhóm (submodular: điểm đầu miễn phí)
   − γ Σ β_g a_ij [cùng nhóm]          T4 hai điểm cùng nhóm liền nhau
   + Σ_s B_s z_s                       T5 có bữa trong khung sáng / trưa / tối
   − A · (bữa thừa trong 1 khung + cặp bữa cách < 2,5 giờ)   T6
   + R(pace) · r                       T7 nghỉ ngay sau bữa trưa
   − Σ_{k>K0} κ_k s_k                  T8 số điểm vượt mức thoải mái
   − Σ c_ij a_ij                       T9 phút chạy xe + phần vượt 45 phút + đổi zone
   + w_edge · Σ q_ij a_ij              T10 thưởng chuyển tiếp PATM
   − Σ_k σ_k d_k                       T11 điểm trùng: cùng chỗ, khu + điểm trong khu, chợ thứ hai, trùng món
c_ij = τ·m_ij + τ_L·max(0, m_ij − 45) + ζ·[zone_i ≠ zone_j]
```

Mọi trọng số tính theo **U = điểm ranker cao nhất trong pool** (biến `unit` có sẵn trong optimizer). Trọng số nằm ở `BE/app/services/objective_weights/v1.json`; trọng số học được sau này chỉ là một file mới cùng khoá (`DAVEL_OBJECTIVE=<đường dẫn file>`).

| Trọng số | v1 | Câu đánh đổi |
|---|---|---|
| ρ₂ / ρ₃ / ρ₄₊ × β nhóm | 0,35 / 0,7 / 1,0 | bãi biển thứ hai (β = 1,5) phải hơn phương án khác 0,53U |
| γ × β nhóm | 0,15 | hai chùa liền nhau trừ 0,18U |
| B sáng / trưa / tối | 0,2 / 1,0 / 1,2U | bữa trưa đáng bằng điểm tốt nhất ngày; bữa tối chỉnh 24/11 (0,8 → 1,2): ngày đi qua buổi tối thiếu bữa tối ở 6/26 lịch held-out vì điểm cuối ngày (du thuyền, Cầu Rồng) đáng hơn 0,8U |
| A (T6) | 1,0U; food tour 0,1U | như A2 cũ |
| R theo pace 1 / 2 / 3 | 0,5 / 0,25 / 0,1U | |
| κ cho điểm vượt thứ 1 / 2 / 3+ | 0,6 / 1,2 / 2,0U | chỉnh 24/11: bản 0,3 / 0,6 / 1,0 để 28/120 lịch vượt trần nhịp của template |
| τ | 0,014U mỗi phút | chạy thêm khoảng 36 phút để đổi điểm 0,5U lấy điểm 1U |
| τ_L | thêm 1/120 U mỗi phút vượt 45 | chặng 75 phút tính như khoảng 93 phút |
| ζ | 0,08U mỗi lần đổi zone | ≈ 10 phút chạy xe |
| w_state, w_edge | 0,5; 1,0 | giữ như cũ |
| σ cùng chỗ / khu + điểm trong khu | 2,0 / 2,0U | điểm thứ hai của một chỗ gần như không bao giờ đáng |
| ngân sách CP-SAT (`search_scale`) | × 1,6 (5 → 8 đơn vị) | v1 nhiều số hạng hơn: ở 5 đơn vị một ngày kém tối ưu 32%; 8 đơn vị đạt ~93% (chốt 25/11) |
| σ chợ ban ngày thứ hai | 1,5U; food tour 0,1U | cộng thêm T3 của nhóm chợ |
| σ trùng món | 0,5U | dưới thưởng bữa tối (1,2U): không bỏ bữa để né trùng; khách tiết kiệm có thể ăn đắt hơn một mức thay vì ăn một món hai lần (chốt 24/11) |

**12 nhóm đa dạng** (T3, T4) gộp từ 31 `dwell_kind`: biển, thiên nhiên, điểm ngắm, tâm linh, lịch sử–văn hoá, phố–công trình, chợ–mua sắm, trải nghiệm có vé, khu vui chơi lớn, cafe, nightlife, wellness. Nhà hàng không thuộc nhóm nào (T5, T6 lo).

β theo nhóm: biển 1,5; thiên nhiên 1,0; điểm ngắm 0,8; tâm linh 1,2; lịch sử–văn hoá 1,5 (chỉnh 24/11: hai bảo tàng cùng ngày ở 9/120 lịch); phố–công trình 0,5; chợ–mua sắm 2,0 (chỉnh 24/11: bản 1,0 để Chợ Hàn + Chợ Cồn cùng ngày ở 17/120 lịch); trải nghiệm 1,0; khu vui chơi lớn 3,0; cafe 0,8; nightlife 1,0; wellness 1,5.

**T11 điểm trùng** (thêm 24/11, bước 1). Phạt chạy xe mạnh hơn làm solver gom điểm sát nhau, mà điểm sát nhau nhất thường là một chỗ dưới hai tên. T11 đếm trên cả ngày, không theo cặp liền kề, nên chèn một điểm vào giữa không né được (T4 chỉ thấy hai điểm đứng cạnh nhau). Mọi khoá đọc từ data (`objective.stub_keys`):

| Loại | Khoá | Ví dụ |
|---|---|---|
| cùng chỗ (`SAME_SITE`) | `alt_group` | Đèo Hải Vân / Hải Vân Quan (69 m); Ba Na Hills / Sun World Bà Nà Hills; các bến thuyền thúng Bảy Mẫu |
| khu + điểm trong khu (`SAME_SITE`) | `requires_ticket_of` trỏ tới điểm ô, hoặc tới một POI cùng `alt_group` với điểm ô | Phố cổ Hội An hoặc Phố đi bộ phố cổ + Chùa Cầu. Nhiều điểm trong khu mà không có điểm ô thì không phạt (dạo phố ghé 3 hội quán) |
| chợ thứ hai (`MARKET_REPEAT`) | `dwell_kind = market` (chợ ban ngày; chợ đêm và shop không tính) | Chợ Hàn + Chợ Cồn |
| trùng món (`SAME_DISH`) | món suy từ tên quán (`objective.DISHES`) | hai quán mì Quảng trong ngày |

Ghi trong `strict_rules` thì thành ràng buộc cứng. Greedy hint của CP-SAT cũng bỏ qua điểm trùng (`_hint_dup_kinds`): với ngân sách 5 đơn vị, solver hay giữ lời giải gợi ý dù nó bị phạt. Nhãn `alt_group` mới nằm ở `BE/data/sources/decisions_zfinal_20261124_dedup.json` (chạy lại `migrate_v2` để vào snapshot).

**K0 (T8)** = `max_stops` của template hoặc của ngày có `meals` (đếm mọi điểm); thiếu thì giờ trong ngày × 0,55 / 0,65 / 0,8 theo pace. T8 chỉ đếm **điểm tham quan**, không đếm bữa ăn: ngưỡng là K0 trừ số khung bữa ngày đi qua (`objective.sight_k0`). Chỉnh 25/11: trước đó ngày đã đủ K0 bỏ bữa tối, vì điểm thứ 9 (quán ăn) bị trừ 0,6U (savings 1,2U), gần hết thưởng bữa tối.

## 3. Mỗi luật một chỗ, ba bộ trọng số

- **Sổ luật** `BE/app/services/rules.py`: mỗi luật có một lớp (physical, user, taste, quality, edge, mirror) và số hạng của J sở hữu nó. Gate (`SOFT_CHECKS`, gương HCS), `soft_rules` (tập luật gu), `objective` (`STRICTABLE`) đọc từ đây; không module nào giữ danh sách riêng.
- **Không đếm hai lần.** Legacy đã có phạt trên cạnh q_ij: A2 (hai quán liền nhau), B1 (hai điểm cùng loại liền nhau) và `EDGE_TRAVEL_WEIGHT` (quy về U: khoảng 0,006U mỗi phút với balanced và experience, 0,038U với savings). Ở v1, cạnh chỉ còn điểm PATM; T6, T4, T9 là chỗ duy nhất của ba thứ đó. τ = 0,014 = phần cạnh cũ (0,006) + T9 bản đầu (0,0083); savings giữ τ riêng 0,045.
- **Ba lịch = ba bộ trọng số.** Khoá `profiles` trong file trọng số ghi đè theo profile: experience `repeat_scale` 2,5 (đúng hệ số đa dạng 2,5 của legacy); savings τ 0,045, `pace_scale` 2,0, `repeat_scale` 1,5 (điểm miễn phí của savings đều gần U, bỏ trần nhịp cứng thì lịch nhồi thêm điểm). Phần khác nhau còn lại của profile nằm ở điểm từng POI (T1).

## 4. Thay đổi trong code (nhánh `feat/planner-objective-v1`)

| File | Thay đổi |
|---|---|
| `BE/app/services/objective.py` | mới: chế độ, trọng số, nhóm đa dạng, `Spec`, `features()` + `objective_value()` (tính J trên lịch đã xong, dùng để kiểm và để học trọng số) |
| `BE/app/services/objective_weights/v1.json` | mới: trọng số v1 |
| `optimizer.py` | `StubPOI.group`, `StubPOI.zone`; tham số `objective=`; `_objective_v1_terms` (T3–T9); A1 và nghỉ trưa thành mềm khi không strict; trả thêm `unit`, `rest_taken` |
| `profiles.py` | dựng `Spec`; `_v1_limits` bỏ pace band, nhóm bắt buộc của template, late_end, bữa tối khỏi ràng buộc; cap mặc định 40 ở v1 |
| `replan.py` | cùng hàm mục tiêu cho phần còn lại của ngày |
| `rules.py` | mới: sổ luật duy nhất |
| `soft_rules.py`, `gate.py` | đọc tập luật từ `rules.py`; `taste_rules()` mở rộng ở v1; gương HCS bỏ luật gu đang mềm; `check_lunch` giữ bữa trưa cứng trong HCS (khoá `constraint_status` của API không đổi) |
| `scorer.py` | `edge_scores(rule_penalties=False)` cho v1 |
| `BE/tests/unit/test_objective_v1.py`, `test_objective_dedup.py` (T11), `test_rules_registry.py` | khớp công thức, kịch bản, đơn điệu, gate; sổ luật và cạnh không đếm trùng |

## 5. Chưa làm ở v1

- Học trọng số (LLM chấm cặp, lịch mẫu, cặp người chấm) — xem doc kiến trúc.
- T9 ở replan chưa tính các điểm đã đi trong ngày khi đếm lặp nhóm.
- Đèo ban đêm, tối ưu chung nhiều ngày.
- Thời gian giải tăng 15–35% so với legacy (balanced 8,5 → 9,9 giây trung vị). Hướng giảm: pointer hint, gộp biến T5 với biến bữa trưa có sẵn.
- Trùng món mới suy từ tên quán; về lâu dài cần nhãn món chính khi thu data.

## 6. Kết quả đo

`reports/objective_v1/README.md`. Balanced, 120 request giữ riêng, cùng cap 40: có lịch, gate, bữa trưa giữ nguyên (120/120, 120/120, 49/49); phút chạy xe trung vị 57 → 35,5; đổi zone 1,65 → 1,06; lịch lặp nhóm 32 → 28; thời gian giải 8,5 → 9,9 giây. Gold 30: 29/30 cả hai bản, chạy xe trung vị 60 → 44. Savings và experience (30 request mỗi profile) giữ nguyên có lịch, gate, bữa trưa và chạy xe ít hơn; savings lặp nhóm nhiều hơn (8 → 15, chủ yếu cầu + phố du lịch).
