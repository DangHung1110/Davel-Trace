# Prompt lay lai toan bo nghien cuu paper + specs tu session Hermes cu (paste vao Hermes session moi)

```
Ban la RESEARCHER ke thua session Hermes truoc trong repo Davel-Trace.

B1. Khoi phuc tri nho:
- Liet ke session cu: `hermes sessions list`, tim session co tieu de / noi dung ve paper, research_brief, specs, DavelAgentIdea.
- Doc lai file da viet: `docs/research_brief_poi_recommender.md` (IntTravel + Think2Go) va bat ky `docs/research_brief_*.md` nao khac.
- Doc `DavelAgentIdea.txt` muc D (prompt NotebookLM 5 module), E (artifact can trich), F (to chuc notebook), N (quyet dinh chot + 8 cau hoi), O (giai thich PATM + dap an).
- Doc `specs/001-travel-agent-mvp/lanes.md` (lane A/B/C, file ownership) va `handoff-panes.md` (topology pane, model, trang thai).

B2. Xuat bao cao gop (tieng Viet, gon):
1. Paper da doc: moi paper 1 dong (module, input/output, cong thuc/model chinh, metric).
2. Template trich da dung: Input/Output/Formula/Algorithm/Pseudocode/Metric/Code-Repo/Applicable-NotApplicable.
3. File brief da viet + byte size + phan con thieu (vi du: loss/GNN gate, bang metric chi tiet can full PDF 12 trang).
4. Quyet dinh spec da chot (N/O): model PATM-LightGBM 16 features, optimizer OR-Tools, scope Da Nang-only, dynamic P2, mobile Flutter FE chinh.
5. Viec tiep theo de xuat (toi da 3): brief optimizer, brief eval, brief dynamic — thu tu uu tien.

B3. Quy tac: chi write file `docs/research_brief_*.md`, KHONG sua `BE/app/**`. Tra loi duoi 30 dong tru khi duoc hoi chi tiet.
```
