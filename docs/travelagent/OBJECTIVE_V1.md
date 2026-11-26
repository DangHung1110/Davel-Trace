# Hàm mục tiêu v1 — luật gu chuyển vào hàm mục tiêu (cập nhật 25/11/2026)

Hàm mục tiêu v1 có 11 số hạng và là **mặc định** của planner từ 25/11/2026; `DAVEL_OBJECTIVE=legacy` quay về luật cứng cũ để chạy A/B. Ràng buộc cứng chỉ còn hai loại: điều vật lý không cho phép và điều user tự nói. Mọi luật "gu" khác là thưởng hoặc phạt trong J, với trọng số đặt sẵn bằng các câu đánh đổi đọc được.

Bản này đồng bộ với doc "Davel — Hàm mục tiêu v1 (bản chốt)" trên claude.ai. Liên quan: `ARCHITECTURE.md` (toàn luồng), `TRAVELAGENT_CONTEXT.md` §3 và §12, `ARCHITECTURE_BACKLOG.md` A1, A2, A4. Kết quả đo: `reports/objective_v1/README.md`.

**Có cần người chấm không:** không bắt buộc. v1 chạy được ngay; trọng số học sau từ LLM chấm cặp và lịch mẫu đã công bố, cả hai tự động (mục 7). Verify thì vẫn cần nhưng tự động hoàn toàn (mục 8). Người chỉ cần khi muốn khẳng định "lịch khớp ý người": khoảng 30 cặp, chừng 1 giờ.

## 1. Công thức

```
J =  Σ v_i x_i                         T1 giá trị: một hàm điểm POI (value.py)
   + w_state · S                       T2 trạng thái theo giờ (trip_ctx)
   − Σ_g β_g Σ_{k≥2} ρ_k y_gk          T3 lặp nhóm (submodular: điểm đầu miễn phí)
   − γ Σ β_g a_ij [cùng nhóm]          T4 hai điểm cùng nhóm liền nhau
   + Σ_s B_s z_s                       T5 có bữa trong khung sáng / trưa / tối
   − A · (bữa thừa trong 1 khung + cặp bữa cách < 2,5 giờ)   T6
   + R(pace) · r                       T7 nghỉ ngay sau bữa trưa
   − Σ_{k>K0'} κ_k s_k                 T8 điểm vượt mức thoải mái (đếm điểm tham quan)
   − Σ c_ij a_ij                       T9 phút chạy xe + phần vượt 45 phút + đổi zone
   + w_edge · Σ q_ij a_ij              T10 thưởng chuyển tiếp PATM
   − Σ_k σ_k d_k                       T11 điểm trùng: cùng chỗ, khu + điểm trong khu, chợ thứ hai, trùng món
c_ij = τ·m_ij + τ_L·max(0, m_ij − 45) + ζ·[zone_i ≠ zone_j]
```

Ký hiệu: x_i = có đi điểm i; a_ij = đi thẳng từ i sang j; m_ij = phút chạy xe i → j. Mọi trọng số tính theo **U = giá trị v_i cao nhất trong pool** (biến `unit` của optimizer), nên một con số có cùng nghĩa với mọi profile. v_i là một hàm duy nhất cho cả ba profile (mục 5, "T1"). Trọng số ở `BE/app/services/objective_weights/v1.json`; trọng số học được sau này chỉ là một file mới cùng khoá (`DAVEL_OBJECTIVE=<đường dẫn file>`).

## 2. Ba lớp

Mỗi luật thuộc đúng một lớp. Phép thử: nếu có một kiểu khách hợp lý muốn vi phạm luật đó, thì nó là gu chứ không phải vật lý.

| Lớp | Gồm | Vi phạm thì | Ở đâu |
|---|---|---|---|
| 1. Vật lý | giờ mở cửa (VROH), đi kịp theo ma trận (B3), không chồng giờ (TCS), POI đã xác minh (FAR), tối đa 1 suất đặt chỗ | lịch không đi được | ràng buộc CP-SAT + gate cứng |
| 2. User nói | must_visit, avoid, ngân sách (BCS), giờ về (ETB), hoạt động đã nêu, PROFILE_SAFE, cấm của template user chọn, **bữa trưa của ngày đi qua giờ trưa (LUNCH)**, `strict_rules` | sai điều user đã dặn | ràng buộc CP-SAT + gate cứng |
| 3. Gu | đa dạng, bữa ăn, nghỉ trưa, nhịp, chạy xe, đổi vùng, điểm trùng | lịch kém hơn, vẫn đi được | số hạng trong J; gate chỉ báo cáo |

User muốn giữ một luật gu cứng thì ghi vào `trip["strict_rules"]`: `CATEGORY_CAP`, `NO_CONSECUTIVE`, `CAFE_CAP`, `A1`, `NO_ADJACENT_FOOD`, `REST_FOLLOWS_LUNCH`, `SAME_SITE`, `MARKET_REPEAT`, `SAME_DISH`. `DAVEL_TASTE_RULES=hard` giữ cứng tất cả (A/B).

**Sổ luật** `BE/app/services/rules.py` là chỗ duy nhất ghi lớp của mỗi luật và số hạng của J sở hữu nó. Gate (`SOFT_CHECKS`, gương HCS), `soft_rules`, `objective` (`STRICTABLE`), `scorer` đọc từ đây. Lunch giữ cứng qua `check_lunch` **bên trong HCS**, không thêm khoá mới vào `CHECKS`, nên khoá `constraint_status` của API không đổi. T11 cũng không có check gate riêng vì cùng lý do; báo cáo eval tự đếm.

## 3. Luật hiện có xếp vào ô

| Luật | Trước v1 | Lớp | Trong v1 |
|---|---|---|---|
| FAR (POI đã xác minh) | cứng | vật lý | giữ cứng |
| VROH (giờ mở cửa) | cứng | vật lý | giữ cứng |
| B3 (đi kịp theo ma trận) | cứng | vật lý | giữ cứng |
| TCS (không chồng giờ, trong cửa sổ) | cứng | vật lý | giữ cứng |
| Tối đa 1 suất đặt chỗ | cứng | vật lý | giữ cứng |
| ETB (hạn cuối ngày) | cứng | user nói | giữ cứng |
| BCS (ngân sách) | cứng | user nói | giữ cứng |
| HCS: must_visit, avoid | cứng | user nói | giữ cứng; `must_visit` trỏ tới bản ghi đã gộp được chuyển sang bản ghi giữ lại (`BE.common.merged_into`) |
| PROFILE_SAFE (must_avoid, đi lại) | cứng | user nói | giữ cứng; phần dị ứng đã bỏ |
| Hoạt động user nêu (wish) | cứng trong CP-SAT | user nói | giữ cứng |
| LUNCH (bữa trưa khi ngày đi qua giờ trưa) | cứng | user nói | giữ cứng (gate kiểm trong HCS) |
| A1 (1 quán ăn mỗi bữa) | cứng | gu | T6, cứng lại qua `strict_rules` |
| CAFE_CAP (1–2 cafe/ngày) | cứng | gu | T3 nhóm cafe |
| CATEGORY_CAP | mềm, cứng nếu strict | gu | T3 |
| NO_CONSECUTIVE | mềm, cứng nếu strict | gu | T4 |
| NO_ADJACENT_FOOD, B1, B2 | cứng / phạt cạnh | gu | T3, T4, T6 |
| REST_FOLLOWS_LUNCH | cứng | gu | T7 |
| Bắt buộc bữa tối | cứng, ladder nới dần | gu | T5 (thưởng 1,2U) |
| late_end, pace min/max, nhóm bắt buộc của template | cứng | gu | T1 + T8 quyết độ dài ngày |
| A2 (hai bữa cách dưới 2,5 giờ) | phạt cạnh | gu | T6 |
| SAME_SITE, MARKET_REPEAT, SAME_DISH | chưa có | gu | T11 (thêm 24/11) |
| F1, TIME_FIT, DINNER | báo cáo | quality | chỉ báo cáo (T5, T2 + chỉ số) |
| E2 (nightlife trước 17:00) | phạt trong ranker | gu | T2 |
| Không chạy đèo ban đêm | chưa có | vật lý (an toàn) | ngoài v1 (mục 9) |

**Không đếm hai lần.** Legacy có phạt trên cạnh q_ij: A2, B1 và `EDGE_TRAVEL_WEIGHT` (quy về U: khoảng 0,006U mỗi phút với balanced/experience, 0,038U với savings). Ở v1 cạnh chỉ còn điểm PATM; T6, T4, T9 là chỗ duy nhất của ba thứ đó. Legacy **có** trừ phút chạy xe (trên cạnh), chỉ không tính chặng dài hay đổi vùng.

## 4. Các số hạng

| # | Số hạng | Đo gì | Hình dạng | Thay cho |
|---|---|---|---|---|
| T1 | Giá trị | tổng v_i của các điểm được đi; v_i là một hàm (`value.py`) với trọng số theo profile | tuyến tính | ba công thức theo profile + `rank.py` (bước 4, 26/11) |
| T2 | Trạng thái theo giờ | no, mệt, nóng, buồn ngủ, buổi tối tại giờ ghé | hệ số theo khung giờ | TIME_FIT, E2 |
| T3 | Lặp nhóm | điểm thứ 2, 3, 4… cùng một nhóm | phạt tăng dần (submodular) | CATEGORY_CAP, CAFE_CAP |
| T4 | Liền kề cùng nhóm | hai điểm cùng nhóm đi liền nhau | phạt mỗi cung | NO_CONSECUTIVE |
| T5 | Bữa đúng giờ | có quán ăn bắt đầu trong khung bữa | thưởng một lần mỗi bữa | bắt buộc bữa tối, F1, DINNER |
| T6 | Bữa dồn | hai quán trong cùng bữa, hoặc cách nhau dưới 2,5 giờ | phạt mỗi cặp | A1, A2 |
| T7 | Nghỉ trưa | có điểm nghỉ ngay sau bữa trưa | thưởng theo pace | REST_FOLLOWS_LUNCH |
| T8 | Nhịp | điểm tham quan + quán ăn ngoài bữa trưa/tối, vượt mức thoải mái | phạt tăng dần | late_end, pace min/max |
| T9 | Chạy xe và đổi vùng | phút chạy xe, phần vượt 45 phút/chặng, số lần đổi zone; cả chặng từ/về nơi ở khi có `origin_id` | chi phí cố định trên mỗi cung | `EDGE_TRAVEL_WEIGHT` |
| T10 | Chuyển tiếp PATM | thưởng q_ij hiện có | tuyến tính theo cung | giữ để thử tắt (ablation) |
| T11 | Điểm trùng | cùng chỗ, khu + điểm trong khu, chợ ban ngày thứ hai, bữa cùng món | phạt mỗi điểm thừa trong ngày | mới (24/11) |

**Vì sao T3 là submodular:** điểm đầu tiên của một nhóm không bị phạt, mỗi điểm sau bị trừ nặng hơn điểm trước. Với biển (β = 1,5), bãi thứ hai bị trừ 0,53U, bãi thứ ba 1,05U.

**T11 điểm trùng** (bước 1, 24–25/11). Phạt chạy xe mạnh hơn làm solver gom điểm sát nhau, mà điểm sát nhau nhất thường là một chỗ dưới hai tên. T11 đếm trên cả ngày, không theo cặp liền kề, nên chèn một điểm vào giữa không né được (T4 chỉ thấy hai điểm đứng cạnh nhau). Mọi khoá đọc từ data (`objective.stub_keys`):

| Loại | Khoá | Ví dụ |
|---|---|---|
| cùng chỗ (`SAME_SITE`) | `alt_group` | Đèo Hải Vân / Hải Vân Quan (69 m); Ba Na Hills / Sun World Bà Nà Hills; các bến thuyền thúng Bảy Mẫu |
| khu + điểm trong khu (`SAME_SITE`) | `requires_ticket_of` trỏ tới điểm ô, hoặc tới một POI cùng `alt_group` với điểm ô | Phố cổ Hội An hoặc Phố đi bộ phố cổ + Chùa Cầu. Nhiều điểm trong khu mà không có điểm ô thì không phạt (dạo phố ghé 3 hội quán) |
| chợ thứ hai (`MARKET_REPEAT`) | `dwell_kind = market` (chợ ban ngày; chợ đêm và shop không tính) | Chợ Hàn + Chợ Cồn |
| trùng món (`SAME_DISH`) | món chính của quán: nhãn `tags.dishes` (`BE.common.DISHES`, có nguồn), không có thì suy từ tên; "món chay" là chế độ ăn, không tính | hai quán mì Quảng trong ngày |

**Nhóm đa dạng** cho T3, T4 lấy từ `dwell_kind` (31 loại) gộp thành 12 nhóm, thay cho `category` quá thô ("attraction" gộp cả công viên nước lẫn lớp nấu ăn). Một quyết định đổi category trong `decisions_*.json` nay kéo theo loại điểm (`migrate_v2`, 24/11).

## 5. Trọng số v1

| Trọng số | v1 | Câu đánh đổi |
|---|---|---|
| w_state (T2) | 0,5U | giữ giá trị đã chỉnh trong code (`STATE_WEIGHT`) |
| ρ₂ / ρ₃ / ρ₄₊ (T3) | 0,35 / 0,7 / 1,0, nhân β nhóm | điểm cùng nhóm thứ hai phải hơn phương án khác 0,35β U |
| γ (T4) | 0,15, nhân β nhóm | hai chùa liền nhau trừ 0,18U: đủ đảo thứ tự, không đủ bỏ điểm |
| B sáng / trưa / tối (T5) | 0,2 / 1,0 / 1,2U | bữa trưa đáng bằng điểm tốt nhất ngày. Bữa tối chỉnh 25/11 (0,8 → 1,2): ngày qua buổi tối thiếu bữa tối ở 6/26 lịch held-out vì điểm cuối ngày (du thuyền, Cầu Rồng) đáng hơn 0,8U. Bữa sáng chỉ tính khi bắt đầu trước 8:00 |
| A (T6) | 1,0U mỗi cặp; food tour 0,1U | như A2 cũ |
| R (T7) | pace 1 / 2 / 3: 0,5 / 0,25 / 0,1U | người đi chậm sẵn sàng bỏ nửa điểm tốt nhất để được nghỉ trưa |
| κ (T8) | 0,6 / 1,2 / 2,0U cho điểm vượt thứ 1 / 2 / 3+ | chỉnh 24/11: bản 0,3 / 0,6 / 1,0 để 28/120 lịch vượt trần nhịp |
| τ (T9) | 0,014U mỗi phút | chạy thêm khoảng 36 phút để đổi điểm 0,5U lấy điểm 1U; = phần cạnh cũ (0,006) + T9 bản đầu (0,0083) |
| τ_L (T9) | thêm 1/120 U mỗi phút vượt 45 | chặng 75 phút tính như khoảng 93 phút |
| ζ (T9) | 0,08U mỗi lần đổi zone | bằng khoảng 10 phút chạy xe |
| w_edge (T10) | 1,0 | ablation: đặt 0 để xem PATM còn đóng góp gì |
| σ cùng chỗ / khu + điểm trong khu (T11) | 2,0 / 2,0U | điểm thứ hai của một chỗ gần như không bao giờ đáng |
| σ chợ ban ngày thứ hai (T11) | 1,5U; food tour 0,1U | cộng thêm T3 của nhóm chợ |
| σ trùng món (T11) | 0,5U | dưới thưởng bữa tối: không bỏ bữa để né trùng; khách tiết kiệm có thể ăn đắt hơn một mức thay vì một món hai lần (chốt 24/11) |
| Ngân sách CP-SAT (`search_scale`) | × 1,6 (5 → 8 đơn vị) | v1 nhiều số hạng hơn: ở 5 đơn vị một ngày kém tối ưu 32% (3 quán ăn); 8 đơn vị đạt khoảng 93% (chốt 25/11) |

**Ba lịch = ba bộ trọng số.** Khoá `profiles` ghi đè theo profile: experience `repeat_scale` 2,5 (đúng hệ số đa dạng 2,5 của legacy); savings τ 0,045 (mức cạnh cũ của nó), `pace_scale` 2,0, `repeat_scale` 1,5 (điểm miễn phí của savings đều gần U). Phần khác nhau còn lại của profile là các khoá `value` của T1 (dưới đây); ngoài trọng số, tên profile không đổi gì trong J.

**T1: một hàm điểm POI** (bước 4, 26/11; `BE/app/services/value.py`). Trước 26/11 ba profile chấm v_i bằng ba công thức khác nhau (`profiles._score`: savings = chi phí, balanced = rating, experience = độ lạ), còn lời giải thích và repair đọc một bộ chấm thứ hai (`rank.py`). Nay:

```
v_i = Σ_k w_k · φ_k(i)  +  U0 · Σ_m w_m · ψ_m(i)
```

- φ (nơi chốn, giống nhau với mọi khách): `base` (1 mỗi điểm), `fee` (mỗi 100k/người, ×2 khi ngân sách chuyến dưới 1 triệu; chi phí, trừ đi), `price_level` (số bậc trên mức rẻ; chi phí), `rating` (số sao tin cậy), `fame` (log10(1 + số review); bằng 0 trên danang-v2 vì không có số review), `novelty` (0–1, theo pool), `free` (vé 0đ), `free_outdoor` (0đ và thiên nhiên / chợ / công viên / biển).
- ψ (khách trả lời ở onboarding), tính theo U0 = giá trị φ cao nhất của pool: `taste` (−1..1), `spending` (−1 / 0 / 1), `outdoor` (−1..1), `liked` (0 / 1).
- Trọng số: khối `value` của `v1.json` là balanced; savings và experience chỉ ghi đè vài khoá trong `profiles.<tên>.value`. Một file trọng số không có khối `value` (chỉ có hệ số của J) dùng của v1.

| Khoá | balanced (mặc định) | savings | experience |
|---|---|---|---|
| rating / fame | 1,0 / 0,4 | 0,05 / 0,05 | 0,1 / 0,3 |
| novelty | 0 | 0 | 10 |
| base / fee / price_level | 0 / 0 / 0 | 1,0 / 1,0 / 0,15 | 0 / 0 / 0 |
| free / free_outdoor | 0 / 0 | 0,15 / 0,10 | 0 / 0 |
| taste / spending / outdoor / liked | 0,20 / 0,15 / 0,15 / 0,20 | như mặc định | như mặc định |
| `cap_avg_leg` (chỉ bước 6) | 0 | 1/60 mỗi phút | 0 |

Đây là các số cũ trong code: balanced và experience cho ra v_i y hệt trước (test `test_value_function` ghim từng bit). Savings đổi hai chỗ. Một: phút chạy xe trung bình (`avg_leg`) ra khỏi v_i vì T9 đã tính chạy xe, nhưng vẫn xếp hạng ở bước cắt còn 40 (`cap_avg_leg`); bỏ hẳn thì mọi điểm miễn phí gần bằng điểm nhau và top-40 đổi 71%. Hai: gu ăn và lean nhân với U0 = giá trị cao nhất, không phải trị tuyệt đối lớn nhất (quán đắt nhất, −8,7): trước đó một món hợp gu của khách tiết kiệm đáng khoảng 1,6U thay vì 0,2U. Thang điểm giữ như cũ ("sao") vì T10 (q × 100) và `must_go` (+0,5) còn tính tuyệt đối.

Lời giải thích mỗi điểm (`explanation.evidence`, `source: "value"`) là các thành phần đã nâng v_i theo trọng số của profile ("rating cao 4.9", "mien phi", "doc dao, it nguoi biet", "dung gu an: …") cộng bữa mà điểm đó là ("bua trua", "bua toi"). `/v1/repair` chọn điểm cần đổi và điểm thay theo giá trị planner lưu cùng lịch (`_context.values`). Điểm của `rank.py` không còn vào lịch v1; nó chỉ còn quyết thứ tự ứng viên đưa vào solver (thứ tự nút, không đổi J) và là điểm của legacy. Đã thử xếp ứng viên theo v_i (26/11): 63/134 ngày balanced/experience đổi điểm chỉ vì đường tìm kiếm khác, J thấp hơn ở 13 ngày và cao hơn ở 10, bench trung vị chậm thêm 1,5 giây, nên giữ thứ tự cũ.

**12 nhóm đa dạng và hệ số "ngán" β** (số POI trên danang-v2, không tính nơi ở; nhà hàng và bữa sáng không nằm trong T3 vì T5, T6 đã lo):

| Nhóm | dwell_kind | Số POI | β |
|---|---|---|---|
| Biển | beach | 27 | 1,5 |
| Thiên nhiên | nature, eco_park, park | 27 | 1,0 |
| Điểm ngắm | viewpoint | 22 | 0,8 |
| Tâm linh | religious, religious_major | 105 | 1,2 |
| Lịch sử – văn hóa | museum, gallery, historic_site, heritage_site, old_town, village | 38 | 1,5 (chỉnh 24/11: hai bảo tàng cùng ngày ở 9/120 lịch) |
| Phố – công trình | outdoor_urban | 36 | 0,5 |
| Chợ – mua sắm | market, shop, night_market | 54 | 2,0 (chỉnh 24/11: bản 1,0 để Chợ Hàn + Chợ Cồn ở 17/120 lịch) |
| Trải nghiệm có vé | boat_short, cooking_class, evening_show, paid_site | 30 | 1,0 |
| Khu vui chơi lớn | theme_park_big, water_park, indoor_play, island_day_trip | 9 | 3,0 |
| Cafe | cafe | 167 | 0,8 |
| Nightlife | nightlife | 102 | 1,0 |
| Wellness | wellness | 90 | 1,5 |

Số POI đếm ngày 23/11, trước khi nhãn 24/11 chuyển Quốc Tự Tam Thai sang tâm linh và Khu ẩm thực Chợ Cồn thành chỗ ăn.

**Mức thoải mái K₀ cho T8** = `max_stops` của template hoặc của ngày có `meals`; thiếu thì làm tròn(số giờ × 0,55 / 0,65 / 0,8) theo pace 1 / 2 / 3. T8 đếm **điểm tham quan cộng quán ăn ngoài bữa trưa và bữa tối** (`objective.paced_stops`), với ngưỡng K₀ trừ số bữa trưa/tối mà ngày còn đủ thời gian ăn (`objective.sight_k0`, `main_meals`: cần khoảng 90 phút trong khung). Chỉnh 25/11, vì ba lý do: ngày đã đủ K₀ bỏ bữa tối (điểm thứ 9 bị trừ 0,6U, savings 1,2U); miễn hẳn mọi quán ăn thì một ngày nhét 3 quán mì Quảng; ngày kết thúc 18:00 không ăn tối được mà vẫn bị giữ chỗ cho bữa tối.

Các con số trên là điểm khởi đầu có lý do, không phải sự thật. Khi học (mục 7) chỉ học các hệ số tổng (mục 7); hình dạng bên trong (β từng nhóm, ρ_k, K₀) giữ cố định ở v1.

## 6. Mã hóa trong CP-SAT

Mọi số hạng tuyến tính theo biến bool hoặc nguyên; hệ số nào cũng nhân 1000·U rồi làm tròn (`optimizer._objective_v1_terms`).

| Số hạng | Biến và ràng buộc phụ |
|---|---|
| T1, T2 | giữ code hiện có (điểm × visit; probe STATE theo khung giờ) |
| T3 | mỗi nhóm g: bool y₂, y₃ và nguyên e_g, với y₂ + y₃ + e_g ≥ n_g − 1; phạt β_g(ρ₂y₂ + ρ₃y₃ + ρ₄e_g); ρ tăng dần nên solver tự bật biến rẻ nhất trước |
| T4, T9, T10 | hằng số trên mỗi cung, cộng vào hệ số của a_ij; không thêm biến |
| T5 | `_window_hits` cho mỗi quán ăn và mỗi khung bữa → h_is; bool z_s ≤ Σ_i h_is. Khung giờ bắt đầu: trưa 11:00–13:00, tối 17:30–20:30, sáng 6:30–9:00 |
| T6 | nguyên e_s ≥ Σ_i h_is − 1 mỗi khung; cặp cách dưới 150 phút |
| T7 | logic `rest_after_lunch` với `OnlyEnforceIf(rest_taken)`; thưởng R·r |
| T8 | như T3 trên số đếm của `paced_stops` (điểm tham quan + nguyên `pace_meals` ≥ số quán − số bữa trưa/tối) với ngưỡng `sight_k0` |
| T11 | mỗi khoá (alt_group, chợ ban ngày, món): nguyên e ≥ Σ visit − 1; khu + điểm trong khu: bool u_b ≥ visit_a + visit_b − 1. Ở `strict_rules`: Σ visit ≤ 1 |

**Bỏ khỏi ràng buộc cứng** (trừ khi ở `strict_rules`): bắt buộc bữa tối, A1, giới hạn cafe, nghỉ trưa, late_end, pace min/max và nhóm bắt buộc của template.

**Greedy hint** (`_greedy_hint`) bỏ qua điểm trùng của T11 (`_hint_dup_kinds`): ở ngân sách giới hạn CP-SAT hay giữ lời giải gợi ý dù nó bị phạt. **Ngân sách** nhân `search_scale` (`objective.search_budget`) ở mọi đường gọi qua `build_plan` và replan.

**Biến thêm vào:** khoảng 40 biến cho T3, T8, T11, cộng vài chục h_is cho T5; nhỏ so với 1.560 biến cung ở cap 40.

## 7. Học trọng số không cần người chấm

`objective.features(...)` tính từng thành phần J trên một lịch đã xong (16 đặc trưng: value, state, repeat, adjacent, meal, meal_crowd, rest, pace, ride, long_leg, zone, edge, same_site, umbrella, market, dish), có tính chặng về điểm xuất phát; `objective_value` ráp lại J. Đây là đầu vào cho việc học. Chạy cả hai nguồn nhãn dưới đây, rồi chọn bộ thắng trên test tự động (mục 8).

**Cách A: LLM chấm cặp lịch**
1. Sinh cặp: với mỗi request, giải hai lần bằng hai vector w lệch nhau 1–2 hệ số (cộng 459 cặp có sẵn); hai lịch khác nhau đúng ở điểm cần hỏi.
2. LLM chấm mỗi cặp hai lần, đổi thứ tự A/B; bỏ cặp tự mâu thuẫn (ở PATM v4 là 28%). Judge chạy bằng Claude trong phiên (chốt 25/11), không dùng API trả phí.
3. Học hồi quy logistic theo cặp (Bradley–Terry) trên hiệu đặc trưng của hai lịch; cần khoảng 1.000–2.000 cặp.

```
P(A ≻ B) = σ( w · (f(A) − f(B)) )
```

**Cách B: học từ lịch mẫu đã công bố (inverse optimization)**
1. Thu 30–50 lịch 1 ngày ở Đà Nẵng / Hội An đã đăng công khai, giữ link nguồn; không tự viết lịch mẫu.
2. Khớp từng điểm sang `poi_id`; bỏ lịch có điểm không khớp hoặc vi phạm ràng buộc cứng theo data của mình.
3. Dựng request tương ứng (giờ đi, khu vực).
4. Lặp: giải bằng w hiện tại được lịch P; nếu P khác lịch mẫu D thì kéo w về phía D (structured perceptron).

```
w ← w + η ( f(D) − f(P) )
```

Ưu: nhãn là lịch người thật viết. Nhược: lịch blog thường dày và thiên về điểm nổi tiếng, có thể kéo T8 và T1 lệch.

**Hai quy tắc khi học:** giữ đúng dấu (hệ số phạt τ, ζ, A, κ, γ, σ không âm); kéo về v1 bằng λ‖w − w_v1‖² trong loss, để w chỉ lệch khi data đủ mạnh. Học các hệ số tổng (w_state, một hệ số chung cho β·ρ, γ, B, A, R, κ, τ, τ_L, ζ, w_edge, σ); ghi ra file mới cùng khoá với `v1.json`.

**Khi nào học lại:** khi đổi data đủ để lịch đổi (POI mới, giờ mở / giá mới, ma trận mới) thì chạy lại eval; trọng số chỉ cần học lại khi chỉ số tụt hoặc có thêm nhãn (cặp chấm, lịch mẫu). Bộ lọc và pointer bắt chước solver chạy dưới **đúng bộ trọng số đó**, nên đổi trọng số (hoặc đổi data làm lời giải đổi nhiều) là sinh lại data thầy và train lại hai model này (`ARCHITECTURE.md` §4).

**Giới hạn ghi trong báo cáo:** không có người kiểm thì chỉ viết "trọng số học từ LLM và lịch mẫu"; muốn viết "khớp với người" cần thêm khoảng 30 cặp người chấm.

## 8. Kiểm tra tự động

Năm lớp, chạy bằng `pytest` và script eval, không cần người:

1. **Khớp công thức.** Σ w·features(plan) bằng giá trị mục tiêu CP-SAT trả về (sai số làm tròn): bắt lỗi sai dấu, sai thang, quên số hạng (`test_objective_v1`, `test_objective_dedup`).
2. **Gate.** 100% lịch qua lớp 1 và lớp 2.
3. **Test kịch bản**, mỗi cái là một unit test: khu nhiều bãi biển không quá 2 bãi; cửa sổ 8:00–18:00 có quán ăn bắt đầu trong khung trưa; pace 1 ít điểm hơn pace 3; food tour được 3 quán trở lên; `strict_rules: ["CATEGORY_CAP"]` giống luật cứng cũ; hai điểm cùng giá trị thì chọn điểm gần; cùng chỗ / hai chợ / trùng món chỉ giữ một; ngày đủ K₀ vẫn ăn tối.
4. **Đơn điệu.** Gấp đôi một hệ số phạt thì đại lượng bị phạt không tăng.
5. **Ablation.** Tắt từng số hạng (w = 0) xem chỉ số nào đổi; số hạng tắt mà không chỉ số nào đổi thì bỏ (cách quyết giữ T10).

**Chỉ số trước/sau** (held-out 120, gold 30, savings 30, experience 30; `reports/objective_v1/scripts/analyze_objective.py`): tỉ lệ có lịch không thấp hơn; thời gian giải trung vị không tăng quá ~10% (ngoại lệ đã duyệt: ngân sách × 1,6); phút chạy xe, chặng dài nhất, số lần đổi zone giảm; số lịch lặp nhóm và tỉ trọng top-20 POI không tăng; bữa trưa đúng khung từ 95%; các dòng trùng (`plans_with_duplicates`) không cao hơn legacy; đọc 10–20 lịch cụ thể sau mỗi lần đổi J (solver tìm ra mọi chỗ hở của phạt).

## 9. Cố ý để ngoài v1

| Mục | Vì sao chưa làm | Khi nào làm |
|---|---|---|
| Không chạy đèo Hải Vân, Sơn Trà ban đêm | an toàn (lớp 1), nhưng ma trận chưa đánh dấu cung qua đèo | khi gắn cờ đèo cho các cung |
| Chia điểm giữa 2 ngày | số hạng tính theo từng ngày; data mới có chuyến 1 ngày | sau khi có data chuyến 2 ngày |
| Thời tiết | đã nằm trong điểm ranker và T2 | không cần thêm |
| Học hình dạng (β từng nhóm, ρ, K₀) | cần nhiều cặp hơn các hệ số tổng | khi có trên 2.000 cặp |
| Trọng số bên trong T1 (khối `value`) | ở giai đoạn 1, T1 là một đặc trưng (`features()["value"]`); các hệ số bên trong giữ số cũ | giai đoạn 2: tách "value" thành tổng từng φ_k, ψ_m của các điểm được đi (rating, fame, novelty, fee, taste…) để học cùng các hệ số của J |
| w riêng từng user | là bandit, cần log sửa lịch | sau khi app ghi log |
| T3 ở replan tính cả điểm đã đi trong ngày | replan giải phần còn lại | khi làm replan v2 |
| Dị ứng | đã bỏ khỏi phạm vi | không làm |

## 10. Code

| File | Vai trò |
|---|---|
| `BE/app/services/objective.py` | chế độ (`DEFAULT = "v1"`), trọng số, nhóm đa dạng, khoá T11 (`stub_keys`, `dish_of`, `duplicate_counts`), `Spec`, `sight_k0` / `paced_stops`, `search_budget`, `features()` + `objective_value()` |
| `BE/app/services/objective_weights/v1.json` | trọng số v1 và ghi chú vì sao từng số đổi; khối `value` (T1) và `profiles.<tên>.value` |
| `BE/app/services/value.py` | T1: một hàm điểm POI cho cả ba profile (`score`, `place_features`, `lean_parts`, `novelty_scores`, `price_reference`); lý do cho lời giải thích (`explain`) |
| `BE/app/services/optimizer.py` | `StubPOI` (group, zone, site, inside, substitute, dish); `_objective_v1_terms` (T3–T11); A1 và nghỉ trưa mềm khi không strict; hint bỏ điểm trùng |
| `BE/app/services/profiles.py` | dựng `Spec`; `_v1_limits` bỏ luật gu của template; v_i từ `value.score`; cap 40 (savings trừ thêm `cap_avg_leg`); ngân sách × `search_scale`; giữ thứ tự của solver (chỉ chỉnh giờ); lời giải thích đọc v_i |
| `BE/app/services/repair.py` | ở v1, chọn điểm cần đổi và điểm thay theo `_context.values` của lịch |
| `BE/app/services/replan.py` | cùng hàm mục tiêu, cùng khoá của stub, cùng ngân sách cho phần còn lại của ngày |
| `BE/app/services/rules.py` | sổ luật duy nhất |
| `soft_rules.py`, `gate.py`, `scorer.py` | đọc tập luật từ `rules.py`; `check_lunch` trong HCS; `edge_scores(rule_penalties=False)` ở v1 |
| `BE/common.py` | `merged_into` (bản ghi đã gộp); `DISHES`, `dish_ids` (nhãn món của data) |
| `BE/ml/data/migrate_v2.py`, `BE/data/sources/decisions_*.json` | quyết định data: `alt_group`, gộp bản ghi, đổi category kéo theo loại điểm |
| `BE/tests/unit/test_objective_v1.py`, `test_objective_dedup.py`, `test_rules_registry.py`, `test_soft_taste_rules.py` | khớp công thức, kịch bản, đơn điệu, gate, sổ luật |
| `BE/tests/unit/test_value_function.py` | T1: cùng một hàm cho ba profile, balanced/experience y hệt số cũ, savings bỏ `avg_leg`, đơn vị gu ăn, cap savings, giải thích và repair đọc cùng v_i, legacy không đổi |
| `reports/objective_v1/` | script eval và kết quả đo (`README.md`, `compare_*.json`) |

## Nguồn

- Sáu nhóm ràng buộc để đối chiếu độ phủ: ChinaTravel (Shao và cộng sự).
- Số liệu luật, hệ số và POI: repo Davel-Trace (`gate.py`, `optimizer.py`, `soft_rules.py`, snapshot danang-v2) và data thử nghiệm v2 ngày 23/11/2026; kết quả đo 24–25/11 ở `reports/objective_v1/`.
