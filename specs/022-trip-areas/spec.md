# Khu vực muốn đi (`areas`) — hợp đồng cho app

Người dùng chọn một hay vài khu của Đà Nẵng, lịch chỉ xếp điểm trong các khu đó
(trừ điểm bắt buộc ghé). Khu được **lưu theo chuyến** giống khách sạn
(`specs/021-trip-planning-inputs`), nên mọi lần lập lịch và replan của chuyến đều
dùng. Trợ lý AI cũng đề xuất khu khi câu người dùng nhắc tới, cho riêng lần lập
lịch đó.

Ví dụ thật (gold q14, "ưu tiên check-in trung tâm"): không lọc khu, ba phương án
savings/balanced/experience lái xe 21/61/40 phút; lọc `trung_tam` còn 9/31/31 phút.

## 1. Sáu mã khu

App chỉ gửi và lưu **mã**; nhãn là để hiển thị. Mã khác bị từ chối (422).

| Mã | Nhãn gợi ý | Dòng phụ gợi ý (điểm có trong dữ liệu khu đó) |
|---|---|---|
| `trung_tam` | Trung tâm (Hải Châu) | Cầu Rồng, chợ Hàn, chợ Cồn, Bảo tàng Chăm |
| `son_tra_my_khe` | Sơn Trà – Mỹ Khê | Biển Mỹ Khê, chùa Linh Ứng Sơn Trà, đỉnh Bàn Cờ |
| `ngu_hanh_son` | Ngũ Hành Sơn | Núi Ngũ Hành Sơn, biển Non Nước |
| `hoi_an` | Hội An | Phố cổ, Chùa Cầu, An Bàng, rừng dừa Bảy Mẫu, Cù Lao Chàm |
| `hai_van_lien_chieu` | Hải Vân – Liên Chiểu | Đèo Hải Vân, Hải Vân Quan, làng Nam Ô |
| `ba_na_tay` | Bà Nà – phía Tây | Bà Nà Hills, suối khoáng Núi Thần Tài |

- Thứ tự trên là thứ tự của `AREA_CODES` (`BE/app/schemas/trip.py`); app hiển thị
  theo thứ tự này.
- Ranh giới khu tính gần đúng theo toạ độ (`BE/ml/data/v2_rules.zone_of`). Đã biết:
  Bãi biển Tiên Sa (bán đảo Sơn Trà) đang nằm trong `trung_tam`.
- "Đà Nẵng" không phải một khu. Không chọn khu nào = mọi khu.

## 2. Lưu theo chuyến

Khu nằm trong `preference_overrides` của chuyến, cạnh `base_poi_id` và
`outdoor_bias`. Lưu bằng `PATCH /v1/trips/{trip_id}`, gửi **cả map** (giữ các khóa
đang có), như cách lưu khách sạn:

```json
PATCH /v1/trips/{trip_id}
{
  "expected_version": 3,
  "preference_overrides": {
    "base_poi_id": "ChIJMeyhoXgXQjERqCs6CuNR5yI",
    "outdoor_bias": 0.5,
    "areas": ["trung_tam", "son_tra_my_khe"]
  }
}
```

- Bỏ chọn hết: xoá khóa `areas` (hoặc gửi `[]`); lịch đi mọi khu.
- Phải là danh sách mã. Nhãn ("Trung tâm"), chuỗi đơn ("trung_tam") hay mã lạ trả
  `422 VALIDATION_ERROR` với thông báo "Khu vực phải là danh sách mã: trung_tam, ...".
- Sửa khu cũng như mọi lần sửa chuyến: `version` tăng (khóa idempotency lập lịch của
  app đổi theo), phương án chưa chọn của lần lập lịch trước không chọn được nữa, và
  chuyến đã có lịch đang dùng thì sang `needs_review`.
- Đọc lại: `GET /v1/trips/{trip_id}` trả `preference_overrides.areas` như đã lưu.

## 3. Gửi khi lập lịch

**Lập lịch thường: không phải gửi gì.** Backend tự đọc `preference_overrides.areas`
của chuyến (`_areas` trong `planning_lifecycle/service.py`), kể cả khi replan.

Chỉ gửi `constraint_overrides.areas` của `POST /v1/trips/{trip_id}/planning-requests`
khi muốn đổi khu **cho riêng lần đó** (ví dụ khu AI đề xuất đã được xác nhận):

| `constraint_overrides.areas` | Khu dùng để lập lịch |
|---|---|
| không gửi, `null` hoặc `[]` | khu lưu trong chuyến; chuyến chưa lưu thì mọi khu |
| `["hoi_an"]` | chỉ `hoi_an`, cho lần này; khu lưu trong chuyến không đổi |

- Replan (`POST /v1/trips/{trip_id}/replans`) dùng khu lưu trong chuyến. Khu chỉ xác
  nhận cho một lần (AI) không theo sang replan, trừ khi app gửi lại trong
  `changed_constraints.areas`.
- Đừng gộp khu đã lưu vào `constraint_overrides` sau khu AI đã xác nhận (kiểu
  `{...confirmed, 'areas': trip.areas}`): khóa sau sẽ đè khu người dùng vừa xác nhận.
  Backend đã tự đọc khu đã lưu.

## 4. Đề xuất của AI

`POST /v1/trips/{trip_id}/ai/interpretations` luôn trả `hard_constraints.areas`
(danh sách mã, có thể rỗng). Backend đọc khu **thẳng từ câu** bằng bảng cụm từ cố
định (`parser.areas_in_text`), không hỏi LLM: câu nào cũng có "Đà Nẵng", một LLM
hiểu thành "trung tâm" sẽ khoá mọi lịch vào một khu.

```json
// "ưu tiên check-in trung tâm"
"hard_constraints": {"must_visit": [], "avoid": [], "accessibility": [],
                     "areas": ["trung_tam"]}
```

- Cụm từ nhận ra: trung tâm, Hải Châu → `trung_tam`; Sơn Trà, Mỹ Khê →
  `son_tra_my_khe`; Ngũ Hành Sơn, Non Nước → `ngu_hanh_son`; Hội An, phố cổ (cả
  "trung tâm Hội An") → `hoi_an`; Hải Vân, Liên Chiểu → `hai_van_lien_chieu`; Bà Nà →
  `ba_na_tay`. Gõ không dấu cũng nhận.
- Không tính: "trung tâm thương mại/mua sắm/hội nghị/vui chơi/triển lãm"; khu đứng
  sau "không, tránh, trừ, khỏi, đừng, chẳng, bỏ" (tối đa 3 từ, cùng vế câu), ví dụ
  "ở trung tâm, không đi Hội An" → `["trung_tam"]`.
- Nhắc tên một điểm trùng tên khu cũng ra khu: "phải ghé Ngũ Hành Sơn" →
  `["ngu_hanh_son"]`. Vì vậy màn kiểm tra phải cho người dùng thấy và bỏ khu.
- App hiện tại đã gửi đi: `AiInterpretationProposal.confirmedOverrides` gộp
  `fields + hard_constraints + soft_preferences` thành `constraint_overrides`, và màn
  `PlanningRequestReview` giữ nguyên khóa nó không sửa. Nhưng màn này **chưa hiện
  khu**, nên người dùng chưa thấy và chưa bỏ được khu AI đề xuất.
- Khu AI đề xuất chỉ dùng cho lần lập lịch đó, không tự lưu vào chuyến.

## 5. Planner làm gì với khu

- Điểm khu khác bị loại trước khi lập lịch, lý do `ngoai khu vuc` (đếm trong
  `retrieval.excluded`). Điểm `must_visit` luôn được giữ dù ở khu khác.
- Mong muốn (`activities`) chỉ khu khác mới có: `activity_match.status =
  "outside_areas"` kèm cảnh báo; app nên gợi ý thêm khu hoặc bỏ lọc.
- Dữ liệu chưa chia khu (danang-v1): không lọc, `warnings` có "khong loc theo khu
  vuc: du lieu nay chua chia khu vuc".

Chi tiết lọc: `specs/001-travel-agent-mvp/contracts/api.md` (quy tắc `trip.areas`).

## 6. Việc phía app (Hùng)

- [ ] `Trip.areas`: đọc `preferenceOverrides['areas']`, chỉ giữ 6 mã trên.
- [ ] Ô chọn khu (chọn nhiều, 6 chip theo bảng mục 1) ở màn lập lịch, cạnh ô khách
      sạn. Lưu như `setPlanningHotel`: chép `trip.preferenceOverrides`, đặt hoặc xoá
      `areas`, gọi `updateActiveTrip({'preference_overrides': ...})`.
- [ ] Màn kiểm tra đề xuất AI: hiện `values['areas']` bằng chip có nhãn, cho bỏ từng
      khu; bỏ hết thì gửi `[]` hoặc xoá khóa (cả hai = khu đã lưu của chuyến).
- [ ] `requestPlan`: không thêm khu đã lưu vào `overrides` (mục 3).
- [ ] Hiện `outside_areas` trong kết quả mong muốn của phương án.
- [ ] Test widget: chọn/bỏ khu ra đúng payload chuyến; đề xuất AI có `areas` thì
      yêu cầu lập lịch mang `constraint_overrides.areas`.

## 7. Kiểm thử backend

- `BE/tests/unit/test_ai_assistance.py`: khu đọc từ câu, LLM không thêm được khu,
  câu không nhắc khu ra `[]`, đề xuất gộp lại hợp lệ với `ConstraintOverrides`.
- `BE/tests/unit/test_trip_areas.py`: `_trip_request` đọc khu đã lưu, replan giữ khu,
  khu của request thắng, giá trị đã lưu không phải mã bị bỏ qua; `validate_trip`
  từ chối nhãn.
- `BE/tests/contract/test_areas_app_contract.py`: "ưu tiên check-in trung tâm" qua
  endpoint AI tới đầu vào planner là `["trung_tam"]`; khu lưu trong chuyến tới lần
  lập lịch và replan; lưu nhãn bị 422.
