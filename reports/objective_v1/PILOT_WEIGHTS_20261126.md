# Pilot objective weights — bàn giao review 26/11/2026

> Báo cáo lịch sử **trước sửa A2**. Sau báo cáo này, người dùng đã duyệt sửa OR/AND và chạy lại pilot vào thư mục `pilot_20261126_a2fix/`. Giữ nguyên số liệu dưới đây để đối chiếu; không dùng cặp/nhãn cũ cho phiên bản A2 mới.

## Trạng thái thật

Người dùng duyệt T1–T3 trong `tasks/plan.md` và `tasks/todo.md`.
T1/T2 đã triển khai. T3 đã sinh, audit và render đủ 40 request; chấm Claude
và train trên nhãn thật **chưa thực hiện được** vì Claude hết hạn mức tuần.
Không commit/push, không đổi nhánh hoặc objective mặc định. Không sửa optimizer.

Branch `feat/objective-weights-learning`, nền HEAD `b79d296`.
Data: `C:/Users/ADMIN/Documents/code/davel_distill_data/objective_learning/pilot_20261126/`.

## Đã thay đổi

- Đồng bộ ARCHITECTURE.md, OBJECTIVE_V1.md và thêm OBJECTIVE_LEARNING_PROTOCOL.md:
  BT chính; lịch công bố chỉ kiểm độc lập; perceptron dự phòng; rubric, split,
  chỉ số và hai lượt chấm độc lập được định nghĩa trước khi train.
- `profiles.py` giữ raw activities/status/objective riêng trong private context.
- `objective.plan_features(plan)` chấm lịch cuối theo end-start, state và nghỉ
  thực tế; `raw=True` đối chiếu lời giải gốc. Mưa là `fixed_cost` không học.
- Generator truyền dynamic context offline, không fetch forecast; audit cả cặp
  bị loại, gate và raw J; lưu hash code/data/config/request IDs.
- Renderer xuất pass1/pass2 riêng, đảo phía, xáo thứ tự, key có hash nội dung;
  từ chối ghi đè sheet/key. Judge chỉ được nhận một pass/session, tools và MCP tắt.
- Runner chỉ chấp nhận auth `claude.ai`, không dùng paid API key. Trainer giữ
  fixed rain offset, kiểm key hash, báo tie/contradiction/incomplete riêng.

## Kết quả pilot thật

| Chỉ số | Kết quả |
|---|---|
| Request | 40, loại toàn bộ 259 held-out IDs |
| Hai lần solve/request | 80 lời giải cuối, tất cả qua gate |
| Solver status | 23 optimal, 57 feasible-timeout |
| Cặp giữ lại | 17/40 (42,5%) |
| Cặp cùng chuỗi điểm | 23/40 |
| Gate fail / formula mismatch | 0 / 0 |
| Sai số raw J lớn nhất | 0,0009453U (ngưỡng khai báo 0,03U) |
| Lịch đổi J sau polish trên 0,03U | 29/80 |
| Độ lệch J sau polish lớn nhất | 0,806U |
| Thời gian/request trung vị | 59,086 giây, 2 process / 1 worker CP-SAT mỗi solve |

Không suy từ gate xanh rằng lịch sát thực tế hoặc learned đã tốt hơn v1.
Raw/final khác J là kết quả thực đo; không gán objective raw cho lịch hiển thị.

Chênh lệch feature trong 17 cặp có tín hiệu cho w_state (13 cặp), repeat_scale
(6), gamma (2), meal_scale (2), rest_scale (3), tau (15), tau_long (3), zeta (9),
w_edge (17). Không có tín hiệu cặp cho meal_crowd, pace_scale và 4 dup_*:
giữ prior cho các hệ số này, hoặc thu thêm request. Có tín hiệu không đồng nghĩa
độc lập định danh được hệ số; phải đo lại coverage sau khi lọc nhãn nhất quán.

Đã đọc 20 lịch của 10 cặp đầu: 000011, 000013, 000014, 000020, 000021,
000022, 000024, 000029, 000031, 000033 (prefix gv2-).
Có cặp chỉ đổi chợ/thứ tự gần tương đương nên tie là hợp lý. Có cặp đổi rõ
nghỉ trưa, giờ ăn, zone và số điểm. Cặp 000029 đáng kiểm thêm nguồn/ma trận
và ticket dependency của Cầu Vàng; gate chỉ kiểm dữ liệu hiện có, không tự
xác minh thực địa. Một số wish không được đáp ứng ở cả hai lịch, cần xem
activity_match/ladder trước khi quy kết hoàn toàn cho trọng số.

## Hai vấn đề Claude cần review trước khi mở rộng

1. **A2 OR/AND, chưa sửa solver:** optimizer dùng OR giữa hai kiểm tra khoảng
   cách hướng, nên mọi cặp restaurant bị phạt, không chỉ cặp dưới 150 phút.
   Pilot giữ hành vi theo phạm vi user đã duyệt; feature khớp đúng hành vi đó.
   Có regression test ghi rõ đây là bug hiện hành. Nếu sửa OR thành AND, phải
   chạy lại pilot/eval và tạo manifest/dataset phiên bản mới.
2. **459 cặp cũ không phải 459 cặp train:** 259 dòng eval_learned40.jsonl đều
   thuộc held-out, chỉ để eval. 200 dòng compare_v1_vs_v2.jsonl có ID gv1-*
   không giao chuỗi ID với gv2 held-out nhưng còn cần kiểm trùng request thực,
   join đủ trip/profile và tính lại features. Không tự cộng vào train.

## Claude bị chặn và cách tiếp tục

`labels.jsonl.pass1.response.json` lưu lỗi thật:
`429 rate_limit_error / usage_limit_reached`; thông báo reset 27/11 lúc 19:00
Asia/Ho_Chi_Minh. Không có labels.jsonl, không có trọng số học từ pilot thật.
Không thay Claude bằng nhãn từ J hoặc từ assistant khác.

Sau khi có quota, dùng **tên labels mới** để giữ nguyên raw response lỗi:

```powershell
$ObjectivePilot = 'C:/Users/ADMIN/Documents/code/davel_distill_data/objective_learning/pilot_20261126'
python BE/ml/objective/judge_pairs.py "$ObjectivePilot/sheet.md" "$ObjectivePilot/labels_retry.jsonl"
python BE/ml/objective/train_bt.py "$ObjectivePilot/pairs.jsonl" "$ObjectivePilot/labels_retry.jsonl" "$ObjectivePilot/weights_PILOT_ONLY.json" --lambda 1.0 --holdout 0.25 --key "$ObjectivePilot/sheet.md.key.json"
```

Hoặc đưa riêng sheet.pass1.md và sheet.pass2.md cho hai phiên Claude độc lập,
không đưa key, features hoặc kết quả lượt trước. Lưu nhãn theo đúng schema.
Không cần sinh lại 40 request nếu không thay công thức/config/data.

CLI train hiện hỗ trợ train/holdout cho phép kiểm pilot. Split ba tập,
chọn lambda trên validation, bootstrap và final evaluation chính thức thuộc T5,
chưa được tuyên bố đã triển khai hay đã đạt trong T1–T3.

## Kiểm chứng plumbing tách riêng

`synthetic_cli_check/` chứa 500 cặp từ known weights, 1.000 nhãn **synthetic,
không phải Claude**, 375 train / 125 holdout. Đi hết render -> decode key ->
CLI train -> export: accuracy v1 0,760, learned 0,968 (>0,9); bounds và
profile overrides đúng. File weights ghi rõ SYNTHETIC ONLY / NOT FOR PRODUCTION.
Đây không phải bằng chứng cải thiện trên 17 cặp pilot thật.

## Tests và artifacts

- `python -m pytest BE/tests/unit -q -k objective -p no:cacheprovider`: **56 passed** (gồm 15 test learning).
- Contract itinerary/replan/select + unit multiday: 36 passed.
- Chỉ focused tests, không phải full suite hay full held-out eval mới.
- Python 3.10.11, OR-Tools 9.15.6755, SciPy 1.15.3, Claude CLI 2.1.332;
  auth claude.ai; GOOGLE_POLICY=cach_ly; taste mode soft.
- Data: pairs.jsonl, pairs.jsonl.audit.jsonl, pairs.jsonl.manifest.json,
  coverage.json, sheet.pass1.md, sheet.pass2.md, sheet.md.key.json, weights/.
- sheet.md là bản audit gộp, không đưa cả hai lượt này vào cùng phiên judge.
- Manifest ghi code tại lúc sinh data; guard chống ghi đè renderer và kiểm
  subscription auth runner được thêm sau đó, không thay giá trị các cặp đã sinh.

Chưa mở khóa data thầy chính thức/filter/pointer. Cần nhãn thật và quyết định
về A2 trước khi đi tiếp tới học/chốt trọng số.
