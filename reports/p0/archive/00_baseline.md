# P0 – Bước 0: baseline test (2026-11-18)

Môi trường: VM Linux của phiên làm việc (Python 3.10.12, 2 CPU), `pip install -r BE/requirements.txt` (+ pytest).
Chạy **từ gốc repo** (test dùng đường dẫn `BE/...`), từng file một vì mỗi lệnh trong VM bị giới hạn 180 giây.

| | Trước P0 (code gốc `a1ef7a2`) | Sau P0 |
|---|---|---|
| File test chạy xong | 88 / 89 | 90 / 91 (+ `test_v2_rules.py`, `tests/data/test_snapshot_v2.py`) |
| Passed | **808** | **838** |
| Failed / Error | 0 / 0 | 0 / 0 |
| Skipped | — | 2 (cổng P0, bật bằng `P0_GATE=1`) |
| Không chạy xong | `BE/tests/unit/test_baselines.py` (12 test) | như cũ |

`test_baselines.py` chạy CP-SAT ~5 s/lịch cho 23 truy vấn; trên VM 2 lõi không xong trong 170 s (không phải lỗi code).
**Cần chạy lại trên máy của bạn**: `python -m pytest BE/tests -q` (dự kiến 822 + 30 = ~852 test).

Ghi chú cùng hiện tượng: với `EVAL_DETERMINISTIC_TIME = 1.5`, CP-SAT trên VM này trả UNKNOWN cho cả v1 lẫn v2
(chưa kịp tìm nghiệm); với 4–6 đơn vị thì cả hai đều ra lịch. Trên máy mạnh hơn có thể không gặp.
