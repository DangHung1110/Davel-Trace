# Research Brief: POI Recommender — IntTravel + Think2Go

Nguon: DavelAgentIdea.txt muc D2 (notebook_02_poi_recommender), E, F, N, O.
Papers: IntTravel (arXiv:2602.11664v2, Amap 2026) + Think2Go (KDD 2026, arXiv:2607.28997).
Scope: chi trich xuat phan dung cho POI/restaurant recommender + PATM. Khong sua BE code.

## 1. IntTravel

### Input
- Sequence 3 loai token: S (scenario: thoi gian, block dia ly, thoi tiet), I (item: lich su POI tuong tac theo thoi gian), F (feedback: click/order/route-plan/navi theo tung item).
- User profile an danh hoa (6 feature roi rac thanh integer ID, khong dich nguoc y nghia).
- POI attrs: Nscore (0-1 popularity), GID (block dia ly), CID (category ID), ARID (region ID), toa do 2D an danh (giu tuong quan, khong phai lat/lon that).
- 4 nhiem vu dung chung 1 input sequence, label gan rieng: When/How/Where gan tren token S (chi dung context + qua khu); Via gan tren token I (dieu kien tren destination da biet).

### Output
- 4 dau ra sinh dang generative decoder-only: When (thoi diem khoi hanh), Where (POI dich tiep theo), How (mode: drive/walk/transit), Via (POI ghe doc duong).
- Online metric bao cao: +1.09% CTR vs baseline generative don nhiem tren Amap.

### Formula
- Framework 3 khoi (mo ta kien truc, khong cong bo cong thuc chi tiet trong trich doan doc duoc):
  1. Task-Guided Information Persistence: lam giau hyper-connection bang thuoc tinh task de giu thong tin xuyen tang.
  2. Task-Specific Selective Gating: gate chon thong tin da tang, phu hop tung muc encoding cho tung task.
  3. Task-Aware Scenario Factorization: tron output 2 khoi tren bang experts shared + separate (can bang kien thuc chung vs dac thu task).
- Y nghia: giai quyet van de multi-task truyen thong (encode chung roi tach sau lam mat tinh doc lap task trong Transformer) — dua task-singal vao ngay trong encoding layers.

### Pseudocode
```python
seq = build_sequence(S_tokens, I_tokens, F_tokens)  # chung cho 4 task
h = decoder_only_backbone(seq)
h_persist = task_guided_persistence(h, task_id)     # task in {when,where,how,via}
h_select = selective_gating(h, task_id)             # multi-scale per task
logits = factorized_experts(h_persist, h_select, shared=True, specific=True)
loss = sum(task_weight[t] * CE(logits[t], label[t]) for t in tasks)
# inference: sinh token ke tiep cho task duoc hoi (when/where/how/via)
```

### Metric
- Offline: so voi multi-task DL baselines tren dataset IntTravel (chi tiet metric Recall/NDCG trong ban full; trich doan chi khang dinh vuot toan bo baseline).
- Online: A/B test CTR tren Amap (+1.09% relative).
- Dataset scale: 163M users, 7.3M POIs, 4.1B interactions, 90 ngay, 10 city TQ. Link: github AMAP-ML/DreamX-Rec + HF GD-ML/IntTravel_dataset.

### Applicable (cho MVP Da Nang)
- Lay: y tuong 4-task When/Where/How/Via -> anh xa sang trip state (gio khoi hanh, POI, mode, via/restaurant doc duong); cau truc token S/I/F -> schema context + history + feedback cho PATM/ranker; cach gan label chong leakage (chi dung qua khu + context hien tai).
- Khong lay: toan bo data Amap (khong public day du y nghia profile, toa do an danh, chi 10 city TQ); mo hinh generative nang (qua suc MVP, PATM-LightGBM van la core); Nscore cong thuc kin (chi coi la popularity feature).
- Tuong thich DavelAgentIdea: E2 (user+context+POI/transition -> relevance score), E6 (ghi dataset/link/license/split), K-recommender (Recall@K, NDCG@K, MRR giu lam metric recommender).

## 2. Think2Go

### Input
- Prompt: lich su check-in user (POI sequence + thoi gian) + temporal cue (thoi diem muon du doan) + Semantic IDs (SID: ID khoi tao co ngu nghia dia ly/chuc nang gan nhau).
- Lich su dung de tinh epistemic uncertainty (kernel density estimation do can pho khong-thoi gian giua query hien tai vs lich su).

### Output
- Sinh truc tiep ID cua next-POI (generative, khong qua scoring tat ca candidates).
- Dinh dang sinh co cau truc: Think -> Go -> Self-Correct -> Answer. Answer dung tinh SFT loss; Think+Go la reasoning trajectory toi uu bang policy gradient.

### Formula
- Unified SFT+RL: L = L_SFT(Answer) + L_PG(Think,Go) voi advantage da hieu chinh.
- (1) Prompt epistemic uncertainty weighting: u = KDE(query spatio-temporal, history); advantage nhan he so tang theo u (kho -> explore nhieu hon).
- (2) Reward-informed advantage scaling: r_norm = r / r_max trong group (vi du cung advantage [0.33,0.33,-0.67] cho 2 group kho/de neu khong chuan hoa theo max -> phai scale theo max de phan biet do kho).
- Ket hop 2 co che = implicit curriculum learning, instance-aware update, chong entropy collapse.
- SID hieu sau hon nho hoc chung (joint) chu khong pretrain tach roi nhu GNPR.

### Pseudocode
```python
sid = semantic_id_init(pois)  # dia ly/chuc nang gan nhau -> id gan nhau
for batch in data:
    out = llm.generate(prompt(history, time_cue, sid), pattern="Think->Go->SelfCorrect->Answer")
    r = reward(out.Answer, gold_next_poi)
    u = kde_uncertainty(query_st, history_st)   # prompt-aware
    adv = group_advantage(r) * f(u) * (r / r_max)  # + difficulty-aware
    loss = CE(out.Answer, gold) + PG_loss(out.ThinkGo, adv)
    update(llm, loss)
```

### Metric
- 3 real-world datasets (Foursquare-style check-in), khang dinh generalize tot + hieu SID tot hon (chi tiet Recall/NDCG/ACC trong ban full 12 trang).
- Can trich them tu PDF full khi lam brief sau: so baseline GNPR/LLM4POI, ablation 2 co che weighting, SID category discrimination test.
- Code: Zenodo doi 10.5281/zenodo.18206701.

### Applicable (cho MVP Da Nang)
- Lay: pattern Think->Go->SelfCorrect->Answer cho parser/judge/explanation local (Qwen3 tren MacBook, muc O3); swap-check trong PATM labeling chinh la dang self-correct don gian; KDE uncertainty -> y tuong gan uncertainty cho POI/thoi gian thieu (FR-013, FR-026); SID gan nhau theo dia ly/chuc nang -> y tuong alias/category embedding Da Nang (Cau Rong/Dragon Bridge, Ba Na/Sun World, muc N3.3).
- Khong lay: full RL reasoning (can GPU, unstable data nho — cung ket luan nhu I.0 cam GRPO/RL); next-POI sinh truc tiep (MVP rank tren candidates co dinh + OR-Tools, khong sinh ID tu do de tranh POI ao FR-009).
- Tuong thich DavelAgentIdea: D2 muc 13 (bien preference "yen tinh/hop hen ho/sau hiking" thanh feature — Think2Go goi y dua vao prompt + SID); K-recommender (Pairwise Accuracy, Preference Satisfaction, Activity Order Accuracy).

## 3. Quyet dinh ap dung (Spec Decisions)
- PATM giu LightGBM pairwise (I.0, N1.3); khong thay bang IntTravel-generative hay Think2Go-RL trong MVP.
- Lay tu 2 paper: schema S/I/F + 4-task mapping (IntTravel), self-correct/swap-check + uncertainty flag + SID gan nhau (Think2Go).
- Metric recommender chot theo K: Recall@K, NDCG@K, MRR, Pairwise Accuracy, Preference Satisfaction, Activity Order Accuracy.
- Open: doc full PDF de lay cong thuc loss/GNN gate va bang metric chi tiet; doi co POI snapshot DN 100-200 (N3.1) moi map feature CID/GID/Nscore that.

## 4. Open Questions
- IntTravel: cong thuc Nscore? Task weights? Metric offline cu the theo tung task?
- Think2Go: reward dung gi (hit/NDCG)? KDE bandwidth bao nhieu? Baseline so sanh chi tiet?
- Ca 2: code co chay duoc CPU-only khong, dependency gi (can check entry point theo E7)?
