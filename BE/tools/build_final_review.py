"""Build the LAST review form for the danang-v2.1 data freeze.

    python BE/tools/build_final_review.py      # -> reports/p0/final_review.html

Only what an agent cannot settle by itself:
  A. policy decisions (lodging, cooking classes, VỌC category, closed venues...)
  B. values the agent chose on the user's behalf (tick = agree)
  C. hours/price confirmation for signature + top POIs, so >= 50 POIs carry
     human-checked hours (DATA_FIX_PLAN §4). "Đúng" = current value is right.
Export keeps schema `review_v21` (verify/status) so `ingest_review.py` reads it;
policies/confirm land in extra keys that the ingest turns into decisions.
Stdlib only; data embedded; nothing is sent anywhere.
"""

from __future__ import annotations

import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAP = os.path.join(ROOT, "BE", "data", "snapshots", "danang-v2")
OUT = os.path.join(ROOT, "reports", "p0", "final_review.html")
HUMAN_TARGET = 50
CONFIRM_MAX = 45

# (key, question, options; first = recommended/current, affected poi_ids)
POLICIES = [
    ("lodging", "76 điểm lưu trú: giá null + giờ unknown",
     ["Giữ nguyên — lưu trú không xếp vào lịch tham quan (khuyên dùng)", "Cần tìm giá/giờ cho lưu trú"], []),
    ("cooking", "12 lớp nấu ăn / workshop: giờ theo lịch đặt",
     ["Giữ active, giờ 'theo lịch đặt' (kiểu by_booking ở P1)", "Loại khỏi lịch (excluded)"], "COOKING"),
    ("voc", "VỌC Glamping (chỗ ở qua đêm, gói 695–795k/người)",
     ["Để paid_attraction (trải nghiệm)", "Chuyển sang lodging"], ["ChIJlxydWJEZQjER5GSMuHJHtak"]),
    ("helio", "Trung Tâm Giải Trí Helio — tạm ngưng từ 9/2025, đang chuyển mô hình Art Mall",
     ["Loại (excluded) tới khi có giờ mới", "Giữ active, giờ unknown"], ["ChIJK4sVPc0ZQjERdGROWQ8MMg4"]),
    ("nha66", "Nhà biểu diễn nghệ thuật cổ truyền 66 Bạch Đằng — tạm đóng 3/2026, show chuyển sang 01 Cao Hồng Lãnh",
     ["Loại (excluded) tới khi xác nhận mở lại", "Giữ active, giờ unknown"], ["osm:node/7127442985"]),
    ("bai_rang", "Bãi Rạng và KDL Sinh thái Suối Rạng (cách 166 m)",
     ["Tách 2 điểm, cùng cụm bai_rang (đang dùng)", "Gộp: chỉ giữ KDL Suối Rạng"], ["manual:son-tra-bai-rang"]),
]

COOKING_WORDS = ("cooking", "coffee workshop", "coffee class", "craft workshop", "cooking tour")

# values the agent picked when sources disagreed or were missing
AUTO = [
    ("manual:hoi-an-bai-choi", "Hát Bài Chòi: kết thúc 21:00 là ƯỚC LƯỢNG (nguồn chỉ nêu bắt đầu 19:00)"),
    ("osm:way/140401174", "Hồ Xanh: không có nguồn vé/giờ → free + khung an toàn nơi công cộng"),
    ("manual:son-tra-bai-rang", "Bãi Rạng: toạ độ từ worldplaces (tin cậy trung bình) 16.1056, 108.29177"),
    ("manual:son-tra-bai-da-den", "Bãi Đá Đen: bỏ alias 'Bãi Obama' (OSM 'Obama' là bãi khác ~9 km)"),
    ("ChIJHZakNa8ZQjERWNFToM16eB4", "Chùa Linh Ứng: nguồn 06:30–17:30, áp khung bán đảo → mở trong lịch từ 07:30"),
    ("ChIJOZ__YJwXQjER4wLDpzs9L5c", "Chợ Đêm An Thượng: nguồn lệch 17:00 / 18:00 → lấy 18:00–23:00"),
    ("ChIJcVJkUPcXQjERsA8_dfySw5E", "3D Art in Paradise: nguồn lệch → lấy 09:00–18:00"),
    ("ChIJLeqV3_cXQjERH0Dq1Mte6_w", "Son Tra Retreat: 3 nguồn lệch → giao 10:00–21:00"),
    ("ChIJSRWy6Hr3QTERiU3vuI0PbHw", "KDL Lái Thiêu: 07:30–17:00 (fantasticity) vs 07:00–19:00 (VinWonders) → lấy hẹp"),
    ("ChIJQWQVKr4ZQjERcafNnRyLelk", "DD Wonderland: nguồn lệch theo thứ → giao 09:00–21:00"),
    ("osm:way/14131302", "Ký ức Hội An: công viên 17:00–21:30, nghỉ thứ Ba, show 20:00–21:00, vé ECO 600k"),
    ("osm:node/5286977425", "Núi Thần Tài: vé 480k có nguồn, GIỜ cả ngày chưa có nguồn"),
]


def _brief(p):
    pv = p["provenance"]
    return {"poi_id": p["poi_id"], "name": p["name"], "category": p["category"], "zone": p["zone"],
            "hours": ", ".join(p["hours"]["open"]) or "—", "closed": p["hours"].get("closed_days") or [],
            "hours_kind": p["hours"]["kind"], "hours_by": pv["hours"]["verified_by"],
            "hours_url": pv["hours"].get("evidence_url") or "", "tier": p["price"]["tier"],
            "price_by": pv["price"]["verified_by"], "price_url": pv["price"].get("evidence_url") or "",
            "note": (p["price"].get("note") or pv["hours"].get("note") or "")[:220],
            "lat": p["lat"], "lon": p["lon"], "signature": p["popularity"]["signature"]}


def collect():
    with open(os.path.join(SNAP, "pois.json"), encoding="utf-8") as f:
        pois = json.load(f)["pois"]
    by_id = {p["poi_id"]: p for p in pois}
    active = [p for p in pois if p["status"] == "active"]
    human = sum(1 for p in active if p["provenance"]["hours"]["verified_by"] in ("human", "user"))
    cooking = [p["poi_id"] for p in active
               if any(w in p["name"].lower() for w in COOKING_WORDS) and p["hours"]["kind"] == "unknown"]
    policies = [{"key": k, "q": q, "opts": o,
                 "ids": cooking if ids == "COOKING" else ids,
                 "names": [by_id[i]["name"] for i in (cooking if ids == "COOKING" else ids) if i in by_id]}
                for k, q, o, ids in POLICIES]
    auto = [{**_brief(by_id[i]), "why": why} for i, why in AUTO if i in by_id]
    auto_ids = {r["poi_id"] for r in auto}
    cand = [p for p in active if p["category"] != "lodging" and p["role"] == "attraction"
            and p["hours"]["kind"] == "fixed" and p["poi_id"] not in auto_ids
            and p["provenance"]["hours"]["verified_by"] not in ("human", "user")]
    cand.sort(key=lambda p: (not p["popularity"]["signature"],
                             not p["provenance"]["hours"].get("evidence_url"),
                             -(p["popularity"]["prize_prior"] or 0)))
    confirm = [_brief(p) for p in cand[:CONFIRM_MAX]]
    # second opinion: AI-Hay answer (an LLM — hint only) + Codex check of the page it cited
    links = os.path.join(ROOT, "reports", "p0", "links")
    hint = {}
    for fn, kind in (("aihay_rows.json", "aihay"), ("aihay_verified.json", "checked")):
        path = os.path.join(links, fn)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for r in json.load(f):
                    hint.setdefault(r["poi_id"], {})[kind] = r
    for r in auto + confirm:
        r["hint"] = hint.get(r["poi_id"])
    return {"built_at": dt.date.today().isoformat(), "human_now": human, "human_target": HUMAN_TARGET,
            "policies": policies, "auto": auto, "confirm": confirm}


PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chốt dữ liệu cuối</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e2e1dc;--acc:#2f6f5e;--warn:#a5481d;--chip:#eef3f1;--ok:#e3f1ea}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--mute:#9b9a94;--line:#33322f;--acc:#6fb7a2;--warn:#e08a5f;--chip:#24302c;--ok:#1f3a30}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:16px;margin:0 auto 0 0}button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 14px;font:inherit;cursor:pointer}
button.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}button.sm{padding:3px 9px;font-size:12px}
main{max-width:1180px;margin:0 auto;padding:16px}section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 16px}
h2{font-size:15px;margin:0 0 4px}p.help{color:var(--mute);margin:0 0 10px;font-size:13px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;padding:6px;border-top:1px solid var(--line)}th{font-size:12px;color:var(--mute);font-weight:600}
td small{color:var(--mute)}input[type=text],input[type=url],select{width:100%;padding:5px 6px;border:1px solid var(--line);border-radius:5px;background:var(--bg);color:var(--ink);font:inherit}
.chip{display:inline-block;background:var(--chip);border-radius:10px;padding:0 7px;font-size:12px;margin:1px 2px 1px 0}.count{font-weight:600;color:var(--acc)}
tr.ok{background:var(--ok)}.warn{color:var(--warn)}.wrap{overflow-x:auto}a{color:var(--acc)}.bar{height:8px;background:var(--line);border-radius:4px;overflow:hidden;min-width:120px}.bar i{display:block;height:100%;background:var(--acc)}
@media (max-width:720px){th:nth-child(n+3),td:nth-child(n+3){min-width:150px}}
</style></head><body>
<header><h1>Chốt dữ liệu danang-v2.1 — lần cuối <small style="color:var(--mute);font-weight:400">build __BUILT__</small></h1>
<span>Giờ người kiểm: <b id="hn"></b>/<span id="ht"></span></span><div class="bar"><i id="hb"></i></div>
<button onclick="exportJson()">Xuất JSON</button></header>
<main>
<section><p class="help">3 phần, làm 1 lần là xong. Nháp tự lưu trong trình duyệt. Xong bấm <b>Xuất JSON</b> → bỏ file vào <code>BE/data/sources/</code> → nhắn Claude.
<br><b>C · Đúng</b> = bạn đã mở link bằng chứng (hoặc tự biết) và giờ/giá hiện tại đúng → được ghi <code>human</code>. Sai thì gõ giờ đúng (<code>08:00-17:00</code>, nhiều khung cách dấu phẩy) và dán link.
Cần thêm <b id="need"></b> mục "Đúng/Sửa" ở phần C để đạt mốc <span id="ht2"></span>.</p></section>
<section><h2>A · Quyết định chính sách <span class="count" id="ca"></span></h2><p class="help">Ô đầu = đề xuất của Claude.</p><div class="wrap"><table id="ta"></table></div></section>
<section><h2>B · Giá trị Claude đã tự chọn <span class="count" id="cb"></span></h2><p class="help">Bỏ tick nếu không đồng ý và ghi cách sửa.</p><div class="wrap"><table id="tb"></table></div></section>
<section><h2>C · Xác nhận giờ / giá điểm tiêu biểu <span class="count" id="cc"></span></h2><p class="help">Sắp: điểm tiêu biểu trước, rồi điểm có link, rồi độ nổi tiếng.</p><div class="wrap"><table id="tc"></table></div></section>
</main>
<script>
const D = __DATA__;
const KEY = "final_review_" + D.built_at;
let S = {}; try { S = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { S = {}; }
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const osm = r => `<a target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lon}#map=18/${r.lat}/${r.lon}">bản đồ</a>`;
const link = u => u && /^https?:/.test(u) ? `<a target="_blank" rel="noopener" href="${esc(u)}">nguồn</a>` : "";
const info = r => `<b>${esc(r.name)}</b>${r.signature ? ' <span class="chip">tiêu biểu</span>' : ""}<br><small>${esc(r.category)} · ${esc(r.zone)}</small> ${osm(r)}`;
const now = r => `<span class="chip">${esc(r.hours)}${r.closed.length ? " · nghỉ " + esc(r.closed.join(",")) : ""}</span><span class="chip">giá ${esc(r.tier ?? "null")}</span>
  <small>giờ: ${esc(r.hours_by)} ${link(r.hours_url)} · giá: ${esc(r.price_by)} ${link(r.price_url)}</small>${r.note ? `<br><small>${esc(r.note)}</small>` : ""}${hint(r)}`;
const hint = r => {
  const h = r.hint || {}, a = h.aihay, c = h.checked; let s = "";
  if (a) s += `<br><small class="${a.verdict.startsWith("SAI") ? "warn" : ""}">AI-Hay: <b>${esc(a.verdict)}</b> — ${esc(a.hours_src).slice(0, 90)} · ${esc(a.ticket_src).slice(0, 60)} ${(a.links || []).slice(0, 2).map(link).join(" ")}</small>`;
  if (c) s += `<br><small class="${c.agrees_with_ours === false ? "warn" : ""}">Codex mở trang: ${c.agrees_with_ours === true ? "khớp" : c.agrees_with_ours === false ? "<b>LỆCH</b>" : "chưa rõ"} — ${esc(c.page_says_hours || "")} ${esc(c.page_says_ticket || "")} ${link(c.source)}</small>`;
  return s; };
const inp = (k, ph, type = "text") => `<input type="${type}" data-k="${k}" placeholder="${esc(ph)}" value="${esc(S[k] ?? "")}">`;
function T(id, head, rows) { document.getElementById(id).innerHTML = `<tr>${head.map(h => `<th>${h}</th>`).join("")}</tr>` + rows.join(""); }
function render() {
  T("ta", ["Câu hỏi", "Áp cho", "Chọn", "Ghi chú"], D.policies.map(p => `<tr><td><b>${esc(p.q)}</b></td>
    <td><small>${p.names.length ? esc(p.names.slice(0, 12).join(" · ")) : "—"}</small></td>
    <td><select data-k="A|${p.key}">${p.opts.map((o, i) => `<option value="${i}" ${String(S["A|" + p.key] ?? 0) === String(i) ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></td>
    <td>${inp("A|" + p.key + "|note", "tuỳ chọn")}</td></tr>`));
  T("tb", ["POI", "Claude đã chọn", "Hiện tại", "Đồng ý", "Nếu không: sửa thế nào"], D.auto.map(r => `<tr>
    <td>${info(r)}</td><td>${esc(r.why)}</td><td>${now(r)}</td>
    <td><input type="checkbox" data-k="B|${r.poi_id}" ${(S["B|" + r.poi_id] ?? true) ? "checked" : ""}></td>
    <td>${inp("B|" + r.poi_id + "|fix", "giờ / giá / link đúng")}</td></tr>`));
  T("tc", ["POI", "Hiện tại", "Kết luận", "Giờ đúng (nếu sai)", "Mức giá (nếu sai)", "Link bằng chứng"], D.confirm.map(r => {
    const k = "C|" + r.poi_id, v = S[k] || "";
    return `<tr class="${v ? "ok" : ""}"><td>${info(r)}</td><td>${now(r)}</td>
    <td><select data-k="${k}"><option value="">chưa kiểm</option><option value="ok" ${v === "ok" ? "selected" : ""}>Đúng</option>
      <option value="fix" ${v === "fix" ? "selected" : ""}>Sửa →</option><option value="closed" ${v === "closed" ? "selected" : ""}>Đã đóng cửa</option></select></td>
    <td>${inp(k + "|hours", r.hours)}</td>
    <td><select data-k="${k}|tier">${["", "free", "cheap", "medium", "expensive", "included"].map(t => `<option value="${t}" ${(S[k + "|tier"] ?? "") === t ? "selected" : ""}>${t || "giữ"}</option>`).join("")}</select></td>
    <td>${inp(k + "|url", r.hours_url || "https://…", "url")}</td></tr>`; }));
  document.querySelectorAll("[data-k]").forEach(el => el.addEventListener("change", () => {
    S[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; save(); progress();
    if (el.dataset.k.startsWith("C|") && !el.dataset.k.includes("|", 2)) el.closest("tr").className = el.value ? "ok" : ""; }));
  progress();
}
function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} }
function done() { return D.confirm.filter(r => ["ok", "fix"].includes(S["C|" + r.poi_id])).length; }
function progress() {
  const h = D.human_now + done();
  document.getElementById("hn").textContent = h; document.getElementById("ht").textContent = D.human_target;
  document.getElementById("ht2").textContent = D.human_target;
  document.getElementById("need").textContent = Math.max(0, D.human_target - h);
  document.getElementById("hb").style.width = Math.min(100, 100 * h / D.human_target) + "%";
  document.getElementById("ca").textContent = `${D.policies.length} câu`;
  document.getElementById("cb").textContent = `${D.auto.filter(r => S["B|" + r.poi_id] ?? true).length}/${D.auto.length} đồng ý`;
  document.getElementById("cc").textContent = `${D.confirm.filter(r => S["C|" + r.poi_id]).length}/${D.confirm.length} đã kiểm`;
}
function exportJson() {
  const out = {schema: "review_v21", final: true, snapshot_built: D.built_at, exported_at: new Date().toISOString().slice(0, 10),
    questions: {}, names: [], status: [], duplicates: [], verify: [], old_town: {parent: null, include: [], exclude: []},
    policies: {}, auto_review: []};
  D.policies.forEach(p => { const i = Number(S["A|" + p.key] ?? 0);
    out.policies[p.key] = {choice: i, label: p.opts[i], recommended: i === 0, ids: p.ids, note: S["A|" + p.key + "|note"] || null}; });
  D.auto.forEach(r => { const ok = S["B|" + r.poi_id] ?? true; out.auto_review.push({poi_id: r.poi_id, name: r.name, agree: ok, fix: S["B|" + r.poi_id + "|fix"] || null}); });
  D.confirm.forEach(r => { const k = "C|" + r.poi_id, v = S[k];
    if (v === "closed") out.status.push({poi_id: r.poi_id, status: "excluded", reason: "người dùng: đã đóng cửa (chốt cuối)"});
    if (v !== "ok" && v !== "fix") return;
    const it = {poi_id: r.poi_id, hours: (v === "fix" && S[k + "|hours"]) ? S[k + "|hours"].trim() : r.hours,
      evidence_url: (S[k + "|url"] || r.hours_url || "").trim() || undefined, note: v === "ok" ? "người dùng xác nhận giá trị hiện tại (chốt cuối)" : "người dùng sửa (chốt cuối)"};
    if (S[k + "|tier"]) it.price_tier = S[k + "|tier"];
    if (r.closed.length && v === "ok") it.closed_days = r.closed;
    out.verify.push(it); });
  const blob = new Blob([JSON.stringify(out, null, 1)], {type: "application/json"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `final_review_${out.exported_at.replaceAll("-", "")}.json`; a.click();
}
render();
</script></body></html>
"""


def main():
    data = collect()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = PAGE.replace("__DATA__", blob).replace("__BUILT__", data["built_at"])
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote", OUT, {"human_now": data["human_now"], "policies": len(data["policies"]),
                         "auto": len(data["auto"]), "confirm": len(data["confirm"]),
                         "cooking": len(data["policies"][1]["ids"])})


if __name__ == "__main__":
    main()
