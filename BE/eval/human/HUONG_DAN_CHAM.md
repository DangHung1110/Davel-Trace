# Hướng dẫn chấm cặp lịch

**Việc của bạn:** mỗi màn hình có một yêu cầu của khách và hai lịch, A và B, cùng làm cho yêu cầu đó. Bạn chọn lịch mà bạn, nếu là vị khách ấy, muốn đi theo hơn. Bộ hiện có 150 cặp, mỗi cặp mất 1 đến 2 phút. Bạn có thể chia ra nhiều buổi.

Kết quả dùng vào hai việc: kiểm tra "hàm chấm điểm lịch" mà nhóm đang dạy cho máy, và đo xem giám khảo AI (LLM) chấm lệch khỏi người thật bao nhiêu. Vì vậy hãy chấm theo cảm nhận thật của bạn. Không có đáp án đúng, và bạn không cần đoán máy muốn gì.

## 1. Mở trang

- Bấm đúp vào file `BE/eval/human/plan_pairs.html` để mở bằng Chrome, Edge, Safari hoặc Firefox. Trang không cần mạng và không cần chạy server.
- Đừng dùng cửa sổ ẩn danh, vì khi đóng cửa sổ trình duyệt sẽ quên tiến độ.
- Nhập **mã người chấm**: một tên ngắn, ví dụ `an`. Lần sau mở lại, hãy nhập đúng mã cũ để chấm tiếp.

## 2. Chấm một cặp

1. Đọc **Yêu cầu của khách**: ai đi (cặp đôi, gia đình có người già và trẻ nhỏ, nhóm bạn...), mấy người, ngân sách cho cả nhóm, đi từ mấy giờ đến mấy giờ, ở khách sạn nào, khách muốn gì, và lưu ý nếu có (dị ứng, xe lăn...).
2. Đọc **Lịch A** rồi **Lịch B**. Mỗi dòng cho biết giờ, tên điểm, loại điểm và giá cho mỗi người. Bấm tên điểm để mở Google Maps nếu cần. Điểm có nền xám kèm chữ "cả 2" là điểm có trong cả hai lịch, để bạn tập trung vào chỗ khác nhau.
   - Mỗi ngày bắt đầu từ khách sạn ghi ở thẻ yêu cầu, nên dòng "đi xe từ nơi ở" là đường từ khách sạn đến điểm đầu tiên. Đường về khách sạn chưa được tính.
   - Giữa hai điểm có số phút đi xe máy. Lịch luôn chừa thêm khoảng 12 phút cho việc gửi xe và đi bộ vào. Chữ "rảnh" là thời gian trống ngoài khoảng đó.
3. Bấm **A tốt hơn**, **B tốt hơn** hoặc **Ngang nhau** ở thanh dưới cùng màn hình. Chỉ chọn Ngang nhau khi bạn thật sự không chọn được.
4. Nếu muốn, bấm vài nhãn dưới mỗi lịch và ghi chú lý do (không bắt buộc). Nhãn màu cam là điểm chưa tốt: đi lại nhiều, quá dày, nhiều giờ trống, thiếu bữa, tốn kém, giờ giấc lạ, không hợp nhóm khách. Nhãn màu xanh là điểm tốt: đúng ý khách, điểm đến hấp dẫn.
5. Bấm **Cặp sau →**.

Phím tắt: <kbd>A</kbd> chọn A, <kbd>B</kbd> chọn B, <kbd>N</kbd> ngang nhau, <kbd>→</kbd> hoặc <kbd>Enter</kbd> sang cặp sau, <kbd>←</kbd> về cặp trước. Muốn đổi ý thì chọn lại. Muốn để trống một cặp thì bấm **Bỏ chọn ở cặp này**.

## 3. Một ví dụ

Đây là ví dụ minh hoạ, không có trong bộ cặp. Yêu cầu: gia đình 4 người có người già và trẻ nhỏ, nhịp đi chậm, ngân sách 2.000.000đ, đi từ 08:00 đến 17:00, muốn tắm biển.

- **Lịch A**: 08:15 Bãi biển Mỹ Khê → 10:30 Bảo tàng Điêu khắc Chăm → 11:45 ăn trưa → 14:00 cà phê → 15:30 Chợ Hàn. Đi xe tổng 30 phút.
- **Lịch B**: 08:30 Chùa Linh Ứng → 11:00 ăn trưa → 13:00 Bãi biển Mỹ Khê → 15:00 Ngũ Hành Sơn → 16:30 Chợ Hàn. Đi xe tổng 55 phút.

Một người chấm có thể nghĩ: "Cả hai đều có biển, nhưng B tắm biển lúc 13 giờ nắng gắt, rồi chiều còn leo Ngũ Hành Sơn, người già sẽ mệt." Người đó chọn **A tốt hơn**, bấm nhãn "Giờ giấc, thứ tự lạ" và "Quá dày, mệt" dưới lịch B, rồi ghi chú "B tắm biển giữa trưa, chiều còn leo núi".

Một người khác có thể chọn B vì thích chùa Linh Ứng, và như vậy cũng không sai. Điều nhóm cần là lựa chọn thật của bạn, kèm lý do nếu bạn có.

## 4. Lưu và gửi kết quả

- Mọi câu trả lời tự lưu trong trình duyệt trên máy này, theo mã của bạn.
- Cuối mỗi buổi chấm, bấm **Xuất JSON**. Trình duyệt sẽ tải về file `cham_<mã>_<ngày-giờ>.json`. Gửi file đó cho người phụ trách qua Zalo hoặc email. Bạn có thể gửi nhiều file qua nhiều buổi: với cặp bạn chấm lại, câu trả lời mới hơn sẽ được dùng.
- Nếu trình duyệt không tải được file, trang sẽ hiện đoạn JSON. Bấm **Sao chép**, dán vào một file `.json` rồi gửi đi.
- Khi đổi máy hoặc lỡ xoá dữ liệu trình duyệt: bấm **Nhập lại file đã xuất** và chọn file JSON mới nhất của bạn.

## 5. Nên và không nên

- Hãy chấm một mình và đừng bàn với người chấm kia, vì nhóm cần đo độ đồng ý thật giữa hai người.
- Đừng cố đoán lịch nào do kiểu nào tạo ra. Hai lịch được xếp vào A và B một cách ngẫu nhiên.
- Giá có dấu * là giá ước tính theo loại quán, chưa phải giá thật. Thời gian đi lại tính theo xe máy.
- Đừng chấm quá nhanh. Dưới 10 giây một cặp thường là chưa đọc kỹ.
- Có lúc hai cặp cùng một yêu cầu, và một lịch xuất hiện lại. Cứ chấm bình thường.

## Dành cho người phụ trách

Sinh lại bộ cặp. Lệnh này chạy planner trên danang-v2 cho khoảng 100 yêu cầu, mất khoảng 15 phút:

```bash
python BE/eval/human/make_plan_pairs.py --plans-cache plans.json
```

Sinh lại từ kết quả planner đã lưu, ví dụ để đổi số cặp:

```bash
python BE/eval/human/make_plan_pairs.py --reuse plans.json --n 120
```

Gộp kết quả của hai người chấm. Lệnh in độ đồng ý (% và Cohen's kappa) và chỉ ghi file khi có `--out`:

```bash
python BE/eval/human/ingest_plan_pairs.py cham_an_*.json cham_binh_*.json --out BE/eval/human/plan_pairs_v1_labels.json
```

So với nhãn của LLM: thêm `--llm nhan_llm.jsonl`. Mỗi dòng là một cặp, dạng `{"pair_id": "P001", "choice": "A"}` (LLM xem A/B giống người chấm), hoặc dạng của PATM `{"first_id": ..., "second_id": ..., "label": 1}` với mã lịch trong `plan_pairs_v1_key.json`.

Các file trong thư mục này:
- `plan_pairs_v1.json`: thứ người chấm thấy (yêu cầu, lịch A, lịch B).
- `plan_pairs_v1_key.json`: phần giấu kín, cho biết A và B là lịch của kiểu nào, cùng yêu cầu gốc gửi cho planner. Đừng gửi file này cho người chấm.
- `plan_pairs.html`: trang chấm, đã nhúng sẵn `plan_pairs_v1.json`.

Quy ước nhãn giống PATM: +1 nghĩa là lịch `first` tốt hơn, 0 là ngang nhau, -1 là lịch `second` tốt hơn. `first` và `second` theo thứ tự cố định Tiết kiệm < Cân bằng < Trải nghiệm, không theo A/B.
