> Cập nhật 27/11: giữ A2 main sau A/B; phần <150/schema 3 bên dưới là lịch sử bị bác bỏ. Trạng thái mới: `reports/objective_v1/A2_AB_20261127.md`, schema 4.

# Tích hợp main và pipeline BT — 27/11/2026

Nhánh `feat/objective-weights-learning` đã fast-forward từ `b79d296` tới main
`7cb6d73` (#52), không tạo commit hoặc push. Đã giữ WIP và file untracked;
bản sao 20 file trước tích hợp nằm ở
`C:/Users/ADMIN/AppData/Local/Temp/davel_main_integrate_fi4ssrra/backup/`.
Không sửa file `reports/p0/review_v21_20261119 (1).json`.

## Thay đổi

- Dùng T1, ma trận, giá và `search_scale=1.2` của main mới. Mặc định vẫn là v1,
  chưa có trọng số learned được bật.
- Solver và greedy hint giữ A2 đã duyệt: chỉ phạt cặp quán cách nhau dưới 150
  phút. Đúng 150 phút không phạt cặp; phần dư quán cùng meal slot vẫn tính riêng.
- Giữ 19 feature của main. `meal_far` chỉ đếm, không trừ J; `wait` chỉ đo với
  `w_wait=0`. BT vẫn học 15 hệ số, value=1; rain giữ hệ số v1 trong offset.
- `shown_acts` giữ `end`; state/rain, rest, idle và giao slot của lớp đặt trước
  dùng thời lượng hiển thị thực tế. Guard polish dùng cùng extractor này.
- `_features.raw/shown` là snapshot chung với độ chính xác đầy đủ;
  `plan_features` chỉ đọc bản sao feature. Thay đổi chỉ `end` cũng tính retimed.
- Dataset schema 3, `objective-shown-v3-near-a2`; pair gắn provenance của manifest.
  Generator xuất toàn bộ trip, gồm avoid. Trainer kiểm code/data/weights và hash
  cặp/key; analyzer kiểm thêm hash và ID/count của audit. Pilot schema 2 bị từ chối.
- Dataset human/gold từ main giữ riêng để đánh giá, không nhập vào BT train.

Code chính: `BE/app/services/{objective,optimizer,profiles}.py`,
`BE/ml/objective/{gen_pairs,train_bt,analyze_pairs}.py`. Tests được cập nhật theo
ngưỡng A2, thời lượng thực tế, snapshot và provenance. Tài liệu đã đồng bộ trong
`docs/travelagent/{OBJECTIVE_V1,OBJECTIVE_LEARNING_PROTOCOL,ARCHITECTURE}.md`
và `tasks/{plan,todo}.md`.

## Kiểm tra

Môi trường chạy: Python 3.10.11, OR-Tools 9.15.6755; không thêm dependency.

- `python -m pytest BE/tests/unit -q -k objective -p no:cacheprovider`:
  **80 passed + 20 subtests**, 1 warning deprecation có sẵn.
- Nhóm value/seed/return-leg/polish/rules/state/multiday và contract
  itinerary/replan/select, integration plan-features: **111 passed**.
- Sau siết provenance và thêm kiểm guard với thời lượng kéo dài: nhóm
  objective-learning/polish/seed **26 passed**.
- Boundary/encoding/optimizer và feature: **63 passed + 36 subtests** ở bước
  tích hợp đầu. Các số trên là các lượt kiểm riêng, không cộng thành tổng duy nhất.
- CLI xác nhận pilot schema 2 bị từ chối trước khi đọc nhãn/train.
- Cặp chung giữa smoke 1 process và pilot 2 process có trip, perturb, lịch và
  feature giống nhau (chỉ provenance dataset khác theo cấu hình chạy).
- Review hai trục đã kiểm lại: không còn blocker trong phạm vi tích hợp;
  hai lỗi provenance được phát hiện đã sửa và có regression tests.

## Artifact

Data root: `C:/Users/ADMIN/Documents/code/davel_distill_data/objective_learning/`.

Smoke: `smoke_20261127_main_v3/`: 4 request, 8/8 lịch qua gate, giữ 1 cặp;
max raw formula error **0.00080106 U**; không giảm J sau polish.
Đã có `coverage.json`, `sheet.pass1.md`, `sheet.pass2.md`, `sheet.md.key.json`.

Pilot: `pilot_20261127_main_v3/` đã hoàn tất 40 request, 2 process,
1 solver worker mỗi solve, seed 42, deterministic_time đầu vào 5 (×1,2 = 6).

| Chỉ số | Kết quả |
|---|---:|
| Cặp giữ lại / request | 17/40 (42,5%) |
| Cùng chuỗi POI nên loại | 23 |
| Lịch có nghiệm / gate qua | 80/80 |
| Formula mismatch / giảm J sau polish | 0/0 |
| Max raw formula error | 0,00111642 U |
| Raw → shown J thay đổi | 0/80 |
| Thời gian trung vị mỗi request (hai solve) | 47,625 s |
| Request giao held-out | 0 |
| Request nguồn có avoid / cặp giữ có avoid | 32/40 và 13/17 |
| Request nguồn có origin | 0/40 |

Đã kiểm lại code/data/weights theo manifest, ID/count/hash audit, trip context
so với nguồn, must/avoid, tổng phí/chặng chạy và cửa sổ nghỉ. Tái dựng chênh J
từ vector BT trên cả 17 cặp sai số tối đa `1,22e-15`. Đã xác minh hai pass độc
lập, đủ 17 mục/pass, đảo bên đúng và key khớp hash từng cặp, không lộ feature/J.

Artifact: `pairs.jsonl`, `pairs.jsonl.audit.jsonl`, `pairs.jsonl.manifest.json`,
`coverage.json`, `verification.json`, `sheet.pass1.md`, `sheet.pass2.md`,
`sheet.md.key.json`, phiếu tổng hợp `sheet.md` chỉ để audit và `weights/` chứa
các bản perturb, không phải trọng số learned. Chưa có nhãn hoặc trọng số learned mới.

Độ phủ chênh feature theo hệ số: w_state 11, repeat_scale 5, gamma 2,
meal_scale 1, meal_crowd 3, rest_scale 2, pace_scale 3, tau 15, tau_long 6,
zeta 8, w_edge 15 cặp; cả bốn dup_* đều 0 nên giữ prior. Các tín hiệu 1–3 cặp
còn yếu, và số cặp khác 0 không chứng minh khả năng định danh độc lập. Đo lại
sau khi loại tie/mâu thuẫn. Không so trực tiếp với pilot A2 cũ vì T1/data/config đổi.

Đã đọc 10 lịch (A/B của `gv2-000004`, `000005`, `000007`, `000011`, `000014`).
Cặp có khác biệt về số bữa, bữa cách dưới 150 phút, nghỉ, chạy sang Hội An và
nhãn món lặp. Có trường hợp chỉ đổi quán cùng món; có thể nhận tie, không tự
gán winner. Đây là kiểm nội dung, không phải nhãn preference hoặc bằng chứng
gu đã tốt hơn. Request không có origin là open tour: chặng đầu bằng 0, không
được suy diễn là đã tính chạy từ trung tâm/thực tế GPS.

## Giới hạn và việc tiếp theo

Chưa chấm lại bằng Claude, chưa train trọng số thật hoặc chứng minh learned
thắng v1. Không dùng nhãn synthetic thay thế. Hai pilot 26/11 giữ nguyên để audit;
không so trực tiếp J hoặc quy thay đổi lịch thành cải thiện gu khi T1/data đã đổi.
Thời gian pilot là hai solve/request với wall guard 60 s mỗi solve và có cạnh
tranh CPU; không phải benchmark p95 production. Kết quả latency cũ của main dùng
encoding A2 khác, nên cần đo lại ở bước đánh giá end-to-end.

Trainer hiện phục vụ pilot train/holdout. Chọn lambda bằng validation,
train/validation/final-test chính thức, bootstrap và kiểm 30–50 lịch công bố vẫn
là T4–T7; cần làm trước quyết định đóng băng trọng số để sinh data filter/pointer.
Hệ số thiếu tín hiệu phải giữ prior hoặc thu request phù hợp.

Lệnh tiếp tục khi chạy nhãn thật (không được gọi trong đợt tích hợp này):

```powershell
$MainPilot = 'C:/Users/ADMIN/Documents/code/davel_distill_data/objective_learning/pilot_20261127_main_v3'
python BE/ml/objective/judge_pairs.py "$MainPilot/sheet.md" "$MainPilot/labels.jsonl"
python BE/ml/objective/train_bt.py "$MainPilot/pairs.jsonl" "$MainPilot/labels.jsonl" "$MainPilot/learned_pilot.json" --key "$MainPilot/sheet.md.key.json"
```

Đây là train/holdout để kiểm luồng pilot; không dùng kết quả này để tuyên bố
trọng số chính thức thắng v1. Trước lần train sau, phải giữ đúng phiên bản code
đã đóng hash hoặc sinh dataset mới nếu code/data/weights đã thay đổi.
