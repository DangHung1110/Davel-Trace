"""Render geo review form for beach/nature/park POIs (lane A).

50 POIs with duration/hours/ticket/access context. Per POI: 3 verdict
groups (duration ok?/ticket ok?/access ok?) + note box. Export JSON
[{poi_id, dur, ticket, access, note}] for ingest.

Sơn Trà access note: peninsula road restricted 07:30-18:30 (07:30-17:30
Oct-Feb) per mytour.danang.vn; viewpoints inside inherit the constraint.

Usage: python BE/ml/data/render_geo_review.py --snapshot BE/data/snapshots/danang-v1
"""

from __future__ import annotations

import argparse
import html
import json
import os

GEO_CATS = ("beach", "nature", "park")

SON_TRA_KEYS = ("son tra", "tien sa", "ban dao", "bai rang", "mui nghe",
                "dinh ban co", "vong canh", "radar", "ghenh bang", "tien son")
SON_TRA_NOTE = ("Đường lên bán đảo giới hạn 07:30-18:30 "
                "(T10-T2: 07:30-17:30, mytour.danang.vn) — lịch phải ra trước giờ đóng đường")


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        pois = [p for p in json.load(f)["pois"] if p.get("cat") in GEO_CATS]

    cards = []
    for p in pois:
        nm = _norm(p.get("name", ""))
        access = p.get("access_note", "")
        vm = p.get("visit_min") or {}
        st = p.get("smart_tags") or {}
        ticket = (f"{p['ticket_vnd']:,}đ".replace(",", ".") if p.get("ticket_vnd")
                  else ("có vé" if st.get("ticket") is True
                        else ("không vé" if st.get("ticket") is False else "chưa rõ")))
        det = (f"Loại: {p.get('type')} · ★{p.get('rating')} · "
               f"~{vm.get('p25', '?')}–{vm.get('p75', '?')}p (độ tin cậy {p.get('dur_confidence', '?')})<br>"
               f"Giờ: {', '.join(p.get('opening_hours') or ['chưa rõ'])}"
               f"{' (' + p['hours_source'] + ')' if p.get('hours_source') else ''}<br>"
               f"Vé: {html.escape(ticket)}"
               f"{' — ' + html.escape(p['ticket_note']) if p.get('ticket_note') else ''}<br>"
               f"Đi với: {', '.join(st.get('party') or [])} · "
               f"Lúc đẹp: {', '.join(st.get('time') or [])}")
        if access:
            det += f"<br><b>Hạn chế đường: {html.escape(access)}</b>"
        cards.append(
            f"<div class='card' data-n='{p['poi_id']}'>"
            f"<h3>{html.escape(p['name'])}</h3><div class='t'>{det}</div>"
            + "".join(
                f"<div class='vote' data-q='{q}'><span>{lbl}</span>"
                f"<label><input type='radio' name='{q}{p['poi_id']}' value='ok'>ĐÚNG</label>"
                f"<label><input type='radio' name='{q}{p['poi_id']}' value='fix'>SAI</label></div>"
                for q, lbl in (("dur", "Thời lượng"), ("ticket", "Vé"),
                               ("access", "Giờ/đường vào")))
            + "<input class='note' placeholder='ghi chú sửa (số phút đúng / giá vé / giờ đường)…'></div>")
    page = PAGE.replace("__CARDS__", "\n".join(cards)).replace("__N__", str(len(pois)))
    out = os.path.join(args.snapshot, "GEO_REVIEW.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    son = sum(1 for p in pois if any(k in _norm(p.get("name", "")) for k in SON_TRA_KEYS))
    print(f"wrote {len(pois)} geo cards ({son} with Son Tra road note) -> {out}")
    return 0


PAGE = """<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review biển + núi (50)</title>
<style>
body{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:12px;background:#f4f4f5;color:#18181b}
.bar{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin-bottom:12px;z-index:5}
.bar b{font-size:18px}button{margin:4px 6px 4px 0;padding:8px 14px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer}
button.exp{background:#2563eb;color:#fff;border-color:#2563eb}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 12px;margin-bottom:8px}
.card h3{margin:0 0 6px;font-size:15px}.t{font-size:13px;color:#3f3f46}
.vote{display:flex;gap:8px;margin-top:6px;align-items:center}.vote span{width:110px;color:#71717a;font-size:13px}
.vote label{border:2px solid #d4d4d8;border-radius:8px;padding:4px 12px;cursor:pointer;font-weight:600}
.vote input{display:none}.vote label.yes{border-color:#16a34a;background:#f0fdf4}
.note{width:100%;box-sizing:border-box;border:1px solid #d4d4d8;border-radius:8px;padding:6px 10px;margin-top:6px}
.hide{display:none}
</style></head><body>
<div class="bar"><b id="prog">Đã tick 0/__N__</b><br>
<button data-f="all" class="on">Tất cả</button><button data-f="todo">Chưa tick</button>
<button class="exp" id="exp">Xuất đáp án (JSON)</button></div>
<div id="list">__CARDS__</div>
<script>
const ans={};
function upd(){let n=0;document.querySelectorAll('.card').forEach(c=>{if(c.querySelectorAll('label.yes').length===3)n++;});document.getElementById('prog').textContent=`Xong ${n}/__N__ POI (đủ 3 ô/điểm)`;}
document.querySelectorAll('.vote input').forEach(i=>i.addEventListener('change',()=>{
 const v=i.closest('.vote');v.querySelectorAll('label').forEach(l=>l.classList.remove('yes'));
 i.closest('label').classList.add('yes');
 const c=i.closest('.card'),id=c.dataset.n;ans[id]=ans[id]||{};
 ans[id][v.dataset.q]=i.value;ans[id].note=c.querySelector('.note').value;upd();}));
document.querySelectorAll('.note').forEach(t=>t.addEventListener('input',()=>{
 const c=t.closest('.card'),id=c.dataset.n;ans[id]=ans[id]||{};ans[id].note=t.value;}));
document.querySelectorAll('[data-f]').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('[data-f]').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 const f=b.dataset.f;document.querySelectorAll('.card').forEach(c=>{
  let done=c.querySelectorAll('label.yes').length===3;
  c.classList.toggle('hide',f==='todo'&&done);});}));
document.getElementById('exp').addEventListener('click',()=>{
 const out=Object.keys(ans).map(id=>({poi_id:id,...ans[id]}));
 const b=new Blob([JSON.stringify(out)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='geo_answers.json';a.click();
 alert(`Đã xuất ${out.length} đáp án. Gửi file geo_answers.json lại cho team.`);});
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
