# Track: 001-travel-agent-mvp execution log

**Chủ file: reviewer (w2:p6). Coder KHÔNG sửa file này. Orchestrator đọc để điều phối.**

## Models (2026-09-28, đã verify chạy được trên free usage)

- coder (w2:p2): `Muse Spark 1.3 Free` (Default/OpenCode) · variant `xhigh`
- reviewer (w2:p6): `Muse Spark 1.3 Free` (Default/OpenCode) · variant `xhigh`
- LƯU Ý: account chỉ có free usage qua Ollama Cloud — kimi-k2.7-code, deepseek-v4-pro đều báo `not included in your free usage`. Muốn dùng model trả phí thì nạp credits ollama.com rồi đổi bằng picker (`ctrl+x m`). ĐÃ REVERT: `opencode.json` + preset `opencode-go.orchestrator` về `muse-spark-1.3-contributor` (backup `.pre-kimi-bak`).
- 2026-09-28: preset `fixer` (deepseek-v4.1-flash high) TEST OK qua subagent (reply READY) → đường dispatch @fixer cho implement vẫn sống. Flash hợp vai executor nhanh; pane giữ Free xhigh vì mạnh hơn cho việc khó.
- 2026-09-28: preset `oracle` (qwen3.8-max/high) và `agents.verifier` (kimi-k3/high) SAI VARIANT (không tồn tại) → đã sửa file thành xhigh / max. Nhưng server cache config cũ nên preset vẫn lỗi; workaround: truyền `model` trực tiếp khi gọi subagent (`opencode-go/qwen3.8-max#xhigh`, `opencode-go/kimi-k3#max`) — TEST OK cả 2 (READY). Chưa restart `opencode service` (sợ rớt session orchestrator đang chạy); restart để sau, giữa 2 đợt việc.

## Quy ước ghi log (append-only, mới nhất lên đầu)

Mỗi entry:
```
## [YYYY-MM-DD HH:mm] Txxx — <tên việc> (pane: coder/reviewer)
- Trạng thái: DONE | ISSUE | FIX-REQUEST | NOTE
- Làm gì: ...
- File đổi: ...
- Cần fix / cần orchestrator quyết: ...
```

## Vùng sở hữu

- coder: code theo lanes.md lane được giao + tick `[X]` tasks.md đúng dòng task mình.
- reviewer: file track này + chạy test/validate/check (pytest, validator, đối chiếu spec). KHÔNG sửa code của coder; phát hiện lỗi thì ghi FIX-REQUEST, coder sửa.
- orchestrator (w2:p1): giao việc, đọc track, reconcile, merge/PR.

## Log

## [2026-09-28] T044 — Review event classifier S2 (templates + TF-IDF/LightGBM) (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-a (feat/lane-a-data-eval, commits f749536 + 3a1c8a9). (1) Vùng file: OK — 3 file mới BE/ml/event_clf/{templates,paraphrase,train}.py ∈ BE/ml/** + BE/tests/unit/test_event_clf.py là unit test của lane; tasks.md chỉ tick 1 dòng T044. (2) Chạy test `python BE/tests/unit/test_event_clf.py -v`: 5/5 OK exit 0 (0.8s, train in-process); acc 1.0 macro-F1 1.0 min-F1 1.0 ≥ gates (0.85/0.70). py_compile 4 file exit 0. (3) acc 1.0 ĐÚNG là template-overfit: train/test là stratified split trên cùng phân phối template-generated (cùng surface forms ở cả 2 phía), 10 classes có keywords đặc trưng tách dễ bằng TF-IDF 1-2gram → số này là optimism in-distribution, không phải năng lực tổng quát. Ghi NOTE (không FIX): cần paraphrase đa dạng (Qwen batch frame đã có sẵn emit/collect) + human-label sau; code đã tự đặt ngưỡng revisit (PhoBERT chỉ khi macro-F1 < 0.8 trên data paraphrased). Vẫn DONE vì đúng phạm vi T044 hiện tại. (4) Tick xứng đáng: task đòi templates + paraphrase + TF-IDF/LightGBM-hoặc-PhoBERT ~8 types → giao 10 types (rain/delay/drop_poi/add_req/tired/closure/time_change/traffic/budget/lost), kèm predict() serve cho lane B T046; bỏ PhoBERT có lý do ghi rõ (CPU-only, template phase chưa cần). (5) Secret-scan diff f749536~1..HEAD: 0 hit. Worktree sạch (__pycache__ đã ignore).
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T026+T027 — Review 16-feature extractor + nac-1 scorer + hooks (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-a (feat/lane-a-data-eval, commits 0c3028f + 122fbf8 + 89a8e76 + 8bdab9b). (1) Vùng file: OK — 4 file mới (BE/ml/patm/features.py + rule_score.py ∈ BE/ml/**, BE/tests/unit/test_features.py + test_rule_score.py là unit tests của lane) + 2 file hook cùng lane (make_pairs.py, train.py); tasks.md chỉ tick 2 dòng T026/T027. (2) Full BE/tests/unit/ (chạy từng file script vì chưa có __init__.py): snapshot 8 OK, patm 3 pass + 1 skip (gate model T029), features 5 OK, rule_score 5 OK → 21 pass + 1 skip, exit 0 hết; py_compile 6 file exit 0. (3) 16 features = 4 nhóm × 4 (A attr deltas / B cross ordered / C user centered / D context), khớp R2 'RankNet/Bradley-Terry, 16 features'; test_no_absolute_poi_id + neutral user/ctx về 0 (không rò POI_ID, default tái hiện base margins). rule_score antisymmetric by construction, default fitness=2/rain=0 cho margins y hệt legacy (0.5/0.3/0.2, TIE 0.15). (4) Tái sinh pairs seed (n=42): 38 pairs, ids + labels GIỐNG HỆT bản T028 (backward-compat đúng như docstring); retrain 16 features: 26 rows / CV 0.850 (5 folds) / held-out 0.833 (n=6) / flip 0.667 — Y NGUYÊN so với bản 10 features (ổn định). (5) Tick xứng đáng: T026/T027 là code thuần (extractor + scorer + unit tests), không đợi data; T028/T029 giữ [ ] đúng. (6) Secret-scan diff 0c3028f~1..HEAD: 0 hit. Worktree sạch (đã xóa __pycache__ do chạy test).
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T029-TRAINER — Review LightGBM pairwise trainer (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-a (feat/lane-a-data-eval, commit 46234b9, 1 file mới). (1) Vùng file: OK — BE/ml/patm/train.py ∈ BE/ml/**, commit chỉ 1 file. (2) Loss/split/eval: ĐÚNG — Bradley-Terry-via-logistic trên diff features F(a)-F(b), ties drop có đếm report; groups = unordered pair key, held-out 20% + 5-fold chia trên GROUPS (mirror chung group → không mirror-leak); held tách trước rồi mới fold trên phần còn lại (held không lọt CV). (3) Smoke tự chạy lại trên seed (lgb 4.7.0, pairs ra /tmp): 26 rows (12 ties dropped), 15 groups, CV 0.850 (5 folds), held-out 0.833 (n=6 = 3 groups × 2 mirrors), flip 0.667, exit 0 — khớp số orchestrator đưa, HỢP LÝ ở seed nhỏ (held n=6 → 1 miss = 0.833; flip thấp đúng vì n nhỏ + metric flip xấp xỉ bằng -x, xem NOTE). py_compile exit 0. (4) Không binary/temp trong repo: git ls-files BE/ml/patm/ chỉ 3 file .py; smoke của reviewer ghi model/metrics ra Temp/opencode; đã xóa __pycache__ do chạy test sinh ra, worktree sạch. (5) tasks.md: T029 giữ [ ] (đúng — trainer mới smoke trên seed, cần full pairs + model gate T031 xanh mới đóng). (6) Hook T026 ghi rõ pending: docstring 'interim extractor until T026 features.py (16 features) lands — swap one line' + upgrade path R2 lambdarank.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST. NOTE cho coder (không chặn, khi rảnh): flip consistency trong train.py xấp xỉ mirror bằng cách phủ định toàn vector -x, nhưng 5 slot one-sided (a/b_is_food, a/b_outdoor, same_type) phủ định không bằng features(b,a) thật — metric chẩn đoán này sẽ bớt nhiễu khi dùng rebuild features(b,a) hoặc khi có data full.

## [2026-09-28] T031-TEST — Review PATM eval test (pairwise/flip/leave-POI-out) (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-a (feat/lane-a-data-eval, commit 36865bb, 1 file mới). (1) Vùng file: OK — BE/tests/unit/test_patm.py thuộc vùng A liệt kê đích danh trong lanes.md; commit chỉ 1 file, không chạm tasks.md. (2) Chạy test `python BE/tests/unit/test_patm.py -v`: 3 pass + 1 skip, exit 0; py_compile exit 0. Số liệu khớp review T028: pairwise 38/38 = 1.000, flip 38/38 = 1.000, leave-POI-out train 27 / eval 11 / unseen ['dragon-bridge'] / acc 11/11 / leaked []. (3) Ý nghĩa cho T029: gate model (ranker T029) stub rõ ràng bằng @unittest.skip có lý do 'needs T029 model.txt'; ngưỡng SC-004 >= 70% assert cứng ở cả pairwise và leave-POI-out (assertGreaterEqual 0.70). NOTE trung thực: trên seed rule-generated, scorer==labeler nên 1.000 là tất yếu — docstring đã tự thừa nhận (regression gate chống drift rule); sức phân biệt thật chờ pairs judge/human + model T029. (4) tasks.md: T031 giữ [ ] (đúng — test mới là khung trên seed, T031 chỉ đóng khi có full pairs + model gate xanh). (5) Secret-scan diff 36865bb: 0 hit.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST.

## [2026-09-28] T028-BUILDER — Review pair builder rule protocol + swap-check + judge frame (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-a (feat/lane-a-data-eval, commit c29e0e4, 1 file mới). (1) Vùng file: OK — BE/ml/patm/make_pairs.py ∈ BE/ml/**, không chạm tasks.md. (2) Chạy thử trên seed danang-v1 (7 POIs): py_compile exit 0; build --n 42 --seed 7 → 38 pairs (không phải 42: tie pool chỉ 12 < quota 16 nên `pool[:q]` cắt bớt — đúng hành vi kỳ vọng trên seed nhỏ, đủ pool trên snapshot full 100-200 POIs); --check: format 0 errors, balance 31.6/31.6/36.8 so với mục tiêu 30/40/30 (lệch do cắt pool, chấp nhận được ở seed), swap 34 checked / 0 inconsistent / rate 1.0, leave-POI-out train 27 / eval 11 / leaked []. Không leakage: `_rule_margin` chỉ dùng intensity/type/weather_sensitive (không dùng poi_id), check_pairs cấm self-pair, split giấu 20% POI khỏi train. Judge frame + human sampling + collect_judge chỉ là khung (chưa có data Qwen — đúng theo docstring, T028 chưa đóng). (3) tasks.md: T028 giữ [ ] (đúng — còn thiếu snapshot full T003b + batch judge thật; diff tasks.md của commit này rỗng). (4) Secret-scan diff c29e0e4: 0 hit.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST. NOTE tùy chọn cho coder (không chặn): in 1 dòng warning khi pool < quota bị cắt (`pool[:q]` lặng lẽ thiếu n) để dễ debug trên snapshot full.

## [2026-09-28] T008 — Review snapshot loader + validation (pane: reviewer)
- Trạng thái: DONE
- Làm gì: review trong worktree lane-a (feat/lane-a-data-eval, commits 3530313 + ad7cd2b). (1) Vùng file: OK — đúng 2 file mới BE/app/services/snapshot.py + BE/tests/unit/test_snapshot.py, tasks.md chỉ tick 1 dòng T008 ([ ]→[X]); không có __init__.py/conftest.py. NOTE: snapshot.py nằm ngoài bảng File ownership lanes.md (A và C đều không liệt kê) nhưng tasks.md T008 ghi đúng path này và lanes.md giao T008 cho lane A → không tính lấn lane, đề nghị orchestrator bổ sung `BE/app/services/snapshot.py` vào vùng A. (2) Test: pytest chưa cài trong env nên chạy đúng cách stdlib của test — `python -m unittest BE.tests.unit.test_snapshot -v` và `python BE/tests/unit/test_snapshot.py`: cả 2 đều 8/8 OK (exit 0); py_compile cả 2 file exit 0. (3) Loader đối chiếu data-model.md (có đủ verified/fetched_at/visit_min): enforce fetched_at ở snapshot-level + per-POI, verified phải bool + verified_pois() loại unverified khỏi main plan (FR-013), schema check fields/tọa độ/visit_min p25<=p50<=p75/dur_source+dur_confidence vocab, matrix check ids khớp + đủ n*n cells + diagonal 0 + off-diagonal >0, lỗi raise ValueError liệt kê hết. (4) Secret-scan diff 3530313~1..HEAD: 0 hit.
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có FIX-REQUEST. Orchestrator patch lanes.md ownership (câu NOTE trên) khi rảnh.

## [2026-09-28] T003/T003b/T003c — Review lane A seed + estimator + fetch script (pane: reviewer)
- Trạng thái: DONE
- Làm gì: checkout feat/lane-a-data-eval, review diff chore/vibe-setup..HEAD (6 files). (1) Vùng file: OK — BE/ml/data/fetch_apify.py + BE/ml/patm/estimate_duration.py ∈ BE/ml/**, data/snapshots/danang-v1/* ∈ data/snapshots/**, tasks.md chỉ chạm 2 dòng T003/T003c (đúng luật chung). (2) pois.json: dict, 7/7 POIs đủ field bắt buộc (poi_id/name/lat/lon/type/visit_min/dur_source/dur_confidence/source/verified), verified=true cả 7; matrix.json: n=7, ids khớp pois, cells dict đủ 49/49 key `a->b`, missing=0. (3) estimator --check: 7/7 match nac-1 rules exit 0; py_compile cả 2 file py exit 0. (4) fetch script thiếu token: in đúng câu hướng dẫn THIEU APIFY_TOKEN, dừng sạch exit 2, không bulk, không traceback; secret-scan diff: 0 hit; `apify_api_...` chỉ là placeholder trong docstring. (5) tasks.md: T003 [X], T003c [X] kèm note nac-1 DONE/nac-2 pending T003b, T003b giữ [ ] (đúng — chưa bulk).
- File đổi: (reviewer) specs/001-travel-agent-mvp/track.md — thêm entry này; không sửa code coder.
- Cần fix / cần orchestrator quyết: không có. Đề xuất orchestrator: cho merge lane A phase này (diff ~515 dòng, dưới ngưỡng cần tách PR nhỏ hơn nếu tính cả seed JSON) hoặc tiếp tục T003b khi có token.

_(chưa có entry nào)_
