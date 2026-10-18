# Research Brief: Da Nang Itinerary Optimizer — TOPTW + OR-Tools CP-SAT

Nguon: `specs/001-travel-agent-mvp/research.md` (R1, R2, R4, R6, R8), `tasks.md` (T017, T030, T061), `data-model.md`; handoff 2026-10-17; BE POI schema, PATM scorer, OSRM-based eval.
Scope: brief design cho solver 1 ngay Da Nang; khong sua BE code. Model TOPTW/OPTW co 1 depot, time-window, Tmax, objective ket hop diem POI + diem chuyen tiep + thoi gian di chuyen. CP-SAT tim nghiem toi da 5 giay.

## 1. OR-Tools CP-SAT cho TOPTW

### Input
- Tap ung vien `V` sau hard-filter: POI verified, khong nam trong `avoid`, fee khong vuot budget; moi `must_visit` phai con kha thi, neu khong tra infeasible thay vi am tham bo.
- Depot `0`: khach san/diem xuat phat co trong ma tran OSRM. Khuyen nghi MVP coi route dong: bat dau va quay ve depot; neu chon open route thi bo cung depot-return va ghi ro trong benchmark. `tasks.md` T061 hien de depot decision mo, can chot truoc khi wiring.
- Moi POI `i`: `opening_hours`, `visit_min.p50` lam thoi luong lap lich (phu hop R8), `visit_min.p75` de feasibility gate kiem buffer, `fee`, `verified`, utility `r_i` (diem phu hop POI neu pipeline cung cap).
- Ma tran OSRM co huong `tau_ij` (phut) giua depot va POI; khong thay bang haversine. PATM cung cap diem chuyen tiep co huong `q_ij` cho cap POI (T030).
- Trip window `[t_start, t_end]` va `Tmax` (phut). Han ve depot `H = min(t_end, t_start + Tmax)`; opening-hours duoc doi sang phut cung ngay. Neu POI co nhieu khoang mo cua, tach thanh cac lua chon window.
- Hard constraints khac neu co: `must_visit`, `avoid`, ngan sach, precedence `A before B`; rang buoc khong the nhoi vao objective.

### Output
- `status`: OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN; neu timeout ma co incumbent thi tra lich kha thi tot nhat tim duoc, khong goi la optimal.
- Route co thu tu `depot -> POI... -> depot`, gio bat dau/ket thuc moi activity, thoi gian di chuyen, tong thoi luong/chi phi, objective components va violation status.
- Neu infeasible hoac het 5 giay ma chua co incumbent: tra trang thai ro rang, khong tu tao lich vi pham constraint. Feasibility gate doc lap van kiem lai lich, dung p75 buffer theo R8.

### Formula
- Bien: `x_i in {0,1}` = co ghe POI i; `y_ij in {0,1}` = di truc tiep i→j; `s_i` = phut bat dau tham quan i; `u` = co route (bat buoc co itinerary trong MVP). `A` gom cac cung co du lieu OSRM; `A_POI` chi gom cung POI→POI.
- Muc tieu sau khi chuan hoa `r_i, q_ij` ve [0,1]:
  `max Σ_i r_i*x_i + α*Σ_(i,j)∈A_POI q_ij*y_ij - β*Σ_(i,j)∈A (tau_ij/Tmax)*y_ij`.
  `r_i` la diem relevance/quality POI, `q_ij` la PATM transition preference theo huong, `tau_ij` la chi phi thoi gian di chuyen; `α, β >= 0` chot tren development/validation split truoc khi test. Neu chua co POI relevance score thi dat `r_i=0` va ghi ro, khong tu suy ra tu `q_ij`. Quy doi objective sang so nguyen (vi du nhan 1000 va round) truoc khi dua vao CP-SAT.
- Moi POI duoc chon co dung mot cung vao/ra: `Σ_j y_ji = x_i`, `Σ_j y_ij = x_i`; depot co cung ra/vao bang `u`. `x_i=1` voi moi must-visit; `x_i=0` voi avoid/khong kha thi. Ngan sach la constraint tong `Σ_i fee_i*x_i <= budget` (khong chi loc tung POI theo fee). Cac lien ket flow + rang buoc thoi gian loai chu trinh con khi moi duration/travel-time duong.
- `s_i >= t_start` va `s_i + d_i <= H`; voi tung opening interval `[a_ik,b_ik]`, chon dung mot interval neu `x_i=1` va ep `a_ik <= s_i`, `s_i+d_i <= b_ik`. `d_i=visit_min.p50`; gate co the kiem p75 thay cho p50.
- Neu `y_0i=1`: `s_i >= t_start + tau_0i`. Neu `y_ij=1`: `s_j >= s_i + d_i + tau_ij`. Neu `y_i0=1`: `s_i + d_i + tau_i0 <= H`. Trong CP-SAT, moi implication duoc reify bang BoolOnlyEnforceIf hoac big-M hop le; uu tien reification de tranh M qua lon. Precedence `A before B` duoc ep bang thoi gian/thu tu khi ca hai POI duoc chon; voi must-go thi bat buoc ca hai.
- Tat ca thoi gian dung integer minutes; objective chi chon trong cac route thoa constraint. Hard constraints khong duoc doi lay diem so cao.

### Pseudocode
```python
model = cp_model.CpModel()
# Tao x[i], y[i,j], start[i], va bien chon opening interval.
# Noi flow depot <-> POI; bat must_visit, loai avoid/ung vien khong kha thi.
# Ep tong fee[i] * x[i] <= budget; khong chi loc tung POI rieng le.
# Ep opening windows, Tmax, depot legs, precedence va time propagation.
# Ma tran tau_ij lay tu OSRM; d_i = visit_min.p50.
# Objective scores are scaled/rounded to integers before model.maximize.
model.maximize(sum(R[i] * x[i] for i in V)
               + alpha_int * sum(Q[i, j] * y[i, j] for i, j in A_POI)
               - beta_int * sum(T[i, j] * y[i, j] for i, j in A))
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 5.0
status = solver.solve(model)
if status in (OPTIMAL, FEASIBLE):
    itinerary = decode_route_and_schedule(solver, x, y, start)
    assert independent_feasibility_gate(itinerary)  # gate p75 + hard constraints
else:
    return explicit_status(status)  # never fabricate a route
```
- Thuc thi: tao cac bien tren integer domain va objective integer (da scale); cap 5s cho moi request, luu status va wall-clock. Kiem tra chu trinh con bang time propagation tren arc duoc chon, dong thoi dung validator doc lap.

### Metric
- Benchmark tap nho (vi du 7–8 POI/case, depot va OSRM cung mot input): tao exact oracle bang liet ke tat ca route/subset hop le va tinh lai cung objective, cua so gio, duration, precedence, must-go va depot policy. Khong so objective voi oracle khac formulation.
- Objective gap tren case co exact solution `z*` va CP-SAT tra feasible incumbent `z`: `gap_pct = 100 * (z* - z) / max(abs(z*), epsilon)` cho bai toan maximize; neu `z*≈0` thi bao cao absolute gap thay vi %.
- Bao cao cung: hard-feasibility pass rate (muc tieu 100%), so case co incumbent trong 5s, OPTIMAL rate, wall-clock median/p95/max, gap mean/median/p95. Phan biet OPTIMAL (da chung minh toi uu) voi FEASIBLE (incumbent chua chung minh).
- Exact benchmark chi dung tap nho; tren tap production, do feasibility va latency 5s, khong tuyet doi gap voi exact neu khong co oracle.
- Neu exact instance infeasible thi tinh rieng infeasibility agreement; khong dua vao gap. Khong tinh gap cho CP-SAT khong tra feasible solution.

### Applicable (cho MVP Da Nang)
- Hop voi stack da chot: OR-Tools CP-SAT (R1), OSRM directed matrix (R4), POI hours/duration p25-p50-p75 (R8), PATM `q_ij` se noi vao optimizer qua T030; T017 yeu cau depot/flow/Tmax/time-window va timeout 5s. CP-SAT la solver cho lich trinh, khong phai LLM tu sinh route.
- Pham vi MVP la tour 1 ngay; baseline exact tap nho la oracle metric cho solver, khong phai doi thu production. `T061` can chot depot route dong hay mo truoc khi adapter/wiring; bo khong du lieu OSRM thi khong duoc thay bang khoang cach duong chim bay.
- ITINERA/LLM-Modulo chi lien quan o muc ket hop LLM va optimizer; khong can de xuat lai formulation CP-SAT. TravelPlanner, ChinaTravel, TripTide, Gavalas va Righini de danh brief eval/dynamic sau, chi dua vao khi brief do can doi chieu baseline hoac replan.

## 2. Quyet dinh ap dung (Spec Decisions)
- Chon TOPTW/OPTW 1 depot, mot ngay, OR-Tools CP-SAT, hard time windows + Tmax va time limit 5s; depot mac dinh la hotel va de xuat route dong, can xac nhan theo T061.
- Lap lich bang p50; giu p75 cho feasibility gate, khong trộn duration buffer vao objective ma khong ghi ro.
- Objective dung utility POI `r_i`, transition PATM `q_ij` va travel-time penalty; scale thanh integer, chot `alpha/beta` tren development split, khong tune tren test.
- Benchmark solver gap voi exact enumeration tren tap nho, cung formulation/objective; bao cao ca feasibility, timeout/incumbent, objective gap va latency.
- Chua xac dinh numeric `alpha/beta`, cach tao `r_i` cho moi request, policy open-vs-closed route, cung quy tac opening-hours thieu/null. Can chot/ghi assumption trong T017/T061; khong tu xem opening-hours rong la gio mo ca ngay neu chua co policy data.

## 3. Open Questions
- Depot chi la noi xuat phat hay bat buoc quay lai? Chot cung T061 va benchmark truoc khi code.
- POI relevance `r_i` lay tu rule ranker/context nao; normalize/quantize `r_i`, PATM `q_ij`, va chon `alpha/beta` tren split nao?
- `Tmax` la thoi gian tu departure den luc ve depot hay tong gio tham quan? Brief nay de xuat tong elapsed time, tinh ca travel va dwell.
- Opening-hours rong, khong ro ngay trong tuan, qua dem, hoac nhieu interval se duoc chuan hoa/filter the nao? Dinh nghia truc tiep truoc khi lap model.
- Exact oracle gioi han N bao nhieu de enumeration chay duoc tren may test; benchmark can luu seed/input va objective components nao de lap lai?