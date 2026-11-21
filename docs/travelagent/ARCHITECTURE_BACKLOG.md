# Yêu cầu cho kiến trúc — phát hiện trong lúc làm data P0 (20–21/11/2026)

Đầu vào cho spec kiến trúc / pipeline sắp viết (`/speckit.specify`). Mỗi mục: **vì sao** (bằng chứng) → **yêu cầu**.
Data không phải sửa để đáp ứng các mục này; chúng là việc của tầng lịch trình.
Bối cảnh chung: `TRAVELAGENT_CONTEXT.md` · đặc tả data: `DATA_SPEC_v2_1.md` · spec giá + luật mềm: `specs/002-pricing-soft-rules/` (nhánh `feat/002-pricing-soft-rules`).

## A1. Điểm neo của chuyến đi: khách sạn là tuỳ chọn, không phải mặc định

**Vì sao.** Người địa phương dùng app để đi chơi ngắn (2–5 tiếng, buổi tối, cuối tuần) rồi về nhà. Họ không có khách sạn. Khách sạn chỉ thuộc về khách từ nơi khác tới (ý của người dùng, 21/11). Hiện optimizer **chưa mô hình chặng xuất phát** (`optimizer.py`, ghi chú T061a); lưu trú (`role = base`) chỉ là dữ liệu.

**Yêu cầu.**
1. Yêu cầu lịch trình có trường `anchor`:

   | `anchor.type` | Khi nào | Lịch trình |
   |---|---|---|
   | `current` (mặc định) | mở app để đi ngay; có GPS | bắt đầu từ vị trí hiện tại; kết thúc ở điểm cuối hoặc gần nhà |
   | `home` | người dùng lưu / nói địa chỉ nhà | có chặng về nhà; nghỉ trưa = về nhà hoặc bỏ |
   | `hotel` | **chỉ khi** người dùng nói đang ở khách sạn (chọn 1 trong 76 POI `lodging` hoặc nhập địa chỉ) | xuất phát / về nghỉ trưa / về cuối ngày; dùng `time_profile = lodging_rest` |
   | `none` | đi một chiều (vd. từ sân bay) | không có chặng về |

   Kèm `lat`, `lon`, `poi_id` (nếu là khách sạn có sẵn), `return_by`.
2. Nhận biết kiểu neo từ câu nói hoặc GPS. Không rõ thì hỏi 1 câu, hoặc dùng `current`.
3. Chặng **neo → điểm đầu** và **điểm cuối → neo**: neo là khách sạn có sẵn thì dùng ma trận (đã có hàng cho cả 76 lưu trú); neo là toạ độ tuỳ ý thì gọi OSRM local lúc chạy (`MatrixService.fetch_osrm`, đã có).
4. Nghỉ trưa (`REST_FOLLOWS_LUNCH`), "về khách sạn" và số bữa bắt buộc thành **luật mềm theo kiểu neo và độ dài chuyến**: chuyến 3 tiếng buổi tối không cần bữa trưa hay nghỉ trưa. Khớp hướng cứng → mềm của spec 002.
5. **Kiểu người dùng** (địa phương / khách du lịch), suy từ neo + lịch sử:
   - Địa phương: giảm trọng số `prize_prior`, vì nó đếm cẩm nang du lịch nên thiên về điểm khách du lịch, tức điểm người địa phương đã đi. Tăng điểm cho độ mới / chưa ghé, không ép điểm "signature".
   - Khách du lịch: giữ như hiện nay.
6. **Gợi ý chọn khách sạn** là tính năng riêng, chỉ bật khi người dùng hỏi. Khi đó cần **giá theo đêm** làm trường riêng; không dùng `price.tier`, vốn là chi tiêu một người cho một lần ghé (lý do giá lưu trú để `null`: `BE/data/snapshots/danang-v2/README.md`).

## A2. Điểm theo giờ = độ nổi tiếng × u(t) × thời tiết

**Vì sao.** `reports/p0/15_ut_sufficiency.md`: u(t) qua hook `state_bands/state_score` có sẵn cho +16% hàm mục tiêu, giảm 59% điểm đi vào giờ xấu, không mất lịch. `16_context_sufficiency.md`: nhân thêm w(khí hậu) giảm 62% điểm phơi nắng gắt tháng 6.

**Yêu cầu.**
1. Hàm mục tiêu: Σ `prize_prior` · ū(t) · w̄(thời tiết) − di chuyển − phạt.
2. Chỉnh trọng số để **không đếm trùng nắng trưa**: đường cong của biển và điểm ngắm cảnh đã ngầm tính nắng.
3. **Ngân sách bộ giải / warm start:** 28/30 lần giải dừng vì hết giờ; gợi ý tham lam hiện chưa biết u(t).

## A3. Mưa: dự báo trước, khí hậu sau, cho phép xếp lại

**Vì sao.** Tháng 11, P(mưa) ≈ 0,25 rải đều cả ngày; khí hậu chỉ giảm được 8% điểm ngoài trời giờ hay mưa.

**Yêu cầu.** Khi chuyến đi trong tầm dự báo (khoảng 16 ngày) dùng `weather.fetch_forecast`; ngoài tầm thì dùng `climate.as_forecast` (cùng dạng). Gần ngày đi hoặc trong ngày đổi trời thì cho phép xếp lại lịch (`replan`).

## A4. Di chuyển theo khung giờ: kiểm tra, không đưa vào lõi bộ giải

**Vì sao.** 30/30 lịch xếp trên ma trận thông thoáng không bị phá khi nhân hệ số kẹt xe, vì đã có đệm 12 phút mỗi chặng. Còn xếp trên ma trận xấu nhất thì mất 9% số điểm.

**Yêu cầu.** Giữ ma trận thông thoáng + đệm trong bộ giải. `travel_time.factor` dùng để kiểm tra lịch và hiển thị giờ đến dự kiến. Hiệu chỉnh hệ số bằng log pilot.

## A5. Đọc thẳng v2.1, bỏ lớp chuyển đổi v1

**Vì sao.** Các service còn đọc dạng v1 qua `BE.common.poi_view` (`rating` ← 3 + 2·`prize_prior`, `verified`, `smart_tags`…).

**Yêu cầu.** Tầng mới đọc trực tiếp các trường v2.1 (`prize_prior`, `hours.kind`, `tags.*`, `provenance.*.confidence`); lớp chuyển đổi chỉ giữ cho code cũ tới khi gỡ. Dùng `confidence` để phân biệt số thật với ước lượng (vd. nhãn "nên kiểm tra giờ" khi `kind = safe_window`).

## A6. Theo suất (by_booking) và sự kiện

Lớp theo suất chỉ gợi ý khi người dùng muốn trải nghiệm ẩm thực / văn hoá hoặc khi là điểm bắt buộc; tối đa 1/ngày; suất trùng khung bữa thì là bữa đó (đã làm 20/11). Show, tour có giờ khởi hành (Ký ức Hội An 20:00, tour CT15) cần dạng "suất" tương tự (`DATA_FIX_PLAN` §4b mục 5).

## A7. Ngày nghỉ trong tuần (`hours.closed_days`)

**Vì sao.** 17 POI active có `closed_days` (vd. bảo tàng nghỉ thứ Hai, show Ký ức Hội An nghỉ thứ Ba) nhưng **chưa module nào trong `BE/app` đọc trường này**. Lịch xếp cho thứ Hai vẫn có thể chọn bảo tàng đóng cửa.

**Yêu cầu.** Yêu cầu lịch trình mang ngày đi (`date`); bộ lọc loại POI có thứ đó trong `closed_days`; gate kiểm lại.

**Cập nhật sau đồng bộ `main` (21/11).** `main` đã có logic theo thứ: `hours_by_day` + `BE.common.poi_on_date` → `closed_today`. `poi_view` giờ chuyển `closed_days` của v2 thành `hours_by_day`, nên khi trip có `date` thì phần của `main` tự áp cho v2. Còn lại: kiểm tra đầu-cuối khi chuyển runtime sang v2.

## A8. Export cho model đọc từ bản ghi v2.1 cuối

Đã sửa 21/11 (`write_exports`): trước đó `poi_features.csv` lấy từ bản ghi trung gian nên lệch `pois.json` ở 63 trạng thái và 5 loại. Test `test_16_export_matches_snapshot` giữ hai bên khớp. Pipeline train mới nên đọc `poi_features.csv` hoặc trực tiếp `pois.json`, không đọc `archive_fields.json`.

## A9. Chuyển runtime sang danang-v2 trên platform của `main`

**Vì sao.** Sau khi đồng bộ 21/11, `main` vẫn chạy mặc định `danang-v1` (`BE/app/core/config.py`). Planner của `main` đọc thêm những trường v2 chưa có:
- `plan_tier` (main / local / excluded) và `plan_tier_reason`: dùng cho tầng "ước muốn" của `retrieve`;
- `review_count`: dùng cho `trusted_rating`, rating Google co về trung bình theo số review;
- `subcat`.

**Yêu cầu.**
1. `poi_view` sinh `plan_tier` từ dữ liệu sạch của v2 (vd. `status`, `prize_prior`, `hours.kind`, `signature`), không lấy từ Google. `trusted_rating` đọc `prize_prior` thay cho rating × review_count khi `GOOGLE_POLICY=cach_ly`.
2. Chạy lại `reports/p0/15_ut_sufficiency` và `16_context_sufficiency` trên **ma trận xe máy**: các số hiện tại đo trên ma trận ô tô, mà thời gian xe máy dài hơn 1,67 lần (trung vị).
3. Đổi `snapshot_dir` mặc định chỉ khi gold v2 ≥ v1 trên planner của `main` (hiện 27/30 so với 26/30).

