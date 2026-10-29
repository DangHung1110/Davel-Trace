#!/usr/bin/env python3
"""Build a self-contained human-review page for the auto-verify queue.

Reads
-----
BE/data/snapshots/<snapshot>/pois.json          (full POI details)
BE/data/snapshots/<snapshot>/auto_verify_queue.jsonl
                                                (rows: poi_id, name, cat,
                                                 decision, hard, queue, siblings)

Writes
------
FE/verify_review.html   -- single file, no CDN, no fetch, no build step.
                           Opens by double-click (file://) and can be emailed.

Export format produced by the page (consumed by a future ingest lane)
---------------------------------------------------------------------
The "Xuất JSONL" button downloads ``verify_verdicts_YYYYMMDD.jsonl``
(UTF-8, no BOM, one JSON object per line, LF line ending)::

    {"poi_id": "ChIJ...", "verdict": "dung", "note": "", "reviewer": "Lan", "ts": "2026-10-29T14:03:11.482Z"}
    {"poi_id": "ChIJ...", "verdict": "loai", "note": "trùng quán bên cạnh", "reviewer": "Lan", "ts": "2026-10-29T14:04:02.010Z"}

Field contract (stable; ingest must reject anything else):

- ``poi_id``   str  -- key of ``pois.json`` / queue row. Unique per line.
- ``verdict``  str  -- exactly ``"dung"`` (keep + may mark verified) or
                      ``"loai"`` (drop from pool). **Rows skipped in the UI
                      ("Bỏ qua") are NOT exported.**
- ``note``     str  -- free text, ``""`` when empty. May contain newlines;
                      JSON-escaped, so the line stays one physical line.
- ``reviewer`` str  -- name typed in the page header, ``""`` if not filled.
- ``ts``       str  -- ISO-8601 UTC timestamp (``datetime.isoformat()`` with
                      trailing ``Z``) captured when the verdict was clicked.

Lines are emitted in page (priority) order, i.e. fail rows first, then
museum/park/bar/spa/nature/viewpoint, then the rest alphabetically. The file
name date is the reviewer's local date at export time. Ingest should treat
``poi_id`` as the idempotency key: last line wins if a file contains dupes.

Usage (PowerShell, from repo root)::

    python BE/tools/build_verify_page.py
    python BE/tools/build_verify_page.py --snapshot BE/data/snapshots/danang-v1 \\
        --out FE/verify_review.html

Stdlib only, Python 3.10+.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = REPO_ROOT / "BE" / "data" / "snapshots" / "danang-v1"
DEFAULT_OUT = REPO_ROOT / "FE" / "verify_review.html"

# Categories at 0 verified rows (docs/verify-criteria.md §7) get reviewed
# first so capacity planning can start from them.
PRIORITY_CATS = ["museum", "park", "bar", "spa", "nature", "viewpoint"]


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:  # pragma: no cover - bad data
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _first(mapping: dict, *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def build_rows(snapshot: Path) -> tuple[list[dict], dict]:
    pois_doc = _load_json(snapshot / "pois.json")
    poi_list = pois_doc.get("pois", [])
    pois = {p["poi_id"]: p for p in poi_list}
    queue_path = snapshot / "auto_verify_queue.jsonl"
    queue = _load_jsonl(queue_path)

    missing = [q["poi_id"] for q in queue if q["poi_id"] not in pois]
    if missing:
        raise SystemExit(
            f"{len(missing)} queue rows have no POI in pois.json, e.g. {missing[:3]}"
        )

    rows: list[dict] = []
    for item in queue:
        poi = pois[item["poi_id"]]
        hard = list(item.get("hard") or [])
        soft = list(item.get("queue") or [])
        siblings = []
        for sid in item.get("siblings") or []:
            sib = pois.get(sid)
            if not sib:
                siblings.append({"poi_id": sid, "name": sid, "cat": "", "dist_m": None})
                continue
            dist = None
            if all(isinstance(poi.get(k), (int, float)) for k in ("lat", "lon")) and all(
                isinstance(sib.get(k), (int, float)) for k in ("lat", "lon")
            ):
                dist = round(
                    haversine_m(poi["lat"], poi["lon"], sib["lat"], sib["lon"]), 1
                )
            siblings.append(
                {
                    "poi_id": sid,
                    "name": sib.get("name") or sid,
                    "cat": sib.get("cat") or "",
                    "dist_m": dist,
                    "hours": list(sib.get("opening_hours") or []),
                    "lat": sib.get("lat"),
                    "lon": sib.get("lon"),
                    "verified": bool(sib.get("verified")),
                }
            )

        web_evidence = poi.get("web_evidence")
        if isinstance(web_evidence, dict):
            web_evidence = "; ".join(f"{k}: {v}" for k, v in web_evidence.items() if v)
        elif not isinstance(web_evidence, str):
            web_evidence = None

        visit = poi.get("visit_min") if isinstance(poi.get("visit_min"), dict) else {}
        rows.append(
            {
                "poi_id": item["poi_id"],
                "name": item.get("name") or poi.get("name") or "",
                "cat": item.get("cat") or poi.get("cat") or "",
                "type": poi.get("type") or "",
                "address": _first(poi, "address", "addr", "formatted_address"),
                "hours": list(poi.get("opening_hours") or []),
                "hours_note": poi.get("hours_note") or "",
                "hours_source": poi.get("hours_source") or "",
                "rating": poi.get("rating"),
                "source": poi.get("source") or "",
                "lat": poi.get("lat"),
                "lon": poi.get("lon"),
                "verified": bool(poi.get("verified")),
                "verified_by": poi.get("verified_by") or "",
                "decision": item.get("decision") or "queue",
                "hard": hard,
                "queue": soft,
                "siblings": siblings,
                "access_note": poi.get("access_note") or "",
                "ticket_vnd": poi.get("ticket_vnd"),
                "dur_p50": visit.get("p50"),
                "web_evidence": web_evidence,
                "tags": list(poi.get("tags") or [])[:5],
            }
        )

    def sort_key(row: dict) -> tuple:
        cat = row["cat"]
        rank = PRIORITY_CATS.index(cat) if cat in PRIORITY_CATS else len(PRIORITY_CATS)
        return (
            0 if row["decision"] == "fail" else 1,
            rank,
            cat,
            row["name"].lower(),
        )

    rows.sort(key=sort_key)

    meta = {
        "snapshot": pois_doc.get("snapshot") or snapshot.name,
        "fetched_at": pois_doc.get("fetched_at") or "",
        "generated": __import__("datetime").date.today().isoformat(),
        "queue_hash": hashlib.sha256(queue_path.read_bytes()).hexdigest()[:16],
        "queue_total": len(queue),
        "poi_total": len(poi_list),
        "priority_cats": PRIORITY_CATS,
    }
    return rows, meta


def _script_json(payload: Any) -> str:
    """JSON safe to inline inside a <script type="application/json"> block."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace(
        "\u2029", "\\u2029"
    )


PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Duyệt POI · __SNAPSHOT__ · Davel-Trace</title>
<style>
  :root{
    --bg:#f4f6f8; --card:#ffffff; --ink:#121a24; --muted:#5c6b7a;
    --line:#dde4ec; --brand:#0f6ab4; --brand-ink:#0a4f87;
    --ok:#137a4b; --ok-bg:#e6f6ee; --no:#b3261e; --no-bg:#fdeceb;
    --skip:#6b7280; --skip-bg:#eef1f4; --warn:#8a5a00; --warn-bg:#fff4d6;
    --fail:#7f1d1d; --fail-bg:#fbe3e3;
    --radius:10px; --shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.08);
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:var(--bg); color:var(--ink);
    font:15px/1.55 "Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  a{color:var(--brand);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:1040px;margin:0 auto;padding:0 18px 80px}
  header.top{background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20;box-shadow:var(--shadow)}
  .top-inner{max-width:1040px;margin:0 auto;padding:12px 18px 10px}
  .top-row{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
  .brand{font-weight:700;font-size:15px;letter-spacing:.2px}
  .brand span{color:var(--muted);font-weight:500}
  .spacer{flex:1 1 auto}
  .rev{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--muted)}
  .rev input{border:1px solid var(--line);border-radius:7px;padding:6px 9px;font:inherit;font-size:13px;width:150px;background:#fff;color:var(--ink)}
  .bar-row{display:flex;align-items:center;gap:12px;margin-top:9px;flex-wrap:wrap}
  .bar{flex:1 1 240px;height:9px;background:#e3e9f0;border-radius:99px;overflow:hidden;min-width:160px}
  .bar > i{display:block;height:100%;width:0;background:linear-gradient(90deg,#0f6ab4,#25a06b);transition:width .18s ease}
  .counts{font-size:13px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
  .counts b{color:var(--ink)}
  .btn{
    appearance:none;border:1px solid var(--line);background:#fff;color:var(--ink);
    border-radius:8px;padding:7px 12px;font:inherit;font-size:13.5px;font-weight:600;
    cursor:pointer;transition:background .12s,border-color .12s,transform .06s;
  }
  .btn:hover{background:#f7f9fb;border-color:#c7d2de}
  .btn:active{transform:translateY(1px)}
  .btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}
  .btn.primary:hover{background:var(--brand-ink);border-color:var(--brand-ink)}
  .btn.ghost{background:transparent}
  .btn:disabled{opacity:.5;cursor:not-allowed}
  .intro{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);margin:18px 0;box-shadow:var(--shadow)}
  .intro summary{cursor:pointer;padding:14px 18px;font-weight:700;font-size:15px;list-style:none;display:flex;align-items:center;gap:8px}
  .intro summary::-webkit-details-marker{display:none}
  .intro summary::before{content:"▸";color:var(--muted);font-size:12px;transition:transform .15s}
  .intro[open] summary::before{transform:rotate(90deg)}
  .intro .body{padding:0 18px 18px;border-top:1px solid var(--line);margin-top:2px}
  .intro h3{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin:16px 0 7px}
  .intro ol,.intro ul{margin:0;padding-left:20px}
  .intro li{margin:4px 0}
  .crit{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin:8px 0 0}
  .crit div{background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:9px 11px;font-size:13.5px}
  .crit b{display:block;margin-bottom:2px}
  .note{font-size:13px;color:var(--muted)}
  .callout{background:var(--warn-bg);border:1px solid #f0dca4;border-radius:8px;padding:10px 12px;font-size:13.5px;margin-top:12px}
  .filters{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;box-shadow:var(--shadow);margin-bottom:14px}
  .filters label{font-size:12.5px;color:var(--muted);display:flex;flex-direction:column;gap:3px}
  .filters select,.filters input[type=search]{
    border:1px solid var(--line);border-radius:7px;padding:6px 9px;font:inherit;font-size:13.5px;background:#fff;color:var(--ink);
  }
  .filters input[type=search]{min-width:210px}
  .filters .chk{flex-direction:row;align-items:center;gap:6px;font-size:13.5px;color:var(--ink)}
  .filters .chk input{width:15px;height:15px}
  .hits{margin-left:auto;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
  .card{background:var(--card);border:1px solid var(--line);border-left:5px solid #c9d4e0;border-radius:var(--radius);padding:14px 16px;margin-bottom:12px;box-shadow:var(--shadow);scroll-margin-top:96px}
  .card.v-dung{border-left-color:var(--ok)}
  .card.v-loai{border-left-color:var(--no)}
  .card.v-skip{border-left-color:#9aa6b2}
  .card.hide{display:none}
  .card h2{font-size:17px;line-height:1.3;margin:0 0 3px;font-weight:700;word-break:break-word}
  .card .pid{font:11.5px/1.4 ui-monospace,Consolas,monospace;color:#8b98a6;word-break:break-all}
  .badges{display:flex;gap:6px;flex-wrap:wrap;margin:7px 0 0}
  .badge{font-size:11.5px;font-weight:700;letter-spacing:.2px;border-radius:99px;padding:2px 9px;background:#eef2f6;color:#41505f;border:1px solid #e0e7ef}
  .badge.cat{background:#eaf3fb;color:#0a4f87;border-color:#cfe4f5}
  .badge.prio{background:var(--warn-bg);color:var(--warn);border-color:#f0dca4}
  .badge.fail{background:var(--fail-bg);color:var(--fail);border-color:#f3c7c7}
  .badge.ok{background:var(--ok-bg);color:var(--ok);border-color:#bfe6d2}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:6px 18px;margin:11px 0 0;font-size:13.5px}
  .grid .k{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.4px;display:block}
  .mono{font-family:ui-monospace,Consolas,monospace;font-size:12.5px}
  .reasons{margin:12px 0 0;padding:10px 12px;background:#fbfcfd;border:1px solid var(--line);border-radius:8px}
  .reasons .ttl{font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:7px}
  .chip{display:block;margin:0 0 7px}
  .chip:last-child{margin-bottom:0}
  .chip .tag{display:inline-block;font:600 12px/1.5 ui-monospace,Consolas,monospace;border-radius:6px;padding:1px 7px;background:var(--warn-bg);color:var(--warn);border:1px solid #f0dca4;margin-right:7px;vertical-align:top}
  .chip.hard .tag{background:var(--fail-bg);color:var(--fail);border-color:#f3c7c7}
  .chip .hint{font-size:13px;color:#3d4a58}
  .siblings{margin:10px 0 0;padding:10px 12px;background:#f8fafc;border:1px dashed #cfd9e3;border-radius:8px;font-size:13.5px}
  .siblings .ttl{font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:5px}
  .siblings ul{margin:0;padding-left:18px}
  .siblings li{margin:2px 0}
  .extra{margin:9px 0 0;font-size:13px;color:#3d4a58}
  .extra .k{color:var(--muted);font-weight:600}
  .actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:13px;padding-top:12px;border-top:1px solid var(--line)}
  .vbtn{min-width:86px}
  .vbtn.dung.on{background:var(--ok);border-color:var(--ok);color:#fff}
  .vbtn.loai.on{background:var(--no);border-color:var(--no);color:#fff}
  .vbtn.skip.on{background:var(--skip);border-color:var(--skip);color:#fff}
  .vbtn.dung:hover:not(.on){background:var(--ok-bg);border-color:#bfe6d2;color:var(--ok)}
  .vbtn.loai:hover:not(.on){background:var(--no-bg);border-color:#f3c7c7;color:var(--no)}
  .actions .note-in{flex:1 1 260px;min-width:200px}
  .actions textarea{
    width:100%;border:1px solid var(--line);border-radius:7px;padding:6px 9px;font:inherit;font-size:13px;
    resize:vertical;min-height:34px;background:#fff;color:var(--ink);
  }
  .actions textarea:focus,.filters select:focus,.filters input:focus,.rev input:focus{outline:2px solid #bcdaf3;outline-offset:1px}
  .empty{background:var(--card);border:1px dashed var(--line);border-radius:var(--radius);padding:28px;text-align:center;color:var(--muted)}
  footer{margin-top:22px;font-size:12px;color:#8b98a6;line-height:1.7;text-align:center}
  .toast{
    position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(12px);
    background:#121a24;color:#fff;padding:10px 16px;border-radius:9px;font-size:13.5px;
    opacity:0;pointer-events:none;transition:opacity .18s,transform .18s;z-index:50;max-width:90vw;
  }
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
  @media (max-width:640px){
    .top-inner{padding:10px 12px 9px}
    .wrap{padding:0 12px 70px}
    .rev input{width:120px}
    .actions .note-in{flex-basis:100%}
    .grid{grid-template-columns:1fr 1fr}
  }
  @media print{
    header.top,.filters,.actions,.intro{display:none!important}
    .card{break-inside:avoid;box-shadow:none}
    body{background:#fff}
  }
</style>
</head>
<body>
<header class="top">
  <div class="top-inner">
    <div class="top-row">
      <div class="brand">Duyệt POI <span>· __SNAPSHOT__ · __GENERATED__</span></div>
      <div class="spacer"></div>
      <div class="rev">
        <label for="reviewer">Người duyệt</label>
        <input id="reviewer" type="text" placeholder="Tên của bạn" autocomplete="off">
      </div>
      <button class="btn primary" id="export" type="button">Xuất JSONL</button>
    </div>
    <div class="bar-row">
      <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="bar"><i id="barfill"></i></div>
      <div class="counts" id="counts">Đã làm <b>0</b>/__TOTAL__</div>
      <div class="counts" id="breakdown">Dung 0 · LOẠI 0 · Bỏ qua 0</div>
    </div>
  </div>
</header>

<div class="wrap">
  <details class="intro" open>
    <summary>Việc cần làm &amp; tiêu chí (đọc 1 lần, ~2 phút)</summary>
    <div class="body">
      <h3>1. Việc cần làm</h3>
      <ol>
        <li>Mỗi thẻ là <b>một POI bị máy đẩy vào hàng chờ</b> (không tự bật <code>verified=true</code>). Đọc tên, loại hình, giờ, toạ độ; mở <b>Google Maps</b> khi cần đối chiếu ngoài đời.</li>
        <li>Bấm <b>Dung</b> nếu điểm này giữ được trong pool; <b>LOẠI</b> nếu không phải điểm du lịch / sai quá nặng / trùng; <b>Bỏ qua</b> nếu chưa đủ căn cứ — dòng Bỏ qua <u>không</u> được xuất file.</li>
        <li>Ghi chú ngắn khi quyết định không hiển nhiên (vd: "trùng quán bên cạnh", "giờ chỉ là ước lượng"). Bấm lại nút đang chọn để bỏ đánh dấu.</li>
        <li>Tiến độ tự lưu trong trình duyệt này (localStorage) — đóng tab mở lại vẫn còn, miễn là cùng file + cùng snapshot.</li>
      </ol>

      <h3>2. Tiêu chí ngắn gọn (chi tiết: <code>docs/verify-criteria.md</code>)</h3>
      <div class="crit">
        <div><b>Địa chỉ / toạ độ</b>Nằm trong Đà Nẵng (bbox 15.80–16.35 N, 107.75–108.55 E) và đúng chỗ trên bản đồ. Snapshot <u>không có field địa chỉ</u> — phải xem link Maps.</div>
        <div><b>Giờ mở cửa</b>Đọc được, giờ hợp lệ, qua đêm vẫn OK (vd 11:00-00:00). Máy chỉ kiểm format, <u>không</u> kiểm POI có mở đúng giờ đó không.</div>
        <div><b>Tên &amp; loại hình</b>Tên đúng là điểm du lịch, không phải cửa hàng điện nước; <code>type</code> phải khớp <code>cat</code> (bảng refinement ở mục 3.1 của criteria).</div>
        <div><b>Có trùng không</b>Trùng tên đã chuẩn hoá, hoặc cặp &lt;100 m có ≥2 token tên chung → xem siblings, chọn giữ 1 hoặc LOẠI.</div>
      </div>
      <div class="callout">
        <b>Thứ tự ưu tiên mặc định:</b> <code>museum · park · bar · spa · nature · viewpoint</code> (nhóm đang 0 verified, mở được capacity plan ngay) lên trước, sau đó các category còn lại; dòng <b>fail</b> (vi phạm cứng) luôn nằm đầu.
        <br><b>Nhắc lại:</b> <code>verified=true</code> chỉ có nghĩa "cấu trúc đủ tin để planner dùng", <u>không</u> xác nhận type/giá/rating đúng ngoài đời. Đừng Dung chỉ để đủ số.
      </div>

      <h3>3. Xuất file &amp; gửi lại</h3>
      <ol>
        <li>Bấm <b>Xuất JSONL</b> ở góc trên. File tải về tên <code>verify_verdicts_YYYYMMDD.jsonl</code>.</li>
        <li>Mỗi dòng đã quyết định là 1 JSON: <code>{"poi_id","verdict":"dung"|"loai","note","reviewer","ts"}</code>. Mỗi POI tối đa 1 dòng; dòng Bỏ qua không có trong file.</li>
        <li>Gửi lại file đó kèm tên snapshot <code>__SNAPSHOT__</code> (và ngày review) cho người phụ trách ingest — <u>không</u> sửa tay <code>pois.json</code>.</li>
      </ol>
      <p class="note">File này tự chứa: mở bằng double-click, không cần mạng, không cần server. Chỉ link Google Maps là ra ngoài.</p>
    </div>
  </details>

  <div class="filters">
    <label>Category
      <select id="f-cat"><option value="">Tất cả</option></select>
    </label>
    <label>Lý do
      <select id="f-reason"><option value="">Tất cả</option></select>
    </label>
    <label>Tìm kiếm
      <input id="f-q" type="search" placeholder="tên, type, poi_id, ghi chú…" autocomplete="off">
    </label>
    <label class="chk"><input id="f-todo" type="checkbox"> Chỉ chưa xử lý</label>
    <button class="btn ghost" id="f-reset" type="button">Xoá lọc</button>
    <div class="hits" id="hits"></div>
  </div>

  <div id="list"></div>
  <div class="empty hide" id="empty">Không có dòng nào khớp bộ lọc.</div>

  <footer>
    Snapshot <b>__SNAPSHOT__</b> · queue hash <span class="mono">__HASH__</span> · tạo __GENERATED__ · __TOTAL__ dòng<br>
    Tiến độ lưu tại key <span class="mono" id="storekey"></span>
  </footer>
</div>

<div class="toast" id="toast" role="status" aria-live="polite"></div>

<script type="application/json" id="verify-data">__DATA__</script>
<script type="application/json" id="verify-meta">__META__</script>
<script>
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("verify-data").textContent);
  var META = JSON.parse(document.getElementById("verify-meta").textContent);
  var STORE_KEY = "davel-trace-verify:" + META.snapshot + ":" + META.queue_hash + ":" + META.generated;
  var REASON_LABEL = {
    hours_missing: "Thiếu giờ mở cửa",
    rating_perfect: "Rating 5.0 tuyệt đối",
    near_duplicate: "Nghi trùng gần (<100 m)",
    duplicate_name: "Trùng tên",
    duration_outlier: "Thời lượng lệch bất thường",
    name_generic: "Tên chung chung / 1 token",
    ticket_unverified: "Giá vé chưa xác minh",
    type_unmapped: "Type không map được",
    type_cat_mismatch: "Type lệch category",
    coords_outside_bbox: "Toạ độ ngoài Đà Nẵng",
    coords_missing: "Thiếu toạ độ",
    name_missing: "Thiếu tên",
    source_missing: "Thiếu nguồn",
    type_missing: "Thiếu type",
    cat_missing: "Thiếu category",
    cat_unknown: "Category lạ",
    duplicate_poi_id: "Trùng poi_id",
    hours_format_invalid: "Giờ sai format",
    hours_out_of_range: "Giờ ngoài 00:00–23:59",
    hours_zero_length: "Giờ bắt đầu = kết thúc"
  };
  var REASON_HINT = {
    hours_missing: "Kiểm giờ thật trên Google Maps/website. Không rõ thì Bỏ qua hoặc ghi chú, đừng đoán.",
    rating_perfect: "5.0 tuyệt đối thường do ít review hoặc review ảo — mở Maps xem số lượng review.",
    near_duplicate: "So với sibling bên dưới (tên + khoảng cách). Nếu là cùng một chỗ: giữ 1, LOẠI phần còn lại.",
    duplicate_name: "Trùng tên sau chuẩn hoá — xác nhận có phải cùng một điểm hay 2 chi nhánh khác nhau.",
    duration_outlier: "p50 lệch >60% median của category. Chỉ là cảnh báo mềm; cân nhắc khi planner dùng để chia lịch.",
    name_generic: "Tên 1 token hoặc quá chung, dễ junk/trùng. Kiểm tên thật, nếu là quán nhỏ không phải điểm du lịch thì LOẠI.",
    ticket_unverified: "Có thể có vé/giá nhưng chưa xác minh (fee toàn snapshot = 0). Nếu là điểm thu vé, ghi chú giá.",
    type_unmapped: "Nhãn type thô không map được sang 14 category. Kiểm loại hình thật trước khi Dung.",
    type_cat_mismatch: "Type và cat lệch nhau (ngoài bảng refinement). Một trong hai field sai — xem tên thật.",
    coords_outside_bbox: "Toạ độ nằm ngoài Đà Nẵng → gần như chắc chắn LOẠI (vd VinWonders Nam Hội An ở Quảng Nam).",
    coords_missing: "Không có toạ độ → không dùng được cho route. Sửa dữ liệu hoặc LOẠI.",
    name_missing: "Không có tên → LOẠI hoặc bổ sung tên.",
    source_missing: "Không có nguồn → không truy vết được. LOẠI nếu không xác minh được.",
    type_missing: "Thiếu type → kiểm loại hình rồi bổ sung.",
    cat_missing: "Thiếu category → kiểm loại hình rồi bổ sung.",
    cat_unknown: "Category ngoài 14 nhóm planner biết → sửa cat hoặc LOẠI.",
    duplicate_poi_id: "poi_id lặp trong snapshot — báo lại người ingest, không tự sửa.",
    hours_format_invalid: "Chuỗi giờ không khớp HH:MM-HH:MM → sửa giờ, hoặc LOẠI nếu không tìm được giờ.",
    hours_out_of_range: "Giờ ngoài 00:00–23:59 → sửa giờ.",
    hours_zero_length: "Giờ bắt đầu trùng giờ kết thúc → sửa giờ."
  };
  var CAT_LABEL = {
    restaurant: "Nhà hàng", cafe: "Cà phê", attraction: "Điểm tham quan", landmark: "Di tích",
    spa: "Spa", lodging: "Lưu trú", bar: "Bar", market: "Chợ", beach: "Biển",
    nature: "Thiên nhiên", museum: "Bảo tàng", park: "Công viên", viewpoint: "Ngắm cảnh",
    transport: "Giao thông"
  };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtCoord(v) { return (typeof v === "number" && isFinite(v)) ? v.toFixed(6) : "—"; }
  function mapsUrl(row) {
    if (typeof row.lat !== "number" || typeof row.lon !== "number") return "";
    return "https://www.google.com/maps/search/?api=1&query=" + row.lat + "," + row.lon;
  }
  function reasonLabel(key) { return REASON_LABEL[key] || key; }
  function catLabel(cat) { return CAT_LABEL[cat] ? CAT_LABEL[cat] + " (" + cat + ")" : (cat || "—"); }

  var state = loadState();
  var byId = {};

  function loadState() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (!raw) return { reviewer: "", verdicts: {} };
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return { reviewer: "", verdicts: {} };
      return {
        reviewer: typeof parsed.reviewer === "string" ? parsed.reviewer : "",
        verdicts: parsed.verdicts && typeof parsed.verdicts === "object" ? parsed.verdicts : {}
      };
    } catch (e) {
      return { reviewer: "", verdicts: {} };
    }
  }
  var saveTimer = null;
  function saveNow() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }
    catch (e) { toast("Không lưu được tiến độ (localStorage bị chặn)."); }
  }
  function saveSoon() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { saveTimer = null; saveNow(); }, 250);
  }
  function toast(msg) {
    var el = $("toast");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.classList.remove("show"); }, 2600);
  }

  function verdictOf(row) {
    var v = state.verdicts[row.poi_id];
    return v && (v.verdict === "dung" || v.verdict === "loai" || v.verdict === "skip") ? v : null;
  }

  function reasonsOf(row) {
    var out = [];
    row.hard.forEach(function (r) { out.push({ key: r, hard: true }); });
    row.queue.forEach(function (r) { out.push({ key: r, hard: false }); });
    if (!out.length) out.push({ key: "unknown", hard: false });
    return out;
  }

  function renderCard(row, idx) {
    var v = verdictOf(row);
    var cls = "card" + (v ? " v-" + v.verdict : "");
    var url = mapsUrl(row);
    var hours = row.hours && row.hours.length ? row.hours.join(" · ") : null;
    var reasons = reasonsOf(row).map(function (r) {
      return '<div class="chip' + (r.hard ? " hard" : "") + '">' +
        '<span class="tag">' + esc(r.key) + "</span>" +
        '<span class="hint"><b>' + esc(reasonLabel(r.key)) + ":</b> " +
        esc(REASON_HINT[r.key] || "Máy không tự quyết được — cần người xem.") + "</span></div>";
    }).join("");

    var sib = "";
    if (row.siblings && row.siblings.length) {
      sib = '<div class="siblings"><div class="ttl">Sibling nghi trùng (' + row.siblings.length + ")</div><ul>" +
        row.siblings.map(function (s) {
          var extra = [];
          if (s.dist_m != null) extra.push("≈ " + s.dist_m + " m");
          if (s.cat) extra.push(esc(s.cat));
          if (s.hours && s.hours.length) extra.push("giờ: " + esc(s.hours.join(" · ")));
          if (s.verified) extra.push("đã verified");
          var link = (typeof s.lat === "number" && typeof s.lon === "number")
            ? ' · <a href="https://www.google.com/maps/search/?api=1&query=' + s.lat + "," + s.lon + '" target="_blank" rel="noopener">Maps</a>'
            : "";
          return "<li><b>" + esc(s.name) + "</b>" +
            (extra.length ? ' <span class="note">(' + extra.join(" · ") + ")</span>" : "") + link +
            '<br><span class="pid">' + esc(s.poi_id) + "</span></li>";
        }).join("") + "</ul></div>";
    }

    var extras = [];
    if (row.access_note) extras.push('<div><span class="k">Ghi chú truy cập:</span> ' + esc(row.access_note) + "</div>");
    if (row.hours_note) extras.push('<div><span class="k">Ghi chú giờ:</span> ' + esc(row.hours_note) + "</div>");
    if (row.hours_source) extras.push('<div><span class="k">Nguồn giờ:</span> ' + esc(row.hours_source) + "</div>");
    if (row.web_evidence) extras.push('<div><span class="k">Bằng chứng web:</span> ' + esc(row.web_evidence) + "</div>");
    if (typeof row.ticket_vnd === "number") extras.push('<div><span class="k">Vé:</span> ' + row.ticket_vnd.toLocaleString("vi-VN") + " đ</div>");
    if (typeof row.dur_p50 === "number") extras.push('<div><span class="k">Thời lượng gợi ý p50:</span> ' + row.dur_p50 + " phút</div>");

    var badges = '<span class="badge cat">' + esc(catLabel(row.cat)) + "</span>";
    if (row.decision === "fail") badges += '<span class="badge fail">FAIL · vi phạm cứng</span>';
    if (META.priority_cats.indexOf(row.cat) !== -1) badges += '<span class="badge prio">ưu tiên</span>';
    if (row.verified) badges += '<span class="badge ok">đã verified (' + esc(row.verified_by || "?") + ")</span>";

    var html =
      '<article class="' + cls + '" id="row-' + idx + '" data-id="' + esc(row.poi_id) + '">' +
        '<h2>' + esc(row.name || "(không tên)") + "</h2>" +
        '<div class="pid">' + esc(row.poi_id) + "</div>" +
        '<div class="badges">' + badges + "</div>" +
        '<div class="grid">' +
          '<div><span class="k">Địa chỉ</span>' + (row.address ? esc(row.address) : '<span class="note">snapshot không có field địa chỉ — đối chiếu qua Maps</span>') + "</div>" +
          '<div><span class="k">Giờ mở cửa</span>' + (hours ? esc(hours) : '<span class="note">— (thiếu)</span>') + "</div>" +
          '<div><span class="k">Rating</span>' + (typeof row.rating === "number" ? row.rating.toFixed(1) : "—") + "</div>" +
          '<div><span class="k">Type (nhãn thô)</span>' + esc(row.type || "—") + "</div>" +
          '<div><span class="k">Nguồn</span>' + esc(row.source || "—") + "</div>" +
          '<div><span class="k">Toạ độ</span><span class="mono">' + fmtCoord(row.lat) + ", " + fmtCoord(row.lon) + "</span>" +
            (url ? ' · <a href="' + url + '" target="_blank" rel="noopener">Google Maps ↗</a>' : "") + "</div>" +
        "</div>" +
        '<div class="reasons"><div class="ttl">Lý do bị queue — cần kiểm gì</div>' + reasons + "</div>" +
        sib +
        (extras.length ? '<div class="extra">' + extras.join("") + "</div>" : "") +
        '<div class="actions">' +
          '<button class="btn vbtn dung' + (v && v.verdict === "dung" ? " on" : "") + '" type="button" data-verdict="dung">Dung</button>' +
          '<button class="btn vbtn loai' + (v && v.verdict === "loai" ? " on" : "") + '" type="button" data-verdict="loai">LOẠI</button>' +
          '<button class="btn vbtn skip' + (v && v.verdict === "skip" ? " on" : "") + '" type="button" data-verdict="skip">Bỏ qua</button>' +
          '<div class="note-in"><textarea rows="1" placeholder="Ghi chú (tuỳ chọn) — vd: trùng quán bên cạnh, giờ ước lượng…" aria-label="Ghi chú cho ' + esc(row.name) + '">' + esc(v ? v.note || "" : "") + "</textarea></div>" +
        "</div>" +
      "</article>";
    return html;
  }

  function buildList() {
    var parts = [];
    DATA.forEach(function (row, idx) {
      byId[row.poi_id] = { row: row, idx: idx };
      parts.push(renderCard(row, idx));
    });
    $("list").innerHTML = parts.join("");
  }

  function setVerdict(poiId, verdict) {
    var cur = state.verdicts[poiId];
    var card = document.querySelector('[data-id="' + CSS.escape(poiId) + '"]');
    var textarea = card ? card.querySelector("textarea") : null;
    if (cur && cur.verdict === verdict) {
      // Un-toggling keeps a typed note (as a pending, un-decided entry).
      var keepNote = textarea ? textarea.value : (cur.note || "");
      if (keepNote) {
        state.verdicts[poiId] = { verdict: null, note: keepNote, ts: new Date().toISOString() };
      } else {
        delete state.verdicts[poiId];
      }
    } else {
      state.verdicts[poiId] = {
        verdict: verdict,
        note: cur ? cur.note || "" : (textarea ? textarea.value : ""),
        ts: new Date().toISOString()
      };
      if (textarea) state.verdicts[poiId].note = textarea.value;
    }
    saveNow();
    updateCardUI(poiId);
    updateProgress();
    updateHits();
  }

  function updateCardUI(poiId) {
    var entry = byId[poiId];
    if (!entry) return;
    var card = document.getElementById("row-" + entry.idx);
    if (!card) return;
    var v = verdictOf(entry.row);
    card.classList.toggle("v-dung", !!v && v.verdict === "dung");
    card.classList.toggle("v-loai", !!v && v.verdict === "loai");
    card.classList.toggle("v-skip", !!v && v.verdict === "skip");
    card.querySelectorAll(".vbtn").forEach(function (b) {
      b.classList.toggle("on", !!v && b.getAttribute("data-verdict") === v.verdict);
    });
  }

  function updateProgress() {
    var n = { dung: 0, loai: 0, skip: 0 };
    DATA.forEach(function (row) {
      var v = state.verdicts[row.poi_id];
      if (v && n[v.verdict] != null) n[v.verdict]++;
    });
    var done = n.dung + n.loai + n.skip;
    var total = DATA.length;
    var pct = total ? Math.round(done / total * 100) : 0;
    $("barfill").style.width = pct + "%";
    $("bar").setAttribute("aria-valuenow", String(pct));
    $("counts").innerHTML = "Đã làm <b>" + done + "</b>/" + total + " (" + pct + "%) · xuất được " + (n.dung + n.loai);
    $("breakdown").textContent = "Dung " + n.dung + " · LOẠI " + n.loai + " · Bỏ qua " + n.skip;
  }

  function updateHits() {
    var visible = document.querySelectorAll("#list .card:not(.hide)").length;
    $("hits").textContent = "Hiện " + visible + "/" + DATA.length;
    $("empty").classList.toggle("hide", visible !== 0);
  }

  function applyFilters() {
    var cat = $("f-cat").value;
    var reason = $("f-reason").value;
    var q = $("f-q").value.trim().toLowerCase();
    var todoOnly = $("f-todo").checked;
    DATA.forEach(function (row, idx) {
      var card = document.getElementById("row-" + idx);
      if (!card) return;
      var ok = true;
      if (cat && row.cat !== cat) ok = false;
      if (ok && reason) {
        var keys = row.hard.concat(row.queue);
        if (keys.indexOf(reason) === -1) ok = false;
      }
      if (ok && todoOnly && verdictOf(row)) ok = false;
      if (ok && q) {
        var v = state.verdicts[row.poi_id];
        var hay = [row.name, row.type, row.poi_id, row.cat, row.source, (v && v.note) || ""]
          .join(" ").toLowerCase();
        if (hay.indexOf(q) === -1) ok = false;
      }
      card.classList.toggle("hide", !ok);
    });
    updateHits();
  }

  function fillFilters() {
    var cats = {}, reasons = {};
    DATA.forEach(function (row) {
      cats[row.cat] = (cats[row.cat] || 0) + 1;
      row.hard.concat(row.queue).forEach(function (r) { reasons[r] = (reasons[r] || 0) + 1; });
    });
    var catSel = $("f-cat");
    Object.keys(cats).sort().forEach(function (cat) {
      var o = document.createElement("option");
      o.value = cat;
      o.textContent = (CAT_LABEL[cat] || cat) + " — " + cats[cat];
      catSel.appendChild(o);
    });
    var rSel = $("f-reason");
    Object.keys(reasons).sort(function (a, b) { return reasons[b] - reasons[a]; }).forEach(function (r) {
      var o = document.createElement("option");
      o.value = r;
      o.textContent = reasonLabel(r) + " — " + reasons[r];
      rSel.appendChild(o);
    });
  }

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function exportJsonl() {
    var rows = [];
    DATA.forEach(function (row) {
      var v = state.verdicts[row.poi_id];
      if (!v || (v.verdict !== "dung" && v.verdict !== "loai")) return;
      rows.push({
        poi_id: row.poi_id,
        verdict: v.verdict,
        note: v.note || "",
        reviewer: state.reviewer || "",
        ts: v.ts || new Date().toISOString()
      });
    });
    if (!rows.length) {
      toast("Chưa có dòng nào Dung/LOẠI để xuất. (Bỏ qua không được xuất.)");
      return;
    }
    var now = new Date();
    var name = "verify_verdicts_" + now.getFullYear() + pad(now.getMonth() + 1) + pad(now.getDate()) + ".jsonl";
    var text = rows.map(function (r) { return JSON.stringify(r); }).join("\n") + "\n";
    var blob = new Blob([text], { type: "application/x-ndjson;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 1500);
    var skipped = Object.keys(state.verdicts).filter(function (k) {
      return state.verdicts[k] && state.verdicts[k].verdict === "skip";
    }).length;
    toast("Đã xuất " + rows.length + " dòng → " + name + (skipped ? " (bỏ qua " + skipped + " dòng Bỏ qua)" : ""));
  }

  /* ---------- wiring ---------- */
  $("reviewer").value = state.reviewer || "";
  $("reviewer").addEventListener("input", function () {
    state.reviewer = this.value;
    saveSoon();
  });
  $("export").addEventListener("click", exportJsonl);

  $("list").addEventListener("click", function (ev) {
    var btn = ev.target.closest(".vbtn");
    if (!btn) return;
    var card = btn.closest(".card");
    if (!card) return;
    setVerdict(card.getAttribute("data-id"), btn.getAttribute("data-verdict"));
  });
  $("list").addEventListener("input", function (ev) {
    if (ev.target.tagName !== "TEXTAREA") return;
    var card = ev.target.closest(".card");
    if (!card) return;
    var id = card.getAttribute("data-id");
    var cur = state.verdicts[id];
    if (cur) {
      cur.note = ev.target.value;
      cur.ts = new Date().toISOString();
    } else {
      // Keep notes typed before a verdict: stash as pending, applied on click.
      state.verdicts[id] = { verdict: null, note: ev.target.value, ts: new Date().toISOString() };
    }
    saveSoon();
    if ($("f-q").value.trim()) applyFilters();
  });

  ["f-cat", "f-reason", "f-q", "f-todo"].forEach(function (id) {
    $(id).addEventListener("input", applyFilters);
    $(id).addEventListener("change", applyFilters);
  });
  $("f-reset").addEventListener("click", function () {
    $("f-cat").value = "";
    $("f-reason").value = "";
    $("f-q").value = "";
    $("f-todo").checked = false;
    applyFilters();
  });

  $("storekey").textContent = STORE_KEY;
  buildList();
  fillFilters();
  updateProgress();
  applyFilters();
  if (Object.keys(state.verdicts).length) {
    toast("Đã khôi phục tiến độ đã lưu cho snapshot này.");
  }
})();
</script>
</body>
</html>
"""


def render(rows: list[dict], meta: dict) -> str:
    html = PAGE_TEMPLATE
    html = html.replace("__DATA__", _script_json(rows))
    html = html.replace("__META__", _script_json(meta))
    html = html.replace("__SNAPSHOT__", _esc_html(meta["snapshot"]))
    html = html.replace("__GENERATED__", _esc_html(meta["generated"]))
    html = html.replace("__HASH__", _esc_html(meta["queue_hash"]))
    html = html.replace("__TOTAL__", str(len(rows)))
    return html


def _esc_html(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    snapshot = args.snapshot
    if not (snapshot / "pois.json").is_file():
        raise SystemExit(f"missing {snapshot / 'pois.json'}")
    if not (snapshot / "auto_verify_queue.jsonl").is_file():
        raise SystemExit(f"missing {snapshot / 'auto_verify_queue.jsonl'}")

    rows, meta = build_rows(snapshot)
    html = render(rows, meta)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8", newline="\n")

    counts: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in rows:
        counts[row["cat"]] = counts.get(row["cat"], 0) + 1
        for key in row["hard"] + row["queue"]:
            reasons[key] = reasons.get(key, 0) + 1
    print(f"wrote {args.out} ({args.out.stat().st_size:,} bytes)")
    print(f"rows={len(rows)} snapshot={meta['snapshot']} queue_hash={meta['queue_hash']}")
    print("cats: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
