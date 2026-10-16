"""Render REVIEW_V2.md as an offline tick form (lane A).

Parses ## sections / ### clusters / '- [ ] text => ' items into cards.
D1 items: GIỮ/LOẠI radios. Others: ĐÚNG/SAI radios + note box.
Export-JSON button downloads [{idx, verdict, note}] for ingest.

Usage: python BE/ml/data/render_review.py --snapshot BE/data/snapshots/danang-v1
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re

ITEM_RE = re.compile(r"^- \[ \] (.*?) =>\s*$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    with open(os.path.join(args.snapshot, "REVIEW_V2.md"), encoding="utf-8") as f:
        lines = f.read().splitlines()
    sections, cur_sec, cur_clu, idx = [], "", "", 0
    for ln in lines:
        if ln.startswith("## "):
            cur_sec = ln[3:].strip()
        elif ln.startswith("### "):
            cur_clu = ln[4:].strip()
        else:
            m = ITEM_RE.match(ln)
            if m:
                idx += 1
                sections.append({"idx": idx, "sec": cur_sec,
                                 "clu": cur_clu, "text": m.group(1)})
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        ids = {p["poi_id"] for p in json.load(f)["pois"]}

    def verdict_buttons(i, sec):
        if sec.startswith("D1"):
            return (f"<label><input type='radio' name='q{i}' value='keep'>GIỮ</label>"
                    f"<label><input type='radio' name='q{i}' value='drop'>LOẠI</label>")
        return (f"<label><input type='radio' name='q{i}' value='ok'>ĐÚNG</label>"
                f"<label><input type='radio' name='q{i}' value='fix'>SAI</label>")

    cards = []
    last_clu = None
    for s in sections:
        if s["clu"] != last_clu:
            cards.append(f"<h2>{html.escape(s['sec'])} / {html.escape(s['clu'])}</h2>")
            last_clu = s["clu"]
        m = re.search(r"\[([A-Za-z0-9:_/-]{4,})\]", s["text"])
        known = ""
        if m:
            pre = m.group(1)
            hits = [i for i in ids if i.startswith(pre) or i == pre]
            known = " · khớp snapshot" if len(hits) == 1 else (
                " · KHÔNG khớp snapshot!" if not hits else f" · {len(hits)} khớp (mờ)")
        cards.append(
            f"<div class='card' data-n='{s['idx']}'>"
            f"<div class='t'>{html.escape(s['text'])}{known}</div>"
            f"<div class='vote'>{verdict_buttons(s['idx'], s['sec'])}"
            f"<input class='note' placeholder='ghi chú (tên giữ lại / sửa gì)…'></div></div>")
    page = PAGE.replace("__CARDS__", "\n".join(cards)).replace("__N__", str(len(sections)))
    out = os.path.join(args.snapshot, "REVIEW_V2.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {len(sections)} items -> {out}")
    return 0


PAGE = """<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review V2 dedup + flags</title>
<style>
body{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:12px;background:#f4f4f5;color:#18181b}
.bar{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin-bottom:12px;z-index:5}
.bar b{font-size:18px}button{margin:4px 6px 4px 0;padding:8px 14px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer}
button.exp{background:#2563eb;color:#fff;border-color:#2563eb}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 12px;margin-bottom:8px}
.card h2,.t{font-size:14px}h2{margin:18px 0 6px}
.vote{display:flex;gap:8px;margin-top:8px}.vote label{border:2px solid #d4d4d8;border-radius:8px;padding:6px 14px;cursor:pointer;font-weight:600;white-space:nowrap}
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
const LSKEY='review_v2_v1';
function save(){try{localStorage.setItem(LSKEY,JSON.stringify(ans));}catch(e){}}
function upd(){document.getElementById('prog').textContent=`Đã tick ${Object.keys(ans).length}/__N__`;}
document.querySelectorAll('.vote input[type=radio]').forEach(i=>i.addEventListener('change',()=>{
 const c=i.closest('.card');c.querySelectorAll('.vote label').forEach(l=>l.classList.remove('yes'));
 i.closest('label').classList.add('yes');
 ans[c.dataset.n]={v:i.value,note:c.querySelector('.note').value};upd();save();}));
document.querySelectorAll('.note').forEach(t=>t.addEventListener('input',()=>{
 const c=t.closest('.card');if(ans[c.dataset.n]){ans[c.dataset.n].note=t.value;save();}}));
(function restore(){let s={};try{s=JSON.parse(localStorage.getItem(LSKEY)||'{}');}catch(e){}
 for(const [n,v] of Object.entries(s)){const c=document.querySelector(`.card[data-n="${CSS.escape(n)}"]`);if(!c)continue;
  const r=c.querySelector(`input[value="${v.v}"]`);if(r){r.checked=true;r.closest('label').classList.add('yes');}
  if(v.note)c.querySelector('.note').value=v.note;ans[n]=v;}upd();})();
document.querySelectorAll('[data-f]').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('[data-f]').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 const f=b.dataset.f;document.querySelectorAll('.card').forEach(c=>{
  c.classList.toggle('hide',f==='todo'&&ans[c.dataset.n]===undefined);});}));
document.getElementById('exp').addEventListener('click',()=>{
 const out=Object.keys(ans).sort((a,b)=>a-b).map(n=>({idx:+n,...ans[n]}));
 const b=new Blob([JSON.stringify(out)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='review_answers.json';a.click();
 alert(`Đã xuất ${out.length} đáp án. Gửi file review_answers.json lại cho team.`);});
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
