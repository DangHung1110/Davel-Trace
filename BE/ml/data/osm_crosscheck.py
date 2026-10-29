"""Cross-check every POI against OpenStreetMap, field by field (Phase 4, tier 1).

OSM is a second source, independent of the Google crawl. A POI is matched
to a named OSM object when a name variant agrees and the distance to the
object's GEOMETRY (not its centre: a beach is a long line) is <= RADIUS_M.
Names are folded (no diacritics), generic words ("bãi biển", "beach") and a
trailing address ("- 58 Ông Ích Đường", "cơ sở 2 462 ...") are dropped; then
the token sets must be equal, or share >= 2 tokens in the same order
("Trà Sơn" is not "Sơn Trà"), one of them not a kind of place or a Da Nang
place name. Each field then gets a status:

  exists, location  confirmed (matched, category not in conflict) | single
  category          confirmed (OSM tags allow the POI `cat`) | conflict
                    (specific tags say another category; the match is then
                    doubtful, so exists/location stay single) | single (no
                    usable tag; tourism=attraction or a bare shop/building
                    tag never makes a conflict)
  hours             confirmed (envelopes within HOURS_TOLERANCE_MIN) |
                    conflict | single (OSM has none / unparsed) | osm_only
                    (POI has none, OSM has: a candidate value) | missing
  same_source       the POI value itself came from OSM: no second source

Two POIs matched to one OSM object are reported as possible duplicates.
Writes nothing into pois.json and never touches `verified`: the output is a
sidecar (`osm_crosscheck.json` + `OSM_CROSSCHECK.md`) for the review page.

Needs `osmium` on PATH and the extract from BE/tools/osrm/build_osrm.sh:

  python BE/ml/data/osm_crosscheck.py --snapshot BE/data/snapshots/danang-v1 \\
      --pbf <data_dir>/danang.osm.pbf [--write]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.common import DAY_MIN, SIGHTSEEING_CATS, hhmm, open_windows  # noqa: E402

FORMAT = "osm-crosscheck-v1"
RADIUS_M = 150
NAME_SCORE_MIN = 0.6
HOURS_TOLERANCE_MIN = 30
CELL_DEG = 0.01
NAME_KEYS = ("name", "name:vi", "name:en", "alt_name", "old_name", "official_name",
             "short_name")
# osmium tags-filter expressions: every kind of object a POI can be.
OSM_FILTERS = ("nwr/amenity", "nwr/tourism", "nwr/shop", "nwr/leisure", "nwr/historic",
               "nwr/natural", "nwr/religion", "nwr/place=island,islet",
               "nwr/waterway=waterfall", "w/bridge", "nwr/man_made=bridge,lighthouse",
               "nwr/building=temple,church,pagoda,shrine")
# Words that name a kind of place, not this place.
GENERIC = {
    "quan", "nha", "hang", "cafe", "coffee", "ca", "phe", "da", "nang", "danang",
    "the", "va", "and", "spa", "bar", "restaurant", "beach", "bai", "bien", "cho",
    "tiem", "shop", "hotel", "khach", "san", "massage", "pub", "co", "so", "chi",
    "nhanh", "tam", "to", "of", "city", "thanh", "pho", "vietnam", "viet",
}
# Kept in the names but never enough on their own: kinds of place ("Bảo tàng
# Đà Nẵng" is not "Bảo tàng Mỹ thuật Đà Nẵng"), dishes ("Mỳ Quảng Quê Xưa" is
# not "My Quang Restaurant") and Da Nang place names ("Son Tra Retreat" is not
# "Son Tra Viewpoint"). A partial match must share one word outside this set.
NOT_DISTINCTIVE = {
    "bao", "tang", "museum", "chua", "pagoda", "temple", "tho", "church", "cong",
    "vien", "park", "cau", "bridge", "dinh", "mieu", "tuong", "dai", "khu", "du",
    "lich", "nui", "ho", "dong", "cave", "suoi", "thac", "vinh", "ban", "dao",
    "deo", "view", "viewpoint", "point", "market", "night", "dem", "lang", "resort",
    "son", "tra", "ngu", "hanh", "hai", "chau", "khe", "lien", "chieu", "cam", "le",
    "hoa", "vang", "my", "non", "nuoc", "hoi", "an", "tan", "han", "nam", "xuan",
    "thuan", "phuoc", "van",
    "mi", "quang", "bun", "bo", "banh", "xeo", "com", "lau", "nuong", "oc", "che",
    "kem", "sua", "bia", "ga", "vit", "heo", "chay", "seafood", "bbq", "grill",
    "kitchen", "house", "garden", "lounge", "rooftop", "sky", "food", "an",
}
DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
SIGHT = set(SIGHTSEEING_CATS)
# OSM tag (key, value or "*") -> POI categories it supports.
TAG_CATS = {
    ("amenity", "restaurant"): {"restaurant"}, ("amenity", "fast_food"): {"restaurant"},
    ("amenity", "food_court"): {"restaurant", "market"},
    ("amenity", "cafe"): {"cafe"}, ("amenity", "ice_cream"): {"cafe"},
    ("amenity", "bar"): {"bar"}, ("amenity", "pub"): {"bar"},
    ("amenity", "nightclub"): {"bar"}, ("amenity", "biergarten"): {"bar"},
    ("amenity", "marketplace"): {"market"},
    ("amenity", "place_of_worship"): {"landmark", "attraction"},
    ("amenity", "spa"): {"spa"}, ("leisure", "spa"): {"spa"},
    ("shop", "massage"): {"spa"}, ("shop", "beauty"): {"spa"},
    ("shop", "hairdresser"): {"spa"}, ("amenity", "public_bath"): {"spa"},
    ("shop", "*"): {"market"},
    ("tourism", "museum"): {"museum"}, ("tourism", "gallery"): {"museum"},
    ("tourism", "attraction"): SIGHT, ("tourism", "viewpoint"): {"viewpoint", "landmark",
                                                               "nature", "attraction"},
    ("tourism", "theme_park"): {"attraction", "park"}, ("tourism", "zoo"): {"attraction"},
    ("tourism", "aquarium"): {"attraction"},
    ("tourism", "hotel"): {"lodging"}, ("tourism", "guest_house"): {"lodging"},
    ("tourism", "hostel"): {"lodging"}, ("tourism", "resort"): {"lodging"},
    ("tourism", "apartment"): {"lodging"}, ("tourism", "motel"): {"lodging"},
    ("historic", "*"): {"landmark", "attraction", "museum"},
    ("leisure", "park"): {"park"}, ("leisure", "garden"): {"park"},
    ("leisure", "water_park"): {"attraction"}, ("leisure", "amusement_arcade"): {"attraction"},
    ("leisure", "beach_resort"): {"beach", "lodging"},
    ("natural", "beach"): {"beach"},
    ("natural", "cave_entrance"): {"nature", "landmark", "attraction"},
    ("natural", "*"): {"nature", "viewpoint", "attraction"},
    ("place", "*"): {"nature", "attraction"}, ("waterway", "waterfall"): {"nature"},
    ("bridge", "*"): {"landmark", "attraction"},
    ("man_made", "bridge"): {"landmark", "attraction"},
    ("man_made", "lighthouse"): {"landmark", "attraction", "viewpoint"},
    ("building", "*"): {"landmark", "attraction"},
}
# Tags any kind of place may carry (a famous restaurant is a tourism
# attraction, a museum runs a shop): they confirm a category, never refute it.
GENERIC_TAGS = {("tourism", "attraction"), ("shop", "*"), ("building", "*")}


# --- names -----------------------------------------------------------------

def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text or "").lower()).replace("đ", "d")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", text)


def name_tokens(text: str) -> list[str]:
    """Distinctive tokens in order (generic words and 1-char tokens dropped)."""
    out: list[str] = []
    for t in fold(text).split():
        if len(t) > 1 and t not in GENERIC and t not in out:
            out.append(t)
    return out


def core_name(name: str) -> str:
    """The name without a branch/address tail: text after " - ", "|", "(",
    "," and, inside the head, from a house number (digits only) that follows
    a distinctive word and precedes a capitalised street ("Nhà Mình Spa cơ sở
    2 462 Điện Biên Phủ" -> "Nhà Mình Spa cơ sở 2"; "3D Art" stays). Falls
    back to the full name."""
    head = re.split(r"\s[-–|/]\s|[|(,]", str(name or ""))[0]
    words = head.split()
    for i, word in enumerate(words):
        if re.fullmatch(r"\d+", word) and i + 1 < len(words) \
                and words[i + 1][:1].isupper() and name_tokens(" ".join(words[:i])):
            head = " ".join(words[:i])
            break
    return head if name_tokens(head) else str(name or "")


def name_score(poi_name: str, osm_names: list[str]) -> float:
    """1.0 for equal token sets; else shared/shorter when >= 2 tokens are
    shared in the same order and one of them is distinctive; 0 otherwise.
    One shared word ("Sao" in "Bãi tắm Sao Biển" vs "Nhà thờ Đức Mẹ Sao
    Biển") is never enough."""
    mine, best = name_tokens(core_name(poi_name)), 0.0
    for other in osm_names:
        theirs = name_tokens(other)
        if not mine or not theirs:
            if fold(other).split() == fold(poi_name).split():
                best = 1.0
            continue
        if set(mine) == set(theirs):
            return 1.0
        shared = set(mine) & set(theirs)
        if len(shared) >= 2 and shared - NOT_DISTINCTIVE and \
                [t for t in mine if t in shared] == [t for t in theirs if t in shared]:
            best = max(best, len(shared) / min(len(mine), len(theirs)))
    return best


# --- geometry --------------------------------------------------------------

def _xy(lat0: float, lat: float, lon: float) -> tuple[float, float]:
    """Metres on a local equirectangular plane around latitude lat0."""
    return lon * 111320.0 * math.cos(math.radians(lat0)), lat * 110540.0


def _segment_m(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy)
                                               / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _rings(geometry: dict) -> tuple[list[list], list[list]]:
    """(lines, polygon outer rings) as [lon, lat] coordinate lists."""
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    if kind == "Point":
        return [[coords]], []
    if kind == "LineString":
        return [coords], []
    if kind == "MultiLineString":
        return list(coords), []
    if kind == "Polygon":
        return list(coords), [coords[0]]
    if kind == "MultiPolygon":
        return [r for poly in coords for r in poly], [poly[0] for poly in coords]
    return [], []


def _inside(x: float, y: float, ring: list) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def distance_m(lat: float, lon: float, geometry: dict) -> float:
    """Metres from a point to the nearest part of a GeoJSON geometry (0 inside)."""
    lines, outers = _rings(geometry)
    if any(_inside(lon, lat, ring) for ring in outers):
        return 0.0
    p = _xy(lat, lat, lon)
    best = math.inf
    for line in lines:
        pts = [_xy(lat, c[1], c[0]) for c in line]
        if len(pts) == 1:
            best = min(best, math.hypot(p[0] - pts[0][0], p[1] - pts[0][1]))
        for a, b in zip(pts, pts[1:]):
            best = min(best, _segment_m(p, a, b))
    return best


def _bbox(geometry: dict) -> tuple[float, float, float, float]:
    lines, _ = _rings(geometry)
    lons = [c[0] for line in lines for c in line]
    lats = [c[1] for line in lines for c in line]
    return min(lats), min(lons), max(lats), max(lons)


# --- tags ------------------------------------------------------------------

def osm_categories(tags: dict) -> tuple[set[str], set[str]]:
    """(categories from specific tags, categories from generic tags)."""
    specific: set[str] = set()
    generic: set[str] = set()
    for key, value in tags.items():
        rule = (key, value) if (key, value) in TAG_CATS else (key, "*")
        cats = TAG_CATS.get(rule, set())
        (generic if rule in GENERIC_TAGS else specific).update(cats)
    return specific, generic


def category_status(cat: str, tags: dict) -> tuple[str, list[str]]:
    specific, generic = osm_categories(tags)
    seen = sorted(specific | generic)
    if cat in specific or cat in generic:
        return "confirmed", seen
    return ("conflict" if specific else "single"), seen


def _days(selector: str) -> list[int] | None:
    out: list[int] = []
    for part in selector.split(","):
        part = part.strip()
        if part in ("PH", "SH"):
            continue  # holidays never decide an ordinary day
        ends = part.split("-")
        if not all(e in DAYS for e in ends) or len(ends) > 2:
            return None
        a, b = DAYS.index(ends[0]), DAYS.index(ends[-1])
        out += list(range(a, b + 1)) if a <= b else list(range(a, 7)) + list(range(b + 1))
    return out


def parse_osm_hours(raw: str) -> dict[int, list[tuple[int, int]]] | None:
    """OSM opening_hours -> {weekday 0..6: same-day spans}; None if any rule is
    outside the common subset (weekday selectors, HH:MM-HH:MM lists, off)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw == "24/7":
        return {d: [(0, DAY_MIN)] for d in range(7)}
    week: dict[int, list[tuple[int, int]]] = {}
    day_sel = r"(?:Mo|Tu|We|Th|Fr|Sa|Su|PH|SH)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?"
    for rule in re.split(r";|\|\|", raw):
        rule = rule.strip()
        if not rule:
            continue
        m = re.match(rf"^({day_sel}(?:\s*,\s*{day_sel})*)\s*(.*)$", rule)
        days = _days(m.group(1)) if m else list(range(7))
        body = (m.group(2) if m else rule).strip()
        if days is None:
            return None
        if body in ("off", "closed"):
            spans = []
        else:
            parts = [p.strip() for p in body.split(",")]
            spans = []
            for part in parts:
                t = re.fullmatch(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", part)
                if not t:
                    return None
                o = int(t.group(1)) * 60 + int(t.group(2))
                c = int(t.group(3)) * 60 + int(t.group(4))
                spans.append((o, c if c > o else c + DAY_MIN))
        for d in days:
            week[d] = sorted(spans)
    for d in range(7):
        week.setdefault(d, week.get(d, []))
    return week if any(week.values()) else None


def osm_open_windows(week: dict) -> tuple[list[tuple[int, int]], list[str]]:
    """(windows open on every open day, closed weekdays) for a parsed week."""
    closed = [DAYS[d] for d in range(7) if not week.get(d)]
    variants = {",".join(f"{hhmm(o)}-{hhmm(c % DAY_MIN)}" for o, c in week[d])
                for d in range(7) if week.get(d)}
    return open_windows(sorted(variants)) or [], closed


def compare_hours(poi: dict, osm_raw: str | None) -> tuple[str, dict]:
    if poi.get("hours_source") in ("osm", "osm-converted"):
        return "same_source", {}
    mine = open_windows(poi.get("opening_hours"))
    week = parse_osm_hours(osm_raw) if osm_raw else None
    if week is None:
        status = "single" if mine else "missing"
        return status, ({"osm_raw": osm_raw, "unparsed": True} if osm_raw else {})
    theirs, closed = osm_open_windows(week)
    evidence = {"osm_raw": osm_raw,
                "osm_windows": [f"{hhmm(o)}-{hhmm(c % DAY_MIN)}" for o, c in theirs]}
    if closed:
        evidence["osm_closed_days"] = closed
    if not mine:
        return "osm_only", evidence
    if not theirs:
        return "conflict", evidence
    gap = max(abs(mine[0][0] - theirs[0][0]), abs(mine[-1][1] - theirs[-1][1]))
    evidence["envelope_gap_min"] = gap
    return ("confirmed" if gap <= HOURS_TOLERANCE_MIN else "conflict"), evidence


# --- matching --------------------------------------------------------------

def load_features(lines) -> list[dict]:
    """Named OSM objects from `osmium export -f geojsonseq` lines."""
    out = []
    for line in lines:
        line = line.strip().lstrip("\x1e")
        if not line:
            continue
        feature = json.loads(line)
        tags = feature.get("properties") or {}
        names = [tags[k] for k in NAME_KEYS if tags.get(k)]
        geometry = feature.get("geometry") or {}
        if not names or not geometry.get("coordinates"):
            continue
        out.append({"id": feature.get("id") or tags.get("@id") or "", "names": names,
                    "tags": tags, "geometry": geometry, "bbox": _bbox(geometry)})
    return out


def _grid(features: list[dict]) -> dict:
    grid = defaultdict(list)
    for i, f in enumerate(features):
        la0, lo0, la1, lo1 = f["bbox"]
        for gy in range(math.floor(la0 / CELL_DEG), math.floor(la1 / CELL_DEG) + 1):
            for gx in range(math.floor(lo0 / CELL_DEG), math.floor(lo1 / CELL_DEG) + 1):
                grid[(gy, gx)].append(i)
    return grid


def best_match(poi: dict, features: list[dict], grid: dict) -> dict | None:
    lat, lon = poi.get("lat"), poi.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    gy, gx = math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG)
    seen, best = set(), None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for i in grid.get((gy + dy, gx + dx), ()):
                if i in seen:
                    continue
                seen.add(i)
                f = features[i]
                score = name_score(poi.get("name", ""), f["names"])
                if score < NAME_SCORE_MIN:
                    continue
                d = distance_m(lat, lon, f["geometry"])
                if d <= RADIUS_M and (best is None or (score, -d) > (best[0], -best[1])):
                    best = (score, d, f)
    if best is None:
        return None
    score, d, f = best
    keep = {k: v for k, v in f["tags"].items()
            if k in {"amenity", "tourism", "shop", "leisure", "historic", "natural",
                     "religion", "place", "bridge", "man_made", "building", "fee",
                     "opening_hours"}}
    return {"osm": f["id"], "name": f["names"][0], "dist_m": round(d, 1),
            "score": round(score, 2), "tags": keep}


def check_poi(poi: dict, match: dict | None) -> dict:
    own_source = str(poi.get("poi_id", "")).startswith("osm:") or \
        poi.get("source") == "osm/overpass"
    fields, evidence = {}, {}
    if match is None:
        fields.update(exists="single", location="single", category="single")
        hours, ev = compare_hours(poi, None)
    elif own_source:
        fields.update(exists="same_source", location="same_source",
                      category="same_source")
        hours, ev = compare_hours(poi, match["tags"].get("opening_hours"))
    else:
        category, seen = category_status(poi.get("cat") or "", match["tags"])
        evidence["osm_categories"] = seen
        doubtful = category == "conflict"
        fields.update(exists="single" if doubtful else "confirmed",
                      location="single" if doubtful else "confirmed",
                      category=category)
        hours, ev = compare_hours(poi, match["tags"].get("opening_hours"))
    fields["hours"] = hours
    if ev:
        evidence["hours"] = ev
    return {"fields": fields, "match": match, "evidence": evidence}


def crosscheck(pois: list[dict], features: list[dict]) -> dict:
    grid = _grid(features)
    rows = {p["poi_id"]: check_poi(p, best_match(p, features, grid)) for p in pois}
    by_osm = defaultdict(list)
    for pid, row in rows.items():
        if row["match"]:
            by_osm[row["match"]["osm"]].append(pid)
    for ids in by_osm.values():
        if len(ids) > 1:
            for pid in ids:
                rows[pid]["duplicate_of"] = sorted(set(ids) - {pid})
    return rows


def summarize(pois: list[dict], rows: dict) -> dict:
    out = {}
    for scope in ("all", "verified"):
        members = [p for p in pois if scope == "all" or p.get("verified")]
        fields = defaultdict(Counter)
        for p in members:
            for field, status in rows[p["poi_id"]]["fields"].items():
                fields[field][status] += 1
        by_cat = defaultdict(Counter)
        for p in members:
            by_cat[p.get("cat") or ""][rows[p["poi_id"]]["fields"]["exists"]] += 1
        out[scope] = {"pois": len(members),
                      "fields": {k: dict(v) for k, v in sorted(fields.items())},
                      "exists_by_cat": {k: dict(v) for k, v in sorted(by_cat.items())},
                      "duplicates": sum(1 for p in members
                                        if rows[p["poi_id"]].get("duplicate_of"))}
    return out


# --- io --------------------------------------------------------------------

def export_features(pbf: str) -> tuple[list[dict], dict]:
    """Run osmium tags-filter + export on the extract; (features, provenance)."""
    with open(pbf, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        named = os.path.join(tmp, "named.osm.pbf")
        seq = os.path.join(tmp, "named.geojsonseq")
        subprocess.run(["osmium", "tags-filter", "--overwrite", "-o", named, pbf,
                        *OSM_FILTERS], check=True, capture_output=True)
        subprocess.run(["osmium", "export", "--overwrite", "-f", "geojsonseq",
                        "--add-unique-id=type_id", "-o", seq, named],
                       check=True, capture_output=True)
        stamp = subprocess.run(["osmium", "fileinfo", "-e", "-g", "data.timestamp.last",
                                pbf], check=True, capture_output=True, text=True)
        with open(seq, encoding="utf-8") as f:
            features = load_features(f)
    return features, {"pbf": os.path.basename(pbf), "pbf_sha256": sha,
                      "osm_timestamp": stamp.stdout.strip(),
                      "filters": list(OSM_FILTERS)}


def markdown(summary: dict, pois: list[dict], rows: dict, meta: dict) -> str:
    by_id = {p["poi_id"]: p for p in pois}
    v = summary["verified"]
    lines = [
        "# OSM cross-check (tier 1)", "",
        f"Generated by `BE/ml/data/osm_crosscheck.py` from `{meta['pbf']}` "
        f"(OSM data up to {meta['osm_timestamp']}). Radius {RADIUS_M} m to the object's "
        f"geometry, name score >= {NAME_SCORE_MIN}, hours tolerance "
        f"{HOURS_TOLERANCE_MIN} min. `verified` is untouched.", "",
        "| Field | " + " | ".join(("confirmed", "conflict", "single", "same_source",
                                   "osm_only", "missing")) + " |",
        "|---|---|---|---|---|---|---|",
    ]
    for scope in ("verified", "all"):
        for field, counts in summary[scope]["fields"].items():
            cells = [str(counts.get(s, 0)) for s in ("confirmed", "conflict", "single",
                                                     "same_source", "osm_only", "missing")]
            lines.append(f"| {scope}: {field} | " + " | ".join(cells) + " |")
    lines += ["", f"Possible duplicates among verified POIs: {v['duplicates']}.", ""]

    def section(title, keep):
        hits = [p for p in pois if p.get("verified") and keep(rows[p["poi_id"]])]
        lines.extend([f"## {title} ({len(hits)} verified)", ""])
        for p in sorted(hits, key=lambda p: (p.get("cat") or "", p["name"])):
            row = rows[p["poi_id"]]
            m = row["match"] or {}
            hours = row["evidence"].get("hours", {})
            lines.append(
                f"- {p['name']} [{p.get('cat')}] -> OSM `{m.get('osm')}` \"{m.get('name')}\""
                f" {m.get('dist_m')} m | tags {sorted(row['evidence'].get('osm_categories', []))}"
                f" | POI hours {p.get('opening_hours')} vs OSM {hours.get('osm_raw')}")
        lines.append("")

    section("Category conflicts", lambda r: r["fields"]["category"] == "conflict")
    section("Hours conflicts", lambda r: r["fields"]["hours"] == "conflict")
    section("Hours only in OSM", lambda r: r["fields"]["hours"] == "osm_only")
    dups = [p for p in pois if p.get("verified") and rows[p["poi_id"]].get("duplicate_of")]
    lines.extend([f"## Possible duplicates ({len(dups)} verified)", ""])
    for p in sorted(dups, key=lambda p: p["name"]):
        others = [by_id[i]["name"] for i in rows[p["poi_id"]]["duplicate_of"]]
        lines.append(f"- {p['name']} == {others} (OSM `{rows[p['poi_id']]['match']['osm']}`)")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pbf", help="danang.osm.pbf from build_osrm.sh (needs osmium)")
    src.add_argument("--geojsonseq", help="pre-exported named features (tests)")
    ap.add_argument("--write", action="store_true",
                    help="write osm_crosscheck.json + OSM_CROSSCHECK.md into --snapshot")
    args = ap.parse_args(argv)
    with open(os.path.join(args.snapshot, "pois.json"), encoding="utf-8") as f:
        pois = json.load(f)["pois"]
    if args.pbf:
        features, meta = export_features(args.pbf)
    else:
        with open(args.geojsonseq, encoding="utf-8") as f:
            features = load_features(f)
        meta = {"pbf": os.path.basename(args.geojsonseq), "osm_timestamp": "unknown"}
    rows = crosscheck(pois, features)
    summary = summarize(pois, rows)
    meta.update({"osm_named_objects": len(features), "radius_m": RADIUS_M,
                 "name_score_min": NAME_SCORE_MIN,
                 "hours_tolerance_min": HOURS_TOLERANCE_MIN})
    print(json.dumps(summary["verified"]["fields"], ensure_ascii=False))
    print(f"all: {json.dumps(summary['all']['fields'], ensure_ascii=False)}")
    if args.write:
        doc = {"format": FORMAT, "meta": meta, "summary": summary, "pois": rows}
        with open(os.path.join(args.snapshot, "osm_crosscheck.json"), "w",
                  encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        with open(os.path.join(args.snapshot, "OSM_CROSSCHECK.md"), "w",
                  encoding="utf-8") as f:
            f.write(markdown(summary, pois, rows, meta))
        print(f"wrote osm_crosscheck.json + OSM_CROSSCHECK.md -> {args.snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
