# API Contracts: BE ↔ Flutter (`v1`)

**Feature**: `001-travel-agent-mvp` | **Date**: 2026-09-21
Base: `http://<be-host>:8000/v1`. All bodies JSON, Pydantic-validated.
Errors: `{ "error": "<code>", "message": "<vi>" }`.

## POST /parse — NL → TripRequest
- In: `{ "text": "cuối tuần đi Đà Nẵng 2 người 3 triệu thích biển", "user_id": "u1" }`
- Out: `TripRequest` (data-model.md) OR `{ "needs_clarification": ["budget", ...] }`
- Rule: `areas` đọc thẳng từ câu (không qua LLM): "trung tâm", "Hải Châu" → `trung_tam`; "Sơn Trà", "Mỹ Khê" → `son_tra_my_khe`; "Ngũ Hành Sơn", "Non Nước" → `ngu_hanh_son`; "Hội An", "phố cổ" → `hoi_an`; "Hải Vân", "Liên Chiểu" → `hai_van_lien_chieu`; "Bà Nà" → `ba_na_tay`. "Đà Nẵng" không phải khu vực; "trung tâm thương mại" không phải trung tâm; khu đứng sau "không", "tránh", "trừ"... trong cùng vế câu bị bỏ qua.

## POST /itinerary — TripRequest → plans
- In: `{ "trip": {TripRequest}, "profiles": ["savings", "balanced", "experience"] }`
- Out: `{ "plans": [{Itinerary + scores + explanations + activity_match}], "selected": null, "retrieval": {...} }`
- Rule: every plan passed feasibility gate; ≥2 plans when feasible.
- Rule (FR-006, FR-022): `activities` không bao giờ lọc bớt POI. Mỗi hoạt động hiểu được thành ràng buộc "ít nhất 1 điểm thật sự đúng mong muốn đó" cho bộ giải ("hải sản" là quán hải sản, "chùa" là chùa, không chỉ cùng nhóm loại); không xếp được thì bỏ ràng buộc đó và cảnh báo. Mỗi plan có `activity_match: [{activity, categories, status, poi_id?, start_between?}]`. `status`: `met` (kèm `poi_id` của điểm đáp ứng) / `unmet` / `no_verified_poi` (dữ liệu chưa có điểm nào như vậy) / `over_budget` (có điểm nhưng ngân sách không đủ) / `blocked_by_profile` (hồ sơ khách loại điểm đó) / `outside_areas` (chỉ khu ngoài `trip.areas` có điểm như vậy) / `outside_trip_hours` (mong muốn chỉ có nghĩa trong một khung giờ ngoài chuyến đi, `start_between` là khung phút) / `not_understood`.
- Rule: "ngắm hoàng hôn", "ngắm bình minh" là mong muốn có giờ: điểm đáp ứng phải bắt đầu trong khung 16:00–18:00, 05:00–07:00.
- Rule: `trip.date` (ISO) cho biết thứ của ngày đi. Giờ mở cửa đọc theo đúng thứ đó (`hours_by_day`), điểm nghỉ ngày đó không được xếp; điểm trong `must_visit` nghỉ ngày đó bị bỏ kèm cảnh báo. Không có `date` thì plan cảnh báo các điểm có ngày nghỉ trong tuần. Chuyến nhiều ngày tính thứ riêng cho từng ngày.
- Rule: ngày đi qua khung 17:30–20:30 có bữa tối như bữa trưa; tiền hoặc giờ không đủ thì bỏ bữa tối kèm cảnh báo. Cổng mềm `DINNER` và `TIME_FIT` (điểm xếp đúng thời điểm trong ngày theo loại) có trong `constraint_status`, không làm rớt plan; `must_visit` không bị chấm `TIME_FIT`.
- Rule: điểm `must_visit` không vừa ở thời lượng thường dùng được xếp ở thời lượng ngắn nhất thường gặp (p25) kèm cảnh báo.
- Rule: điểm đi cả ngày (thời lượng từ 5 giờ: Bà Nà, VinWonders, Cù Lao Chàm) chạy suốt khung 11:00–13:00 thì bữa trưa ăn ngay tại đó: plan không xếp nhà hàng trưa và không có khoảng nghỉ sau bữa trưa, `template.lunch_on_site` là `poi_id` của điểm đó (`lunch_restaurant` và `rest_block` là `null`), kèm một dòng trong `warnings`. Cổng `REST_FOLLOWS_LUNCH` chấp nhận trường hợp này. Số điểm tối thiểu của ngày chỉ tính trên phần ngày còn lại.
- Rule: dự báo thời tiết đọc theo `trip.date`, mỗi ngày của chuyến nhiều ngày đọc ngày của nó; ngày nằm ngoài dự báo (quá một tuần) thì không dùng dự báo và `warnings` nói rõ; không có `date` thì chuyến được coi là bắt đầu vào ngày đầu của dự báo và `warnings` ghi ngày đã dùng. Giờ có xác suất mưa từ 50% làm điểm ngoài trời mất điểm trong bộ giải theo mức che mưa của điểm (`smart_tags.rain_cover`): mưa cả ngày thì điểm lộ thiên chỉ còn trong lịch khi khách yêu cầu hoặc lịch cần đủ số điểm; mưa một phần ngày thì điểm đó dời sang giờ khô. Khi dự báo có giờ mưa, `warnings` có một dòng "du bao mua HH:MM-HH:MM (toi da N%) ..." nêu các khung giờ mưa, tên các điểm ngoài trời còn nằm trong giờ mưa, và ngày dự báo đã dùng nếu chuyến không có `date`.
- Rule: thứ tự và giờ của các điểm được chọn theo quãng đường cộng thời gian chết (khởi hành muộn hơn 30 phút, khoảng trống hơn 30 phút giữa hai điểm, nghỉ trưa dài hơn mức nghỉ 45 phút); điểm `must_visit` được đặt trong khung giờ hợp lý của loại điểm khi có thứ tự cho phép.
- Rule: các câu trả lời SOFT của hồ sơ onboarding cộng hoặc trừ điểm cho từng điểm trong bộ giải, không chỉ trong bảng xếp hạng: `spending_level` (1 hoặc 3 nghiêng về quán rẻ hơn hoặc đắt hơn mức thường gặp của loại đó), `outdoor_bias` (-1..1, trên các điểm ngoài trời), `activities` (mã của danh mục onboarding như `beach`, `museum`, `nightlife`, hoặc chữ tự do; là sở thích, không phải điểm bắt buộc như `trip.activities`) và `food_prefs` (mã như `seafood`, `BBQ`, `local_cuisine`, hoặc chữ tự do). Hồ sơ trung tính (mức 2, 0, không chọn gì) cho đúng lịch như khi không có các trường này. `explanation.evidence` của điểm được chọn có thêm "hop muc chi tieu", "hop gu ngoai troi", "hop hoat dong ban thich" khi đúng.
- Rule: POI có `plan_tier`: `main` vào lịch mặc định; `local` chỉ khi một mong muốn có dưới 3 điểm `main` dùng được (không bị khách tránh, mở trong khung giờ chuyến đi, vé không vượt ngân sách); `wish_only` chỉ khi có mong muốn đúng điểm đó; `excluded` không tự vào lịch. `must_visit` bỏ qua `plan_tier`.
- Rule: trên cùng một máy và cùng bản cài đặt, cùng một yêu cầu cho cùng một lịch ở mọi mức tải (bộ giải 1 luồng, giới hạn theo khối lượng tính toán, không theo đồng hồ). Mới đo trên một máy: máy khác có thể cho lịch khác nếu khác phiên bản bộ giải, hoặc không nạp được mô hình PATM và phải dùng luật dự phòng. Dự báo thời tiết đổi thì lịch cũng có thể đổi.
- Rule (FR-013, FR-024): `retrieval = { candidates, needs_verification_total, needs_verification: [{poi_id, name, cat, must_visit, reasons, uncertainty}] (tối đa 20, must_visit trước), excluded: {lý do: số POI}, unmatched_activities }`.
- Rule: `must_visit` chưa xác minh không vào lịch và không làm hỏng lịch: plan vẫn lập với các điểm còn lại, kèm cảnh báo trong `warnings`; điểm đó nằm trong `needs_verification` với `must_visit: true`.
- Rule: `trip.areas` (mã `zone` của danang-v2: `trung_tam`, `son_tra_my_khe`, `ngu_hanh_son`, `hoi_an`, `hai_van_lien_chieu`, `ba_na_tay`; mã khác → 422) giữ lịch trong các khu đó: POI khu khác bị loại với lý do `ngoai khu vuc` (đếm trong `retrieval.excluded`, không vào `needs_verification`), trừ `must_visit` luôn được giữ. Rỗng hoặc không gửi thì lịch như cũ. POI không có `zone` (danang-v1) không lọc được: lịch giữ nguyên và `warnings` có "khong loc theo khu vuc: du lieu nay chua chia khu vuc". App lưu khu theo chuyến trong `preference_overrides.areas` (mọi lần lập lịch và replan đều đọc), hoặc gửi `constraint_overrides.areas` của `POST /trips/{id}/planning-requests` cho riêng một lần (`changed_constraints.areas` khi replan); trợ lý AI đề xuất trong `hard_constraints.areas`. Hợp đồng app: `specs/022-trip-areas/spec.md`.
- Rule: pool rỗng sau bộ lọc cứng → plan rỗng `passed: false`, `infeasible_by.rule = "EMPTY_POOL"`; không bao giờ lấy toàn bộ snapshot thay thế.
- Rule: `constraint_status` có thêm cổng cứng `PROFILE_SAFE` (dị ứng / must_avoid / khả năng đi lại của hồ sơ, kiểm lại trên plan cuối).

- Rule (FR-020): `trip.days = 2` trả một plan cho cả chuyến. Mỗi phần tử `activities` và `segments` có `day` (1, 2); `days = [{day, date, stops, total_cost, total_km, total_min, travel_min, cost_estimated, passed, violations, template, soft_penalties}]`. Không điểm nào lặp giữa các ngày; `total_cost` và `passed` tính cho cả chuyến. Không xếp đủ số ngày → `passed: false` kèm cảnh báo. `days = 1` giữ nguyên dạng cũ (không có `day`, `days`).
- Rule: `trip.resume = {start_time, origin?}` (mặc định `null`) dùng cho replan giữa ngày đầu của chuyến 2 ngày. Ngày 1 bắt đầu lúc `resume.start_time`, từ `resume.origin` (nơi khách đang ở; không gửi thì dùng `trip.origin`). Các ngày sau vẫn bắt đầu lúc `trip.start_time` từ `trip.origin`. Gate chấm ngày 1 theo giờ và điểm đó: ngày bắt đầu sau 12:30 (không còn đủ 60 phút của khung trưa 11:30–13:30) không phải có bữa trưa, chặng đầu B3 tính từ `resume.origin`. Điểm không có hàng trong ma trận thì ngày 1 không có điểm xuất phát và `warnings` nói rõ. Với `days = 1`, `resume` chỉ là `start_time` và `origin` của ngày đó.
- Rule: `origin` (của `trip` hay `resume`) có `poi_id` thì ngày bắt đầu ở địa điểm đó (`lat`/`lon` chỉ để hiển thị). Chỉ có `lat`/`lon` thì đó là vị trí GPS (`accuracy_m?`, `fallback_poi_id?`): chặng đầu mượn hàng ma trận của các địa điểm gần nhất cộng đoạn đi tới đó, `segments` đầu có `from_id` bắt đầu bằng `@gps:` và `source: "gps_estimate"`, mỗi plan có `gps_origin`. Cách địa điểm có dữ liệu gần nhất trên 1 km thì có cảnh báo; trên 3 km, ngoài Đà Nẵng hoặc `accuracy_m` trên 1000 thì không dùng vị trí, ngày bắt đầu ở `fallback_poi_id` (không có thì tour mở) và `warnings` nói lý do. Chi tiết: `specs/024-gps-origin/spec.md`.

## POST /itinerary/select — chốt plan
- In: `{ "itinerary_id": "..." }` → Out: `{ "active_id": "..." }`

Stable-planning addendum: client mới gửi thêm `idempotency_key` để nhận
acceptance summary; client cũ giữ nguyên response trên nhưng server vẫn lưu
accepted-plan evidence. Xem `specs/003-stable-planning-roadmap/contracts/api.md`.

## POST /replan — disruption → new version
- In: `{ "itinerary_id": "...", "event": {DynamicEvent}, "completed": [...], "day": 2 }`
- Out: `{ "itinerary": {Itinerary v+1}, "mode": "plan|clarify|no_solution", "changes": [...], "day": 2 }`
- Rule: completed activities preserved; version++.
- Rule (FR-020): plan nhiều ngày chỉ xếp lại một ngày: `day`, mặc định là ngày đầu tiên còn điểm chưa đi. Các ngày khác trả về nguyên vẹn. Ngày không có trong plan → 404 `UNKNOWN_DAY`.

## POST /trips/{trip_id}/replans — app lập lại phần còn lại (cần đăng nhập)
- In: `{ "source_version_id": "...", "remaining_from": "2026-11-24T14:05:00+07:00", "current_location": {"lat": 16.0744, "lon": 108.245, "accuracy_m": 12}, "completed_activity_ids": [...], "skipped_activity_ids": [...], "unavailable_poi_ids": [...], "changed_constraints": {...}, "target_count": 5 }`, header `Idempotency-Key` (mới cho mỗi lần bấm). Chỉ `source_version_id` là bắt buộc.
- Rule: `current_location` là một lần đọc GPS của máy lúc bấm (không phải luồng GPS). Ngày đang đi bắt đầu từ đó, thay cho điểm vừa đi xong; vị trí không dùng được thì quay về điểm vừa đi xong, rồi khách sạn. Chỉ dùng cho ngày của `remaining_from`; phần còn lại bắt đầu từ ngày sau thì ngày đó vẫn từ khách sạn. Server làm tròn 4 chữ số thập phân (~11 m) và lưu trong `remaining_context.current_location`. Chi tiết: `specs/024-gps-origin/spec.md`.
- Out: planning request như `POST /trips/{id}/planning-requests`, `request_kind: "replan"`, có thêm `remaining_context.window = {day, date, days, start_time}` và `plan.window` trong từng phương án.
- Rule: `remaining_from` là giờ thiết bị (ISO 8601; có múi giờ thì đổi sang giờ Đà Nẵng, không có thì coi là giờ Đà Nẵng; chỉ `HH:MM` thì là hôm nay). Không gửi thì server lấy giờ hiện tại theo Asia/Ho_Chi_Minh. Giờ rơi vào một ngày của chuyến: lập ngày đó từ giờ ấy (không sớm hơn `day_start`) và các ngày sau. Còn dưới 60 phút trước `day_end` thì chuyển sang ngày sau từ `day_start`; ngày cuối thì 409 `REPLAN_WINDOW_CLOSED`. Trước hoặc sau chuyến: lập cả chuyến từ `day_start`. `remaining_from` không đọc được → 422 `VALIDATION_ERROR`.
- Rule: ngày bắt đầu lại từ điểm vừa đi xong trong chính ngày đó; điểm của hôm trước không tính, ngày đó bắt đầu từ khách sạn (`base_poi_id`). Giữa ngày 1 của chuyến 2 ngày, planner nhận `trip.resume` (ngày 2 vẫn từ `day_start` và khách sạn).
- Rule: `changed_constraints` ghi đè từng khóa lên `constraint_overrides` của request đã tạo phiên bản nguồn: khóa có gửi thay hẳn giá trị cũ (`[]` làm rỗng danh sách, `null` bỏ ràng buộc có thể bỏ), khóa không gửi giữ nguyên. Không gửi gì thì dùng lại toàn bộ ràng buộc cũ. Điểm đã đi, bỏ qua hoặc đóng cửa vào `avoid` và ra khỏi `must_visit`; ngân sách trừ chi tiêu đã ghi.
- Rule: thử lại đúng khóa và body cũ trả lại request đã lưu, kể cả khi đã qua giờ; giờ server không nằm trong fingerprint. Cùng khóa mà khác body → 409 `IDEMPOTENCY_CONFLICT`. Chi tiết và việc phía app: `specs/023-replan-remaining/spec.md`.

## GET /itinerary/{id} — đọc lịch (offline cache key)

## POST /expenses + GET /expenses/summary?trip_id=
- In: `{ "trip_id": "...", "label": "Mì Quảng", "amount": 120000, "kind": "food" }`
- Out summary: `{ "budget": 3000000, "spent": 2500000, "left": 500000, "alert": "80%" }`

## GET /weather?lat=&lon= — Open-Meteo snapshot (cached + `fetched_at`)

## POST /evaluate — itinerary → scores
- In: `{ "itinerary": {...}, "trip": {TripRequest} }`
- Out: `{ "gate": {"passed": bool, "violations": [...]}, "soft": {...}, "reward": 0.0 }`
- Rule: gate fail → no quality scores.

## POST /score-transition — PATM (debug/mobile pre-check)
- In: `{ "a": {poi+ctx}, "b": {poi+ctx}, "user": {...} }`
- Out: `{ "score": 0.82 }` (<5ms target)

## Env: LLM_PROVIDER (local|api)
- `local` (mặc định, demo day): parser/judge/explanation qua Ollama `http://localhost:11434` (Qwen3-14B).
- `api` (test env, BE deploy): qua GPT-4o-mini/Gemini Flash, temp 0.1. Key qua `.env`, không commit.
