"""Render money review form: expensive-band check + adult venues + must-go adds (lane A).

Items:
  P1 expensive non-lodging POIs -> band ĐÚNG/SAI + note (giá đúng).
  P2 adult-suggestive bars -> GIỮ/LOẠI.
  P3 must-go proposals (curated 20) -> ĐỒNG Ý/LOẠI.
Export [{key, verdict, note}].

Usage: python BE/ml/data/render_money_review.py --snapshot BE/data/snapshots/danang-v1
"""

from __future__ import annotations

import argparse
import html
import json
import os
import unicodedata

MUST_GO = [
    "Sun World Bà Nà Hills", "Cầu Rồng", "Bãi biển Mỹ Khê", "Ngũ Hành Sơn",
    "Chùa Linh Ứng - Bãi Bụt Sơn Trà", "Chợ Hàn", "Chợ Cồn",
    "Bán đảo Sơn Trà", "Hải đăng Tiên Sa", "Ghềnh Bàng",
    "Chợ đêm Helio - B. Night Market", "Bảo tàng Điêu khắc Chăm Đà Nẵng",
    "Bảo Tàng Đà Nẵng", "Đỉnh Bàn Cờ", "Mũi Nghê",
    "Chùa Quán Thế Âm", "Non Nuoc Stone Carving Memory Museum Da Nang City",
    "Du thuyền sông Hàn Vinh Anh - Da Nang cruise on Han river",
    "Đà Nẵng Food Tour", "Bảo tàng 3D Art In Paradise",
]
ADULT_KEYS = ("tiep vien", "hostess", "gai ", "massage rico", "thư giãn a-z")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        pois = json.load(f)["pois"]
    by_name = {p["name"]: p for p in pois}
    items = []
    for p in pois:
        st = p.get("smart_tags") or {}
        if st.get("price_band") == "expensive" and p.get("cat") != "lodging":
            items.append({"grp": "P1-band", "key": p["poi_id"],
                          "title": f"{p['name']} — band expensive, giá: {p.get('price_note', p.get('ticket_note', 'chưa rõ giá'))}",
                          "q": "Band giá", "a": "ĐÚNG", "b": "SAI"})
    for p in pois:
        if any(k in _norm(p["name"]) for k in ADULT_KEYS):
            items.append({"grp": "P2-adult", "key": p["poi_id"],
                          "title": f"{p['name']} ({p.get('type')}, ★{p.get('rating')})",
                          "q": "Nội dung người lớn?", "a": "GIỮ", "b": "LOẠI"})
    for name in MUST_GO:
        p = by_name.get(name)
        if p and "must-go" not in (p.get("smart_tags") or {}).get("budget", []):
            items.append({"grp": "P3-mustgo", "key": p["poi_id"],
                          "title": f"{name} ({p.get('type')}, ★{p.get('rating')})",
                          "q": "Thêm must-go?", "a": "ĐỒNG Ý", "b": "LOẠI"})
    cards = []
    last = None
    for i, s in enumerate(items):
        if s["grp"] != last:
            cards.append(f"<h2>{html.escape(s['grp'])}</h2>")
            last = s["grp"]
        cards.append(
            f"<div class='card' data-n='{i}' data-k='{html.escape(s['key'], quote=True)}'>"
            f"<div class='t'>{html.escape(s['title'])}</div>"
            f"<div class='vote'><span>{s['q']}</span>"
            f"<label><input type='radio' name='q{i}' value='yes'>{s['a']}</label>"
            f"<label><input type='radio' name='q{i}' value='no'>{s['b']}</label>"
            f"<input class='note' placeholder='ghi chú…'></div></div>")
    page = PAGE.replace("__CARDS__", "\n".join(cards)).replace("__N__", str(len(items)))
    out = os.path.join(args.snapshot, "MONEY_REVIEW.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    from collections import Counter
    print(f"wrote {len(items)} items {dict(Counter(s['grp'] for s in items))} -> {out}")
    return 0


PAGE = """<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review giá + nhạy cảm + must-go</title>
<style>
body{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:12px;background:#f4f4f5;color:#18181b}
.bar{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin-bottom:12px;z-index:5}
.bar b{font-size:18px}button{margin:4px 6px 4px 0;padding:8px 14px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer}
button.exp{background:#2563eb;color:#fff;border-color:#2563eb}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 12px;margin-bottom:8px}
.t{font-size:14px}h2{margin:18px 0 6px;font-size:15px}
.vote{display:flex;gap:8px;margin-top:8px;align-items:center}.vote span{color:#71717a;font-size:13px;min-width:120px}
.vote label{border:2px solid #d4d4d8;border-radius:8px;padding:6px 14px;cursor:pointer;font-weight:600;white-space:nowrap}
.vote input[type=radio]{display:none}.vote label.yes{border-color:#16a34a;background:#f0fdf4}
.note{flex:1;border:1px solid #d4d4d8;border-radius:8px;padding:6px 10px;min-width:0}
.hide{display:none}
</style></head><body>
<div class="bar"><b id="prog">Đã tick 0/__N__</b><br>
<button data-f="all" class="on">Tất cả</button><button data-f="todo">Chưa tick</button>
<button class="exp" id="exp">Xuất đáp án (JSON)</button></div>
<div id="list">__CARDS__</div>
<script>
const ans={};
function upd(){document.getElementById('prog').textContent=`Đã tick ${Object.keys(ans).length}/__N__`;}
document.querySelectorAll('.vote input[type=radio]').forEach(i=>i.addEventListener('change',()=>{
 const c=i.closest('.card');c.querySelectorAll('.vote label').forEach(l=>l.classList.remove('yes'));
 i.closest('label').classList.add('yes');
 ans[c.dataset.n]={key:c.dataset.k,v:i.value,note:c.querySelector('.note').value};upd();}));
document.querySelectorAll('.note').forEach(t=>t.addEventListener('input',()=>{
 const c=t.closest('.card');if(ans[c.dataset.n])ans[c.dataset.n].note=t.value;}));
document.querySelectorAll('[data-f]').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('[data-f]').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 const f=b.dataset.f;document.querySelectorAll('.card').forEach(c=>{
  c.classList.toggle('hide',f==='todo'&&ans[c.dataset.n]===undefined);});}));
document.getElementById('exp').addEventListener('click',()=>{
 const out=Object.keys(ans).sort((a,b)=>a-b).map(n=>({idx:+n,...ans[n]}));
 const b=new Blob([JSON.stringify(out)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='money_answers.json';a.click();
 alert(`Đã xuất ${out.length} đáp án. Gửi file money_answers.json lại cho team.`);});
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
