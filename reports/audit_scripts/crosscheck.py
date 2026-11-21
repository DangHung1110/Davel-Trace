#!/usr/bin/env python3
"""Kiểm chứng độc lập số liệu audit POI (CHỈ ĐỌC snapshot danang-v1).

Chỉ dùng thư viện chuẩn. Chạy:  python -X utf8 reports/audit_scripts/crosscheck.py
Ghi: reports/audit_crosscheck_20261118.md (báo cáo + khối json số chính).
Console chỉ in đếm, không in dữ liệu cá nhân.
"""
import collections
import datetime as dt
import difflib
import json
import math
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "BE/data/snapshots/danang-v1/pois.json"
OUT_MD = ROOT / "reports/audit_crosscheck_20261118.md"

TODAY = dt.date(2026, 11, 18)
CUTOFF_12M = dt.date(2025, 11, 18)
BRIDGE = (16.0612, 108.2275)  # Cầu Rồng (lat, lon)
LON_RANGE = (107.2, 108.8)
LAT_RANGE = (14.9, 16.3)
DUP_METERS = 50.0
DUP_SIM = 0.85
RESTO_CAFE = {"restaurant", "cafe"}

# Có ranh giới từ cho "closed" để không khớp "enclosed" (rain_cover='enclosed' gây 504 dương tính giả).
CLOSED_RE = re.compile(r"đóng cửa|\bclosed\b|ngừng hoạt động")
CLOSED_RE_LITERAL = re.compile(r"đóng cửa|closed|ngừng hoạt động")  # theo chữ của brief
CLOSED_RE_NOACCENT = re.compile(r"dong cua|ngung hoat dong")  # biến thể độ nhạy
HOURS_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})\s*$")
ALWAYS_RE = re.compile(r"^\s*24\s*/\s*7\s*$", re.I)


# ---------- helpers ----------
def is_missing_num(v):
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0


def nonempty(v):
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, tuple)):
        return any(nonempty(x) for x in v)
    if isinstance(v, dict):
        return any(nonempty(x) for x in v.values())
    if isinstance(v, float) and math.isnan(v):
        return False
    return True


def fold(s):
    """Bỏ dấu (NFD + bỏ Mn, đ->d), lower, gom khoảng trắng."""
    s = (s or "").replace("đ", "d").replace("Đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().split())


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    R = 6371.0088
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = p2 - p1
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, h)))


def coord_state(p):
    la, lo = p.get("lat"), p.get("lon")
    if is_missing_num(la) or is_missing_num(lo):
        return "thieu"
    if LON_RANGE[0] <= lo <= LON_RANGE[1] and LAT_RANGE[0] <= la <= LAT_RANGE[1]:
        return "hop_le"
    if LON_RANGE[0] <= la <= LON_RANGE[1] and LAT_RANGE[0] <= lo <= LAT_RANGE[1]:
        return "nghi_dao"
    return "ngoai_khung"


def hours_status(v):
    """Trả về (empty, parsed, kind, raw_sample)."""
    items = v if isinstance(v, list) else [v]
    empty = v is None or v == "" or (isinstance(v, list) and all(x in (None, "") for x in v))
    if empty:
        return True, False, "rong", repr(v)
    for it in items:
        if not isinstance(it, str):
            continue
        m = HOURS_RE.match(it)
        if m:
            h1, m1, h2, m2 = map(int, m.groups())
            if h1 <= 24 and h2 <= 24 and m1 < 60 and m2 < 60:
                return False, True, "HH:MM-HH:MM", it
        if ALWAYS_RE.match(it):
            return False, True, "24/7", it
    return False, False, "khong_parse", repr(v)


def parse_date(s):
    if not isinstance(s, str):
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def walk_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from walk_strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from walk_strings(x)


def bridge_bucket(km):
    if km < 5:
        return "0–5 km"
    if km < 15:
        return "5–15 km"
    if km < 40:
        return "15–40 km"
    return ">40 km"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def pct(n, d):
    return f"{100.0 * n / d:.1f}%" if d else "n/a"


# ---------- main ----------
def main():
    data = json.loads(SNAP.read_text(encoding="utf-8"))
    pois = data["pois"]
    n = len(pois)
    meta_count = data.get("count")
    res = {}

    # 1. Tổng
    res["n_pois"] = n
    res["meta_count"] = meta_count
    res["diff_count"] = n - meta_count if isinstance(meta_count, int) else None
    ids = [p.get("poi_id") for p in pois]
    res["unique_poi_id"] = len(set(ids))
    sec1 = table(
        ["Chỉ số", "Giá trị", "Trường / nguồn"],
        [
            ["Số POI thực tế", n, "len(pois['pois'])"],
            ["Metadata count", meta_count, "pois['count']"],
            ["Chênh lệch (thực − metadata)", res["diff_count"], "—"],
            ["poi_id duy nhất", res["unique_poi_id"], "poi_id"],
        ],
    )

    # 2. Phân bố cat/type
    cat_c = collections.Counter(str(p.get("cat")) for p in pois)
    type_c = collections.Counter(str(p.get("type")) for p in pois)
    resto_n = sum(1 for p in pois if p.get("cat") in RESTO_CAFE)
    res["resto_cafe_n"] = resto_n
    sec2a = table(["cat", "Số POI"], [[k, v] for k, v in cat_c.most_common()])
    sec2b = table(["type (top 20)", "Số POI"], [[k, v] for k, v in type_c.most_common(20)])
    res["n_cat_distinct"] = len(cat_c)
    res["n_type_distinct"] = len(type_c)

    # 3. Nghi trùng
    fnames = [fold(p.get("name")) for p in pois]
    coords_ok = [not (is_missing_num(p.get("lat")) or is_missing_num(p.get("lon"))) for p in pois]
    pairs = []
    near_any = []  # (m, độ giống) của mọi cặp < 50 m, để chẩn đoán
    for i in range(n):
        if not coords_ok[i] or not fnames[i]:
            continue
        for j in range(i + 1, n):
            if not coords_ok[j] or not fnames[j]:
                continue
            d_m = haversine_km(pois[i]["lat"], pois[i]["lon"], pois[j]["lat"], pois[j]["lon"]) * 1000
            if d_m >= DUP_METERS:
                continue
            sim = difflib.SequenceMatcher(None, fnames[i], fnames[j]).ratio()
            near_any.append((d_m, sim))
            if sim >= DUP_SIM:
                pairs.append((i, j, d_m, sim))
    dup_set = set()
    for i, j, _, _ in pairs:
        dup_set.add(i)
        dup_set.add(j)
    res["dup_pairs"] = len(pairs)
    res["dup_pois"] = len(dup_set)
    res["near_50m_pairs_any_name"] = len(near_any)
    res["near_50m_max_sim"] = round(max((s for _, s in near_any), default=0.0), 3)
    pair_rows = []
    for i, j, d_m, sim in sorted(pairs, key=lambda t: -t[3])[:10]:
        pair_rows.append([
            f"{pois[i].get('poi_id')} / {pois[j].get('poi_id')}",
            f"{pois[i].get('name')} ↔ {pois[j].get('name')}",
            f"{d_m:.1f}",
            f"{sim:.3f}",
        ])
    sec3 = (
        f"Số cặp nghi trùng: **{len(pairs)}** (số POI liên quan: **{len(dup_set)}**). "
        f"Chẩn đoán: có **{len(near_any)}** cặp < 50 m (bất kể tên), độ giống tên lớn nhất trong nhóm đó = "
        f"**{res['near_50m_max_sim']}**.\n\n"
        + (table(["poi_id A / B", "Tên A ↔ Tên B", "Khoảng cách (m)", "Độ giống"], pair_rows)
           if pair_rows else "Không có cặp nào.")
    )

    # 4. Toạ độ
    states = collections.Counter(coord_state(p) for p in pois)
    res["coord_states"] = dict(states)
    swap_n = states.get("nghi_dao", 0)
    bridge_b = collections.Counter()
    for p, ok in zip(pois, coords_ok):
        if ok:
            bridge_b[bridge_bucket(haversine_km(p["lat"], p["lon"], *BRIDGE))] += 1
    res["bridge_buckets"] = {k: bridge_b.get(k, 0) for k in ["0–5 km", "5–15 km", "15–40 km", ">40 km"]}
    sec4a = table(
        ["Trạng thái toạ độ (trường lat, lon)", "Số POI"],
        [
            ["Thiếu (None/NaN/0)", states.get("thieu", 0)],
            [f"Ngoài khung lon {LON_RANGE[0]}–{LON_RANGE[1]} / lat {LAT_RANGE[0]}–{LAT_RANGE[1]}", states.get("ngoai_khung", 0)],
            ["Nghi đảo lat/lon (đảo vào khung)", swap_n],
            ["Hợp lệ (trong khung)", states.get("hop_le", 0)],
        ],
    )
    sec4b = table(
        ["Khoảng cách tới Cầu Rồng (haversine)", "Số POI"],
        [[k, res["bridge_buckets"][k]] for k in ["0–5 km", "5–15 km", "15–40 km", ">40 km"]],
    )

    # 5. opening_hours
    type_c_oh = collections.Counter(type(p.get("opening_hours")).__name__ for p in pois)
    empty_n = parsed_n = unparsed_n = 0
    kind_c = collections.Counter()
    unparsed_samples = []
    for p in pois:
        empty, parsed, kind, raw = hours_status(p.get("opening_hours"))
        if empty:
            empty_n += 1
        elif parsed:
            parsed_n += 1
            kind_c[kind] += 1
        else:
            unparsed_n += 1
        if not parsed and len(unparsed_samples) < 10:
            unparsed_samples.append([p.get("poi_id"), kind, raw[:80]])
    res["hours"] = {"types": dict(type_c_oh), "empty": empty_n, "parsed": parsed_n,
                    "parsed_kinds": dict(kind_c), "unparsed_nonempty": unparsed_n}
    sec5a = table(["Kiểu dữ liệu opening_hours", "Số POI"], [[k, v] for k, v in type_c_oh.items()])
    sec5b = table(
        ["Nhóm (opening_hours)", "Số POI"],
        [["Rỗng ([] / null / \"\")", empty_n],
         ["Parse được (HH:MM-HH:MM)", kind_c.get("HH:MM-HH:MM", 0)],
         ["Parse được (24/7)", kind_c.get("24/7", 0)],
         ["Không parse (có dữ liệu)", unparsed_n]],
    )
    sec5c = table(["poi_id", "Trạng thái", "Giá trị thô (cắt 80 ký tự)"], unparsed_samples) if unparsed_samples else "Không có mẫu không parse."
    multi_range = sum(1 for p in pois if isinstance(p.get("opening_hours"), list)
                      and any(isinstance(s, str) and "," in s for s in p["opening_hours"])
                      and not hours_status(p.get("opening_hours"))[1])
    sec5c += f"\n\nTổng không parse = {unparsed_n}; trong đó **{multi_range}** POI có chuỗi nhiều khoảng giờ (\"HH:MM-HH:MM, HH:MM-HH:MM\"), regex một khoảng không khớp."
    res["hours"]["unparsed_multi_range"] = multi_range

    # 6. Giá
    pl = collections.Counter(str(p.get("price_level")) for p in pois)
    fee = collections.Counter(str(p.get("fee")) for p in pois)
    tk = sum(1 for p in pois if nonempty(p.get("ticket_vnd")))
    pn = sum(1 for p in pois if nonempty(p.get("price_note")))
    res["price"] = {"price_level": dict(pl), "fee": dict(fee), "ticket_vnd": tk, "price_note": pn}
    sec6 = table(
        ["Trường", "Phân bố / số có", "Số POI"],
        [["price_level", ", ".join(f"{k}:{v}" for k, v in sorted(pl.items())), n],
         ["fee", ", ".join(f"{k}:{v}" for k, v in sorted(fee.items())), n],
         ["ticket_vnd (khác null)", "—", tk],
         ["price_note (khác rỗng)", "—", pn]],
    )

    # 7. verified_at
    vdates = [parse_date(p.get("verified_at")) for p in pois]
    has_va = sum(1 for p in pois if nonempty(p.get("verified_at")))
    valid_d = [d for d in vdates if d]
    in12 = sum(1 for d in valid_d if CUTOFF_12M <= d <= TODAY)
    future = sum(1 for d in valid_d if d > TODAY)
    unparse_va = has_va - len(valid_d)
    res["verified"] = {"present": has_va, "min": str(min(valid_d)) if valid_d else None,
                       "max": str(max(valid_d)) if valid_d else None, "in_12m": in12,
                       "future": future, "unparsable": unparse_va}
    sec7 = table(
        ["Chỉ số (trường verified_at)", "Giá trị"],
        [["Số có verified_at", has_va],
         ["Khoảng min – max", f"{res['verified']['min']} – {res['verified']['max']}"],
         [f"Trong 12 tháng ({CUTOFF_12M} → {TODAY})", in12],
         ["Ngày tương lai (> 2026-11-18)", future],
         ["Không parse được ngày", unparse_va]],
    )

    # 8. Phân hạng A/B/C
    grade = {}
    grade_by_cat = collections.defaultdict(collections.Counter)
    closed_hits = 0
    closed_literal = 0
    closed_noaccent = 0
    cat_bad = 0
    for i, p in enumerate(pois):
        cs = coord_state(p)
        has_coord = cs != "thieu"
        cat_ok = nonempty(p.get("cat"))
        empty, hours_ok, _, _ = hours_status(p.get("opening_hours"))
        src_ok = nonempty(p.get("source"))
        d = vdates[i]
        ver_ok = bool(d and CUTOFF_12M <= d <= TODAY)
        strings = list(walk_strings(p))
        is_closed = any(CLOSED_RE.search(s.lower()) for s in strings)
        is_closed_lit = any(CLOSED_RE_LITERAL.search(s.lower()) for s in strings)
        is_closed_na = any(CLOSED_RE_NOACCENT.search(fold(s)) for s in strings)
        closed_hits += int(is_closed)
        closed_literal += int(is_closed_lit)
        closed_noaccent += int(is_closed_na)
        cat_bad += int(not cat_ok)
        dup = i in dup_set
        if (not has_coord) or (not cat_ok) or dup or is_closed:
            g = "C"
        elif cs == "hop_le" and hours_ok and src_ok and ver_ok:
            g = "A"
        else:
            g = "B"
        grade[i] = g
        grade_by_cat[str(p.get("cat"))][g] += 1
    gc = collections.Counter(grade.values())
    res["grades"] = dict(gc)
    res["closed_hits"] = closed_hits
    res["closed_literal_hits"] = closed_literal
    res["closed_noaccent_hits"] = closed_noaccent
    res["cat_missing"] = cat_bad
    b_invalid = sum(1 for i, p in enumerate(pois) if grade[i] == "B" and coord_state(p) != "hop_le")
    res["B_with_invalid_coords"] = b_invalid
    rows8 = []
    for c in sorted(grade_by_cat, key=lambda k: -sum(grade_by_cat[k].values())):
        g = grade_by_cat[c]
        rows8.append([c, g.get("A", 0), g.get("B", 0), g.get("C", 0), sum(g.values())])
    rows8.append(["**Tổng**", gc.get("A", 0), gc.get("B", 0), gc.get("C", 0), n])
    sec8 = table(["cat", "A", "B", "C", "Tổng"], rows8)
    sec8_note = (
        f"Quy tắc ưu tiên: C (thiếu toạ độ/cat, nghi trùng, hoặc chữ đóng cửa) > A (toạ độ trong khung, "
        f"giờ parse được, source có, verified_at trong 12 tháng) > B (phần còn lại). "
        f"Chữ \"đóng cửa|closed|ngừng hoạt động\" (khớp chuỗi thuần) khớp **{closed_literal}** POI, nhưng toàn bộ đến từ "
        f"`smart_tags.rain_cover` = \"enclosed\" (chứa \"closed\"). Dùng ranh giới từ `\\bclosed\\b`, số POI khớp là **{closed_hits}** → "
        f"C do đóng cửa chỉ tính theo {closed_hits}. Biến thể không dấu (\"dong cua|ngung hoat dong\") khớp {closed_noaccent} POI. "
        f"B có toạ độ nghi đảo/ngoài khung: **{b_invalid}** (theo quy tắc, các POI này nằm ở B, không ở A). "
        f"Nhóm lodging có A = {grade_by_cat.get('lodging', {}).get('A', 0)}: "
        f"{sum(1 for p in pois if p.get('cat') == 'lodging' and not nonempty(p.get('opening_hours')))} / "
        f"{cat_c.get('lodging', 0)} POI lodging không có opening_hours, "
        f"{sum(1 for p in pois if p.get('cat') == 'lodging' and not nonempty(p.get('verified_at')))} không có verified_at."
    )

    # 9. Độ phủ
    def cov(fn):
        return sum(1 for p in pois if fn(p))

    fields = [
        ("ambience", lambda p: nonempty(p.get("ambience"))),
        ("pros", lambda p: nonempty(p.get("pros"))),
        ("cons", lambda p: nonempty(p.get("cons"))),
        ("visit_min", lambda p: nonempty(p.get("visit_min"))),
        ("intensity", lambda p: p.get("intensity") is not None),
        ("weather_sensitive", lambda p: p.get("weather_sensitive") is not None),
        ("smart_tags.time", lambda p: nonempty((p.get("smart_tags") or {}).get("time"))),
        ("tags", lambda p: nonempty(p.get("tags"))),
        ("osm_evidence", lambda p: nonempty(p.get("osm_evidence"))),
        ("web_evidence", lambda p: nonempty(p.get("web_evidence"))),
    ]
    cov_rows = []
    res["coverage"] = {}
    for name, fn in fields:
        c = cov(fn)
        res["coverage"][name] = c
        cov_rows.append([name, c, pct(c, n)])
    sec9 = table(["Trường", "Số POI khác rỗng", "Tỷ lệ"], cov_rows)

    # ---------- write report ----------
    md = f"""# Kiểm chứng độc lập số liệu audit POI (CHỈ ĐỌC)

- Ngày: {TODAY} · Snapshot: `BE/data/snapshots/danang-v1/pois.json` (snapshot={data.get('snapshot')}, source={data.get('source')}, fetched_at={data.get('fetched_at')}, enriched_at={data.get('enriched_at')})
- Script: `reports/audit_scripts/crosscheck.py` (chỉ thư viện chuẩn, không gọi API ngoài, không đọc `data_audit_20261118.md`)
- Giả định: "có toạ độ" = không None/NaN/0 (toạ độ ngoài khung vẫn được tính là có, và rơi vào B). "Đóng cửa" khớp trên chuỗi đã lowercase; đ→d khi so trùng tên.

## 1. Tổng số POI
{sec1}

## 2. Phân bố cat / type
Nhóm nhà hàng + cà phê (cat ∈ restaurant, cafe): **{resto_n}** POI. Số cat khác nhau: {res['n_cat_distinct']}; số type khác nhau: {res['n_type_distinct']}.

**cat** (trường `cat`):
{sec2a}

**type** (trường `type`, top 20):
{sec2b}

## 3. Nghi trùng (khoảng cách < 50 m và độ giống tên ≥ 0.85)
Trường: `name`, `lat`, `lon`. Độ giống: `difflib.SequenceMatcher` trên tên đã bỏ dấu.
{sec3}

## 4. Toạ độ
{sec4a}

Phân bố khoảng cách haversine tới Cầu Rồng (16.0612, 108.2275), trường lat/lon, chỉ POI có toạ độ:
{sec4b}

## 5. opening_hours
{sec5a}

{sec5b}

Mẫu 10 POI không parse (trường `opening_hours`):
{sec5c}

## 6. Giá
{sec6}

## 7. verified_at
{sec7}

## 8. Phân hạng A / B / C theo cat
{sec8}

{sec8_note}

## 9. Độ phủ (khác rỗng)
{sec9}

```json
{json.dumps(res, ensure_ascii=False, indent=2, default=str)}
```
"""
    OUT_MD.write_text(md, encoding="utf-8")

    # Console: chỉ đếm
    print(f"POI={n} metadata_count={meta_count} diff={res['diff_count']}")
    print(f"resto_cafe={resto_n} dup_pairs={len(pairs)} dup_pois={len(dup_set)}")
    print(f"coords={res['coord_states']} bridge={res['bridge_buckets']}")
    print(f"hours={res['hours']}")
    print(f"verified={res['verified']}")
    print(f"grades={res['grades']} closed={closed_hits} closed_noaccent={closed_noaccent} B_invalid={b_invalid}")
    print(f"coverage={res['coverage']}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
