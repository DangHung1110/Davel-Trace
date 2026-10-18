# Research Brief: Evaluation & Acceptance — Gate, PATM, TravelEval

Nguon: handoff 2026-10-17 muc 4; `specs/001-travel-agent-mvp/tasks.md` T011/T031/T049/T057/T061; `quickstart.md` S1–S7; `BE/eval/metrics.py`, `BE/ml/patm/train.py`, `make_pairs.py`, PATM v4 model card.
Scope: de xuat metric va nguong pass cho gate convergence, chong overfit PATM va map TravelEval sang acceptance scenarios. Khong sua BE code.
Trang thai checkout hien tai: `metrics.py` co 5 check (FAR/VROH/BCS/TCS/HCS), chua co B3/ETB; T061 ghi registry canonical 7 check va `{passed: bool, score: float}`. Thu muc `BE/tests/` co nhung hien khong co file test Python; S1–S7 la scenarios trong spec, chua phai test suite da chay.

## 1. Gate convergence — canonical 7-check registry

### Input
- Itinerary, TripRequest, POI snapshot va OSRM matrix; bo test positive (gold/plan kha thi) va negative (moi test pha dung mot hard constraint).
- Dinh nghia duy nhat theo T061: `FAR`, `VROH`, `B3`, `BCS`, `ETB`, `TCS`, `HCS`. Gate owns registry; evaluator import/call registry, khong tu copy danh sach hoac tu tinh lai cong thuc.
- Check-level result co shape `{passed: bool, score: float}`. `passed` la boolean cho feasibility; `score` la float cho metric/bao cao. Khong dung float nhu bool, khong so `True == 1.0`, khong tinh trung binh de thay the hard gate.

### Output
- Bao cao `checks[name] = {passed, score}`, `all_pass` boolean, danh sach `violations` theo ten check.
- `all_pass = True` chi khi dung du 7 key, moi check co `passed` boolean va finite `score`, va tat ca `passed=True`; thieu/khong hop le check phai fail-closed.
- Gate fail: tra violations co ten, khong co soft-quality scores. Gate pass: evaluator moi tinh/tra soft metrics.

### Formula
| Check | Score / pass threshold de xuat | Dien giai |
|---|---|---|
| FAR | `score <= 1e-12` | Ty le activity tren POI unknown/unverified; muc tieu 0. |
| VROH | `score <= 1e-12` | Ty le activity vi pham opening-hours; muc tieu 0. |
| B3 | `score <= 1e-12` | Giu nguyen B3 legacy rule cua gate; spec chot B3=0 nhung checkout nay khong co `gate.py` de xac nhan numerator/semantics. Khong tu alias B3 thanh STR. |
| BCS | `score >= 1 - 1e-12` | Budget constraint satisfaction; dung cung mot cong thuc o gate va evaluator. |
| ETB | `score >= 1 - 1e-12` | Deadline satisfaction; deadline la `min(end_time, return_time)` trong ngay. `return_time` la hard deadline, khong silent stretch plan. |
| TCS | `score >= 1 - 1e-12` | Khong overlap, moi activity nam trong trip window. |
| HCS | `score >= 1 - 1e-12` | Du `must_visit`, khong ghe `avoid`. |

- Cong thuc score cu the cho B3 va ETB phai doc tu gate implementation canonical khi wiring; cac nguong tren theo data-model/T061 va de xuat fail-closed. Moi `score` luon serialize thanh float (vi du `0.0`/`1.0`), moi `passed`/`all_pass` serialize thanh JSON boolean.
- `all_pass = (set(checks) == REQUIRED_7) and all(type(c.passed) is bool and isfinite(c.score) and c.passed for c in checks.values())`.
- Gate convergence pass khi gate va evaluator cung mot registry/function; 7/7 positive gold pass, moi negative mutant fail dung named check, score nhat quan, va `soft == {}` khi `all_pass == False`.

### Pseudocode
```python
checks = canonical_gate.evaluate(itinerary, trip, pois, matrix)
assert set(checks) == {"FAR", "VROH", "B3", "BCS", "ETB", "TCS", "HCS"}
for check in checks.values():
    assert type(check["passed"]) is bool
    assert isinstance(check["score"], float) and math.isfinite(check["score"])
all_pass = all(check["passed"] for check in checks.values())
violations = [name for name, check in checks.items() if not check["passed"]]
soft = evaluate_soft_metrics(...) if all_pass else {}
```
- Test positive gold (7/7 pass); test tung mutation FAR, VROH, B3, BCS, ETB, TCS, HCS (7/7 bi chan, dung violation); test missing/NaN score, sai kieu `passed`, thieu registry key; test BCS gate/evaluator score equality va `soft` rong khi fail.

### Metric
- Hard-gate pass rate tren positive plans = `passed_plans / valid_plans`; nguong pass 100%.
- Mutation rejection rate = `rejected_invalid / invalid_mutants`; nguong pass 100%, voi named violation dung check bi pha.
- Registry coverage = `checks_present / 7`; nguong 7/7; evaluator-gate divergence = 0; soft-score leakage tren failure = 0.
- Bao cao tung check, khong chi aggregate `all_pass`; float rounding tolerance chi ap dung cho threshold score, khong ap dung cho boolean `passed`.

### Applicable (cho MVP Da Nang)
- T061(f) la nguon chot ve registry: FAR/VROH/B3/BCS/ETB/TCS/HCS; gate la single source of truth, evaluator doc `score`, gate doc `passed`. Handoff quy dinh gate before score va phai giu constraints goc sau toi da 2 vong repair.
- `BE/eval/metrics.py` hien tai co FAR/VROH/BCS/TCS/HCS (5 check), dung so sanh exact voi expected values, chua co B3/ETB hay `all_pass`/check payload. T061 convergence chua duoc chung minh trong checkout nay.

## 2. PATM — kiem tra chong hoc vet

### Input
- Pair dataset co unordered pair group, label `1/0/-1`, source (rule/LLM/human), POI IDs, snapshot id va context; model PATM v4 va rule scorer baseline.
- Split phai theo unordered pair group de mirror twins khong roi vao train/eval khac nhau. Leave-POI-out giu nguyen 20% POI ids; moi pair cham vao held POI deu vao eval, khong de POI held xuat hien trong train.
- Dung held-out human labels (hoac gold da swap-check) de ket luan chat luong; rule-generated smoke accuracy chi kiem pipeline, khong phai bang chung quality.

### Output
- `pairwise_accuracy`, `flip_consistency`, `leave_poi_out_accuracy`, `rule_baseline_accuracy`, `delta_vs_rule`, so mau/source, split seed, leakage count va confidence interval.
- Bao cao ties rieng: trainer hien bo label 0 khi fit; pairwise accuracy decisive tinh tren label ±1, tie accuracy/coverage ghi rieng, khong vo hieu hoa tie bang cach bo khoi report.

### Formula
- Pairwise accuracy tren decisive held-out pairs: `Acc = count(pred == y for y in {-1,+1}) / N_decisive`. PASS de xuat: `Acc >= 0.70` tren held-out va mean group-CV; dong thoi bao cao accuracy rieng tren human labels.
- Flip consistency: voi moi cap (a,b), tao lai feature `x_ab=extract(a,b)` va `x_ba=extract(b,a)`; doi prediction ve nhan `+1/-1/0` (neu model binary thi map hai lop sang `+1/-1`, tie band phai chot truoc); tinh `FC = count(pred(x_ab) == -pred(x_ba)) / N_pairs`, trong do tie doi tie. PASS de xuat: `FC >= 0.80`.
- Leave-POI-out: chia POI ID thanh 5 folds xap xi 20% held moi fold; tat ca pair co mot dau la held chi nam trong eval. `LPO-Acc = mean(acc_fold)`; PASS de xuat `>=0.70`, leakage count = 0.
- Rule baseline: cung held-out human pairs va cung metric, `delta = Acc_PATM - Acc_rule`. De xuat chi nang PATM thanh scorer chinh neu `Acc_PATM >= max(0.70, Acc_rule + 0.03)` tren human eval; neu chua hon rule thi giu rule fallback. Bao cao bootstrap CI theo unordered-pair group; khong tuning tren test.
- Nguong 0.70/0.80/+3pp la nguong van hanh de xuat cho brief, khong phai nguong da ghi trong spec. Threshold duoc chot truoc final test; neu human sample qua nho thi them CI va danh dau inconclusive thay vi tu ha nguong.

### Pseudocode
```python
train, eval_ = split_by_unordered_pair_group(pairs)
assert not mirror_group_leak(train, eval_)
cv = grouped_cv_accuracy(train, folds=5, ties="report_separately")

for poi_fold in five_poi_id_folds(all_poi_ids, held_fraction=0.20):
    tr, va = leave_poi_out_split(pairs, held_ids=poi_fold)
    assert not (poi_ids(tr) & poi_fold)
    score_lpo(model, tr, va)

for a, b in eval_pairs:
    p_ab = to_signed_label(predict(extract(a, b)))
    p_ba = to_signed_label(predict(extract(b, a)))  # recompute real reverse features
    record_flip(p_ab == -p_ba)
compare_on_same_human_pairs(PATM, rule_scorer)
```
- Khong dung `-x_ab` lam feature cua pair dao chieu neu extractor co feature symmetric/context. `features.py` danh dau `x_same_type` la swap-invariant; user/context features cung khong phai tat ca deu negated. `train.py` hien flip-check bang `neg = -Xn[i]`, nen metric nay can duoc xac nhan lai bang `extract(b,a)` truoc khi coi la release evidence.

### Metric
- Nguong de xuat: held-out decisive accuracy ≥0.70; group-CV accuracy ≥0.70; flip consistency ≥0.80; leave-POI-out accuracy ≥0.70 va 0 leakage; PATM human accuracy hon rule ≥3 percentage points (dong thoi PATM ≥0.70).
- Bao cao seed/fold va support count; tie rate; accuracy theo source; human-only accuracy; confusion matrix neu co tie prediction; bootstrap 95% CI theo group. Rule-label smoke chi ghi “pipeline check”, khong dung de tuyen bo ranker tot.
- Hien co PATM v4: 5-fold CV 0.793, held-out 0.777 (n=345), flip 0.728; model card ghi leave-POI-out split train 1371/eval 805, 0 leaked nhung chua ghi accuracy tren split do. Chua co metric rule-vs-PATM tren cung human test. Theo nguong de xuat: CV/held-out dat, flip chua dat, LPO va rule-baseline chua du du lieu de ket luan.

### Applicable (cho MVP Da Nang)
- Khop voi T031 va PATM v4: pairwise accuracy, flip, leave-POI-out tren 20% POI. `make_pairs.py` da co split chong POI leakage; `train.py` co group CV/held-out, nhung LPO prediction accuracy va rule baseline chua co trong model card.
- V4 ket hop 1000 rule + 973 Qwen judge + 178 human pairs. Giu rule scorer lam fallback cho POI chua du pair; khong promote model chi vi no hoc tot rule-generated labels. Flip 0.728 la canh bao cu the, khong nen che bang accuracy trung binh.

## 3. TravelEval tiers anh xa sang acceptance S1–S7

### Input
- Quickstart seed 7 POI, matrix 7×7 va cac fixture co the tai lap; S1–S7 trong `specs/001-travel-agent-mvp/quickstart.md`.
- Tang danh gia theo R6/handoff: (1) solver + feasibility, (2) tuan thu yeu cau/lich hop ly, (3) replan, (4) explanation tieng Viet. S1–S7 la acceptance smoke, khong thay the bo 30–50 query Da Nang cho tier evaluator.

### Output
- Moi scenario co `scenario_id`, result, expected/actual, hard-gate checks, soft metrics khi gate pass, latency va failure reason.
- Tong ket S1–S7 green/red; dong thoi tier-level report cho exact gap/feasibility, itinerary adherence, replan preservation/response/deviation va explanation audit.

### Formula
| Tier / scenario | Mapping va dieu kien pass |
|---|---|
| Tier 1 — solver/feasibility; S3, S4 + benchmark rieng | S3: tra ≥2 plans kha thi (savings/balanced/experience), tat ca pass canonical 7-check gate. S4: moi tamper bi reject dung check va khong co soft scores. Tren tap nho: gap voi exact, feasibility 100%, timeout ≤5s; R6/handoff chua dat nguong so cho gap, de xuat mean gap ≤5% va p95 solve time ≤5s (ghi la muc tieu de xuat). |
| Tier 2 — tuan thu y dinh; S2, S3, S7 | S2 parse ra schema hop le hoac liet ke slot can hoi lai; khong tu dien hard slot thieu. S3 phai giu must/avoid/budget/window; voi truy van hiking-before-beach, order preference dat 100% neu kha thi. S7: `score(hike,beach) > score(beach,hike)`. Hard constraints 100%; SSR bao cao rieng tren tap query. |
| Tier 3 — replan; S5 | Giu 100% activity da done, version tang dung 1, khong duplicate, recheck 7 hard gates va ETB deadline. Rain fixture S5 phai thay/loai outdoor remainder va ghi ly do; chi chap nhan clarify/no_solution neu fixture that su infeasible. Bao cao TripTide-style intent retention, event response va plan deviation; cong thuc/nguong so chi tiet de danh dynamic brief tiep theo. |
| Tier 4 — explanation; S3/S4 + audit | Moi activity/decision co ≥1 evidence tren S3; khong them factual claim sai ve ten/giờ/phi khi doi snapshot; S4 gate fail thi khong sinh quality/explanation claim nhu plan hop le. Chay audit tay 30–50 lich, LLM judge chi ho tro, khong thay human spot-check. |
| Cross-cutting acceptance | S1: health HTTP 200 va `{status: ok, snapshot: danang-v1}`. S6: budget 3,000,000 − expense 2,500,000 = con 500,000; alert 83%/threshold 80%. Tat ca response JSON/schema dung contract. |

### Pseudocode
```python
for scenario in quickstart_s1_to_s7(seed_fixture):
    result = run_scenario(scenario)
    assert result.matches_expected_contract
    if result.has_itinerary:
        gate = canonical_gate.evaluate(result.itinerary, scenario.trip, pois, matrix)
        assert gate.all_pass if scenario.requires_feasible_plan else scenario.expects_rejection
    if scenario.id == "S4":
        assert result.gate.violations == [scenario.expected_check]
        assert result.soft == {}
    if scenario.id == "S5":
        assert completed_activities_unchanged(result)
        assert result.version == scenario.previous_version + 1
        assert within_deadline(result, min(end_time, return_time))
    record(result, latency=True, tier=map_to_tier(scenario.id))
```

### Metric
- S1–S7 smoke pass rate: 7/7; hard-gate pass/reject behavior: 100%; output contract match: 100%; no soft scores after failed gate.
- Solver small-set: feasibility 100%, max wall clock ≤5s; provisional objective gap mean ≤5% vs exact (nguong de xuat, chua co trong spec).
- Preference case S3/S7: correct order 100% cho targeted pair, PATM score margin strictly positive; report other order prefs as SSR, not only this one fixture.
- Replan S5: completed-item preservation 100%, version delta exactly +1, no duplicate POI, deadline violation 0. TripTide aggregate thresholds remain open until dynamic brief specifies the protocol.
- Explanation audit: evidence coverage 100% in the fixed sample; report factual error count separately, target 0 verified factual errors. With 30–50 itineraries, report numerator/denominator and human adjudication, not LLM-judge score alone.
- S1–S7 are acceptance fixtures, not statistical evaluation; add 30–50 Da Nang queries for tier-level claims. Numerical thresholds marked “de xuat” need approval before final test set is inspected.

### Applicable (cho MVP Da Nang)
- Scenario names and expected behavior are grounded in `quickstart.md`: S1 health, S2 parse, S3 multi-plan, S4 tampered-plan gate, S5 rain replan, S6 expense, S7 PATM. R6 requires deterministic tier-1 metrics first, LLM-judge second, 30–50 Da Nang test cases; the handoff organizes quality into solver, instruction-following, replan and Vietnamese explanations.
- Current checkout has no Python test files under `BE/tests/`, while spec `T057` requires full S1–S7 green. Add the scenario tests as implementation work; this brief does not claim tests have run.

## 4. Quyet dinh ap dung (Evaluation Decisions)
- Chot gate output type: seven canonical checks, each `{passed: bool, score: float}`; `all_pass` is boolean AND of all seven `passed`; no soft score when false.
- Hard feasibility/gate and S1–S7 scenario pass target 100%; B3 threshold remains 0 per spec, semantics must be sourced from canonical gate implementation.
- PATM promotion requires group-safe evaluation, real reverse-feature flip test, 20% leave-POI-out with zero leakage, human-set comparison to rule baseline. Thresholds 0.70/0.80/+3pp are proposed; v4 flip 0.728 currently misses the proposed threshold.
- Tier-3 TripTide metric definitions and exact-gap acceptance threshold are not fixed by source documents; provisional gap target ≤5% and detailed dynamic thresholds to be confirmed in the next brief.

## 5. Open Questions
- B3 legacy score numerator and precise ETB scoring must be copied from the canonical lane-B `gate.py`; that file is not present in this checkout. Keep the evaluator from inventing an alternate definition.
- Confirm proposed PATM cutoffs (0.70 accuracy, 0.80 flip, +3pp vs rule) and whether final release requires bootstrap CI lower bound above zero.
- Confirm solver exact-gap threshold and tier-2 cohort SSR threshold; S1–S7 alone do not provide statistical power.
- Define TripTide-compatible formulas, rain/delay/closure fixtures, event-response threshold and deviation window in the dynamic brief.

## 6. Brief tiep theo: Dynamic Replan Evaluation
- De xuat `docs/research_brief_dynamic.md`: S5 rolling-horizon eval, preserve completed/must-go intents, response to rain/delay/closure, deadline `min(end_time, return_time)`, versioning/no-duplicate invariants, Plan/Clarify/NoSolution correctness; define TripTide-style intent retention, event response, plan deviation metrics and thresholds; add repeatable scripted event fixtures and report gate/latency after every replan.