"""Standalone human-audit review generator for T063 weather labels.

Produces a single, self-contained HTML file (no external assets or scripts)
that lets a reviewer confirm indoor/outdoor/both labels per POI.  The HTML
persist confirmed choices in localStorage and can export them as JSON keyed by
``poi_id``.

Public API
----------
* ``render_html(rows: list[dict]) -> str``
* CLI: ``python -m BE.ml.weather_label.render_review --input rows.json``

Input row schema
----------------
Each row is a dict with the following keys:

* ``poi_id`` (str|int, required): stable identifier
* ``name`` (str): POI name
* ``type`` (str): POI type/category
* ``lat`` (float, optional)
* ``lon`` (float, optional)
* ``old_space`` (str): old space label, e.g. ``indoor``/``outdoor``/``both``/``unknown``
* ``suggested_space`` (str): suggested space label
* ``space_source`` (str): source of the suggestion
* ``space_confidence`` (float|str): confidence value
* ``space_evidence`` (list[str]): supporting evidence
* ``old_rain_protection`` (str|bool, optional): old rain-protection level
* ``rain_protection`` (str|bool): suggested rain-protection level
* ``rain_protection_confidence`` (float|str, optional)
* ``rain_protection_evidence`` (list[str], optional)
* ``space_conflict`` (bool): whether old vs suggested space disagree
"""

from __future__ import annotations

import argparse
import html
import json
import os
from typing import Any


LS_KEY = "weather_label_review_decisions"


def _norm(v: Any) -> str:
    """Return a lower-case string or 'unknown'."""
    if v is None or v == "":
        return "unknown"
    return str(v).strip().lower()


def _vi_space(value: Any) -> str:
    """Translate a space label to Vietnamese."""
    mapping = {
        "indoor": "trong nhà",
        "outdoor": "ngoài trời",
        "both": "cả hai",
        "unknown": "chưa rõ",
    }
    return mapping.get(_norm(value), str(value) if value is not None else "chưa rõ")


def _vi_rain(value: Any) -> str:
    """Translate a rain-protection value to Vietnamese."""
    if isinstance(value, bool):
        return "có" if value else "không"
    if value is None or value == "":
        return "chưa rõ"
    mapping = {
        "full": "đầy đủ",
        "complete": "đầy đủ",
        "partial": "một phần",
        "sheltered": "có mái che",
        "covered": "có mái che",
        "none": "không",
        "no": "không",
        "unknown": "chưa rõ",
    }
    return mapping.get(_norm(value), str(value))


def _esc(value: Any) -> str:
    """HTML-escape a dynamic value."""
    return html.escape(str(value) if value is not None else "")


def _evidence_block(items: list[Any]) -> str:
    """Render a compact evidence list."""
    if not items:
        return "<i>không có</i>"
    parts = [f"<li>{_esc(item)}</li>" for item in items]
    return f"<ul class='ev'>{''.join(parts)}</ul>"


def _map_link(lat: Any, lon: Any) -> str:
    """Return an OSM map link if coordinates look valid."""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return ""
    url = f"https://www.openstreetmap.org/?mlat={lat_f}&mlon={lon_f}#map=17/{lat_f}/{lon_f}"
    return f" · <a target='_blank' rel='noopener' href='{url}'>Xem bản đồ</a>"


def _row_flag(conflict: bool, old_space: Any, suggested_space: Any) -> tuple[str, str]:
    """Return (flag_text, flag_css_class)."""
    if conflict:
        return ("xung đột", "conflict")
    if _norm(old_space) != _norm(suggested_space):
        return ("thay đổi", "warn")
    return ("giữ nguyên", "ok")


def _render_card(row: dict, index: int) -> str:
    """Render one POI card."""
    poi_id = row["poi_id"]
    name = row.get("name", "")
    poi_type = row.get("type", "")
    lat = row.get("lat")
    lon = row.get("lon")
    old_space = row.get("old_space")
    suggested_space = row.get("suggested_space")
    space_source = row.get("space_source", "")
    space_confidence = row.get("space_confidence", "")
    space_evidence = row.get("space_evidence") or []
    old_rain = row.get("old_rain_protection")
    rain = row.get("rain_protection")
    rain_conf = row.get("rain_protection_confidence", "")
    rain_evidence = row.get("rain_protection_evidence") or []
    conflict = bool(row.get("space_conflict"))

    flag_text, flag_class = _row_flag(conflict, old_space, suggested_space)
    coords_text = "chưa có"
    if lat is not None and lon is not None:
        try:
            coords_text = f"{float(lat):.6f}, {float(lon):.6f}"
        except (TypeError, ValueError):
            coords_text = f"{lat}, {lon}"

    return f"""<div class='card' data-poi-id='{_esc(poi_id)}' data-old='{_esc(_norm(old_space))}'>
<h3>#{index}. {_esc(name)} <span class='flag {flag_class}'>{_esc(flag_text)}</span></h3>
<div class='cols'>
  <div class='poi'>
    <h4>Nhãn cũ</h4>
    <div class='r'><span>Không gian</span><b>{_esc(_vi_space(old_space))}</b></div>
    <div class='r'><span>Chống mưa</span><b>{_esc(_vi_rain(old_rain))}</b></div>
  </div>
  <div class='poi'>
    <h4>Đề xuất mới</h4>
    <div class='r'><span>Không gian</span><b>{_esc(_vi_space(suggested_space))} <span class='conf'>({_esc(space_confidence)})</span></b></div>
    <div class='r'><span>Nguồn</span><b>{_esc(space_source)}</b></div>
    <div class='r'><span>Căn cứ</span><b>{_evidence_block(space_evidence)}</b></div>
    <div class='r'><span>Chống mưa</span><b>{_esc(_vi_rain(rain))} <span class='conf'>({_esc(rain_conf)})</span></b></div>
    <div class='r'><span>Căn cứ chống mưa</span><b>{_evidence_block(rain_evidence)}</b></div>
  </div>
</div>
<div class='dist'>Loại: {_esc(poi_type)} · Tọa độ: {_esc(coords_text)}{_map_link(lat, lon)}</div>
<div class='vote' data-poi='{_esc(poi_id)}'>
  <label><input type='checkbox' class='choice' data-poi='{_esc(poi_id)}' value='indoor'>Trong nhà</label>
  <label><input type='checkbox' class='choice' data-poi='{_esc(poi_id)}' value='outdoor'>Ngoài trời</label>
  <label><input type='checkbox' class='choice' data-poi='{_esc(poi_id)}' value='both'>Cả hai</label>
</div>
<button class='confirm' data-poi='{_esc(poi_id)}'>Xác nhận</button>
</div>"""


def _json_for_script(rows: list[dict]) -> str:
    """Serialize rows for a raw-text ``<script>`` block.

    Browsers do not HTML-unescape ``<script>`` text contents, so we keep the
    JSON as raw text and only escape characters that could break the script
    element or the subsequent ``JSON.parse`` call: ``<``, ``>``, ``&`` and the
    JSON line-separator characters U+2028/U+2029.
    """
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return data


def render_html(rows: list[dict]) -> str:
    """Return a complete standalone HTML review page for ``rows``."""
    rows = [dict(r) for r in rows]
    cards = "".join(_render_card(row, i + 1) for i, row in enumerate(rows))
    json_data = _json_for_script(rows)

    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kiểm tra nhãn thời tiết T063</title>
<style>
body{{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:900px;margin:0 auto;padding:12px;background:#f4f4f5;color:#18181b}}
.bar{{position:sticky;top:0;background:#fff;border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin-bottom:12px;z-index:5;box-shadow:0 2px 6px rgba(0,0,0,.05)}}
.bar b{{font-size:18px}}
button{{margin:4px 6px 4px 0;padding:8px 14px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer}}
button.on{{background:#18181b;color:#fff}}
button.exp{{background:#2563eb;color:#fff;border-color:#2563eb}}
button.confirm{{margin-top:10px;border-color:#16a34a;color:#16a34a}}
button.confirm.confirmed{{background:#16a34a;color:#fff}}
.card{{background:#fff;border:1px solid #ddd;border-radius:12px;padding:14px;margin-bottom:12px}}
.card.confirmed{{border-color:#16a34a}}
.card h3{{margin:0 0 8px;font-size:16px}}
.flag{{border-radius:6px;padding:1px 8px;font-size:12px}}
.flag.ok{{background:#bbf7d0}}
.flag.warn{{background:#fed7aa}}
.flag.conflict{{background:#fecaca;color:#991b1b}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.poi{{border:1px solid #e4e4e7;border-radius:8px;padding:8px}}
.poi h4{{margin:0 0 6px;font-size:14px;color:#52525b}}
.r{{display:flex;justify-content:space-between;gap:8px;font-size:13px;padding:3px 0;border-bottom:1px dashed #eee}}
.r span{{color:#71717a;flex-shrink:0}}
.r b{{text-align:right;font-weight:600}}
.r b .conf{{font-weight:400;color:#71717a}}
.ev{{margin:4px 0 0;padding-left:16px;font-size:12px;color:#52525b}}
.ev li{{margin-bottom:2px}}
.dist{{text-align:center;color:#71717a;font-size:13px;margin:8px 0}}
.vote{{display:flex;gap:8px;margin-top:10px}}
.vote label{{flex:1;text-align:center;border:2px solid #d4d4d8;border-radius:8px;padding:8px;cursor:pointer;font-weight:600}}
.vote input{{display:none}}
.vote label.on{{border-color:#16a34a;background:#f0fdf4;color:#166534}}
.hide{{display:none}}
a{{color:#2563eb}}
@media(max-width:640px){{.cols{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="bar"><b id="prog">Đã xác nhận 0/{len(rows)}</b><br>
<button data-f="all" class="on">Tất cả</button>
<button data-f="todo">Chưa xác nhận</button>
<button data-f="old-indoor">Cũ trong nhà</button>
<button data-f="old-outdoor">Cũ ngoài trời</button>
<button data-f="old-both">Cũ cả hai</button>
<button data-f="old-unknown">Cũ chưa rõ</button>
<button class="exp" id="exp">Xuất đáp án (JSON)</button>
</div>
<div id="list">{cards}</div>
<script type="application/json" id="rows-data">{json_data}</script>
<script>
(function(){{
  const LS_KEY = {json.dumps(LS_KEY)};
  let saved = {{}};
  try {{ saved = JSON.parse(localStorage.getItem(LS_KEY) || '{{}}'); }} catch(e) {{}}
  const rows = JSON.parse(document.getElementById('rows-data').textContent);
  const total = rows.length;
  const list = document.getElementById('list');
  const prog = document.getElementById('prog');

  function save() {{
    try {{ localStorage.setItem(LS_KEY, JSON.stringify(saved)); }}
    catch (e) {{ /* file:// or private mode may block storage */ }}
  }}
  function updateProgress() {{ prog.textContent = 'Đã xác nhận ' + Object.keys(saved).length + '/' + total; }}
  function markConfirmed(poiId) {{
    const card = list.querySelector('.card[data-poi-id="' + CSS.escape(String(poiId)) + '"]');
    if (!card) return;
    card.classList.add('confirmed');
    const btn = card.querySelector('button.confirm');
    if (btn) {{ btn.textContent = 'Đã xác nhận'; btn.classList.add('confirmed'); }}
  }}
  function unmarkConfirmed(poiId) {{
    const card = list.querySelector('.card[data-poi-id="' + CSS.escape(String(poiId)) + '"]');
    if (!card) return;
    card.classList.remove('confirmed');
    const btn = card.querySelector('button.confirm');
    if (btn) {{ btn.textContent = 'Xác nhận'; btn.classList.remove('confirmed'); }}
  }}

  list.addEventListener('change', function(e) {{
    const cb = e.target.closest('.choice');
    if (!cb) return;
    const wrap = cb.closest('.vote');
    if (cb.checked) {{
      wrap.querySelectorAll('.choice').forEach(function(sib) {{
        if (sib !== cb) {{ sib.checked = false; sib.closest('label').classList.remove('on'); }}
      }});
      cb.closest('label').classList.add('on');
    }} else {{
      cb.closest('label').classList.remove('on');
    }}
    const poiId = cb.dataset.poi;
    if (saved[poiId]) {{
      delete saved[poiId];
      save();
      updateProgress();
      unmarkConfirmed(poiId);
    }}
  }});

  list.addEventListener('click', function(e) {{
    const btn = e.target.closest('button.confirm');
    if (!btn) return;
    const poiId = btn.dataset.poi;
    const wrap = list.querySelector('.vote[data-poi="' + CSS.escape(String(poiId)) + '"]');
    const checked = wrap && wrap.querySelector('.choice:checked');
    if (!checked) {{ alert('Vui lòng chọn một nhãn không gian.'); return; }}
    saved[poiId] = checked.value;
    save();
    updateProgress();
    markConfirmed(poiId);
  }});

  const filterBtns = document.querySelectorAll('.bar button[data-f]');
  filterBtns.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      filterBtns.forEach(function(b) {{ b.classList.remove('on'); }});
      btn.classList.add('on');
      const f = btn.dataset.f;
      list.querySelectorAll('.card').forEach(function(card) {{
        let show = false;
        if (f === 'all') show = true;
        else if (f === 'todo') show = !saved[card.dataset.poiId];
        else if (f === 'old-indoor') show = card.dataset.old === 'indoor';
        else if (f === 'old-outdoor') show = card.dataset.old === 'outdoor';
        else if (f === 'old-both') show = card.dataset.old === 'both';
        else if (f === 'old-unknown') show = !card.dataset.old || card.dataset.old === 'unknown';
        card.classList.toggle('hide', !show);
      }});
    }});
  }});

  list.querySelectorAll('.card').forEach(function(card) {{
    const poiId = card.dataset.poiId;
    const val = saved[poiId];
    if (val) {{
      const cb = card.querySelector('.choice[value="' + CSS.escape(String(val)) + '"]');
      if (cb) {{
        cb.checked = true;
        cb.closest('label').classList.add('on');
        markConfirmed(poiId);
      }}
    }}
  }});
  updateProgress();

  document.getElementById('exp').addEventListener('click', function() {{
    const blob = new Blob([JSON.stringify(saved, null, 2)], {{type: 'application/json'}});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'weather_review_decisions.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }});
}})();
</script>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Build the standalone T063 weather-label human audit HTML.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a JSON file containing the review rows.",
    )
    parser.add_argument(
        "--output",
        default="BE/data/snapshots/danang-v1/weather_label_review_200.html",
        help="Path for the generated standalone HTML file (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise SystemExit("Input JSON must be a list of row objects.")

    html_doc = render_html(rows)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"Wrote {len(rows)} POI cards to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
