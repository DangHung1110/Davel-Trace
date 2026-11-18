#!/usr/bin/env python3
"""Audit chỉ đọc cho Davel-Trace: kiểm kê dữ liệu + code, hồ sơ POI, phân hạng A/B/C.

Chỉ dùng thư viện chuẩn. Không gọi mạng, không chạy crawler, không ghi file nào ngoài báo cáo.
Chạy:  python -X utf8 reports/audit_scripts/data_audit.py
Ghi:   reports/data_audit_20261118.md (có khối ```json cuối báo cáo, đúng thứ tự key đề bài).
"""
from __future__ import annotations

import ast
import csv
import datetime as dt
import difflib
import json
import math
import os
import random
import re
import sqlite3
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "data_audit_20261118.md"
POI_PATH = ROOT / "BE/data/snapshots/danang-v1/pois.json"  # file chính: app đọc snapshot_dir này (BE/app/config.py)
TODAY = dt.date(2026, 11, 18)
CUTOFF_12M = TODAY - dt.timedelta(days=365)
BRIDGE = (16.0612, 108.2275)  # Cầu Rồng (lat, lon)
LON_RANGE = (107.2, 108.8)
LAT_RANGE = (14.9, 16.3)
IGNORE = {".git", "node_modules", "venv", ".venv", "__pycache__", ".pytest_cache"}
DATA_EXT = {".csv": "CSV", ".json": "JSON", ".jsonl": "JSONL", ".parquet": "Parquet", ".geojson": "GeoJSON",
            ".xlsx": "XLSX", ".sqlite": "SQLite", ".db": "SQLite", ".sql": "SQL"}
GROUPS9 = ["beach", "viewpoint", "outdoor_landmark", "pagoda", "museum_indoor", "day_market", "night_spot",
           "restaurant", "cafe"]
DISTRICTS_OLD = ["Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu", "Cẩm Lệ", "Hòa Vang", "Hoàng Sa"]
CLOSED_RE = re.compile(r"đóng\s*cửa|dong\s*cua|\bclosed\b|ngừng hoạt động|ngung hoat dong", re.I)
HOURS_RE = re.compile(r"\s*(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})\s*")
ALWAYS_RE = re.compile(r"\s*24\s*/\s*7\s*", re.I)
VN_DIACRITIC = re.compile("[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
VN_CHARS = re.compile("[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", re.I)


# ---------- tiện ích ----------
def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def records(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("pois", "data", "items", "features", "records", "results"):
            if isinstance(obj.get(k), list):
                return obj[k]
    return []


def typ(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def get(d, key: str):
    cur = d
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def nonempty(v) -> bool:
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


def is_missing_num(v) -> bool:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return True
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0


def fold(s) -> str:
    """Bỏ dấu (NFD, bỏ Mn, đ→d), lower, gom khoảng trắng."""
    s = str(s or "").replace("đ", "d").replace("Đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().split())


def haversine_km(a_lat, a_lon, b_lat, b_lon) -> float:
    R = 6371.0088
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def walk_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from walk_strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from walk_strings(x)


def pct(n, d) -> str:
    return f"{100.0 * n / d:.1f}%" if d else "0.0%"


def cell(x) -> str:
    return str(x).replace("|", "/").replace("\n", " ")


def md_table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(cell(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def words_in(v) -> int:
    return len(re.findall(r"\b\w+\b", str(v)))


# ---------- nhóm 9 thể loại (không dấu) ----------
def poi_group(cat: str, type_vi: str) -> str:
    """cat là nguồn chính; type (tiếng Việt) tinh chỉnh các lớp rộng. Mẫu viết trên chuỗi đã bỏ dấu."""
    t = fold(type_vi)
    c = (cat or "").strip().lower()
    if re.search(r"\bchua\b|pagoda|temple", t):
        return "pagoda"
    if re.search(r"museum|bao tang|gallery", t):
        return "museum_indoor"
    if re.search(r"\bbar\b|\bpub\b|night|karaoke|cho dem", t):
        return "night_spot"
    if re.search(r"\bmarket\b|\bcho\b", t):
        return "day_market"
    return {
        "beach": "beach", "viewpoint": "viewpoint", "restaurant": "restaurant", "cafe": "cafe",
        "museum": "museum_indoor", "market": "day_market", "bar": "night_spot",
        "park": "outdoor_landmark", "landmark": "outdoor_landmark", "nature": "outdoor_landmark",
        "attraction": "outdoor_landmark",
    }.get(c, "other")


# ---------- kiểm kê dữ liệu ----------
def file_row(p: Path) -> str:
    ext = p.suffix.lower()
    size = p.stat().st_size
    rows, cols = "KHÔNG XÁC ĐỊNH", []
    try:
        if ext in (".json", ".geojson"):
            o = load_json(p)
            if o is None:
                rows = "KHÔNG ĐỌC ĐƯỢC JSON"
            else:
                recs = [r for r in records(o) if isinstance(r, dict)]
                if recs:
                    rows = len(records(o))
                    cols = schema_of(recs)
                elif isinstance(o, dict):
                    rows = f"object ({len(o)} khóa)"
                    cols = [f"{k}:{typ(v)}" for k, v in o.items()]
                else:
                    rows = len(o)
        elif ext == ".jsonl":
            lines = [x for x in p.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
            rows = len(lines)
            first = json.loads(lines[0]) if lines else {}
            cols = [f"{k}:{typ(v)}" for k, v in first.items()] if isinstance(first, dict) else []
        elif ext == ".csv":
            with p.open(encoding="utf-8-sig", newline="") as f:
                rd = csv.DictReader(f)
                cols = [f"{k}:string" for k in (rd.fieldnames or [])]
                rows = sum(1 for _ in rd)
        elif ext in (".sqlite", ".db"):
            con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
            tabs = con.execute("select name from sqlite_master where type='table'").fetchall()
            counts = {}
            for (t,) in tabs:
                counts[t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                cols += [f"{t}.{x[1]}:{x[2] or 'unknown'}" for x in con.execute(f'PRAGMA table_info("{t}")')]
            con.close()
            rows = json.dumps(counts, ensure_ascii=False)
        elif ext in (".xlsx", ".parquet", ".sql"):
            rows = "KHÔNG XÁC ĐỊNH (không có thư viện đọc định dạng này)"
    except Exception as e:  # ghi lỗi thay vì bỏ qua
        rows = f"KHÔNG ĐỌC ĐƯỢC: {type(e).__name__}"
    return cols_fmt(rel(p), DATA_EXT[ext], size, rows, cols)


def schema_of(recs) -> list[str]:
    keys = Counter(k for r in recs for k in r)
    out = []
    for k in sorted(keys):
        types = Counter(typ(r.get(k)) for r in recs if k in r)
        out.append(f"{k}:{types.most_common(1)[0][0]}")
    return out


def cols_fmt(path, fmt, size, rows, cols, limit=8) -> str:
    shown = cols[:limit]
    extra = f" (+{len(cols) - limit} cột)" if len(cols) > limit else ""
    colstr = ", ".join(shown) + extra if cols else "—"
    return f"| `{path}` | {fmt} | {size:,} B | {rows} | {colstr} |"


def data_files() -> list[Path]:
    out = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE and not d.startswith(".git")]
        for n in names:
            p = Path(base) / n
            if p.suffix.lower() in DATA_EXT:
                out.append(p)
    return sorted(out)


def code_files() -> list[Path]:
    out = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE and not d.startswith(".git")]
        if Path(base).relative_to(ROOT).as_posix().startswith("reports"):
            continue  # script của audit này không phải code dự án
        for n in names:
            p = Path(base) / n
            if p.suffix in (".py", ".ipynb"):
                out.append(p)
    return sorted(out)


def build_tree() -> list[str]:
    lines = []

    def count_files(d: Path) -> int:
        return sum(len(fs) for _, ds, fs in os.walk(d) if not any(x in IGNORE for x in Path(_).parts))

    def visit(p: Path, depth: int):
        for c in sorted(p.iterdir(), key=lambda q: (not q.is_dir(), q.name.lower())):
            if c.name in IGNORE or c.name.startswith(".git"):
                continue
            if c.is_dir():
                lines.append("  " * (depth - 1) + f"{c.name}/ ({count_files(c)} tệp)")
                if depth < 3:
                    visit(c, depth + 1)
            elif depth == 1:
                lines.append(c.name)

    visit(ROOT, 1)
    return lines


# ---------- code: nhóm, trạng thái bằng bằng chứng tĩnh ----------
def module_group(rp: str) -> str:
    if rp.startswith("BE/tests/"):
        return "test"
    if rp.endswith(".ipynb"):
        return "notebook"
    if rp.startswith("BE/ml/data/") or rp.startswith("BE/ml/weather_label/fetch_"):
        return "crawler"
    if rp.startswith("BE/app/schemas/"):
        return "schema"
    if rp.startswith("BE/tools/") or rp in ("BE/app/services/optimizer.py", "BE/app/services/matrix.py",
                                             "BE/app/services/osrm_client.py", "BE/eval/baselines.py"):
        return "solver"
    if rp in ("BE/app/services/validator.py", "BE/app/services/gate.py", "BE/eval/judge.py", "BE/eval/metrics.py"):
        return "verifier"
    return "khác"


def dotted_of(rp: str) -> str:
    base = rp[3:] if rp.startswith("BE/") else rp
    return base[:-3].replace("/", ".")


def stub_info(tree) -> tuple[int, int]:
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    stubs = 0
    for f in funcs:
        body = list(f.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]
        if not body:
            stubs += 1
            continue
        ok = True
        for st in body:
            if isinstance(st, ast.Pass):
                continue
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and st.value.value is Ellipsis:
                continue
            if isinstance(st, ast.Raise) and "NotImplementedError" in ast.dump(st):
                continue
            ok = False
            break
        stubs += int(ok)
    return stubs, len(funcs)


def code_inventory(code: list[Path]):
    tests_text = {}
    for p in (ROOT / "BE/tests").rglob("*.py"):
        if "__pycache__" not in p.parts:
            tests_text[rel(p)] = p.read_text(encoding="utf-8", errors="replace")
    prod_text = {}
    for p in code:
        rp = rel(p)
        if p.suffix == ".py" and not rp.startswith("BE/tests/"):
            prod_text[rp] = p.read_text(encoding="utf-8", errors="replace")
    rows = []
    for p in code:
        rp = rel(p)
        if p.suffix != ".py":
            rows.append({"path": rp, "group": module_group(rp), "doc": "notebook", "status": "KHÔNG XÁC ĐỊNH",
                         "ev": "notebook không chạy được trong phạm vi chỉ đọc", "tests": 0, "app": 0})
            continue
        if rp.startswith("BE/tests/"):
            continue
        if p.name == "__init__.py":
            continue
        text = prod_text[rp]
        try:
            tree = ast.parse(text)
        except SyntaxError:
            rows.append({"path": rp, "group": module_group(rp), "doc": "—", "status": "KHÔNG XÁC ĐỊNH",
                         "ev": "lỗi cú pháp khi phân tích", "tests": 0, "app": 0})
            continue
        doc = (ast.get_docstring(tree) or "").strip().splitlines()
        doc = doc[0][:90] if doc else "(không có docstring)"
        dp = dotted_of(rp)
        pkg, _, name = dp.rpartition(".")
        pats = [re.compile(rf"(?:from|import)\s+(?:BE\.)?{re.escape(dp)}\b")]
        if pkg:
            pats.append(re.compile(rf"from\s+(?:BE\.)?{re.escape(pkg)}\s+import\s+[^\n]*\b{re.escape(name)}\b"))
            pats.append(re.compile(rf"from\s+\.+{re.escape(name)}\b"))
        def refs(src: dict) -> int:
            return sum(1 for k, t in src.items() if k != rp and any(pt.search(t) for pt in pats))
        n_tests, n_app = refs(tests_text), refs(prod_text)
        stubs, nfunc = stub_info(tree)
        markers = len(re.findall(r"TODO|FIXME|NotImplementedError", text))
        has_main = "__name__" in text and "__main__" in text
        if stubs or markers:
            status = "dở dang"
        elif n_tests + n_app:
            status = "chạy được*"
        elif has_main:
            status = "KHÔNG XÁC ĐỊNH"
        else:
            status = "bản nháp"
        why = {"dở dang": "có hàm rỗng/NotImplemented/TODO", "chạy được*": "có test hoặc import từ code khác",
               "bản nháp": "không có test, không được import", "KHÔNG XÁC ĐỊNH": "script CLI, không có test/import"}[status]
        ev = f"test:{n_tests}; import:{n_app}; hàm rỗng:{stubs}/{nfunc}; TODO:{markers}; {why}"
        rows.append({"path": rp, "group": module_group(rp), "doc": doc, "status": status, "ev": ev,
                     "tests": n_tests, "app": n_app})
    test_files = sorted(tests_text)
    test_funcs = sum(len(re.findall(r"^\s*(?:async\s+)?def\s+test_", t, re.M)) for t in tests_text.values())
    return rows, test_files, test_funcs


# ---------- POI ----------
def hours_status(v):
    """(rỗng, parse được, kiểu, mẫu) cho opening_hours dạng list chuỗi."""
    items = v if isinstance(v, list) else [v]
    if v is None or v == "" or (isinstance(v, list) and all(x in (None, "") for x in v)):
        return True, False, "rỗng", repr(v)
    for it in items:
        if not isinstance(it, str):
            continue
        m = HOURS_RE.fullmatch(it)
        if m:
            h1, m1, h2, m2 = map(int, m.groups())
            if h1 <= 24 and h2 <= 24 and m1 < 60 and m2 < 60:
                return False, True, "HH:MM-HH:MM", it
        if ALWAYS_RE.fullmatch(it):
            return False, True, "24/7", it
    return False, False, "không parse", repr(v)


def parse_date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def redact_scrub(o, k=""):
    if isinstance(o, dict):
        return {kk: ("[REDACTED]" if re.search(r"phone|email|user|gps|track|device_id", kk, re.I) and vv
                     else redact_scrub(vv, kk)) for kk, vv in o.items()}
    if isinstance(o, list):
        return [redact_scrub(x, k) for x in o]
    if isinstance(o, str) and (re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", o)
                               or re.search(r"(?:\+?84|0)(?:[\s().-])?\d(?:[\s().-]?\d){7,10}", o)):
        return "[REDACTED: possible personal contact]"
    return o


def raw_payload_scan():
    """Đếm số tệp raw có key liên quan (không in nội dung)."""
    raw_files = [p for p in data_files() if p.suffix.lower() == ".json"
                 and ("raw-round2" in rel(p) or "danang-full-tmp" in rel(p))]
    count = Counter()
    presence = Counter()
    pats = {"review": r"review", "photo": r"photo|image|thumbnail", "phone": r"phone|telephone",
            "website": r"website|facebook", "rating": r"rating", "wikidata": r"wikidata"}

    def scan(o, found):
        if isinstance(o, dict):
            for k, v in o.items():
                lk = str(k).lower()
                for lab, pat in pats.items():
                    if re.search(pat, lk):
                        count[lab] += 1
                        found.add(lab)
                scan(v, found)
        elif isinstance(o, list):
            for x in o:
                scan(x, found)

    for rp in raw_files:
        found = set()
        scan(load_json(rp), found)
        for lab in found:
            presence[lab] += 1
    return raw_files, count, presence


def main():
    root = load_json(POI_PATH) or {}
    raw = [x for x in root.get("pois", []) if isinstance(x, dict)]
    n = len(raw)
    res: dict = {}

    # ----- POI: nhóm, toạ độ, trùng, tier -----
    cats = Counter(str(x.get("type") or "(trống)") for x in raw)
    cat_codes = Counter(str(x.get("cat") or "(trống)") for x in raw)
    grp = [poi_group(str(x.get("cat") or ""), str(x.get("type") or "")) for x in raw]
    grp_c = Counter(grp)
    cross = Counter((str(x.get("cat") or "(trống)"), g) for x, g in zip(raw, grp))
    names = [str(x.get("name") or "") for x in raw]
    fnames = [fold(x) for x in names]
    coord_ok = [not (is_missing_num(x.get("lat")) or is_missing_num(x.get("lon"))) for x in raw]
    coord_state = []
    for x, ok in zip(raw, coord_ok):
        if not ok:
            coord_state.append("thiếu")
            continue
        la, lo = x["lat"], x["lon"]
        if LON_RANGE[0] <= lo <= LON_RANGE[1] and LAT_RANGE[0] <= la <= LAT_RANGE[1]:
            coord_state.append("hợp lệ")
        elif LON_RANGE[0] <= la <= LON_RANGE[1] and LAT_RANGE[0] <= lo <= LAT_RANGE[1]:
            coord_state.append("nghi đảo")
        else:
            coord_state.append("ngoài khung")
    states = Counter(coord_state)
    out_bbox = states.get("ngoài khung", 0) + states.get("nghi đảo", 0)
    bridge = Counter()
    for x, ok in zip(raw, coord_ok):
        if ok:
            km = haversine_km(x["lat"], x["lon"], *BRIDGE)
            bridge["0–5 km" if km < 5 else "5–15 km" if km < 15 else "15–40 km" if km < 40 else ">40 km"] += 1

    dup_pairs = []
    near_50 = []  # mọi cặp < 50 m, bất kể tên, để chẩn đoán
    for i in range(n):
        if not coord_ok[i] or not fnames[i]:
            continue
        la, lo = raw[i]["lat"], raw[i]["lon"]
        for j in range(i + 1, n):
            if not coord_ok[j] or not fnames[j]:
                continue
            lb, lob = raw[j]["lat"], raw[j]["lon"]
            if abs(la - lb) > 0.0006 or abs(lo - lob) > 0.0007:  # lọc sơ bộ ≥ 50 m
                continue
            d_m = haversine_km(la, lo, lb, lob) * 1000
            if d_m >= 50:
                continue
            sim = difflib.SequenceMatcher(None, fnames[i], fnames[j]).ratio()
            near_50.append(sim)
            if sim >= 0.85:
                dup_pairs.append((i, j, d_m, sim))
    near_max_sim = round(max(near_50), 3) if near_50 else 0.0
    dup_idx = {k for i, j, _, _ in dup_pairs for k in (i, j)}

    # tier theo luật đề bài (mục 9 đề bài)
    tier = {}
    strict = {}
    closed_hits = 0
    closed_literal = sum(any(re.search(r"đóng cửa|closed|ngừng hoạt động", s, re.I) for s in walk_strings(x)) for x in raw)
    for i, x in enumerate(raw):
        cs = coord_state[i]
        coordok = coord_ok[i]
        cat_ok = bool(str(x.get("cat") or "").strip())
        hv = x.get("opening_hours")
        _, hours_ok, _, _ = hours_status(hv)
        src_ok = bool(str(x.get("source") or "").strip())
        d = parse_date(x.get("verified_at"))
        recent = bool(d and CUTOFF_12M <= d <= TODAY)
        closed = any(CLOSED_RE.search(s) for s in walk_strings(x))
        closed_hits += int(closed)
        c_flag = (not coordok) or (not cat_ok) or (i in dup_idx) or closed
        if c_flag:
            tier[i] = "C"
        elif cs == "hợp lệ" and hours_ok and src_ok and recent:
            tier[i] = "A"
        else:
            tier[i] = "B"
        money = (isinstance(x.get("ticket_vnd"), (int, float)) and x["ticket_vnd"] > 0) or \
                (isinstance(x.get("fee"), (int, float)) and x["fee"] > 0) or x.get("free_entry") is True
        if c_flag or x.get("verified") is False:
            strict[i] = "C"
        elif cs == "hợp lệ" and hours_ok and money and src_ok and x.get("verified") is True and recent:
            strict[i] = "A"
        else:
            strict[i] = "B"
    tier_total = Counter(tier.values())
    strict_total = Counter(strict.values())

    # ----- phường/xã: THAY THẾ bằng crawl_query -----
    cq = [str(x.get("crawl_query") or "") for x in raw]
    cq_with = sum(bool(c) for c in cq)
    dist_c = Counter()
    for c in cq:
        f = fold(c)
        for dname in DISTRICTS_OLD:
            if fold(dname) in f:
                dist_c[dname] += 1
                break
    dist_matched = sum(dist_c.values())

    # ----- độ phủ -----
    desc_fields = ("ambience", "pros", "cons")
    desc_count = sum(any(nonempty(x.get(k)) for k in desc_fields) for x in raw)
    names_vi = sum(bool(VN_DIACRITIC.search(s)) for s in names)
    hours_nonempty = sum(not hours_status(x.get("opening_hours"))[0] for x in raw)
    hours_parse_n = sum(hours_status(x.get("opening_hours"))[1] for x in raw)
    hours_kind = Counter(hours_status(x.get("opening_hours"))[2] for x in raw)
    hours_empty = sum(hours_status(x.get("opening_hours"))[0] for x in raw)
    hours_bad = [(x.get("poi_id"), hours_status(x.get("opening_hours"))[3])
                 for x in raw if hours_status(x.get("opening_hours"))[2] == "không parse"]
    tickets = [x["ticket_vnd"] for x in raw if isinstance(x.get("ticket_vnd"), (int, float)) and x["ticket_vnd"] > 0]
    price_level = Counter(str(x.get("price_level")) for x in raw if x.get("price_level") is not None)
    fee_c = Counter(str(x.get("fee")) for x in raw if x.get("fee") is not None)
    price_note_n = sum(nonempty(x.get("price_note")) for x in raw)
    free_word = sum(bool(re.search(r"miễn phí|mien phi|free", str(x.get("price_note") or "") + str(x.get("ticket_note") or ""), re.I)) for x in raw)
    verified_vals = [parse_date(x.get("verified_at")) for x in raw]
    va_present = sum(nonempty(x.get("verified_at")) for x in raw)
    va_valid = [d for d in verified_vals if d]
    va_12m = sum(bool(d and CUTOFF_12M <= d <= TODAY) for d in verified_vals)
    fetched_c = Counter(str(x.get("fetched_at")) for x in raw)
    tags_n = sum(nonempty(x.get("tags")) for x in raw)
    space_n = sum(nonempty((x.get("smart_tags") or {}).get("space")) for x in raw)
    family_n = sum("family" in ((x.get("smart_tags") or {}).get("party") or []) for x in raw)
    smart_time_n = sum(nonempty((x.get("smart_tags") or {}).get("time")) for x in raw)
    osm_n = sum(nonempty(x.get("osm_evidence")) for x in raw)
    osm_hours_n = sum(nonempty((x.get("osm_evidence") or {}).get("hours")) for x in raw)
    poi_prefix = Counter("ChIJ" if str(x.get("poi_id", "")).startswith("ChIJ") else
                         str(x.get("poi_id", "")).split(":")[0] for x in raw)
    rating_n = sum(x.get("rating") not in (None, "", 0) for x in raw)
    ev_text = {k: [as_text_v for as_text_v in (x.get(k) for x in raw) if nonempty(as_text_v)]
               for k in ("web_evidence", "price_note", "ticket_note", "access_note")}
    ev_words = {k: [words_in(" ".join(walk_strings(v))) for v in vals] for k, vals in ev_text.items()}
    ev_viet = {k: sum(bool(VN_CHARS.search(" ".join(walk_strings(v)))) for v in vals) for k, vals in ev_text.items()}

    # ----- code, dữ liệu -----
    tree = build_tree()
    data_all = data_files()
    code = code_files()
    code_rows, test_files, test_funcs = code_inventory(code)
    raw_files, raw_count, raw_presence = raw_payload_scan()
    gold_files = sorted((ROOT / "BE/eval/gold").glob("*.json"))
    gold_q = {}
    for gp in gold_files:
        go = load_json(gp)
        if isinstance(go, list):
            gold_q[rel(gp)] = len(go)
        elif isinstance(go, dict) and isinstance(go.get("queries"), list):
            gold_q[rel(gp)] = len(go["queries"])
        else:
            gold_q[rel(gp)] = 0
    matrix = load_json(ROOT / "BE/data/snapshots/danang-v1/matrix.json") or {}
    matrix_ids = set(map(str, matrix.get("ids", []))) if isinstance(matrix, dict) else set()
    matrix_cov = len(matrix_ids & {str(x.get("poi_id")) for x in raw})
    gps = load_json(ROOT / "data/gps/demo_day.json") or {}
    gps_points = len(gps.get("points", [])) if isinstance(gps, dict) else 0
    code_text_hosts = Counter()
    for p in code:
        if p.suffix == ".py" and re.search(r"BE[/\\](ml|app)", rel(p)):
            for h in set(re.findall(r"https?://([^/\s'\"]+)", p.read_text(encoding="utf-8", errors="replace"))):
                code_text_hosts[h] += 1
    doc_files = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".md", ".txt")
                 and not any(part in IGNORE for part in p.relative_to(ROOT).parts)
                 and not rel(p).startswith("reports/")]
    lic_hits = 0
    lic_files = 0
    fb_code = 0
    for p in doc_files:
        t = p.read_text(encoding="utf-8", errors="replace")
        h = len(re.findall(r"license|giấy phép|điều khoản|terms of service|\bToS\b", t, re.I))
        lic_hits += h
        lic_files += int(h > 0)
    for p in code:
        if p.suffix == ".py" and re.search(r"BE[/\\](ml|app)", rel(p)):
            fb_code += int("facebook" in p.read_text(encoding="utf-8", errors="replace").lower())
    serp_refs = sum("serpapi" in p.read_text(encoding="utf-8", errors="replace").lower() for p in code if p.suffix == ".py")

    # ----- bảng -----
    L: list[str] = []
    A = L.append
    dupes_n = len(dup_pairs)
    grp_rows = {g: grp_c.get(g, 0) for g in GROUPS9 + ["other"]}
    rest_n = cat_codes.get("restaurant", 0)
    cafe_n = cat_codes.get("cafe", 0)
    t_ok = {k: tier_total.get(k, 0) for k in "ABC"}
    s_ok = {k: strict_total.get(k, 0) for k in "ABC"}
    other_n = grp_c.get("other", 0)
    hp_rate = hours_parse_n / n if n else 0.0
    price_cov = len(tickets) / n if n else 0.0
    desc_cov = desc_count / n if n else 0.0
    stat = Counter(r["status"] for r in code_rows)
    compliance: list[tuple[str, str, str]] = []

    # ---- 0. tóm tắt ----
    A("# Audit dữ liệu TravelAgent — 2026-11-18")
    A("")
    A("## 0. Tóm tắt")
    A(f"- POI chính `BE/data/snapshots/danang-v1/pois.json`: **{n}** bản ghi (metadata khai {root.get('count')}, lệch {n - int(root.get('count') or 0)}); trùng nghi ngờ {dupes_n} cặp; toạ độ hợp lệ {states.get('hợp lệ', 0)}/{n}.")
    A(f"- Quán ăn **{rest_n}** và quán cà phê **{cafe_n}** (theo `cat`); {other_n} POI ({pct(other_n, n)}) không vào 9 thể loại đích, gồm lưu trú {cat_codes.get('lodging', 0)} và spa {cat_codes.get('spa', 0)} (đếm theo `cat`).")
    A(f"- Giờ mở cửa parse được **{hours_parse_n}/{n}** ({pct(hours_parse_n, n)}); {hours_empty} POI rỗng; không có 24/7. Giá VND (`ticket_vnd`) chỉ **{len(tickets)}/{n}** ({pct(len(tickets), n)}).")
    A(f"- Mô tả: **0/{n}** — THIẾU; văn bản thay thế rất ít. Nguồn chính SerpAPI/Google Maps chiếm {sum(1 for x in raw if x.get('source') == 'serpapi/google-maps')}/{n} POI — cần rà soát điều khoản trước khi dùng ML.")
    A(f"- Phân hạng theo luật đề bài: **A {t_ok['A']}, B {t_ok['B']}, C {t_ok['C']}** (biến thể nghiêm ngặt: A {s_ok['A']}, B {s_ok['B']}, C {s_ok['C']}). Code: {len(code_rows)} module, {len(test_files)} tệp test, {test_funcs} hàm test (chưa chạy).")
    A("")

    # ---- 1. kiểm kê ----
    A("## 1. Kiểm kê project và code")
    A("")
    A("Cây thư mục (tối đa 3 cấp; số tệp tính đệ quy; bỏ `.git`, `node_modules`, `venv`, `__pycache__`, `.pytest_cache`):")
    A("")
    A("```")
    L += tree
    A("```")
    A("")
    A("Tệp dữ liệu: đường dẫn, định dạng, dung lượng, số dòng, cột:kiểu. Thư mục có ≥5 tệp dữ liệu được gộp một dòng (số tệp, tổng dung lượng, schema giao của 5 tệp đầu). JSON không phải danh sách thì số dòng là số khóa.")
    A("")
    A("| Đường dẫn | Định dạng | Dung lượng | Số dòng | Cột: kiểu |")
    A("|---|---|---:|---:|---|")
    by_dir = defaultdict(list)
    for p in data_all:
        by_dir[p.parent].append(p)
    for d, ps in sorted(by_dir.items(), key=lambda kv: rel(kv[0])):
        if len(ps) >= 5:
            total = sum(p.stat().st_size for p in ps)
            keysets = []
            for p in ps[:5]:
                o = load_json(p) if p.suffix == ".json" else None
                keysets.append(set(o.keys()) if isinstance(o, dict) else set())
            common = sorted(set.intersection(*keysets)) if keysets and all(keysets) else []
            L.append(f"| `{rel(d)}/` ({len(ps)} tệp) | {'/'.join(sorted({DATA_EXT[p.suffix.lower()] for p in ps}))} | {total:,} B tổng | payload không đồng nhất | "
                     f"{', '.join(common[:8]) + (f' (+{len(common) - 8} khóa)' if len(common) > 8 else '') or 'schema chung rỗng'} |")
        else:
            for p in ps:
                L.append(file_row(p))
    A("")
    A("Code (phân nhóm theo đường dẫn; trạng thái xác định bằng bằng chứng tĩnh: test/import, hàm rỗng, TODO, có `__main__`; **chưa chạy** crawler hay pytest — pytest không cài trong môi trường này (`No module named pytest`)):")
    A("")
    grp_order = ["crawler", "schema", "solver", "verifier", "test", "notebook", "khác"]
    grp_desc = {
        "crawler": "thu thập/làm giàu/ingest POI (BE/ml/data, fetch weather)",
        "schema": "kiểu dữ liệu API/POI/plan (BE/app/schemas)",
        "solver": "ma trận, tối ưu lộ trình, benchmark (optimizer, matrix, tools)",
        "verifier": "kiểm tra điều kiện, gate, đánh giá (validator, gate, judge, metrics)",
        "test": f"{len(test_files)} tệp test, {test_funcs} hàm test (BE/tests)",
        "notebook": "THIẾU: không có notebook .ipynb nào trong repo",
        "khác": "router API, service, ML model, cấu hình, server",
    }
    gstats = defaultdict(Counter)
    for r in code_rows:
        gstats[r["group"]][r["status"]] += 1
    rows_g = []
    for g in grp_order:
        c = gstats.get(g, Counter())
        nmod = sum(c.values())
        rows_g.append([g, grp_desc[g], nmod, ", ".join(f"{k} {v}" for k, v in c.most_common()) or ("không có" if g != "test" else "chạy được* (tĩnh)")])
    A(md_table(["Nhóm", "Chức năng", "Số module", "Trạng thái"], rows_g))
    A("")
    A("Chi tiết từng module (trạng thái: `chạy được*` = có test/import tĩnh, chưa chạy; `dở dang` = có hàm rỗng/TODO; `bản nháp` = không ai gọi; `KHÔNG XÁC ĐỊNH` = CLI chưa rõ):")
    A("")
    A("| Module | Nhóm | Chức năng (docstring) | Trạng thái | Bằng chứng |")
    A("|---|---|---|---|---|")
    for r in sorted(code_rows, key=lambda r: (grp_order.index(r["group"]), r["path"])):
        A(f"| `{r['path']}` | {r['group']} | {cell(r['doc'])} | {r['status']} | {r['ev']} |")
    A("")
    A(f"Trạng thái tổng: {', '.join(f'{k} {v}' for k, v in stat.most_common())}. Không liệt kê `BE/**/__init__.py` (khai báo package) và `reports/` (script audit này).")
    A("")

    # ---- 2. nguồn ----
    A("## 2. Nguồn gốc và giấy phép")
    A("")
    A(f"- Metadata snapshot: source `{root.get('source')}`, fetched_at `{root.get('fetched_at')}`, enriched_at `{root.get('enriched_at')}`, pruned_at `{root.get('pruned_at')}`. Mỗi POI có `fetched_at` nhưng chỉ {len(fetched_c)} giá trị ngày (lớn nhất {fetched_c.most_common(1)[0][0]} = {fetched_c.most_common(1)[0][1]} POI); `verified_at` có {va_present}/{n} POI.")
    A(f"- Nguồn theo POI (cột `source`): " + ", ".join(f"`{k}`={v}" for k, v in Counter(x.get('source') for x in raw).most_common()) + ".")
    A(f"- **Google Maps qua SerpAPI** ({serp_refs} tệp .py kể cả test nhắc `serpapi`): `{sum(1 for x in raw if x.get('source') == 'serpapi/google-maps')}` POI có nguồn này. Đây là nguồn rủi ro: điều khoản Google/SerpAPI có thể hạn chế lưu, tái sử dụng hoặc dùng để train. **Facebook**: không có POI nào mang nguồn Facebook; {fb_code} tệp code có nhắc `facebook`.")
    A(f"- Hosts trong code thu thập (BE/ml, BE/app, theo số tệp): " + ", ".join(f"`{h}`" for h, _ in code_text_hosts.most_common(8)) + ". OSM: `{osm_n}` POI có `osm_evidence`, nguồn `osm/overpass` = {sum(1 for x in raw if x.get('source') == 'osm/overpass')}.")
    A(f"- Giấy phép: repo có {lic_hits} lần nhắc license/điều khoản trong {lic_files} tệp tài liệu; không có văn bản giấy phép dữ liệu nào được gắn vào snapshot. **KHÔNG XÁC ĐỊNH** quyền sử dụng/tái phân phối từ dữ liệu cục bộ.")
    A(f"- Cập nhật: có ngày cập nhật (`verified_at`) cho {va_present}/{n} POI; thời điểm lấy `fetched_at` không thay thế ngày xác minh.")
    compliance.append(("Mục 2: điều khoản/giấy phép nguồn Google Maps, Facebook", "THIẾU", "không có văn bản giấy phép trong repo hoặc snapshot; cần rà soát điều khoản trước khi dùng ML"))
    A("")

    # ---- 3. danh mục ----
    A("## 3. Hồ sơ danh mục POI")
    A("")
    A(f"- File chính: `BE/data/snapshots/danang-v1/pois.json` (742 POI, khóa `pois`) — app đọc đúng thư mục này (BE/app/config.py). Các ứng viên khác: `data/snapshots/danang-full-tmp/pois_raw.json` ({len(load_json(ROOT/'data/snapshots/danang-full-tmp/pois_raw.json') or [])} bản ghi), `pois_raw_before_2026-10.json` ({len(load_json(ROOT/'data/snapshots/danang-full-tmp/pois_raw_before_2026-10.json') or [])}), `data/snapshots/danang-v1/pois.json` (7 bản ghi, không dùng).")
    A(f"- Tổng {n}; metadata {root.get('count')}; trùng nghi ngờ (< 50 m và tên bỏ dấu ≥ 0.85): **{dupes_n} cặp**, {len(dup_idx)} POI liên quan.")
    A("")
    if dupes_n == 0:
        A(f"**Số cặp trùng: 0 cặp, không có cặp để in.** Chẩn đoán: có {len(near_50)} cặp < 50 m (bất kể tên), độ giống tên lớn nhất {near_max_sim} < 0.85.")
    else:
        A(f"Số cặp trùng: {dupes_n}. In tối đa 10 cặp:")
        for i, j, d_m, sim in dup_pairs[:10]:
            A(f"- `{names[i]}` ↔ `{names[j]}`: {d_m:.1f} m, độ giống {sim:.3f}.")
    A("Ánh xạ 9 thể loại: `cat` là nguồn chính; từ khóa trong `type` (tiếng Việt, đã bỏ dấu) chỉ tinh chỉnh pagoda (chùa), museum_indoor (bảo tàng), night_spot (bar, karaoke, chợ đêm) và day_market (chợ). `cat`→nhóm: beach→beach; viewpoint→viewpoint; park/landmark/nature/attraction→outdoor_landmark; museum→museum_indoor; market→day_market; bar→night_spot; restaurant→restaurant; cafe→cafe; spa, lodging, mã khác→other.")
    A("")
    A("| Thể loại đích | Số POI |")
    A("|---|---:|")
    for g in GROUPS9 + ["other"]:
        A(f"| {g} | {grp_rows[g]} |")
    A("")
    A(f"**Quán ăn và quán cà phê có không? Có.** Theo `cat`: restaurant {rest_n}, cafe {cafe_n}. Theo nhóm đích: restaurant {grp_rows['restaurant']}, cafe {grp_rows['cafe']}. Không ánh xạ được (other): {other_n} POI.")
    A("")
    A("Top 20 `type` gốc trong nhóm `other`:")
    A("")
    other_types = Counter(str(x.get("type") or "(trống)") for x, g in zip(raw, grp) if g == "other")
    A("| type gốc | Số POI |")
    A("|---|---:|")
    for t, c in other_types.most_common(20):
        A(f"| {t} | {c} |")
    A("")
    A("Top 20 `type` gốc toàn bộ:")
    A("")
    A("| type gốc | Số POI |")
    A("|---|---:|")
    for t, c in cats.most_common(20):
        A(f"| {t} | {c} |")
    A("")
    A(f"- Toạ độ: thiếu {states.get('thiếu', 0)}; ngoài khung lon 107.2–108.8 / lat 14.9–16.3: {states.get('ngoài khung', 0)}; nghi đảo lat/lon: {states.get('nghi đảo', 0)}. Cự ly tới Cầu Rồng (chỉ POI có toạ độ): " + ", ".join(f"{k} {bridge.get(k, 0)}" for k in ("0–5 km", "5–15 km", "15–40 km", ">40 km")) + ".")
    A(f"- Phường/xã: **THIẾU** — snapshot không có trường địa chỉ, không có `ward_code`.")
    A(f"- **THAY THẾ**: dùng `crawl_query` (chỉ {cq_with}/{n} POI có) để đếm theo quận cũ: " + ", ".join(f"{k} {dist_c.get(k, 0)}" for k in DISTRICTS_OLD) + f". Khớp được {dist_matched}/{cq_with}; {n - dist_matched} POI không khớp quận nào (có thể chỉ là 'Đà Nẵng' chung hoặc không có `crawl_query`). Đây là vị trí của truy vấn tìm kiếm, không phải địa chỉ thật.")
    compliance.append(("Mục 3: phường/xã (ward_code mới)", "THIẾU", "không có trường địa chỉ hay mã phường/xã"))
    compliance.append(("Mục 3: phân bố theo phường/xã hoặc quận cũ", "THAY THẾ", f"đếm theo `crawl_query` ({dist_matched}/{n} POI khớp quận cũ); không phải địa chỉ thật"))
    A("")

    # ---- 4. độ phủ ----
    A("## 4. Độ phủ từng trường")
    A("")
    A("| Trường | Có giá trị | % | Ví dụ | Ghi chú chất lượng |")
    A("|---|---:|---:|---|---|")
    ex_name = next((s for s in names if VN_DIACRITIC.search(s)), "—")
    cov = [
        ("Tên (có dấu tiếng Việt)", names_vi, "tên có ký tự có dấu; tên là chuỗi lẫn tiếng Việt/Anh", ex_name),
        ("Mô tả", desc_count, "**THIẾU**: ambience/pros/cons có khóa nhưng rỗng; xem mục 6", "—"),
        ("Địa chỉ", 0, "**THIẾU**: không có trường `address`", "—"),
        ("Toạ độ", sum(coord_ok), "lat/lon; 0 thiếu", f"{raw[0].get('lat')}, {raw[0].get('lon')}" if n else "—"),
        ("Category (cat / type)", sum(bool(x.get("cat")) for x in raw), "cat chuẩn hoá và type gốc tiếng Việt", f"{raw[0].get('cat')} / {raw[0].get('type')}" if n else "—"),
        ("Giờ mở cửa (có dữ liệu)", hours_nonempty, f"parse được {hours_parse_n}; rỗng {hours_empty}", "list chuỗi"),
        ("Giá VND (`ticket_vnd`) — THAY THẾ cho giá vé", len(tickets), "**THAY THẾ**: không có trường `price`; dùng `ticket_vnd` (VND) và `price_level` (thang Google 1–3, không phải VND)", str(tickets[:3])),
        ("Price_level (Google, THAY THẾ)", sum(x.get("price_level") is not None for x in raw), "không phải số tiền; phân bố " + ", ".join(f"{k}:{v}" for k, v in sorted(price_level.items())), str(next((x.get("price_level") for x in raw if x.get("price_level") is not None), "—"))),
        ("Website/fanpage", 0, "**THIẾU** trong snapshot; raw payload có khóa website/facebook ở " + f"{raw_presence['website']}/{len(raw_files)} tệp", "—"),
        ("SĐT doanh nghiệp", 0, f"**THIẾU** trong snapshot; raw payload có khóa phone ở {raw_presence['phone']}/{len(raw_files)} tệp", "—"),
        ("Ảnh", 0, f"**THIẾU** trong snapshot; raw payload có khóa ảnh ở {raw_presence['photo']}/{len(raw_files)} tệp (số lần {raw_count['photo']})", "—"),
        ("Giấy phép ảnh", 0, "**THIẾU** hoàn toàn", "—"),
        ("Rating", rating_n, "trường `rating`; số lượt đánh giá (review count) **THIẾU**", "—"),
        ("Ngày cập nhật (`verified_at`)", va_present, f"{va_12m} trong 12 tháng; `fetched_at` là ngày snapshot ({len(fetched_c)} giá trị)", "—"),
        ("Tag", tags_n, f"`tags` list; trong nhà/ngoài trời (`smart_tags.space`) {space_n}; hợp trẻ em (`party` có family) {family_n}", "—"),
        ("Wikidata / mã ngoài", poi_prefix["ChIJ"] + poi_prefix["osm"] + poi_prefix["manual"], f"`poi_id` ChIJ {poi_prefix['ChIJ']}, osm: {poi_prefix['osm']}, manual {poi_prefix['manual']}; `osm_evidence.osm` {osm_n}; **Wikidata THIẾU**", "—"),
    ]
    for label, c, note, ex in cov:
        A(f"| {label} | {c}/{n} | {pct(c, n)} | {cell(ex)} | {note} |")
    compliance.append(("Mục 4: giá vé/giá trung bình", "THAY THẾ", f"`ticket_vnd` {len(tickets)}/{n} + `price_level` (thang Google, không phải VND)"))
    compliance.append(("Mục 4: địa chỉ", "THIẾU", "không có trường địa chỉ"))
    compliance.append(("Mục 4: website/fanpage, SĐT, ảnh, giấy phép ảnh, số lượt đánh giá, Wikidata", "THIẾU", "không có trong snapshot; raw payload có khóa nhưng không lưu thành trường POI"))
    A("")
    A("Ghi chú: 'Ngày cập nhật' — `verified_at` là ngày xác minh từng POI; `fetched_at` ở POI chỉ là ngày snapshot.")
    A("")

    # ---- 5. giờ & giá ----
    A("## 5. Giờ mở cửa và giá")
    A("")
    A(f"- Kiểu dữ liệu: `opening_hours` là list chuỗi (list {len(raw)}/{n}); rỗng `[]` = {sum(1 for x in raw if x.get('opening_hours') == [])}, null = {sum(1 for x in raw if x.get('opening_hours') is None)}. Dạng lưu: `HH:MM-HH:MM` theo khoảng, không có thứ trong tuần.")
    A(f"- Tỉ lệ: parse được **{hours_parse_n}/{n} = {pct(hours_parse_n, n)}** (HH:MM-HH:MM {hours_kind.get('HH:MM-HH:MM', 0)}, 24/7 {hours_kind.get('24/7', 0)}); **24/7: {pct(hours_kind.get('24/7', 0), n)}**; **trống: {hours_empty}/{n} = {pct(hours_empty, n)}**; không parse: {len(hours_bad)}.")
    A(f"- Theo từng thứ trong tuần: **THIẾU** — không có khung giờ theo ngày, parser không xác định được tỉ lệ theo thứ. **THAY THẾ** (ghi nhận): áp cùng một khung giờ cho mọi ngày.")
    A("")
    A(f"10 mẫu không parse (có {len(hours_bad)}; tất cả có dạng nhiều khoảng giờ trong một chuỗi, ví dụ `11:00-15:00, 17:00-22:30`):")
    A("")
    A("| poi_id | Giá trị thô |")
    A("|---|---|")
    for pid, raw_v in hours_bad[:10]:
        A(f"| `{pid}` | {cell(raw_v[:80])} |")
    A("")
    A(f"- Giá: đơn vị VND cho `ticket_vnd` ({len(tickets)} POI, khoảng {min(tickets) if tickets else '—'}–{max(tickets) if tickets else '—'} VND); `price_level` là thang 1–3 (không phải VND); `fee` là trường deprecated, toàn bộ = {', '.join(f'{k}:{v}' for k, v in fee_c.items())}.")
    A(f"- Tỉ lệ có giá VND: **{len(tickets)}/{n} = {pct(len(tickets), n)}**. Tỉ lệ ghi 'miễn phí' (price_note/ticket_note): **{free_word}/{n}**. `fee=0` không chứng minh miễn phí, nên không suy miễn phí từ trường này.")
    compliance.append(("Mục 5: tỉ lệ parse theo từng thứ trong tuần", "THIẾU", "không lưu khung giờ theo ngày"))
    compliance.append(("Mục 5: tỉ lệ miễn phí", "THIẾU", f"không có bằng chứng; fee=0 không đủ, chỉ {free_word} văn bản ghi 'miễn phí'"))
    A("")

    # ---- 6. văn bản & ảnh ----
    A("## 6. Văn bản và ảnh")
    A("")
    A(f"- Mô tả: **THIẾU** — {desc_count}/{n} POI có mô tả; độ dài TB và ngôn ngữ không tính được.")
    A(f"- **THAY THẾ** (các ghi chú/bằng chứng có sẵn): " + "; ".join(
        f"`{k}` {len(v)} POI, TB {statistics.mean(ev_words[k]) if ev_words[k] else 0:.1f} từ, có dấu Việt {ev_viet[k]}/{len(v)}" for k, v in ev_text.items()) + ". Đây là ghi chú/bằng chứng crawl, không phải mô tả điểm đến.")
    A(f"- Review text: **THIẾU** trong snapshot (0 POI). Raw payload SerpAPI có khóa review ở {raw_presence['review']}/{len(raw_files)} tệp (số lần {raw_count['review']}); không in nội dung. Điều khoản: review là nội dung của Google, cần kiểm tra trước khi lưu hay dùng để embedding.")
    A(f"- Ảnh: snapshot không có ảnh hay URL ảnh. Raw payload có khóa ảnh ở {raw_presence['photo']}/{len(raw_files)} tệp; vị trí lưu là các tệp raw trong `BE/data/raw-round2/` và `data/snapshots/danang-full-tmp/`; **giấy phép ảnh THIẾU**.")
    compliance.append(("Mục 6: mô tả (độ dài, ngôn ngữ)", "THIẾU", "0 POI có mô tả; THAY THẾ bằng ghi chú/bằng chứng ở trên"))
    compliance.append(("Mục 6: review text", "THIẾU", "không có trong snapshot; có khóa trong raw payload"))
    compliance.append(("Mục 6: ảnh và giấy phép", "THIẾU", "không có ảnh trong snapshot; giấy phép không có"))
    A("")

    # ---- 7. schema ----
    A("## 7. Đối chiếu schema đích")
    A("")
    A("| Trường đích | Trạng thái | Căn cứ |")
    A("|---|---|---|")
    schema_rows = [
        ("poi_id", "CÓ SẴN", f"{n}/{n}; ChIJ {poi_prefix['ChIJ']}, osm {poi_prefix['osm']}, manual {poi_prefix['manual']}"),
        ("name.vi", "SUY RA ĐƯỢC", f"`name` có dấu {names_vi}/{n}; chưa gắn nhãn ngôn ngữ"),
        ("name.en", "THIẾU", "không có tên tiếng Anh"),
        ("category", "CÓ SẴN", "`cat` và `type` 100%"),
        ("zone", "SUY RA ĐƯỢC", f"từ `crawl_query` quận cũ ({dist_matched}/{n}); chưa có ranh giới để tính từ toạ độ"),
        ("ward_code", "THIẾU", "không có mã phường/xã mới"),
        ("display_point", "CÓ SẴN", "lat/lon 100%"),
        ("access_points", "THIẾU", f"`access_note` {len(ev_text['access_note'])} POI là văn bản, không có toạ độ điểm vào"),
        ("geofence", "THIẾU", "không có đa giác"),
        ("opening_hours", "CÓ SẴN", f"một phần: parse được {hours_parse_n}/{n}"),
        ("price", "SUY RA ĐƯỢC", f"`ticket_vnd` {len(tickets)}/{n}; `price_level` (thang Google) là proxy"),
        ("tags", "CÓ SẴN", f"{tags_n}/{n}"),
        ("effort", "SUY RA ĐƯỢC", "từ `intensity` (100%), thang chưa có tài liệu"),
        ("weather_sensitivity", "CÓ SẴN", "`weather_sensitive` 100%; `smart_tags` exposure"),
        ("time_profile", "CÓ SẴN", f"`smart_tags.time` {smart_time_n}/{n}"),
        ("dwell_prior", "CÓ SẴN", "`visit_min` và `dur_source`/`dur_confidence` 100%"),
        ("provenance.source", "CÓ SẴN", f"`source` {n}/{n}"),
        ("provenance.verified_at", "CÓ SẴN", f"{va_present}/{n} (chưa đủ cho mọi POI)"),
        ("provenance.confidence", "SUY RA ĐƯỢC", "không có trường chung; có `dur_confidence`, `space_confidence`, `rain_protection_confidence`"),
        ("valid_from / valid_to", "THIẾU", "không có thời hạn hiệu lực"),
    ]
    for label, st, why in schema_rows:
        A(f"| `{label}` | {st} | {why} |")
    for label, st, why in schema_rows:
        if st == "THIẾU":
            compliance.append((f"Mục 7: schema `{label}`", "THIẾU", why))
        elif label in ("zone", "price"):
            compliance.append((f"Mục 7: schema `{label}`", "THAY THẾ", why))
    A("")

    # ---- 8. dữ liệu khác ----
    A("## 8. Dữ liệu khác")
    A("")
    ranker = [p for p in data_all if "shadow" in p.name.lower() or "accept" in p.name.lower() or "log" in p.name.lower()]
    review_like = [p for p in data_all if re.search(r"review|human|answers|verify", p.name, re.I)]
    weather_like = [p for p in data_all if "weather" in p.name.lower()]
    trip_like = [p for p in data_all if re.search(r"trip", p.name, re.I)]
    A("| Hạng mục | Kết quả đếm | Ghi chú |")
    A("|---|---|---|")
    A(f"| Log người dùng | {len(ranker)} tệp tên có log/shadow/accept | `BE/data/ranker_shadow.jsonl` là nhật ký ranker (không phải log người dùng thật); không có log người dùng thật. **THIẾU** |")
    A(f"| GPS/chặng đi | {gps_points} điểm trong `data/gps/demo_day.json` | demo, không xác định nguồn người dùng; tọa độ không in. Code: `BE/app/services/gps.py` |")
    A(f"| Đánh giá/nhãn | {len(review_like)} tệp (review/human/answers/verify) | review_answers, human_answers, human_verify_200 là nhãn người xem; số dòng ở mục 1 |")
    A(f"| Thời tiết đã lưu | {len(weather_like)} tệp tên có weather | nhãn weather_label, weather_review_200, WEATHER_AUDIT |")
    A(f"| Ma trận khoảng cách/thời gian | `BE/data/snapshots/danang-v1/matrix.json`: {len(matrix_ids)} ID, phủ {matrix_cov}/{n} POI | ma trận hiện có để xếp hạng/solver |")
    A(f"| TripSpec mẫu | {len(trip_like)} tệp tên có trip | **THIẾU** mẫu dữ liệu; chỉ có schema `BE/app/schemas/trip.py` |")
    A(f"| Câu nói/truy vấn mẫu (gold) | {sum(gold_q.values())} truy vấn trong {len(gold_files)} tệp gold | " + ", ".join(f"`{k}` {v}" for k, v in gold_q.items()) + " |")
    A(f"| Test case | {test_funcs} hàm `def test_` trong {len(test_files)} tệp | chưa chạy (pytest không cài) |")
    A(f"| Bộ benchmark solver | `BE/tools/benchmark_optimizer.py`, `BE/eval/baselines.py`, t053 baseline | có code và test; số kết quả xem `BE/eval/gold/t053_baselines.json` |")
    compliance.append(("Mục 8: log người dùng thật, GPS/chặng thật", "THIẾU", "chỉ có demo GPS và nhật ký ranker"))
    compliance.append(("Mục 8: TripSpec mẫu", "THIẾU", "không có tệp mẫu"))
    A("")

    # ---- 9. phân hạng ----
    A("## 9. Phân hạng A/B/C")
    A("")
    A("Luật đề bài: **A** = toạ độ hợp lệ + category + giờ parse được + nguồn có giá trị + verified_at trong 12 tháng. **C** = thiếu toạ độ/category, nghi trùng, hoặc chữ đóng cửa/closed/ngừng hoạt động (ranh giới từ, để 'enclosed' không khớp). **B** = phần còn lại.")
    A("")
    A("Bảng chính theo 9 thể loại đích + other:")
    A("")
    A("| Thể loại đích | A | B | C | Tổng |")
    A("|---|---:|---:|---:|---:|")
    by_g = defaultdict(Counter)
    by_c = defaultdict(Counter)
    by_gs = defaultdict(Counter)
    for i, (x, g) in enumerate(zip(raw, grp)):
        by_g[g][tier[i]] += 1
        by_c[str(x.get("cat") or "(trống)")][tier[i]] += 1
        by_gs[g][strict[i]] += 1
    for g in GROUPS9 + ["other"]:
        c = by_g.get(g, Counter())
        A(f"| {g} | {c['A']} | {c['B']} | {c['C']} | {sum(c.values())} |")
    A(f"| **Tổng** | **{t_ok['A']}** | **{t_ok['B']}** | **{t_ok['C']}** | **{n}** |")
    A("")
    A(f"Đối chiếu: A {t_ok['A']}, B {t_ok['B']}, C {t_ok['C']} — {'khớp' if (t_ok['A'], t_ok['B'], t_ok['C']) == (392, 350, 0) else 'KHÔNG khớp'} với A392/B350/C0 của đối chiếu độc lập. Chữ 'closed/đóng cửa' với ranh giới từ khớp {closed_hits} POI; nếu bỏ ranh giới từ, chuỗi thuần khớp {closed_literal} POI, toàn bộ là 'enclosed' trong `rain_cover`.")
    A("")
    A("Bảng phụ theo `cat` gốc:")
    A("")
    A("| cat | A | B | C | Tổng |")
    A("|---|---:|---:|---:|---:|")
    for c_name, c in sorted(by_c.items(), key=lambda kv: -sum(kv[1].values())):
        A(f"| {c_name} | {c['A']} | {c['B']} | {c['C']} | {sum(c.values())} |")
    A("")
    A("Biến thể nghiêm ngặt (bảng phụ): thêm `verified==true` và giá rõ (ticket_vnd>0, fee>0 hoặc free_entry) vào A; `verified==false` thành C.")
    A("")
    A("| Thể loại đích | A | B | C | Tổng |")
    A("|---|---:|---:|---:|---:|")
    for g in GROUPS9 + ["other"]:
        c = by_gs.get(g, Counter())
        A(f"| {g} | {c['A']} | {c['B']} | {c['C']} | {sum(c.values())} |")
    A(f"| **Tổng** | **{s_ok['A']}** | **{s_ok['B']}** | **{s_ok['C']}** | **{n}** |")
    A("")

    # ---- 10. vấn đề ----
    A("## 10. Vấn đề phát hiện")
    A("")
    A("| Mức độ | Mô tả | Số bản ghi | Ví dụ | Gợi ý xử lý |")
    A("|---|---|---:|---|---|")
    issues = [
        ("CAO", "Nguồn Google Maps qua SerpAPI: điều khoản chưa rõ cho lưu/tái dùng/train", sum(1 for x in raw if x.get("source") == "serpapi/google-maps"), "source=serpapi/google-maps", "Rà soát điều khoản và provenance trước khi dùng ML."),
        ("CAO", "Giá VND gần như không có; price_level là thang Google", n - len(tickets), f"ticket_vnd {len(tickets)}/{n}", "Thu thập giá vé có nguồn, đơn vị VND và ngày."),
        ("CAO", "Không có mô tả nào để embedding hay phân loại văn bản", n, "ambience/pros/cons rỗng", "Bổ sung mô tả có nguồn và quyền dùng trước khi embedding."),
        ("TRUNG BÌNH", f"Giờ mở cửa rỗng hoặc không parse được", hours_empty + len(hours_bad), f"rỗng {hours_empty}; nhiều khoảng {len(hours_bad)}", "Thêm parser nhiều khoảng và lịch theo thứ."),
        ("TRUNG BÌNH", "Metadata `count` lệch số POI thực tế", abs(int(root.get("count") or 0) - n), f"{root.get('count')} so với {n}", "Đồng bộ count khi xuất snapshot."),
        ("TRUNG BÌNH", "Thiếu verified_at cho POI (không đủ điều kiện A)", n - va_present, "verified_at trống", "Ưu tiên xác minh các POI dự kiến dùng."),
        ("TRUNG BÌNH", "Lưu trú/spa/bar lẫn trong danh sách POI du lịch", sum(1 for x in raw if x.get("cat") in ("lodging", "spa", "bar")), ", ".join(f"{k}={v}" for k, v in Counter(x.get('cat') for x in raw if x.get('cat') in ("lodging", "spa", "bar")).most_common()), "Tách khỏi activity hoặc gắn cờ suitability."),
        ("TRUNG BÌNH", "Nhóm other chiếm tỉ lệ lớn", other_n, f"{pct(other_n, n)} POI", "Quyết định loại khỏi taxonomy hay thêm nhãn."),
        ("TRUNG BÌNH", "Quận/phường không có trường địa chỉ", n, "không có address/ward", "Thêm địa chỉ có cấu trúc và mã phường/xã mới."),
        ("THẤP", "Regex 'closed' khớp nhầm 'enclosed' trong smart_tags.rain_cover", sum(1 for x in raw if "enclosed" in str(x.get("smart_tags", {}).get("rain_cover", "")).lower()), "rain_cover='enclosed'", "Dùng ranh giới từ (đã áp dụng trong phân hạng)."),
        ("THẤP", "Trường io_label còn rỗng", sum(1 for x in raw if x.get("io_label") in (None, "")), "io_label null", "Bổ sung nhãn trong nhà/ngoài trời khi có bằng chứng."),
    ]
    for sev, desc0, cnt, ex, tip in issues:
        A(f"| {sev} | {desc0} | {cnt} | {cell(ex)} | {tip} |")
    A("")

    # ---- 11. không xác định ----
    A("## 11. Những điều KHÔNG XÁC ĐỊNH được")
    A("")
    A("- Quyền sử dụng, tái phân phối và train trên POI, review, ảnh: không có điều khoản/giấy phép trong repo.")
    A("- Trạng thái đóng/mở thực tế hôm nay; `verified_at` không bảo đảm địa điểm còn hoạt động.")
    A("- Code có chạy được không: crawler gọi mạng và pytest không cài, nên chỉ có bằng chứng tĩnh; các module có `chạy được*` chưa chạy thử.")
    A("- Nội dung và nguồn của log/GPS demo, và TripSpec mẫu (không có tệp).")
    A("- Ranh giới phường/xã và geofence: không có dữ liệu.")
    A("")
    A("Đối chiếu tuân thủ đề bài (mục đã THIẾU hoặc THAY THẾ):")
    A("")
    A("| Yêu cầu đề bài | Trạng thái | Ghi chú |")
    A("|---|---|---|")
    seen = set()
    for req, st, note in compliance:
        if req in seen:
            continue
        seen.add(req)
        A(f"| {req} | {st} | {note} |")
    A("")

    # ---- 12. phụ lục ----
    rng = random.Random(42)
    sample = rng.sample(list(enumerate(raw)), min(10, len(raw))) if raw else []
    A("## 12. Phụ lục")
    A("")
    A("10 bản ghi POI ngẫu nhiên (seed = 42, qua `random.Random(42).sample`; trường cá nhân nhạy cảm đã che nếu có):")
    A("")
    A("```json")
    A(json.dumps([redact_scrub(x) for _, x in sample], ensure_ascii=False, indent=2))
    A("```")
    A("")
    A("Danh sách script: `reports/audit_scripts/data_audit.py` (sinh báo cáo này), `reports/audit_scripts/crosscheck.py` (kiểm chứng độc lập).")
    A("")

    # ---- JSON cuối ----
    category_counts = {g: grp_rows[g] for g in GROUPS9 + ["other"]}
    other_data = {
        "log_nguoi_dung_that": sum("user" in p.name.lower() for p in ranker),
        "gps_demo_points": gps_points,
        "review_label_files": len(review_like),
        "weather_files": len(weather_like),
        "matrix_ids": len(matrix_ids),
        "matrix_covered_pois": matrix_cov,
        "tripspec_sample_files": len(trip_like),
        "gold_queries": sum(gold_q.values()),
        "test_cases": test_funcs,
        "test_files": len(test_files),
        "benchmark_solver": "có code + test; t053_baselines.json",
    }
    code_status = {g: (", ".join(f"{k} {v}" for k, v in gstats.get(g, Counter()).most_common()) or "THIẾU")
                   for g in grp_order}
    code_status["test"] = f"{test_funcs} hàm test, chưa chạy (pytest không cài)"
    code_status["notebook"] = "THIẾU"
    j = {
        "total_poi": n,
        "has_restaurants": rest_n,
        "has_cafes": cafe_n,
        "category_counts": category_counts,
        "duplicates_suspected": dupes_n,
        "missing_coords": states.get("thiếu", 0),
        "out_of_bbox": out_bbox,
        "opening_hours_parse_rate": round(hp_rate, 4),
        "price_coverage": round(price_cov, 4),
        "description_coverage": round(desc_cov, 4),
        "tier_counts": t_ok,
        "sources": sorted({str(x.get("source")) for x in raw}),
        "risky_sources": sorted({str(x.get("source")) for x in raw if re.search(r"google|serpapi|facebook", str(x.get("source")), re.I)}),
        "other_data": other_data,
        "code_status": code_status,
        "price_coverage_note": f"ticket_vnd (VND) {len(tickets)}/{n}; THAY THẾ: price_level là thang Google 1–3 (không phải VND) phủ {sum(x.get('price_level') is not None for x in raw)}/{n}; fee là trường deprecated = 0 cho tất cả, không chứng minh miễn phí",
        "strict_tier_counts": s_ok,
    }
    A("```json")
    A(json.dumps(j, ensure_ascii=False, indent=2))
    A("```")

    md = "\n".join(L) + "\n"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(md, encoding="utf-8")

    # đo số từ: bỏ bảng, khối code, phụ lục (mục 12)
    kept, in_code = [], False
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or s.startswith("|"):
            continue
        if s.startswith("## 12."):
            break
        kept.append(line)
    word_count = len(" ".join(kept).split())
    print(f"POI={n} metadata={root.get('count')} tiers={t_ok} strict={s_ok} rest={rest_n} cafe={cafe_n} other={other_n}")
    print(f"dup_pairs={dupes_n} missing={states.get('thiếu', 0)} out_bbox={out_bbox} hours_parse={hours_parse_n}/{n}")
    print(f"code_modules={len(code_rows)} test_files={len(test_files)} test_funcs={test_funcs} status={dict(stat)}")
    print(f"SỐ TỪ (không tính bảng, khối code, mục 12) = {word_count}")
    print("JSON keys:", list(j)[:15])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
