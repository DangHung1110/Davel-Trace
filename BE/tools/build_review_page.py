"""Build the one-page review form for danang-v2.1 (WP5 / WP8 / WP10 / Q1-Q6).

    python BE/tools/build_review_page.py          # -> reports/p0/review_v21.html

The page bundles every decision the data freeze still needs from a human:
Q1-Q6, the name-cleanup table, POIs in `review`, duplicate candidates,
price `null` POIs, signature POIs that fail gate G3 and the Hội An old-town
ticket list. Nothing is sent anywhere: "Xuất JSON" downloads one
`review_v21_YYYYMMDD.json`; put it in BE/data/sources/ and run
`python BE/tools/ingest_review.py` (writes decisions_* + human_verify_v2_*).
Stdlib only; the data is embedded in the page.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "BE", "ml", "data"))
import v2_rules as R  # noqa: E402

SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
REPORTS = os.path.join(ROOT, "reports", "p0")
OUT = os.path.join(REPORTS, "review_v21.html")
OLD_TOWN_PARENT = "Phố cổ Hội An"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _brief(p):
    pv = p["provenance"]
    return {"poi_id": p["poi_id"], "name": p["name"], "category": p["category"], "zone": p["zone"],
            "status": p["status"], "status_reason": p["status_reason"],
            "hours": ", ".join(p["hours"]["open"]) or "—", "hours_kind": p["hours"]["kind"],
            "hours_by": pv["hours"]["verified_by"], "tier": p["price"]["tier"],
            "price_by": pv["price"]["verified_by"], "price_note": pv["price"].get("note") or "",
            "lat": p["lat"], "lon": p["lon"]}


def collect():
    pois = _load(os.path.join(SNAP, "pois.json"))["pois"]
    by_id = {p["poi_id"]: p for p in pois}
    names = _load(os.path.join(REPORTS, "12_name_proposals.json"))["items"]
    name_rows = [{**_brief(by_id[pid]), "proposed": d["name"], "was": d["name_was"],
                  "proposed_status": d.get("status"), "proposed_reason": d.get("status_reason")}
                 for pid, d in names.items() if pid in by_id]
    review = [_brief(p) for p in pois if p["status"] == "review"]
    with open(os.path.join(REPORTS, "04_duplicate_candidates.csv"), encoding="utf-8") as f:
        dups = [r for r in csv.DictReader(f) if r["a_id"] in by_id and r["b_id"] in by_id]
    dup_rows = [{"a": _brief(by_id[r["a_id"]]), "b": _brief(by_id[r["b_id"]]),
                 "dist_m": r["dist_m"], "name_ratio": r["name_ratio"]} for r in dups]
    null_price = [_brief(p) for p in pois if p["price"]["tier"] is None
                  and p["role"] != "base" and p["status"] != "excluded"]
    sig = []
    for p in pois:
        if not p["popularity"]["signature"] or p["status"] == "excluded":
            continue
        pv = p["provenance"]["price"]
        price_ok = p["price"]["tier"] in ("free", "included") or (
            p["price"]["tier"] is not None and pv["verified_by"] != "inferred")
        if p["hours"]["kind"] != "fixed" or not price_ok:
            sig.append({**_brief(p), "need_hours": p["hours"]["kind"] != "fixed",
                        "need_price": not price_ok})
    parent = next((p for p in pois if p["name"] == OLD_TOWN_PARENT), None)
    old_town = []
    if parent:
        anchor = next((p for p in pois if p["name"] == "Chùa Cầu"), parent)
        for p in pois:
            if p["role"] != "attraction" or p["poi_id"] == parent["poi_id"]:
                continue
            d = R.haversine_m(anchor["lat"], anchor["lon"], p["lat"], p["lon"])
            if p["requires_ticket_of"] == parent["poi_id"] or d <= 700:
                old_town.append({**_brief(p), "in_ticket": p["requires_ticket_of"] == parent["poi_id"],
                                 "dist_m": round(d)})
        old_town.sort(key=lambda r: (not r["in_ticket"], r["dist_m"]))
    return {"built_at": dt.date.today().isoformat(), "names": name_rows, "review": review,
            "duplicates": dup_rows, "null_price": null_price, "signature": sig,
            "old_town": old_town, "old_town_parent": parent["poi_id"] if parent else None}


PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Duyệt dữ liệu v2.1</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e2e1dc;--acc:#2f6f5e;--warn:#a5481d;--chip:#eef3f1}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--mute:#9b9a94;--line:#33322f;--acc:#6fb7a2;--warn:#e08a5f;--chip:#24302c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:16px;margin:0 auto 0 0}nav a{color:var(--mute);text-decoration:none;margin-right:10px;font-size:13px}nav a:hover{color:var(--acc)}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 14px;font:inherit;cursor:pointer}button.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
main{max-width:1180px;margin:0 auto;padding:16px}section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 16px}
h2{font-size:15px;margin:0 0 4px}p.help{color:var(--mute);margin:0 0 10px;font-size:13px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;padding:6px 6px;border-top:1px solid var(--line)}th{font-size:12px;color:var(--mute);font-weight:600}
td small{color:var(--mute)}input[type=text],input[type=url],input[type=number],select{width:100%;padding:5px 6px;border:1px solid var(--line);border-radius:5px;background:var(--bg);color:var(--ink);font:inherit}
.chip{display:inline-block;background:var(--chip);border-radius:10px;padding:0 7px;font-size:12px;margin:1px 2px 1px 0}.warn{color:var(--warn)}
.q{display:grid;grid-template-columns:220px 1fr;gap:6px 12px;align-items:center}.count{font-weight:600;color:var(--acc)}
.done{opacity:.55}.wrap{overflow-x:auto}a.map{font-size:12px}
@media (max-width:720px){.q{grid-template-columns:1fr}th:nth-child(n+4),td:nth-child(n+4){min-width:140px}}
</style></head><body>
<header><h1>Duyệt dữ liệu danang-v2.1 <small style="color:var(--mute);font-weight:400">— build __BUILT__</small></h1>
<nav><a href="#q">Q1–Q6</a><a href="#names">Tên</a><a href="#review">Review</a><a href="#dups">Trùng</a><a href="#null">Giá null</a><a href="#sig">Tiêu biểu</a><a href="#oldtown">Vé phố cổ</a></nav>
<span id="prog" class="count"></span><button class="ghost" onclick="saveDraft()">Lưu nháp</button><button onclick="exportJson()">Xuất JSON</button></header>
<main>
<section><p class="help">Mọi thay đổi chỉ nằm trong trình duyệt (nháp tự lưu). Bấm <b>Xuất JSON</b> → lưu file vào <code>BE/data/sources/</code> → gửi Claude hoặc chạy <code>python BE/tools/ingest_review.py</code>.
Giờ ghi dạng <code>08:00-17:00</code> hoặc <code>11:00-14:00, 17:00-22:00</code> (đúng cho <b>mọi ngày mở</b>). Mức giá/người: free · cheap &lt;100k · medium 100–500k · expensive 500k–1,2tr · included (đã trong vé điểm cha).
<b>URL bằng chứng</b> bắt buộc để được ghi là <code>human</code>; thiếu URL → <code>user</code>. Không dùng giá trị chép từ Google Maps.</p></section>

<section id="q"><h2>Q1–Q6 · quyết định chung</h2><p class="help">Mặc định = ô đầu tiên (giá trị đang dùng).</p><div class="q" id="qbox"></div></section>
<section id="names"><h2>Tên cần làm sạch <span class="count" id="c-names"></span></h2><p class="help">Sửa ô "tên mới" nếu muốn; bỏ tick "đồng ý" để giữ tên cũ.</p><div class="wrap"><table id="t-names"></table></div></section>
<section id="review"><h2>POI đang <code>review</code> <span class="count" id="c-review"></span></h2><p class="help">Chọn active (đưa vào lịch), excluded (giữ trong dữ liệu, không vào lịch) hoặc để nguyên.</p><div class="wrap"><table id="t-review"></table></div></section>
<section id="dups"><h2>Cặp nghi trùng <span class="count" id="c-dups"></span></h2><p class="help">"Giữ A" = loại B (excluded, lý do trùng), và ngược lại. "Khác nhau" = giữ cả hai.</p><div class="wrap"><table id="t-dups"></table></div></section>
<section id="null"><h2>Giá chưa biết (<code>price.tier = null</code>) <span class="count" id="c-null"></span></h2><p class="help">Claude đã tra web nhưng không có nguồn đáng tin (xem <code>reports/p0/13_null_price_research.md</code>).</p><div class="wrap"><table id="t-null"></table></div></section>
<section id="sig"><h2>Điểm tiêu biểu chưa đạt cổng G3 <span class="count" id="c-sig"></span></h2><p class="help">Cần giờ có nguồn (<code>fixed</code>) và giá có nguồn. Ưu tiên trang chính thức / cổng du lịch.</p><div class="wrap"><table id="t-sig"></table></div></section>
<section id="oldtown"><h2>Vé phố cổ Hội An <span class="count" id="c-old"></span></h2><p class="help">Tick = điểm dùng phiếu của vé phố cổ (giá → <code>included</code>). Danh sách hiện tại là ước đoán theo vị trí.</p><div class="wrap"><table id="t-old"></table></div></section>
</main>
<script>
const D = __DATA__;
const KEY = "review_v21_" + D.built_at;
const TIERS = ["", "free", "cheap", "medium", "expensive", "included"];
const Q = [
 ["Q1", "Ngưỡng 4 mức giá", ["free / <100k / 100–500k / 500k–1,2tr (mặc định)", "khác (ghi chú)"]],
 ["Q2", "Ma trận v2", ["file riêng danang-v2/matrix.json (đang dùng)", "gộp vào ma trận v1"]],
 ["Q3", "Chính sách Google lúc chạy", ["cach_ly (đang dùng)", "demo_phi_thuong_mai"]],
 ["Q4", "20 review + trùng", ["duyệt theo bảng dưới", "giữ nguyên chờ sau"]],
 ["Q5", "Danh sách vé phố cổ", ["theo bảng 'Vé phố cổ' dưới", "giữ danh sách ước đoán"]],
 ["Q6", "Profile ma trận", ["OSRM car (đang dùng), Valhalla motor_scooter ở P1", "dựng Valhalla ngay"]],
];
let S = {}; try { S = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { S = {}; }
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const map = r => `<a class="map" target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lon}#map=18/${r.lat}/${r.lon}">OSM</a>`;
const info = r => `<b>${esc(r.name)}</b><br><small>${esc(r.category)} · ${esc(r.zone)}</small> ${map(r)}`;
const now = r => `<span class="chip">${esc(r.hours)} [${esc(r.hours_kind)}]</span><span class="chip">giá: ${esc(r.tier ?? "null")} (${esc(r.price_by)})</span>${r.price_note ? `<br><small>${esc(r.price_note).slice(0,160)}</small>` : ""}`;
const sel = (k, opts, v) => `<select data-k="${k}">${opts.map(o => `<option value="${esc(o[0])}" ${o[0] === (v ?? "") ? "selected" : ""}>${esc(o[1])}</option>`).join("")}</select>`;
const inp = (k, ph, v, type = "text") => `<input type="${type}" data-k="${k}" placeholder="${esc(ph)}" value="${esc(v ?? "")}">`;
const g = k => S[k];
function verifyCells(id) {
  return `<td>${inp(id + "|hours", "08:00-17:00", g(id + "|hours"))}</td>
  <td>${sel(id + "|tier", TIERS.map(t => [t, t || "—"]), g(id + "|tier"))}${inp(id + "|vnd", "VND (tuỳ chọn)", g(id + "|vnd"), "number")}</td>
  <td>${inp(id + "|url", "https://…", g(id + "|url"), "url")}${inp(id + "|note", "ghi chú", g(id + "|note"))}</td>`;
}
function render() {
  document.getElementById("qbox").innerHTML = Q.map(([k, label, opts]) =>
    `<label><b>${k}</b> ${esc(label)}</label><div>${sel("Q|" + k, opts.map((o, i) => [String(i), o]), g("Q|" + k) ?? "0")} ${inp("Q|" + k + "|note", "ghi chú", g("Q|" + k + "|note"))}</div>`).join("");
  T("t-names", ["POI hiện tại", "Tên mới", "Đồng ý", "Trạng thái đề xuất"], D.names.map(r => `<tr>
    <td>${info({...r, name: r.was})}</td><td>${inp(r.poi_id + "|name", "", g(r.poi_id + "|name") ?? r.proposed)}</td>
    <td><input type="checkbox" data-k="${r.poi_id}|name_ok" ${g(r.poi_id + "|name_ok") ?? true ? "checked" : ""}></td>
    <td>${sel(r.poi_id + "|status", [["", "giữ nguyên"], ["active", "active"], ["excluded", "excluded"]], g(r.poi_id + "|status") ?? (r.proposed_status || ""))}<small>${esc(r.proposed_reason || "")}</small></td></tr>`));
  T("t-review", ["POI", "Lý do review", "Hiện tại", "Quyết định", "Lý do / ghi chú"], D.review.map(r => `<tr>
    <td>${info(r)}</td><td class="warn">${esc(r.status_reason)}</td><td>${now(r)}</td>
    <td>${sel(r.poi_id + "|status", [["", "để review"], ["active", "active"], ["excluded", "excluded"]], g(r.poi_id + "|status"))}</td>
    <td>${inp(r.poi_id + "|reason", "lý do", g(r.poi_id + "|reason"))}</td></tr>`));
  T("t-dups", ["A", "B", "Cách nhau", "Quyết định"], D.duplicates.map((r, i) => `<tr>
    <td>${info(r.a)}<br>${now(r.a)}</td><td>${info(r.b)}<br>${now(r.b)}</td><td>${esc(r.dist_m)} m<br><small>tên ${esc(r.name_ratio)}</small></td>
    <td>${sel("dup|" + i, [["", "chưa quyết"], ["keep_a", "giữ A, loại B"], ["keep_b", "giữ B, loại A"], ["distinct", "khác nhau"]], g("dup|" + i))}</td></tr>`));
  T("t-null", ["POI", "Hiện tại", "Trạng thái", "Giờ đúng", "Mức giá", "Bằng chứng"], D.null_price.map(r => `<tr>
    <td>${info(r)}</td><td>${now(r)}</td><td>${sel(r.poi_id + "|status", [["", "giữ"], ["review", "review"], ["excluded", "excluded"]], g(r.poi_id + "|status"))}</td>${verifyCells(r.poi_id)}</tr>`));
  T("t-sig", ["POI", "Hiện tại", "Thiếu", "Giờ đúng", "Mức giá", "Bằng chứng"], D.signature.map(r => `<tr>
    <td>${info(r)}</td><td>${now(r)}</td><td class="warn">${r.need_hours ? "giờ " : ""}${r.need_price ? "giá" : ""}</td>${verifyCells(r.poi_id)}</tr>`));
  T("t-old", ["POI", "Cách Chùa Cầu", "Hiện tại", "Dùng vé phố cổ"], D.old_town.map(r => `<tr>
    <td>${info(r)}</td><td>${r.dist_m} m</td><td>${now(r)}</td>
    <td><input type="checkbox" data-k="${r.poi_id}|oldtown" ${(g(r.poi_id + "|oldtown") ?? r.in_ticket) ? "checked" : ""}></td></tr>`));
  document.querySelectorAll("[data-k]").forEach(el => el.addEventListener("change", e => {
    S[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; saveDraft(true); progress(); }));
  progress();
}
function T(id, head, rows) { document.getElementById(id).innerHTML = `<tr>${head.map(h => `<th>${h}</th>`).join("")}</tr>` + rows.join(""); }
function progress() {
  const n = (rows, f) => rows.filter(f).length;
  const filled = id => ["hours", "tier", "vnd"].some(k => S[id + "|" + k]);
  const set = (id, a, b) => document.getElementById(id).textContent = `${a}/${b}`;
  set("c-names", D.names.length, D.names.length);
  set("c-review", n(D.review, r => S[r.poi_id + "|status"]), D.review.length);
  set("c-dups", n(D.duplicates, (r, i) => S["dup|" + D.duplicates.indexOf(r)]), D.duplicates.length);
  set("c-null", n(D.null_price, r => filled(r.poi_id) || S[r.poi_id + "|status"]), D.null_price.length);
  set("c-sig", n(D.signature, r => filled(r.poi_id)), D.signature.length);
  set("c-old", n(D.old_town, r => S[r.poi_id + "|oldtown"] ?? r.in_ticket), D.old_town.length);
}
function saveDraft(quiet) { try { localStorage.setItem(KEY, JSON.stringify(S)); if (!quiet) alertless("Đã lưu nháp"); } catch (e) {} }
function alertless(msg) { const p = document.getElementById("prog"); p.textContent = msg; setTimeout(progress, 1200); }
function verifyItem(id) {
  const o = {poi_id: id};
  if (S[id + "|hours"]) o.hours = S[id + "|hours"].trim();
  if (S[id + "|tier"]) o.price_tier = S[id + "|tier"];
  if (S[id + "|vnd"]) o.ticket_vnd = Number(S[id + "|vnd"]);
  if (S[id + "|url"]) o.evidence_url = S[id + "|url"].trim();
  if (S[id + "|note"]) o.note = S[id + "|note"];
  return Object.keys(o).length > 1 ? o : null;
}
function exportJson() {
  const out = {schema: "review_v21", snapshot_built: D.built_at, exported_at: new Date().toISOString().slice(0, 10),
    questions: {}, names: [], status: [], duplicates: [], verify: [], old_town: {parent: D.old_town_parent, include: [], exclude: []}};
  Q.forEach(([k, , opts]) => { const i = Number(S["Q|" + k] ?? 0); out.questions[k] = {choice: opts[i], default: i === 0, note: S["Q|" + k + "|note"] || null}; });
  D.names.forEach(r => { if (S[r.poi_id + "|name_ok"] ?? true) out.names.push({poi_id: r.poi_id, name: (S[r.poi_id + "|name"] ?? r.proposed).trim(), name_was: r.was});
    const st = S[r.poi_id + "|status"] ?? (r.proposed_status || ""); if (st) out.status.push({poi_id: r.poi_id, status: st, reason: r.proposed_reason || "WP5"}); });
  [...D.review, ...D.null_price].forEach(r => { const st = S[r.poi_id + "|status"]; if (st) out.status.push({poi_id: r.poi_id, status: st, reason: S[r.poi_id + "|reason"] || r.status_reason || "người dùng duyệt"}); });
  D.duplicates.forEach((r, i) => { const v = S["dup|" + i]; if (v) out.duplicates.push({a: r.a.poi_id, b: r.b.poi_id, decision: v}); });
  [...D.null_price, ...D.signature].forEach(r => { const it = verifyItem(r.poi_id); if (it && !out.verify.some(x => x.poi_id === it.poi_id)) out.verify.push(it); });
  D.old_town.forEach(r => { const v = S[r.poi_id + "|oldtown"] ?? r.in_ticket; if (v !== r.in_ticket) (v ? out.old_town.include : out.old_town.exclude).push(r.poi_id); });
  const blob = new Blob([JSON.stringify(out, null, 1)], {type: "application/json"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `review_v21_${out.exported_at.replaceAll("-", "")}.json`; a.click();
}
render();
</script></body></html>
"""


def main():
    data = collect()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")   # never close <script>
    html = PAGE.replace("__DATA__", blob).replace("__BUILT__", data["built_at"])
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote", OUT, {k: len(v) for k, v in data.items() if isinstance(v, list)})


if __name__ == "__main__":
    main()
