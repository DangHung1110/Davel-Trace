# Ổn định planner: 6 hướng thực thi + paper đi kèm

Ngày chốt: 28/10/2026. Checkpoint: `2732fce` trên `feat/profile-templates-onboarding`.
Nguồn: `stable_planning_papers.md` + wave-2 `inverse_opt_deep_dive.md`, `judge_rerank_calibration.md` (tất cả link đã verify live 28/10).

Bệnh gốc: mỗi lỗi test → vá 1 rule/cân 1 weight (~15 rule chồng nhau, tương tác không lường được).
Paper gọi tên: correction cascades — Sculley et al., NeurIPS 2015.

---

## 1. Đóng băng + gộp rule (dọn sân)

**Mục đích:** dừng vòng vá víu; xóa rule trùng lặp; giữ ~5 gate cứng (giờ, tiền, di chuyển, an toàn/mở cửa).
**Cải thiện:** hết sập chỗ này khi sửa chỗ kia; codebase đứng yên để đo các bước sau.
**Giá / rủi ro:** rẻ nhất / thấp.
**Paper:**
- Sculley et al., "Hidden Technical Debt in Machine Learning Systems," NeurIPS 2015 — https://proceedings.neurips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html (correction cascades / pipeline jungles — đúng kiểu vá rule của mình)
- Oh et al., "Flex-TravelPlanner," arXiv 2025 — https://arxiv.org/abs/2506.04649 (joint-feasibility là bottleneck → ít gate nhưng cứng + 1 scorer)

## 2. Log plan được chấp nhận (thu data)

**Mục đích:** mỗi plan được chốt (harness bấm "chốt") lưu thành mẫu tốt: query + plan + timestamps + phán xét.
**Cải thiện:** nguyên liệu cho hướng 4 (học weight cần 150+ cặp) và hướng 5 (RAG cần 50–200 ngày tốt). Không log thì 2 hướng đó không có gì ăn.
**Giá / rủi ro:** rẻ / thấp. Chỉ thêm nút "chốt" + bảng log, không đụng solver.

## 3. LLM rank N plan hoàn chỉnh (chọn, không lắp)

**Mục đích:** solver sinh 5 ứng viên feasible (diverse beams) → LLM chỉ rank/pick, không lắp từng bước. Chạy shadow trước, live sau.
**Cải thiện:** nuốt các lỗi "cảm tính" khó formal hóa thành rule (nhịp ngày, trông vội, trade-off dở); đồng thời đẻ data A/B miễn phí cho hướng 4.
**Không thay review:** rank chọn hay nhất trong N, review veto plan lỗi. Rank chạy trước, review duyệt sau.
**Giá / rủi ro:** nhỏ (giữ solver, thêm 1 prompt rank) / thấp ở shadow.
**Paper:**
- Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," NeurIPS 2023 — https://arxiv.org/abs/2306.05685 (judge ~80% agree human + bias vị trí/dài dòng + cost baseline)
- Jiang et al., "LLM-Blender," arXiv 2023 (ACL 2023) — https://arxiv.org/abs/2306.02561 (pairwise-rank-then-fuse — template gần nhất với "rank 5 plan")
- Pradeep et al., "RankVicuna," arXiv 2023 — https://arxiv.org/abs/2309.15088 (listwise prompt + open-model cost/latency)
- Sun et al., "RankGPT," EMNLP 2023 — https://arxiv.org/abs/2304.09542 (permutation-generation listwise)
- Cobbe et al., "Training Verifiers to Solve Math Word Problems," arXiv 2021 — https://arxiv.org/abs/2110.14168 (generate-many + verifier-picks-best thắng generator to hơn)
- Wang et al., "Self-Consistency," ICLR 2023 — https://arxiv.org/abs/2203.11171 + Yao et al., "Tree of Thoughts," 2023 — https://arxiv.org/abs/2305.10601 (sample-diverse rồi select là pattern thắng)

## 4. Học weight từ phán xét/demos (thay cân tay)

**Mục đích:** coi ~15 soft weight + POI profit là tham số, fit từ dữ liệu thay vì chỉnh tay.
**Cải thiện:** hết cân số mò; weight nào cũng có bằng chứng đứng sau; pool đổi thì refit thay vì đoán.
**Thang 3 nấc (rẻ → đắt):**
- Rung 1 — Bradley-Terry trên ~150 cặp A/B: `P(A≻B) = σ(θᵀφ(A) − θᵀφ(B))`, logistic regression sklearn, seconds. Promote khi held-out ≥70% + mismatch scorer-vs-solver <25%.
- Rung 2 — Chow-style: 40+ ngày full có timestamp, calibrate khối meal/walk/backtrack, minutes–hours.
- Rung 3 — full inverse-opt với CP-SAT trong loop: chỉ khi solve <2s + demos hàng trăm.
- Guard: fix scale (walk=1.0), ℓ₂ C≈0.5–2, split val theo tuần, feature relative, refit khi pool churn >20%.
**Giá / rủi ro:** nhỏ→vừa / thấp→vừa (cần 100–300 demos sạch; giám khảo ồn → overfit; giữ weight tay làm prior).
**Paper:**
- Chow & Recker, "Inverse optimization with endogenous arrival time constraints…," Trans. Res. Part B 2012 — https://doi.org/10.1016/j.trb.2011.11.005 (template gần nhất: calibrate utility đi lại/sinh hoạt từ pattern quan sát)
- Aswani, Shen & Siddiq, "Inverse Optimization with Noisy Data," Operations Research 2018 — https://doi.org/10.1287/opre.2017.1705 ; preprint https://arxiv.org/abs/1507.03266 (judge ồn: de-noise + regularization, estimator consistent)
- Esfahani et al., "Data-driven inverse optimization with imperfect information," Math. Programming 2018 — https://doi.org/10.1007/s10107-017-1216-6 (DRO: demos cũ/pool đổi thì đừng tin hẳn)
- Scroccaro et al., "Inverse Optimization for Routing Problems," Trans. Science 2024 — https://doi.org/10.1287/trsc.2023.0241 ; preprint https://arxiv.org/abs/2307.07357 (IO cho routing, rank 2/48 Amazon Last-Mile — rung đắt nhất)
- Chan, Mahmood & Zhu, "Inverse Optimization: Theory and Applications" (survey), Operations Research 2023 — https://doi.org/10.1287/opre.2022.0382 ; preprint https://arxiv.org/abs/2109.03920 (taxonomy classical IO)
- Rafailov et al., "Direct Preference Optimization," 2023/NeurIPS 2024 — https://arxiv.org/abs/2305.18290 (pairwise-preference → reward, template cho day-quality scorer)
- Bradley & Terry, Biometrika 1952 — https://doi.org/10.1093/biomet/39.3-4.324 (gốc pairwise comparison)
- Chen et al., Annals of Statistics 2019 — https://doi.org/10.1214/18-aos1745 (top-K ranking cần Ω(K log K) comparisons)
- Vansteenwegen et al., "The orienteering problem: A survey," EJOR 2011 — https://doi.org/10.1016/j.ejor.2010.03.045 + Gunawan et al., EJOR 2016 — https://doi.org/10.1016/j.ejor.2016.04.059 (thuật ngữ profit/time-window)

## 5. RAG khung ngày (mượn ngày tốt, không giải từ số 0)

**Mục đích:** retrieve K ngày tốt quá khứ (cùng city, ràng buộc giống) → giữ skeleton (thứ tự, slot ăn, cụm khu vực) → re-ground POI/giờ → solver repair.
**Cải thiện:** hấp thụ cả cụm soft-penalty địa lý/nhịp ngày một lúc (vì ngày tốt cũ đã thể hiện sẵn), thay vì vá từng cái lẻ. Giữ hard gate giờ/tiền/di chuyển làm check deterministic.
**Điều kiện:** cần thư viện 50–200 ngày tốt (từ hướng 2) — chưa có thì chưa làm được.
**Giá / rủi ro:** vừa / vừa (thiên vị chỗ nổi tiếng, data cũ, cold-start city mới; cần freshness filter + repair-or-reject).
**Paper:**
- Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," NeurIPS 2020 — https://arxiv.org/abs/2005.11401 (nền RAG)
- Xie et al., "TravelPlanner," arXiv 2024 — https://arxiv.org/abs/2402.01622 (agent rớt joint-feasibility — đúng bệnh sinh rule vá; động lực retrieve-skeleton + repair)
- Gadbail et al., "Iti-Validator," arXiv 2025 — https://arxiv.org/abs/2510.24719 (validator-then-correct = nửa repair của retrieve-and-adapt)

## 6. Judge calibration (khóa ranker khỏi bias)

**Mục đích:** trị bias của chính ranker hướng 3 + đặt gate promote bằng số.
**Cải thiện:** ranker không thành lỗi mới; chỉ lên live khi số liệu shadow đạt.
**Cách trị (đã có evidence):**
- Position bias: gọi 2 orders, win chỉ khi thắng cả 2 else tie + shuffle seed logged. Gate: swap-consistency ≥0.85.
- Verbosity: length-neutral + conciseness penalty + verifier-score break tie; monitor Spearman(length, rank) >0.3 báo động, padded-canary pick ≤10%.
- Brand-name (POI nổi tiếng): blind pass-1 (IDs+facts) → named veto-only pass-2; blind/named top-1 agreement ≥85%.
- Cost 5 plans: live listwise ~3–6k tok; shadow pairwise full+swap ~28k; top-2 runoff ~8–15k khi margin mỏng. Cache key = hash(query + plan-set + rubric ver).
- Promote sau 2 tuần liên tiếp n≥200: top-1 agreement ≥75% (ceiling human–human 81%), swap ≥0.85, veto rate ≤ baseline, không bias probe regress.
**Paper:** như hướng 3, cộng:
- Wang et al., "FairEval (LLMs are not Fair Evaluators)," arXiv 2023 — https://arxiv.org/abs/2305.17926 (đảo thứ tự lật Vicuna-13B thắng ChatGPT 66/80; Balanced Position Calibration)
- Pradeep et al., "RankZephyr," arXiv 2023 — https://arxiv.org/abs/2312.02724 (listwise robust, gian cách với GPT-4)
- FastChat `judge_prompts.jsonl` (pair-v2/single-v1, `[[A]]/[[B]]/[[C]]`), MIT — https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/data/judge_prompts.jsonl

---

## Thứ tự thi công (không đảo, đo sau mỗi bước)

1. Hướng 1 + 2 + 3-shadow (1 lane, đều nhỏ, không đụng solver core)
2. Đủ ~150 phán xét → hướng 4 rung 1 (weight tay làm prior)
3. Đủ 40+ ngày full → hướng 4 rung 2; full IO chỉ khi đủ scale
4. Đủ thư viện ngày tốt → hướng 5 (RAG)
5. Hướng 6 chạy xuyên suốt từ khi có ranker shadow (gate promote)
6. Lát 2 cũ (khung V2, verify bar/museum, PATM pilot) xếp sau 1–5

## Khoảng trống trung thực (không bịa citation)

1. Không có paper "retrieve-and-adapt whole day skeleton" đặt tên chính thức.
2. Không có controlled study "1 utility + few gates vs dozens hand rules" cho routing.
3. Không có study travel-specific "rank 5 feasible plans" về accuracy/cost (số judge từ QA/chat/search/math, chuyển qua bằng analogy).
4. Không có dataset/method "learning-to-rank POI profit từ pairwise human" cho orienteering (DPO là template, ứng dụng POI-profit chưa cite).
5. POI-brand bias: NO-CITATION (xử bằng analogy label-bias, không claim là fact).
6. Ngưỡng chunk listwise n≈10: engineering rule, không phải claim paper.
