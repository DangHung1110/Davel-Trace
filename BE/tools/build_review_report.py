"""Build a read-only report of the reviewed POIs (Phase 4).

One row per POI on the review page (the ids in review_drafts.jsonl): the
verdict and note from review_log.jsonl, the edits applied, and the POI as it
is now in pois.json (cat, hours and their source, duration, price band,
rating, who verified it). Search box and filters, no editing: decisions are
made on FE/verify_review.html and applied by ingest_verdicts.py.

Usage (from repo root, after an ingest)::

    python BE/tools/build_review_report.py [--snapshot DIR] [--out FE/verify_result.html]

Stdlib only, Python 3.10+.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from BE.common import SAFE_HOURS, hours_group  # noqa: E402

DEFAULT_SNAPSHOT = REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1"
DEFAULT_OUT = REPO_ROOT / "FE" / "verify_result.html"
BAND_VI = {"cheap": "Rẻ", "medium": "Trung bình", "expensive": "Đắt"}
VERDICT_VI = {"dung": "Đúng", "loai": "LOẠI", None: "Chưa duyệt"}


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def report_rows(snapshot: Path) -> list[dict]:
    pois = {p["poi_id"]: p for p in
            json.loads((snapshot / "pois.json").read_text(encoding="utf-8"))["pois"]}
    ids = [d["poi_id"] for d in _jsonl(snapshot / "review_drafts.jsonl")]
    last = {}
    for entry in _jsonl(snapshot / "review_log.jsonl"):
        last[entry["poi_id"]] = entry  # the latest applied line wins
    rows = []
    for pid in ids:
        poi, entry = pois[pid], last.get(pid) or {}
        hours = poi.get("opening_hours") or []
        safe = SAFE_HOURS.get(hours_group(poi.get("cat") or ""))
        tags = poi.get("smart_tags") or {}
        rows.append({
            "poi_id": pid, "name": poi.get("name"), "cat": poi.get("cat"),
            "verdict": entry.get("verdict"), "reviewer": entry.get("reviewer"),
            "note": entry.get("note") or "", "edits": sorted(entry.get("edits") or {}),
            "hours": ", ".join(hours), "hours_source": poi.get("hours_source") or "",
            "safe": ", ".join(safe) if safe is not None and not hours else "",
            "p50": (poi.get("visit_min") or {}).get("p50"), "dur_source": poi.get("dur_source"),
            "band": tags.get("price_band"), "ticket": poi.get("ticket_vnd"),
            "rating": poi.get("rating"), "verified": bool(poi.get("verified")),
            "verified_by": poi.get("verified_by") or "", "lat": poi.get("lat"), "lon": poi.get("lon"),
        })
    return rows


def render(rows: list[dict], snapshot: str) -> str:
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("__TITLE__", html.escape(f"Kết quả duyệt · {snapshot}")) \
               .replace("__DATA__", data) \
               .replace("__BANDS__", json.dumps(BAND_VI, ensure_ascii=False)) \
               .replace("__VERDICTS__", json.dumps({k or "": v for k, v in VERDICT_VI.items()},
                                                   ensure_ascii=False))


PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f6f8;color:#1d2330}
  header{position:sticky;top:0;background:#fff;border-bottom:1px solid #e3e6eb;padding:12px 16px;z-index:2}
  h1{font-size:17px;margin:0 0 8px}
  .bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  input,select{font:inherit;padding:6px 8px;border:1px solid #cfd5dd;border-radius:6px;background:#fff}
  input{min-width:220px}
  .chip{padding:5px 10px;border:1px solid #cfd5dd;border-radius:999px;background:#fff;cursor:pointer}
  .chip.on{background:#1d2330;color:#fff;border-color:#1d2330}
  .count{color:#5a6472;margin-left:auto}
  main{padding:12px 16px}
  table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e3e6eb}
  th,td{padding:7px 9px;border-bottom:1px solid #edf0f3;text-align:left;vertical-align:top}
  th{background:#fafbfc;font-weight:600;position:sticky;top:96px}
  td.n{white-space:nowrap}
  .v{font-weight:700;white-space:nowrap}
  .v.dung{color:#157347}.v.loai{color:#b42318}.v.none{color:#8a5a00}
  .muted{color:#6b7480}.mono{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
  .ed{display:inline-block;background:#eef3ff;color:#2b4aa0;border-radius:4px;padding:0 5px;margin:1px 2px 1px 0;font-size:12px}
  .note{max-width:460px}
  a{color:#1f5fbf;text-decoration:none}
  @media (max-width:800px){th{top:150px}.note{max-width:none}}
</style></head><body>
<header><h1>__TITLE__</h1>
<div class="bar">
  <input id="q" type="search" placeholder="Tìm tên, ghi chú…">
  <span id="vf"></span>
  <select id="cat"><option value="">Mọi loại hình</option></select>
  <select id="band"><option value="">Mọi mức giá</option></select>
  <select id="hrs"><option value="">Mọi giờ</option><option value="has">Có giờ</option>
    <option value="safe">Dùng giờ an toàn</option></select>
  <span class="count" id="count"></span>
</div></header>
<main><table><thead><tr><th>Kết quả</th><th>Tên</th><th>Loại</th><th>Giờ mở cửa</th>
<th>Thời lượng</th><th>Mức giá</th><th>Rating</th><th>Đã sửa · ghi chú</th></tr></thead>
<tbody id="rows"></tbody></table></main>
<script>
(function () {
  var DATA = __DATA__, BAND = __BANDS__, VERD = __VERDICTS__;
  var state = { v: "", q: "", cat: "", band: "", hrs: "" };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var cats = {}, bands = {};
  DATA.forEach(function (r) { cats[r.cat] = 1; if (r.band) bands[r.band] = 1; });
  Object.keys(cats).sort().forEach(function (c) { document.getElementById("cat").insertAdjacentHTML("beforeend", '<option>' + esc(c) + '</option>'); });
  Object.keys(bands).forEach(function (b) { document.getElementById("band").insertAdjacentHTML("beforeend", '<option value="' + b + '">' + esc(BAND[b]) + '</option>'); });
  var counts = { "": DATA.length };
  DATA.forEach(function (r) { var k = r.verdict || "none"; counts[k] = (counts[k] || 0) + 1; });
  document.getElementById("vf").innerHTML = [["", "Tất cả"], ["dung", "Đúng"], ["loai", "LOẠI"], ["none", "Chưa duyệt"]]
    .map(function (x) { return '<button class="chip' + (x[0] === "" ? " on" : "") + '" data-v="' + x[0] + '">' + x[1] + " " + (counts[x[0]] || 0) + "</button>"; }).join(" ");
  function hoursCell(r) {
    if (r.hours) return '<span class="mono">' + esc(r.hours) + '</span><div class="muted">nguồn: ' + esc(r.hours_source || "crawl") + "</div>";
    if (r.safe) return '<span class="muted">— giờ an toàn nhóm</span><div class="mono muted">' + esc(r.safe) + "</div>";
    return '<span class="muted">—</span>';
  }
  function render() {
    var q = state.q.toLowerCase(), out = [], n = 0;
    DATA.forEach(function (r) {
      var v = r.verdict || "none";
      if (state.v && v !== state.v) return;
      if (state.cat && r.cat !== state.cat) return;
      if (state.band && r.band !== state.band) return;
      if (state.hrs === "has" && !r.hours) return;
      if (state.hrs === "safe" && r.hours) return;
      if (q && (r.name + " " + r.note).toLowerCase().indexOf(q) < 0) return;
      n++;
      var maps = "https://www.google.com/maps/search/?api=1&query=" + r.lat + "," + r.lon;
      out.push("<tr><td class='v " + v + "'>" + esc(VERD[r.verdict || ""]) + "</td>" +
        "<td><a href='" + maps + "' target='_blank' rel='noopener'>" + esc(r.name) + "</a>" +
        "<div class='muted mono'>" + esc(r.verified ? "verified · " + r.verified_by : "chưa verify") + "</div></td>" +
        "<td class='n'>" + esc(r.cat) + "</td><td>" + hoursCell(r) + "</td>" +
        "<td class='n'>" + (r.p50 ? esc(r.p50) + " phút" : "—") + "<div class='muted'>" + esc(r.dur_source === "human" ? "người nhập" : "theo loại") + "</div></td>" +
        "<td class='n'>" + esc(BAND[r.band] || "—") + (r.ticket ? "<div class='muted'>vé " + esc(r.ticket.toLocaleString("vi-VN")) + "đ</div>" : "") + "</td>" +
        "<td>" + esc(r.rating == null ? "—" : r.rating) + "</td>" +
        "<td class='note'>" + r.edits.map(function (e) { return "<span class='ed'>" + esc(e) + "</span>"; }).join("") + esc(r.note) + "</td></tr>");
    });
    document.getElementById("rows").innerHTML = out.join("");
    document.getElementById("count").textContent = n + " / " + DATA.length + " điểm";
  }
  document.getElementById("vf").addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    state.v = b.getAttribute("data-v");
    [].forEach.call(document.querySelectorAll("#vf .chip"), function (x) { x.classList.toggle("on", x === b); });
    render();
  });
  document.getElementById("q").addEventListener("input", function (e) { state.q = e.target.value; render(); });
  ["cat", "band", "hrs"].forEach(function (id) {
    document.getElementById(id).addEventListener("change", function (e) { state[id] = e.target.value; render(); });
  });
  render();
})();
</script></body></html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    rows = report_rows(args.snapshot)
    args.out.write_text(render(rows, args.snapshot.name), encoding="utf-8")
    done = sum(1 for r in rows if r["verdict"])
    print(f"wrote {args.out} ({len(rows)} rows, {done} reviewed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
