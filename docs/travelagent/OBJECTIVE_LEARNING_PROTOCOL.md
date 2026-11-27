# Giao thức học trọng số — pilot 26/11/2026

Phạm vi đã duyệt: T1–T3 trong `tasks/todo.md`. BT là phương pháp học chính;
giữ value = 1, hệ số không âm và regularization tương đối về v1. Không train LLM.
Chưa bật trọng số học được làm mặc định. Không thêm dependency hoặc đổi API/DB.

## 1. Dữ liệu và tái lập

- Sinh từ request `gv2-*`, loại toàn bộ `models/filter_v2/test_ids.json`.
- Pilot: 40 request đầu theo ID, balanced, cap 40, 1 worker CP-SAT mỗi solve,
  deterministic_time đầu vào 5 (v1 nhân search_scale), seed 42.
- Context theo profile, không gọi thời tiết online: `trip_ctx.build(...,
  fetch_weather=False)`. Ghi rõ đây là prior, không phải dự báo hay quan sát thật.
- Mỗi request có base và perturb 1–2 hệ số bằng 0,4 hoặc 2,5; giữ cặp khác
  chuỗi poi_id. Lưu audit cả request không sinh được cặp, gate và sai số raw J.
- Manifest ghi hash code, weights, snapshot/ma trận, teacher files, held-out IDs,
  seed, cấu hình và request IDs. Các lượt chạy không ghi đè artifact cũ.
- Feature cho judge/train lấy từ lịch hiển thị sau polish, dùng end-start thật,
  tính lại nghỉ trưa theo clock. Raw activities/objective giữ riêng để kiểm solver.
- Sau tích hợp main `7cb6d73`: 19 feature từ `_features.raw/shown`, schema
  `objective-shown-v4-a2-pairs`, dataset schema 4. `rain` thay `fixed_cost` cũ;
  BT giữ `w_rain` ở v1 trong offset. `meal_far` chỉ đếm, không phạt; `wait` chỉ đo,
  giữ `w_wait=0` vì solver chưa tối ưu số hạng này. Vẫn học đúng 15 hệ số đã duyệt.
- Trainer kiểm manifest hoàn tất, hash cặp, code/data/weights và provenance mỗi
  cặp trước khi fit. Pilot schema 2/3 và dữ liệu human/gold khác schema bị từ chối;
  sinh lại theo baseline hiện tại, không điền feature thiếu bằng 0.
- Trip context xuất đầy đủ, kể cả `avoid`, strict rules, giờ và thông tin xuất phát;
  judge thấy đúng yêu cầu đã dùng sinh lịch.

## 2. Split trước khi học

Pilot chỉ dùng phát triển pipeline; mọi pilot request ID bị loại khỏi final test
của đợt học chính. Không dùng pilot accuracy để tuyên bố model cải thiện.

Đợt chính: nhóm mọi cặp của cùng request vào một tập. Seed 42, lấy
`int(sha256("objective-bt-42:" + request_id).hexdigest(), 16) % 10000`:
0–5999 train, 6000–7999 validation, 8000–9999 test. Pilot IDs thuộc train/dev,
không thuộc test. Manifest phải đóng băng split trước khi chấm/train; nếu tập
test quá nhỏ thì bổ sung request, không chuyển ID sau khi xem nhãn.

Chỉ chọn lambda trên validation. Final test không dùng chọn lambda, rubric,
feature, hoặc quyết định sửa model sau khi đã mở kết quả. Mọi bước tinh chỉnh
sau đó cần bộ test mới chưa sử dụng.

Kiểm tra dữ liệu cũ ngày 26/11: toàn bộ 259 dòng `eval_learned40.jsonl` thuộc
259 held-out IDs, nên chỉ dùng đánh giá, không được cộng vào train. File
`compare_v1_vs_v2.jsonl` có 200 dòng không giao ID với tập này, nhưng vẫn phải
kiểm trùng nội dung request, phiên bản và tính lại feature trước khi tái dùng.
Con số 459 cặp trong tài liệu cũ không đồng nghĩa có 459 cặp train hợp lệ.

## 3. Rubric chấm

Judge chỉ thấy trip context, hai lịch với giờ, phí, di chuyển, nghỉ và totals.
Không thấy base/perturbed, weights, features, J, key hoặc nhãn lượt trước.

Ưu tiên theo thứ tự:
1. Đáp ứng điều user nói rõ: giờ, ngân sách theo số người, must_visit và hoạt động.
2. Lịch có thể đi: giờ/di chuyển hợp lý, bữa ăn và nghỉ phù hợp độ dài chuyến.
3. Trải nghiệm phù hợp profile: nhịp vừa sức, đa dạng có ý nghĩa, tránh điểm
   trùng và hai bữa cùng món; không mặc định nhiều điểm hơn là tốt hơn.
4. Giảm chạy xe/lòng vòng khi chất lượng trải nghiệm tương đương.

Không suy diễn chất lượng từ tên lạ hoặc bịa điều kiện ngoài dữ liệu. Nếu không
có khác biệt đủ rõ, hoặc thiếu thông tin quyết định, chọn tie. Trả JSON
`{"pair": k, "pass": 1|2, "winner": "left"|"right"|"tie", "reason": "..."}`.
Reason ngắn, chỉ dựa vào nội dung lịch, không phỏng đoán cách sinh lịch.

## 4. Hai lượt độc lập

Renderer xuất riêng `*.pass1.md` và `*.pass2.md`; hai lượt đảo left/right cho
từng cặp và xáo thứ tự trình bày có seed. File tổng hợp chỉ để audit, không đưa
cùng hai lượt cho judge trong một session. Key `*.md.key.json` lưu riêng.

Claude chạy hai session mới, chỉ nhận một pass mỗi session, không có công cụ
đọc file khác. Lưu raw response, model/session provenance và nhãn đã parse.
Không dùng nhãn do code tự suy từ J hoặc do assistant khác giả làm Claude.

Chỉ giữ hai lượt đầy đủ cùng chọn một lịch gốc. Bỏ tie, mâu thuẫn; báo riêng
nhãn thiếu, tie, contradiction và consistency rate. Không tự sửa winner.

## 5. Tiêu chí đánh giá đã định trước

- Pilot: feature/gate/split đúng; thấy độ biến thiên trên feature và chênh lệch
  feature trong cặp. Hệ số không đủ tín hiệu phải giữ v1 hoặc thu thêm request.
- Đợt chính: accuracy và logistic loss learned so với v1 trên final test;
  bootstrap theo request để báo CI 95% của chênh lệch accuracy. Đề xuất chọn
  learned khi cận dưới chênh lệch > 0; nếu chưa rõ thì giữ v1, không tuyên bố thắng.
- Chạy lại held-out 120, gold 30, savings/experience 30: tỷ lệ có lịch, gate,
  bữa trưa không giảm; điểm trùng không tăng; thời gian cùng cấu hình mục tiêu
  không tăng quá 10%. Báo mọi trade-off và đọc 10–20 lịch cụ thể.
- 30–50 lịch công bố có URL làm kiểm tra độc lập: trùng POI (precision/recall,
  Jaccard), chênh số điểm/nhịp và phân bố zone. Không đưa vào loss/chọn lambda.
  Mức giống lịch công bố là proxy, không phải bằng chứng user hài lòng.
- Perceptron chỉ xét khi BT đạt nhưng còn lệch rõ; lịch dùng tinh chỉnh phải
  tách khỏi tập kiểm tra cuối còn nguyên vẹn.

## 6. Đầu ra pilot

`pairs.jsonl`, audit/manifest, phiếu hai pass và hidden key, labels thật nếu
Claude chạy được, feature coverage, pilot training output và báo cáo giới hạn.
Nếu không có Claude hoặc hết hạn mức, để nhãn ở trạng thái chưa chấm; không
bịa nhãn để hoàn thành checklist. Bàn giao đường dẫn cho Claude kiểm tiếp.

## 7. A2: giữ main sau A/B ngày 27/11/2026

Quyết định mới thay thế thử nghiệm <150 phút: giữ A2 đúng main `7cb6d73`.
R quán trong ngày chịu R(R−1)/2 cặp, encoding staircase; greedy trừ một cặp
cho mỗi quán trước đó. Booking session không thuộc tập restaurant của solver;
phần A1 dư quán/lớp trong cùng slot vẫn cộng riêng khi không hard.
`meal_crowd` gồm toàn bộ cặp A2 + A1 slot extra; `meal_far` chỉ là diagnostic
subset, không trừ thêm lần nữa. Không đổi trọng số.

A/B 40 held-out + gold 30 cho thấy <150 tăng quán ăn, né ngưỡng bằng bữa 14:00,
tăng trùng món/site và thời gian giải quá giới hạn 10%. Bảng số liệu và nguồn:
`reports/objective_v1/A2_AB_20261127.md`. Thử nghiệm <150 bị bác bỏ.

Dataset mới dùng schema 4, `objective-shown-v4-a2-pairs`,
`a2_rule=all_restaurant_pairs`. Pilots schema 2/3, gồm `pilot_20261127_main_v3`,
chỉ giữ lịch sử và bị trainer/analyzer từ chối; không tái dùng nhãn hoặc điền
feature cũ. Smoke mới: `smoke_20261127_a2main/`.
