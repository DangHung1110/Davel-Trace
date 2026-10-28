# Research Brief: Dynamic Replan — Intent Preservation & Deviation

Nguồn nội bộ: `specs/001-travel-agent-mvp/quickstart.md` (S5), `tasks.md` (T044–T046), `contracts/api.md`, `data-model.md`, `spec.md` (FR-027–034, FR-047, SC-010–017), `docs/research_brief_eval.md`. TripTide dùng ba trục đánh giá: Preservation of Intent, Responsiveness và Adaptability (semantic/spatial/sequential); brief này mượn khung metric, không tuyên bố tái lập nguyên benchmark TripTide.[1]

## 1. Phạm vi và trạng thái bằng chứng

Mục tiêu là đánh giá replanning theo rolling horizon: giữ nguyên phần đã thực hiện và các ý định còn hiệu lực, chỉ tối ưu phần chưa hoàn thành sau event, phát state delta/version công khai, rồi chạy lại feasibility gate trước khi trả phương án. Giới hạn sản phẩm: Đà Nẵng, 1–2 ngày; deadline trong ngày là `min(end_time, return_time)` theo `docs/research_brief_eval.md` và `tasks.md` T061.

`quickstart.md` S5 quy định fixture tối thiểu: hai activity đã `done`, gửi event “trời mưa”, giữ nguyên hai activity done, thay phần outdoor còn lại và tăng version. API dự kiến trả `{itinerary: v+1, mode: plan|clarify|no_solution, changes: [...]}`; data model có trạng thái Activity `planned|done|cancelled|replaced` và DynamicEvent gồm `type`, `at`, `source`, `affected`, `delta`, `severity`, `resolution`.

Giới hạn checkout cần lưu ý: các đường dẫn được yêu cầu đọc `BE/app/services/replan.py` và `BE/app/services/state.py` không tồn tại trong checkout hiện tại; `BE/app/services/` chỉ có `snapshot.py`. Vì vậy brief này dựa trên contract/spec/task và không khẳng định implementation của state/replan đã được xác minh. `tasks.md` đánh dấu T046 DONE ở lane-B nhưng T045 và T048 vẫn mở trong manifest này; cần tích hợp/kiểm chứng lại trên nhánh tích hợp.

## 2. Trigger và phân loại disruption

### Weather trigger

- Dùng `WeatherSnapshot.hourly[].rain_prob` tại giờ trùng activity. Replan-trigger nếu xác suất mưa **> 70%** (strictly greater) và còn ít nhất một activity chưa hoàn thành, nhạy thời tiết/ngoài trời trong khoảng bị ảnh hưởng. 70% chính xác không kích hoạt rule này.
- Không thay activity `done`. Với activity outdoor còn lại, tìm phương án indoor hoặc thay thế cùng intent; nếu không có phương án khả thi thì hỏi lại hoặc trả `no_solution`, không âm thầm bỏ hard constraint.
- Ghi event `type=rain`, nguồn forecast, `affected[]`, mức/severity và reason có thể truy vết. Spec T041 có fixture mưa 80% buổi chiều → đổi activity outdoor và nêu lý do; dùng fixture đó làm kiểm tra ngưỡng.
- Mưa do người dùng báo vẫn được đưa qua event path dù không có dự báo >70%; forecast threshold là trigger tự động, không phải bộ lọc từ chối lời người dùng.

### Event classifier: tám nhãn vận hành

Đề xuất taxonomy 8 nhãn cho phạm vi dynamic replan:

1. `rain` — thời tiết ảnh hưởng hoạt động ngoài trời.
2. `delay` — trễ lịch/di chuyển; gộp tín hiệu traffic/tắc đường vào nhãn này.
3. `drop_poi` — người dùng bỏ một điểm/hoạt động.
4. `add_req` — thêm yêu cầu hoặc điểm đến.
5. `tired` — giảm cường độ/thêm nghỉ.
6. `closure` — POI đóng cửa/không thể tiếp nhận.
7. `time_change` — đổi giờ bắt đầu/kết thúc hoặc khung giờ.
8. `budget` — ngân sách còn lại thay đổi/vượt giới hạn.

Đây là taxonomy đề xuất để đáp ứng mục tiêu “~8 types” của T044. Có sai khác hiện trạng phải xử lý trước khi đóng contract: `BE/ml/event_clf/templates.py` và `artifacts/labels.json` hiện có 10 label (`rain`, `delay`, `drop_poi`, `add_req`, `tired`, `closure`, `time_change`, `traffic`, `budget`, `lost`). Brief đề xuất gộp `traffic` vào `delay`; `lost` nên đi vào nhánh hỏi vị trí/clarify, không tạo class replan thứ chín. Không đổi classifier/artifact ở task tài liệu này.

Classifier trả `label`, `confidence`, `slots/affected`, `source`; event không rõ hoặc thiếu slot thiết yếu vào `clarify`, không tự suy diễn. Không đặt ngưỡng confidence số mới khi T044 chưa chốt calibration; đo macro-F1 và per-class recall trên paraphrase/test độc lập, và kiểm tra confusion `delay`/`traffic`, `drop_poi`/`tired`, `rain`/`closure`.

## 3. Rolling-horizon state và preservation contract

Mỗi lần xử lý event lấy snapshot `state_before` tại thời điểm hiện tại, tách timeline thành: completed prefix (bất biến), phần đã hủy/thay thế (không tái sinh), và future remainder (được phép tối ưu). Solver chỉ lập lại future remainder từ vị trí/giờ hiện tại; constraints, ngân sách còn lại và hard deadline vẫn áp dụng. Dùng version đầu vào để chống ghi đè state cũ; event retry/idempotency không được thêm activity trùng.

Contract đề xuất cho response `/v1/replan` (bổ sung rõ vào API contract khi implementation wiring):

- `itinerary.version = previous_version + 1` cho mỗi event/state revision được chấp nhận; trả cả `previous_version`, `version`, `version_delta=1` để caller/UI kiểm tra.
- `state_delta` là phần công khai, có cấu trúc và lưu cùng revision: `event_id`, `event_type`, `at`, `source`, `affected[]`, `kept[]`, `removed[]`, `replaced[]`, `added[]`, `rescheduled[]`, `reason[]`, `mode`. Mỗi activity change tham chiếu `poi_id`/activity id, status cũ-mới và reason.
- `done` là bất biến: ID, POI và thứ tự/timestamp thực tế đã ghi không bị sửa, xóa, thay hay nhân đôi. Must-visit còn khả thi phải giữ; nếu event khiến không thể đáp ứng thì ghi rõ xung đột và chọn `clarify|no_solution`, không tự hạ thành soft preference.
- Mỗi thay đổi phải có reason; activity bị ảnh hưởng bởi sự cố được giữ nguyên nếu vẫn khả thi, nếu không thì đánh dấu `replaced/cancelled` và lưu liên kết thay thế. Không lặp POI ngoài trường hợp user yêu cầu rõ.
- `mode=plan`: trả itinerary mới đã qua gate. `mode=clarify`: trả câu hỏi/thiếu slot và delta chưa đủ điều kiện commit như plan. `mode=no_solution`: trả violations/reason và không phát plan khả thi giả.
- Version policy cho Clarify/NoSolution cần chốt khi wiring: khuyến nghị chỉ tăng version khi event/state delta được persist; response phải phân biệt rõ `state_version` và `itinerary_version` nếu ghi event mà không thay plan. S5 `plan` bắt buộc version itinerary tăng đúng 1.

## 4. Đánh giá TripTide-style: intent, response, deviation

TripTide phân biệt preservation, responsiveness và adaptability; paper mô tả intent qua delivery/constraint pass/final pass, responsiveness qua tỷ lệ event được mitigate, và adaptability qua độ lệch semantic, spatial, sequential (độ lệch thấp hơn là ổn định hơn).[1] Các số dưới đây là operationalization phù hợp với dữ liệu Davel-Trace, không phải ngưỡng hoặc công thức nguyên bản của TripTide.

### 4.1 Preservation of Intent (cao hơn tốt)

Tách hard gate khỏi soft-intent để điểm trung bình không che vi phạm:

- `DonePreservation = done_ids_after ∩ done_ids_before / |done_ids_before|`; yêu cầu 100% (nếu mẫu rỗng, ghi N/A).
- `MustIntentRetention = satisfied eligible must_visit / eligible must_visit`; yêu cầu 100%. “Eligible” loại chỉ yêu cầu đã bị user rút lại hoặc bị event làm bất khả thi; mọi ngoại lệ phải có lý do, không âm thầm xóa khỏi mẫu số.
- `SoftIntentRetention = weighted soft intents satisfied after / weighted soft intents still applicable`; intent lấy từ theme/activities/food/order/pace đã lưu trong TripRequest. Đề xuất ngưỡng ≥0.80 trên feasible cases; báo numerator, denominator, và từng loại intent.
- `IntentRetention` báo riêng ba thành phần trên, không gộp completed/hard/soft thành một con số duy nhất. Đề xuất acceptance: Done=100%, Must=100% khi khả thi, Soft ≥0.80.

### 4.2 Responsiveness (cao hơn tốt)

`EventResolutionRate = disruptions resolved by a valid committed plan / feasible triggered disruptions`. Với rain fixture, resolution nghĩa là không còn activity outdoor bị ảnh hưởng trong remainder (trừ khi user chấp thuận), có hoạt động thay thế/khung giờ khác hợp lý và có reason. Báo riêng `Plan`, `Clarify`, `NoSolution`, infeasible; Clarify/NoSolution đúng với case mơ hồ/vô nghiệm không tính là lỗi classifier nhưng không tính là mitigation thành công. Acceptance fixture S5: plan response đúng 100%; toàn bộ tập disruption: mục tiêu đề xuất ≥0.80, cùng ngưỡng recovery SC-010.

### 4.3 Adaptability / deviation (thấp hơn tốt)

Tính trên future remainder; completed prefix được loại khỏi drift nhưng vẫn kiểm tra bằng DonePreservation. Báo từng thành phần, không chỉ một aggregate:

- `D_sem`: 1 − trung bình Jaccard giữa tag/type của activity bị thay và activity thay thế được ghép theo intent. Đây là proxy deterministic cho semantic drift; nếu không ghép được replacement, drift = 1. Đề xuất mean ≤0.30 trên các slot bị thay.
- `D_spatial`: `abs(km_new_remaining − km_old_remaining) / max(km_old_remaining, 1 km)`. Giữ lại số km tuyệt đối và cờ tăng/giảm; ngưỡng đề xuất ≤0.30 trên feasible events. Đây là chỉ báo độ lệch quy mô tuyến, không thay thế routing feasibility.
- `D_seq`: normalized Levenshtein distance của chuỗi POI còn lại: `edit_distance(old_remaining_ids, new_remaining_ids) / max(len(old_remaining_ids), len(new_remaining_ids), 1)`. Đề xuất mean ≤0.30 cho fixture step-level; day/plan-level disruptions báo riêng, không dùng cùng cutoff.
- `D_total`: macro-average `D_sem`, `D_spatial`, `D_seq`, chỉ tính khi cả ba thành phần có dữ liệu; chỉ số tổng hợp để theo dõi, không dùng để che một trục fail. Đề xuất ≤0.30 cho S5 rain fixture.

Các cutoff 0.80/0.30 là mục tiêu vận hành đề xuất cho bộ test nhỏ, không phải kết quả đã đo; chốt trước khi xem final test và hiệu chỉnh bằng adjudication thủ công. Với disruption buộc đổi toàn bộ kế hoạch, phân tầng theo severity (step/day/plan) và traveler tolerance (plan-bound/flexible); không phạt thay đổi bắt buộc như thể đó là thay đổi tùy ý.

## 5. Re-gate sau từng replan

Chạy canonical feasibility gate sau **mỗi** candidate replan, trước khi trả `mode=plan` hoặc tính soft/quality metrics. Dùng đủ registry 7 check; fail-closed nếu thiếu key, score không finite hoặc sai type. Gate fail thì không trả plan như feasible và không phát soft quality score.

| Check | Điều kiện pass theo `docs/research_brief_eval.md` |
|---|---|
| FAR | `score <= 1e-12` |
| VROH | `score <= 1e-12` |
| B3 | `score <= 1e-12`; semantics phải lấy từ canonical gate, không tự alias |
| BCS | `score >= 1 - 1e-12` |
| ETB | `score >= 1 - 1e-12`; deadline `min(end_time, return_time)` |
| TCS | `score >= 1 - 1e-12` |
| HCS | `score >= 1 - 1e-12` |

Trả `checks[name]={passed: bool, score: float}`, `all_pass` và violations theo tên. Kiểm lại sau khi map state delta vào itinerary cuối, không chỉ trên solver candidate. Với `clarify/no_solution`, không đánh dấu candidate là pass; nếu vẫn trả itinerary hiện hữu thì phải gắn rõ version/trạng thái và không gọi nó là itinerary mới đã qua gate.

## 6. Mapping acceptance: S5, T044, T045, T046

| Hạng mục | Acceptance test |
|---|---|
| S5 quickstart | Hai activity `done` giữ nguyên; event rain; phần outdoor tương lai được thay; response `mode=plan`; `version_delta=1`; không duplicate. |
| T044 classifier | 8 nhãn theo taxonomy đề xuất; template/paraphrase Việt; đánh giá macro-F1, per-class P/R/F1 và nhầm lẫn; phải giải quyết chênh lệch 8 nhãn đề xuất so với 10 labels/artifact hiện có. |
| T045 state/delta | Persist state revision; preservation contract; public version + structured state_delta; retry không nhân đôi; stale `previous_version` bị từ chối hoặc yêu cầu refresh. |
| T046 rolling replan | Replan remainder từ current time/location; Plan/Clarify/NoSolution gate; re-gate đủ 7 check; `return_time` là deadline cứng; tăng version; hai lần replan liên tiếp không lặp POI. |
| Rain trigger | Forecast 80% ở khung giờ còn hoạt động outdoor kích hoạt; 70% không kích hoạt strict `>70%`; hoạt động done không đổi. |
| Recovery regression | Đưa ít nhất một delay, closure, add/drop, tired, budget; giữ hard constraints, kiểm tra deadline, reason từng change và metric intent/deviation sau mỗi event. |

S5 là smoke fixture, không đủ chứng minh thống kê. Báo cáo theo event class × severity × mode: count, tỷ lệ pass 7-check, Done/Must/Soft retention, EventResolutionRate, từng deviation, latency (mục tiêu replan <15s theo `plan.md`) và reason failure. Chạy scripted event một bước và chuỗi hai lần replan trên cùng trip để bắt duplicate/version regression. Không ghi nhận benchmark green cho đến khi integration test T048 chạy trên checkout đã có state/replan thật.

## 7. Quyết định đề xuất và điểm cần chốt

1. Dùng trigger weather strict `rain_prob > 0.70` theo giờ hoạt động outdoor; tiếp nhận rain event do user độc lập với ngưỡng forecast.
2. Chốt 8-class mapping nêu trên; quyết định merge `traffic→delay`, đưa `lost→clarify`, và tái huấn luyện/re-export labels trong task implementation riêng.
3. Bảo đảm completed items 100%, must intent 100% khi còn khả thi, soft intent retention mục tiêu ≥0.80; báo từng thành phần.
4. Dùng ba deviation riêng `D_sem/D_spatial/D_seq`; mục tiêu đề xuất ≤0.30 cho fixture step-level S5, chưa phải số đo thực nghiệm.
5. Mỗi candidate plan phải qua FAR/VROH/B3/BCS/ETB/TCS/HCS trước khi trả; hard failure không có soft scores.
6. Chốt semantics version cho `Clarify/NoSolution` và đưa `state_delta` vào API contract; hiện contract chỉ nêu itinerary/mode/changes.
7. Kiểm chứng T044–T046/T048 trên nhánh đã tích hợp, vì hai service paths vắng mặt trong checkout này.

## Sources

[1] https://aclanthology.org/2026.findings-acl.2002.pdf — TripTide: A Benchmark for Adaptive Travel Planning under Disruptions