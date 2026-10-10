"""Render human-verify set as an offline single-file HTML form (lane A).

Reads human_verify_200.jsonl + pois.json, writes human_verify_200.html:
200 cards with rich POI detail, A/hòa/B radios, progress counter,
filter (all/disagree/unanswered), Export-JSON button producing
[{pair_n, human}] for ingest (source=human).

Usage: python BE/ml/patm/render_verify.py --snapshot BE/data/snapshots/danang-v1
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

LBL = {1: "A trước", 0: "hòa", -1: "B trước"}


def haversine_km(a: dict, b: dict) -> float:
    r = 6371.0
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp = math.radians(b["lat"] - a["lat"])
    dl = math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def detail(p: dict) -> str:
    st = p.get("smart_tags") or {}
    vm = p.get("visit_min") or {}
    rows = [
        ("Loại", f"{p.get('type', '?')}"),
        ("Rating", str(p.get("rating") if p.get("rating") is not None else "chưa có")),
        ("Thời lượng ước tính", f"~{vm.get('p25', '?')}–{vm.get('p75', '?')} phút (độ tin cậy thấp)" if vm else "chưa có"),
        ("Giờ mở cửa", ", ".join(p.get("opening_hours") or ["chưa rõ"])
         + (f" (nguồn: {p.get('hours_source', 'crawl')})" if p.get("opening_hours") else "")),
        ("Vé", (f"{p['ticket_vnd']:,}đ".replace(",", ".") if p.get("ticket_vnd")
                else ("có vé (chưa rõ giá)" if st.get("ticket") is True
                      else ("không vé" if st.get("ticket") is False else "chưa rõ")))
         + (f" — {p['ticket_note']}" if p.get("ticket_note") else "")),
    ]
    io = {"I": "indoor", "O": "outdoor", "B": "both"}.get(p.get("io_label") or "")
    space = io or st.get("space") or ""
    space_vn = {"indoor": "trong nhà", "outdoor": "ngoài trời",
                "both": "cả hai"}.get(space, "chưa rõ")
    rows.append(("Không gian", space_vn
                 + (" — mưa vẫn đi được" if "rain-proof" in (st.get("time") or []) else "")))
    rows.extend([
        ("Hợp đi với", ", ".join(st.get("party") or ["chưa rõ"])),
        ("Thời điểm đẹp", ", ".join(st.get("time") or ["chưa rõ"])),
        ("Quỹ thời gian", ", ".join(st.get("budget") or ["chưa rõ"])),
    ])
    return "".join(f"<div class='r'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>"
                   for k, v in rows)


PAGE = """<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verify 200 cặp PATM</title>
<style>
body{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:12px;background:#f4f4f5;color:#18181b}
.bar{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin-bottom:12px;z-index:5}
.bar b{font-size:18px}button{margin:4px 6px 4px 0;padding:8px 14px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer}
button.on{background:#18181b;color:#fff}button.exp{background:#2563eb;color:#fff;border-color:#2563eb}
.card{background:#fff;border:1px solid #ddd;border-radius:12px;padding:14px;margin-bottom:12px}
.card h3{margin:0 0 8px;font-size:16px}.flag{background:#fef08a;border-radius:6px;padding:1px 8px;font-size:12px}
.flag.ok{background:#bbf7d0}.cols{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.poi{border:1px solid #e4e4e7;border-radius:8px;padding:8px}.poi h4{margin:0 0 6px}
.r{display:flex;justify-content:space-between;gap:8px;font-size:13px;padding:2px 0;border-bottom:1px dashed #eee}
.r span{color:#71717a}.r b{text-align:right;font-weight:600}
.dist{text-align:center;color:#71717a;font-size:13px;margin:8px 0}
.vote{display:flex;gap:8px;margin-top:10px}.vote label{flex:1;text-align:center;border:2px solid #d4d4d8;border-radius:8px;padding:8px;cursor:pointer;font-weight:600}
.vote input{display:none}.vote label.yes{border-color:#16a34a;background:#f0fdf4}
.hide{display:none}
@media(max-width:640px){.cols{grid-template-columns:1fr}}
</style></head><body>
<div class="bar"><b id="prog">Đã tick 0/200</b><br>
<button data-f="all" class="on">Tất cả</button><button data-f="dis">Cãi nhau</button><button data-f="todo">Chưa tick</button>
<button class="exp" id="exp">Xuất đáp án (JSON)</button>
</div><div id="list">__CARDS__</div>
<script>
const ans={};
function upd(){const n=Object.keys(ans).length;document.getElementById('prog').textContent=`Đã tick ${n}/__N__`;}
document.querySelectorAll('.vote input').forEach(i=>i.addEventListener('change',()=>{
 const c=i.closest('.card');c.querySelectorAll('.vote label').forEach(l=>l.classList.remove('yes'));
 i.closest('label').classList.add('yes');ans[c.dataset.n]=i.value;upd();}));
document.querySelectorAll('[data-f]').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('[data-f]').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 const f=b.dataset.f;document.querySelectorAll('.card').forEach(c=>{
  c.classList.toggle('hide',f==='dis'&&c.dataset.d!=='1'||f==='todo'&&ans[c.dataset.n]!==undefined);});}));
document.getElementById('exp').addEventListener('click',()=>{
 const out=Object.keys(ans).sort((a,b)=>a-b).map(n=>({pair_n:+n,human:+ans[n]}));
 const b=new Blob([JSON.stringify(out)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='human_answers.json';a.click();
 alert(`Đã xuất ${out.length} đáp án. Gửi file human_answers.json lại cho team để nạp train.`);});
</script></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    pois = {}
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        for p in json.load(f)["pois"]:
            pois[p["poi_id"]] = p
    rows = []
    with open(os.path.join(args.snapshot, "human_verify_200.jsonl"), encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    cards = []
    for r in rows:
        a, b = pois[r["first_id"]], pois[r["second_id"]]
        dis = "1" if (r.get("rule") is not None and r["rule"] != r["llm"]) else "0"
        cards.append(
            f"<div class='card' data-n='{r['pair_n']}' data-d='{dis}'>"
            f"<h3>Cặp {r['pair_n']} "
            f"<span class='flag{' ok' if dis == '0' else ''}'>"
            f"{'CÃI NHAU — cần bạn phân xử' if dis == '1' else 'đồng thuận'}</span></h3>"
            f"<div class='cols'><div class='poi'><h4>A: {html.escape(a['name'])}</h4>{detail(a)}</div>"
            f"<div class='poi'><h4>B: {html.escape(b['name'])}</h4>{detail(b)}</div></div>"
            f"<div class='dist'>Cách nhau ~{haversine_km(a, b):.1f} km (chim bay) · "
            f"máy chấm: <b>{LBL[r['llm']]}</b> · rule: <b>{LBL[r['rule']] if r.get('rule') is not None else '?'}</b></div>"
            f"<div class='vote'><label><input type='radio' name='p{r['pair_n']}' value='1'>A trước</label>"
            f"<label><input type='radio' name='p{r['pair_n']}' value='0'>Hòa</label>"
            f"<label><input type='radio' name='p{r['pair_n']}' value='-1'>B trước</label></div>"
            f"</div>")
    page = PAGE.replace("__CARDS__", "\n".join(cards)).replace("__N__", str(len(rows)))
    out = os.path.join(args.snapshot, "human_verify_200.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {len(rows)} cards -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
