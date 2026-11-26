"""Cross-check Google-sourced POI coordinates against OpenStreetMap (P0 data).

The danang-v2 snapshot took ~600 coordinates from Google Maps
(`provenance.location.source == "google_maps"`) and never compared them with
a second source. A wrong pin (another building, another branch, a city
centre) gives wrong motorbike minutes in `matrix.json`, hence wrong plans.

For each such POI (plus the few `manual` ones, whose note asks for the same
check) this looks for the same place in OSM and measures how far the snapshot
point is from it, to the OSM geometry (0 inside a building or park polygon,
nearest point of a beach). Two name tests, because a loose name match is good
enough to confirm a pin but far too loose to accuse one:

  confirm  (<= 100 m) folded names, generic words dropped, OSM kind not in
           conflict: "Hải Sản Đà Nẵng Bé Biển" ~ "Bé Bien" 11 m -> ok;
  accuse   (> 100 m)  the same, but tone marks must agree when both names
           have them ("Phước Tường" is not "Phước Tượng"), street / ward /
           district names and house numbers are dropped first ("PNJ Liên
           Chiểu" is just "PNJ"), and the rest must share a real word:
           within 1 km (300 m first), then the whole extract for >= 2 shared
           words (a wrong branch or a city centre is often > 1 km away).

Also, independent of OSM objects (most cafes, spas and bars are not in OSM):
the distance to the street in the POI's own name ("- 58 Ông Ích Đường") or in
its evidence notes ("54-56 Quang Trung" on a price page), which also breaks
ties between the pin and a far OSM namesake; the distance to the nearest road
the motorbike profile routes on (OSRM snaps the pin there); several POIs on
one point; a point on an OSM place node (a centroid); "Hội An" / "Bà Nà" in a
name outside that zone.

Read-only: never touches pois.json or matrix.json. Writes one CSV row per
checked POI (verdict, flags, review priority P1/P2/P3, map links) for a human
review. `--validate` runs the matcher on OSM-sourced POIs (should find their
own object); `--print-md` prints the count tables used in the summary.

Needs osmium (Homebrew `osmium-tool`) and the Geofabrik extract that
`BE/tools/osrm/build_osrm.sh` downloads, cut to the matrix bbox:

  osmium extract -b 107.85,15.72,108.55,16.3 vietnam-latest.osm.pbf -o danang.osm.pbf
  python BE/tools/coord_check_osm.py --pbf danang.osm.pbf [--validate] [--print-md]

(~8 s; the summary of the 2026-11-26 run is reports/p0/coord_check.md.)

Stdlib only (Python >= 3.9).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from BE.ml.data.osm_crosscheck import (  # noqa: E402
    GENERIC, NOT_DISTINCTIVE, core_name, distance_m, fold)

DEFAULT_POIS = os.path.join("BE", "data", "snapshots", "danang-v2", "pois.json")
DEFAULT_CSV = os.path.join("reports", "p0", "coord_check.csv")
CHECK_SOURCES = ("google_maps", "manual")
OK_M = 100.0          # matched object this close: the pin is fine
NEAR_M = 300.0        # first search ring
MID_M = 1000.0        # second ring; beyond it only >= 2 shared words count
STREET_FAR_M = 150.0  # a pin this far from the street in its own name is suspect
STREET_BAD_M = 300.0
ON_STREET_M = 60.0    # a pin / OSM object this close to the stated street agrees with it
CLUSTER_M = 75.0      # OSM objects this close are one place (node + building)
CHAIN_MIN = 3         # this many same-name places in the extract: a chain
ROAD_FAR_M = 200.0    # OSRM snaps a pin to the nearest road; this far, minutes drift
ROAD_CELL_DEG = 0.002
SAME_POINT_M = 3.0
PLACE_NODE_M = 30.0
CELL_DEG = 0.01       # ~1.1 km: the 3x3 block around a point covers >= 1 km

NAME_KEYS = ("name", "name:vi", "name:en", "alt_name", "old_name", "official_name",
             "short_name", "int_name", "loc_name", "brand")
# "tắm" (bãi tắm) and "thành" (thành phố) are kept as words here: dropping
# them made "Chùa Tam Thai" look like "Chùa Thái Sơn".
GENERIC_WORDS = GENERIC - {"tam", "thanh"}
# Kept as words but never a match on their own: the shared kind / dish /
# place lists, plus parish, supermarket ("siêu thị" read as one word, so
# "Mì Quảng Thi" keeps its name), relic, river, square / school, therapy,
# honorifics ("Bà Mua", "Bà Vị") and articles.
NOT_DIST = NOT_DISTINCTIVE | {
    "giao", "xu", "sieuthi", "di", "tich", "song", "tam", "thanh", "truong", "tri", "lieu",
    "ba", "ong", "chu", "anh", "bac", "cau", "mo", "la", "de", "des", "les", "with", "in",
    "at", "by", "for", "on", "from"}
# Da Nang place names inside NOT_DIST. Two of them can confirm a pin only when
# the OSM kind agrees: "Nhà thờ Giáo xứ An Hòa" ~ "Nhà thờ An Hòa", while
# "Sơn Trà Retreat" (hotel) is not "Sơn Trà Viewpoint".
PLACE_WORDS = {"son", "tra", "ngu", "hanh", "hai", "chau", "khe", "lien", "chieu", "cam", "le",
               "hoa", "vang", "my", "non", "nuoc", "hoi", "an", "tan", "han", "nam", "xuan",
               "thuan", "phuoc", "van"}
ADMIN_PREFIXES = ("thanh pho ", "thi xa ", "thi tran ", "phuong ", "quan ", "huyen ", "xa ",
                  "tinh ")
# A name that says it is in one of these areas, while its point is not.
AREA_WORDS = {"hoi an": "hoi_an", "hoian": "hoi_an", "ba na": "ba_na_tay", "bana": "ba_na_tay"}
# combining grave, acute, tilde, hook above, dot below
TONES = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}

# lenient levels (confirm)
EXACT, CONTAINS, CONTAINS_1, PARTIAL = 4, 3, 2, 1
LEVEL_NAME = {EXACT: "exact", CONTAINS: "contains", CONTAINS_1: "contains_1word",
              PARTIAL: "partial"}

# --- kinds of place ---------------------------------------------------------
EAT, STAY, WELL, FAITH, SIGHT, MARKET, OTHER = (
    "eat", "stay", "well", "faith", "sight", "market", "other")
AMENITY_FAM = {
    **dict.fromkeys(("restaurant", "fast_food", "food_court", "cafe", "ice_cream", "bar", "pub",
                     "nightclub", "biergarten", "karaoke_box", "hookah_lounge", "casino"), EAT),
    "marketplace": MARKET,
    **dict.fromkeys(("place_of_worship", "monastery"), FAITH),
    **dict.fromkeys(("spa", "public_bath", "massage", "sauna"), WELL),
    **dict.fromkeys(("theatre", "arts_centre", "fountain", "planetarium", "clock"), SIGHT),
}
TOURISM_FAM = {
    **dict.fromkeys(("hotel", "guest_house", "hostel", "motel", "apartment", "chalet", "resort",
                     "camp_site", "caravan_site"), STAY),
    "attraction": None,   # any kind of place can be an attraction
    "information": OTHER,
}
SHOP_FAM = {
    **dict.fromkeys(("massage", "beauty", "hairdresser", "cosmetics", "nail_salon"), WELL),
    **dict.fromkeys(("coffee", "tea", "bakery", "pastry", "confectionery", "beverages", "alcohol",
                     "wine", "deli", "seafood", "ice_cream"), EAT),
    "yes": None,
}
LEISURE_FAM = {"spa": WELL, "sauna": WELL, "fitness_centre": WELL, "resort": STAY,
               "sports_centre": OTHER, "pitch": OTHER, "track": OTHER}
FAITH_VALUES = {"temple", "church", "cathedral", "chapel", "pagoda", "shrine", "mosque",
                "monastery", "religious", "wayside_shrine"}
OTHER_KEYS = ("office", "craft", "healthcare", "public_transport", "railway", "aeroway",
              "emergency", "military", "government")
# POI category -> OSM kinds that agree with it (spas and bars often sit in hotels).
OK_FAMS = {
    "restaurant": {EAT, STAY, MARKET}, "cafe": {EAT, STAY, MARKET}, "nightlife": {EAT, STAY},
    "lodging": {STAY}, "wellness": {WELL, STAY}, "religious": {FAITH, SIGHT},
    "day_market": {MARKET, EAT}, "night_market": {MARKET, EAT, SIGHT},
    "outdoor_landmark": {SIGHT, FAITH}, "paid_attraction": {SIGHT, FAITH, STAY},
    "viewpoint": {SIGHT, FAITH}, "museum_indoor": {SIGHT, FAITH}, "beach": {SIGHT, STAY},
}
KIND_RANK = {"match": 2, "neutral": 1, "conflict": 0}
ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
         "living_street", "service", "pedestrian", "road", "motorway_link", "trunk_link",
         "primary_link", "secondary_link", "tertiary_link"}
# Highway classes BE/tools/osrm/motorbike.lua routes on (its speed table);
# access tags are ignored, so this is the nearest road OSRM could snap to.
MOTORBIKE_ROADS = ("trunk", "trunk_link", "primary", "primary_link", "secondary",
                   "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential",
                   "living_street", "service")
# Areas, not places a POI can be (they still name streets and wards).
PLACE_AREAS = {"country", "state", "province", "region", "county", "municipality", "city",
               "town", "borough", "district", "suburb", "quarter", "neighbourhood", "village",
               "hamlet", "isolated_dwelling", "plot", "city_block"}
PLACE_NODES = {"city", "town", "village", "hamlet", "suburb", "quarter", "neighbourhood",
               "district", "county", "municipality", "borough"}
NOT_PLACE_LANDUSE = {"industrial", "residential", "construction", "military", "port", "railway",
                     "farmland", "farmyard", "quarry", "landfill", "cemetery"}
# Categories named after their locality ("Nhà thờ An Hòa", "Chợ Mân Thái"):
# only these may be confirmed on place names alone.
LOCALITY_NAMED = {"religious", "outdoor_landmark", "beach", "viewpoint", "paid_attraction",
                  "museum_indoor", "day_market", "night_market"}
# Shops, food, spas, hotels: a same name far away is usually another branch.
BUSINESS = {"restaurant", "cafe", "nightlife", "wellness", "lodging"}
MAIN_TAGS = ("amenity", "tourism", "shop", "leisure", "historic", "natural", "place",
             "man_made", "waterway", "highway", "building", "landuse")


def families(tags: dict) -> set:
    """Kinds of place an OSM object's specific tags say it is (empty: no say)."""
    out = set()
    if tags.get("amenity"):
        out.add(AMENITY_FAM.get(tags["amenity"], OTHER))
    if tags.get("tourism"):
        out.add(TOURISM_FAM.get(tags["tourism"], SIGHT))
    if tags.get("shop"):
        out.add(SHOP_FAM.get(tags["shop"], MARKET))
    if tags.get("leisure"):
        out.add(LEISURE_FAM.get(tags["leisure"], SIGHT))
    if tags.get("historic"):
        out.add(FAITH if tags["historic"] in FAITH_VALUES else SIGHT)
    if tags.get("religion"):
        out.add(FAITH)
    if tags.get("building"):
        b = tags["building"]
        out.add(STAY if b == "hotel" else FAITH if b in FAITH_VALUES else None)
    if tags.get("natural") or tags.get("place") or tags.get("waterway") == "waterfall" \
            or tags.get("man_made") in ("bridge", "lighthouse", "tower", "pier") \
            or tags.get("bridge") or tags.get("highway") == "pedestrian":
        out.add(SIGHT)
    if tags.get("landuse") == "religious":
        out.add(FAITH)
    if tags.get("landuse") in NOT_PLACE_LANDUSE:
        out.add(OTHER)
    if any(k in tags for k in OTHER_KEYS):
        out.add(OTHER)
    out.discard(None)
    return out


def kind_check(category: str, fams: set) -> str:
    if not fams:
        return "neutral"
    return "match" if fams & OK_FAMS.get(category, set()) else "conflict"


def main_tag(tags: dict) -> str:
    for k in MAIN_TAGS:
        if tags.get(k):
            return f"{k}={tags[k]}"
    return ""


# --- names: lenient (confirm) -----------------------------------------------

APOSTROPHES = re.compile(r"['\u2019\u02bc`]")


def norm(text: str) -> str:
    """Folded name, apostrophes inside words ("M'healthy"), the dish spelling
    unified ("mỳ quảng" = "mì quảng")."""
    text = APOSTROPHES.sub("", str(text or ""))
    out = re.sub(r"\bmy quang\b", "mi quang", " ".join(fold(text).split()))
    return re.sub(r"\bsieu thi\b", "sieuthi", out)


def tokens(folded: str) -> tuple:
    """Distinctive words in order: generic words dropped, digits kept ("Thiên 2")."""
    out: list = []
    for t in folded.split():
        if (len(t) > 1 or t.isdigit()) and t not in GENERIC_WORDS and t not in out:
            out.append(t)
    return tuple(out)


def variant(text: str) -> tuple:
    f = norm(text)
    return tokens(f), f


def _carrier(words) -> str:
    """'strong': a distinctive word; 'place': only >= 2 Da Nang place names
    (valid when the OSM kind agrees); '': kind words only, never a match."""
    if set(words) - NOT_DIST:
        return "strong"
    return "place" if len(set(words) & PLACE_WORDS) >= 2 else ""


def _run(long_, short) -> bool:
    n = len(short)
    return any(tuple(long_[i:i + n]) == tuple(short) for i in range(len(long_) - n + 1))


def _one_edit(a: str, b: str) -> bool:
    """Damerau distance <= 1 ("Oani Spa" / "Aoni Spa")."""
    if a == b or abs(len(a) - len(b)) > 1:
        return a == b
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:] or (a[i:i + 2] == b[i:i + 2][::-1] and a[i + 2:] == b[i + 2:])
    return a[i:] == b[i + 1:] if len(b) > len(a) else a[i + 1:] == b[i:]


def pair_level(a: tuple, b: tuple) -> tuple:
    """(level, weak) for two (words, folded name) variants; weak = the match
    rests on place names only. Kind words alone never match ("Bảo tàng Đà
    Nẵng" is not "Bảo tàng Mỹ thuật Đà Nẵng")."""
    (ta, fa), (tb, fb) = a, b
    if fa and (fa == fb or fa.replace(" ", "") == fb.replace(" ", "")):
        return EXACT, False                    # "Le Vénin Spa" / "Levenin Spa"
    if not ta or not tb:
        return 0, False
    if set(ta) == set(tb):
        return EXACT, not set(ta) - NOT_DIST
    # the whole shorter name inside the longer: "Bé Bien" in "Hải Sản Đà Nẵng Bé Biển"
    wa, wb = fa.split(), fb.split()
    short_f, long_f = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if len(short_f) >= 2 and set(short_f) - GENERIC_WORDS - NOT_DIST and _run(long_f, short_f):
        return CONTAINS, False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    n = len(short)
    carrier = _carrier(short)
    one_ok = len(short[0]) >= 4 or (len(short[0]) >= 3 and any(c.isdigit() for c in short[0]))
    if carrier and (n >= 2 or one_ok) and _run(long_, short):
        return (CONTAINS if n >= 2 else CONTAINS_1), carrier == "place"
    shared = set(ta) & set(tb)
    carrier = _carrier(shared)
    # word order matters for two words and for place names ("Trà Sơn" is not
    # "Sơn Trà", "An Hội" is not "Hội An"), not for three real words: "Bảo
    # tàng 3D Art In Paradise" is "Art in Paradise Da Nang 3D Museum"
    if len(shared) >= 2 and carrier and len(shared) / n >= 0.6 \
            and ((len(shared) >= 3 and carrier == "strong") or shared == set(short)
                 or [t for t in ta if t in shared] == [t for t in tb if t in shared]):
        return PARTIAL, carrier == "place"
    ca, cb = fa.replace(" ", ""), fb.replace(" ", "")
    if min(len(ca), len(cb)) >= 7 and _one_edit(ca, cb):
        return PARTIAL, False
    return 0, False


def name_level(mine: list, theirs: list) -> tuple:
    best = (0, False)
    for a in mine:
        for b in theirs:
            level, weak = pair_level(a, b)
            if (level, not weak) > (best[0], not best[1]):
                best = (level, weak)
            if best == (EXACT, False):
                return best
    return best


def name_texts(texts) -> list:
    out = []
    for t in texts:
        if t:
            out += [t, core_name(t)]
    return list(dict.fromkeys(out))


def poi_texts(poi: dict) -> list:
    return name_texts((poi.get("name"), poi.get("name_raw"), poi.get("name_en")))


def poi_core_texts(poi: dict) -> list:
    """Names without the address / branch tail: only these can accuse
    ("Coffee Trà, 51 Lý Đạo Thành, Mân Thái" is not "Chợ Mân Thái")."""
    return list(dict.fromkeys(core_name(t) for t in (poi.get("name"), poi.get("name_raw"),
                                                     poi.get("name_en")) if t))


def variants(texts: list) -> list:
    out = []
    for t in texts:
        v = variant(t)
        if (v[0] or v[1]) and v not in out:
            out.append(v)
    return out


# --- names: strict (accuse) ---------------------------------------------------

def accent_key(word: str) -> str:
    """Word with its tone mark set apart, so "hoà" == "hòa", "thuỷ" == "thủy"."""
    d = unicodedata.normalize("NFD", word)
    tone = "".join(c for c in d if c in TONES)
    return unicodedata.normalize("NFC", "".join(c for c in d if c not in TONES)) + "|" + tone


def words_acc(text: str) -> list:
    """[(folded, accent key, plain ascii)] for each word of a name."""
    text = APOSTROPHES.sub("", unicodedata.normalize("NFC", str(text or "").lower()))
    raw = re.sub(r"[^\w]|_", " ", text).split()
    out = []
    for w in raw:
        f = fold(w).split()
        if len(f) == 1:
            out.append((f[0], accent_key(w), w.isascii()))
        else:   # odd characters: no tone check for the pieces
            out += [(x, x, True) for x in f]
    for i in range(len(out) - 1):
        if out[i][0] == "my" and out[i + 1][0] == "quang":
            out[i] = ("mi", accent_key("mì"), False)
    for i in range(len(out) - 2, -1, -1):
        if out[i][0] == "sieu" and out[i + 1][0] == "thi":
            out[i:i + 2] = [("sieuthi", "sieuthi", True)]
    return out


def same_word(x: tuple, y: tuple) -> bool:
    return x[0] == y[0] and (x[2] or y[2] or x[1] == y[1])


def strict_form(text: str, location: set) -> tuple:
    """(identity words, all words, full words) of a name for the strict test:
    street / ward / district runs and the house number before a street are
    dropped, generic words dropped; identity = what is left that is not a
    kind word, place word, honorific or number."""
    full = words_acc(text)
    drop = [False] * len(full)
    i = 0
    while i < len(full):
        step = 1
        for n in range(min(6, len(full) - i), 1, -1):
            if " ".join(w[0] for w in full[i:i + n]) in location:
                for j in range(i, i + n):
                    drop[j] = True
                if i > 0 and full[i - 1][0].isdigit():
                    drop[i - 1] = True
                step = n
                break
        i += step
    kept: list = []
    for w, d in zip(full, drop):
        if d or w[0] in GENERIC_WORDS or (len(w[0]) < 2 and not w[0].isdigit()):
            continue
        if not any(same_word(w, k) for k in kept):
            kept.append(w)
    ident = [w for w in kept if w[0] not in NOT_DIST and not w[0].isdigit()]
    return ident, kept, full


def _runs_in(long_: list, short: list) -> bool:
    n = len(short)
    return any(all(same_word(long_[i + k], short[k]) for k in range(n))
               for i in range(len(long_) - n + 1))


def strict_pair(a: tuple, b: tuple) -> tuple:
    """(level, shared identity words) for two strict forms. EXACT: same word
    set; CONTAINS: the shorter (>= 2 words) runs inside the longer; with no
    identity word on one side, the full names must be equal (shared = 0)."""
    (ia, ka, fa), (ib, kb, fb) = a, b
    if not ia or not ib:
        # "Nhà thờ An Hòa", "Bãi biển Mỹ Khê"; never "Nhà hàng hải sản", "D.coffee"
        if len(ka) >= 2 and len(kb) >= 2 and len(fa) == len(fb) \
                and all(same_word(x, y) for x, y in zip(fa, fb)):
            return EXACT, 0
        return 0, 0
    shared = [w for w in ia if any(same_word(w, v) for v in ib)]
    if not shared:
        return 0, 0
    if len(ka) == len(kb) and all(any(same_word(w, v) for v in kb) for w in ka) \
            and all(any(same_word(v, w) for w in ka) for v in kb):
        return EXACT, len(shared)
    short, long_ = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    if len(short) >= 2 and _runs_in(long_, short):
        return CONTAINS, len(shared)
    return 0, 0


def strict_level(mine: list, theirs: list) -> tuple:
    best = (0, 0)
    for a in mine:
        for b in theirs:
            r = strict_pair(a, b)
            if r > best:
                best = r
    return best


def accusable(level: int, shared: int, kind: str, ident: list, far: bool) -> bool:
    """Is a strict match good enough to say the pin is elsewhere?"""
    if level < CONTAINS or kind == "conflict" or (level == CONTAINS and kind != "match"):
        return False
    if shared == 0:                       # equal full names of kind/place words
        return kind == "match"
    if far:                               # "New World Spa" is not "New World Hoiana Hotel"
        return level == EXACT and shared >= 2 and kind == "match"
    return shared >= 2 or (len(ident) == 1 and len(ident[0][0]) >= 4)


# --- geometry ---------------------------------------------------------------

def _rings(geometry: dict) -> list:
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    if kind == "Point":
        return [[coords]]
    if kind == "LineString":
        return [coords]
    if kind in ("MultiLineString", "Polygon"):
        return list(coords)
    if kind == "MultiPolygon":
        return [r for poly in coords for r in poly]
    return []


def bbox(geometry: dict) -> tuple:
    pts = [c for ring in _rings(geometry) for c in ring]
    return (min(c[1] for c in pts), min(c[0] for c in pts),
            max(c[1] for c in pts), max(c[0] for c in pts))


def rep_point(geometry: dict, lat: float, lon: float) -> tuple:
    """(lat, lon) to show for an OSM object: the node, the mean of a polygon's
    largest outer ring, or the point of a line nearest to (lat, lon)."""
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    if kind == "Point":
        return coords[1], coords[0]
    if kind in ("Polygon", "MultiPolygon"):
        polys = [coords] if kind == "Polygon" else coords
        ring = max((p[0] for p in polys), key=len)
        pts = ring[:-1] or ring
        return (sum(c[1] for c in pts) / len(pts), sum(c[0] for c in pts) / len(pts))
    kx = 111320.0 * math.cos(math.radians(lat))
    best, out = math.inf, (lat, lon)
    px, py = lon * kx, lat * 110540.0
    for line in _rings(geometry):
        for (x1, y1), (x2, y2) in zip(line, line[1:] or line):
            ax, ay, bx, by = x1 * kx, y1 * 110540.0, x2 * kx, y2 * 110540.0
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy)
                                                       / (dx * dx + dy * dy)))
            d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d < best:
                best, out = d, (y1 + t * (y2 - y1), x1 + t * (x2 - x1))
    return out


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + \
        math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


def cells(box: tuple):
    la0, lo0, la1, lo1 = box
    for gy in range(math.floor(la0 / CELL_DEG), math.floor(la1 / CELL_DEG) + 1):
        for gx in range(math.floor(lo0 / CELL_DEG), math.floor(lo1 / CELL_DEG) + 1):
            yield gy, gx


# --- OSM --------------------------------------------------------------------

def export_osm(pbf: str, workdir: str) -> tuple:
    """(named objects, motorbike roads) of the extract as GeoJSON lines (osmium)."""
    out = []
    for name, filters in (("named", ["nwr/name", "nwr/name:vi", "nwr/name:en", "nwr/brand"]),
                          ("roads", ["w/highway=" + ",".join(MOTORBIKE_ROADS)])):
        part = os.path.join(workdir, name + ".osm.pbf")
        lines = os.path.join(workdir, name + ".geojsonseq")
        subprocess.run(["osmium", "tags-filter", pbf, *filters, "-o", part, "--overwrite"],
                       check=True)
        subprocess.run(["osmium", "export", part, "-f", "geojsonseq", "--add-unique-id=type_id",
                        "-o", lines, "--overwrite"], check=True)
        out.append(lines)
    return tuple(out)


def load_roads(geojsonseq: str) -> dict:
    """Road segments in a grid of ROAD_CELL_DEG cells, as (lon1, lat1, lon2, lat2)."""
    grid = defaultdict(list)
    with open(geojsonseq, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            geom = json.loads(line).get("geometry") or {}
            for ring in _rings(geom):
                for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                    for gy in range(math.floor(min(y1, y2) / ROAD_CELL_DEG),
                                    math.floor(max(y1, y2) / ROAD_CELL_DEG) + 1):
                        for gx in range(math.floor(min(x1, x2) / ROAD_CELL_DEG),
                                        math.floor(max(x1, x2) / ROAD_CELL_DEG) + 1):
                            grid[(gy, gx)].append((x1, y1, x2, y2))
    return grid


def road_distance(lat: float, lon: float, roads: dict, max_ring: int = 6) -> float:
    """Metres to the nearest motorbike road (inf beyond ~max_ring cells)."""
    kx, ky = 111320.0 * math.cos(math.radians(lat)), 110540.0
    px, py = lon * kx, lat * ky
    gy, gx = math.floor(lat / ROAD_CELL_DEG), math.floor(lon / ROAD_CELL_DEG)
    best, seen = math.inf, set()
    for r in range(max_ring + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dy), abs(dx)) != r:
                    continue
                for seg in roads.get((gy + dy, gx + dx), ()):
                    if seg in seen:
                        continue
                    seen.add(seg)
                    ax, ay, bx, by = seg[0] * kx, seg[1] * ky, seg[2] * kx, seg[3] * ky
                    vx, vy = bx - ax, by - ay
                    t = 0.0 if vx == vy == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy)
                                                               / (vx * vx + vy * vy)))
                    best = min(best, math.hypot(px - ax - t * vx, py - ay - t * vy))
        if best <= r * ROAD_CELL_DEG * min(kx, ky):   # a farther ring cannot be closer
            break
    return best


def osm_ref(fid: str) -> str:
    """osmium unique id ("n12", "w34", "a69") -> "node/12" | "way/34" | "relation/34".
    Areas: even ids come from ways (2*id), odd ids from relations (2*id+1)."""
    kind, num = fid[:1], int(fid[1:])
    if kind == "n":
        return f"node/{num}"
    if kind == "w":
        return f"way/{num}"
    return f"way/{num // 2}" if num % 2 == 0 else f"relation/{num // 2}"


def street_key(name: str) -> str:
    f = norm(name)
    for prefix in ("duong ", "pho "):
        if f.startswith(prefix):
            f = f[len(prefix):]
    return f if len(f.split()) >= 2 else ""


def area_key(name: str) -> str:
    f = norm(name)
    for prefix in ADMIN_PREFIXES:
        if f.startswith(prefix):
            f = f[len(prefix):]
    return f if len(f.split()) >= 2 else ""


def load_osm(geojsonseq: str) -> dict:
    raw, streets, place_nodes, location = [], defaultdict(list), [], set()
    with open(geojsonseq, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            feat = json.loads(line)
            tags = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            if not geom.get("coordinates"):
                continue
            names = [p.strip() for k in NAME_KEYS if tags.get(k)
                     for p in str(tags[k]).split(";") if p.strip()]
            if not names:
                continue
            hw = tags.get("highway")
            if hw and geom["type"] in ("LineString", "MultiLineString") and hw in ROADS:
                for n in names:
                    key = street_key(n)
                    if key:
                        streets[key].append(geom)
                        location.add(key)
            if tags.get("boundary") == "administrative" or tags.get("place"):
                location.update(k for k in map(area_key, names) if k)
            if tags.get("place") in PLACE_NODES and geom["type"] == "Point":
                place_nodes.append((names[0], geom["coordinates"][1], geom["coordinates"][0]))
            if hw and not (tags.get("bridge") or tags.get("man_made") == "bridge"
                           or hw == "pedestrian"):
                continue   # streets, bus stops ("Chùa Linh Ứng" stop) are not the place
            if tags.get("boundary") or tags.get("leisure") == "nature_reserve":
                continue   # wards, and reserves that cover a whole peninsula
            if tags.get("place") in PLACE_AREAS or tags.get("waterway") not in (None, "waterfall") \
                    or any(k in tags for k in ("railway", "power", "route")):
                continue
            raw.append((feat.get("id") or "", names, tags, geom))
    places, grid, index = [], defaultdict(list), defaultdict(set)
    for fid, names, tags, geom in raw:
        texts = name_texts(names)
        f = {"id": fid, "names": names, "tags": tags, "geometry": geom, "bbox": bbox(geom),
             "fams": families(tags), "variants": variants(texts),
             "strict": [strict_form(t, location) for t in texts]}
        i = len(places)
        places.append(f)
        for c in cells(f["bbox"]):
            grid[c].append(i)
        for ident, _, full in f["strict"]:
            for w in ident:
                index[w[0]].add(i)
            if not ident and full:
                index["=" + " ".join(w[0] for w in full)].add(i)
    return {"places": places, "grid": grid, "index": index, "streets": dict(streets),
            "place_nodes": place_nodes, "location": location}


# --- addresses in names -------------------------------------------------------

def street_in_name(poi: dict, streets: dict):
    """(street key, how) for an address in the name: a house number followed by
    a known street ("- 58 Ông Ích Đường", "cơ sở 2 462 Điện Biên Phủ") -> number;
    else a bare known street right after the first separator -> tail."""
    keys = streets.keys()

    def street_at(words: list):
        for n in range(min(6, len(words)), 1, -1):
            k = " ".join(words[:n])
            if k in keys:
                return k
        return None

    tails = []
    for text in (poi.get("name"), poi.get("name_raw")):
        if not text:
            continue
        parts = re.split(r"\s[-–|/]\s|[,|()]", text)
        for part in parts:
            words = norm(part).split()
            for i, w in enumerate(words):
                if re.fullmatch(r"[1-9]\d*[a-z]?", w) and i + 1 < len(words):
                    nxt = words[i + 1:]
                    if nxt and nxt[0] in ("duong", "pho"):
                        nxt = nxt[1:]
                    k = street_at(nxt)
                    if k:
                        return k, "number"
        if len(parts) > 1:
            words = norm(parts[1]).split()
            if words and words[0] in ("duong", "pho"):
                words = words[1:]
            k = street_at(words)
            if k and len(words) <= len(k.split()) + 1:
                tails.append(k)
    return (tails[0], "tail") if tails else (None, None)


def streets_in_notes(poi: dict, streets: dict) -> list:
    """Streets after a house number in the POI's own evidence notes (price /
    hours pages: "Mục cơ sở 54–56 Quang Trung", "95 Đỗ Bá, P. Mỹ An")."""
    keys, found = streets.keys(), []
    for group in (poi.get("provenance") or {}).values():
        for part in re.split(r"[,;|()\"]", str((group or {}).get("note") or "")):
            words = norm(part).split()
            for i, w in enumerate(words):
                if not re.fullmatch(r"[1-9]\d*[a-z]?", w):
                    continue
                nxt = words[i + 1:]
                if nxt and nxt[0] in ("duong", "pho"):
                    nxt = nxt[1:]
                for n in range(min(6, len(nxt)), 1, -1):
                    k = " ".join(nxt[:n])
                    if k in keys:
                        found.append(k)
                        break
    return list(dict.fromkeys(found))


def street_distance(lat: float, lon: float, geoms: list) -> float:
    return min(distance_m(lat, lon, g) for g in geoms)


# --- matching -----------------------------------------------------------------

def nearby(lat: float, lon: float, osm: dict):
    gy, gx = math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG)
    seen = set()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for i in osm["grid"].get((gy + dy, gx + dx), ()):
                if i not in seen:
                    seen.add(i)
                    yield i


def confirm_candidates(poi: dict, mine: list, osm: dict) -> list:
    """Lenient name matches within 1 km: (level, kind, dist, idx)."""
    out = []
    for i in nearby(poi["lat"], poi["lon"], osm):
        f = osm["places"][i]
        level, weak = name_level(mine, f["variants"])
        if not level:
            continue
        kind = kind_check(poi["category"], f["fams"])
        if kind == "conflict" and (level < EXACT or len(_words(mine, f["variants"])) < 2):
            continue   # "Holiday Beach Hotel" is not the "Holiday Coffee" next door
        if weak and (kind != "match"
                     or (level == PARTIAL and poi["category"] not in LOCALITY_NAMED)):
            continue   # "Lẩu Nấm ... Liên Chiểu" is not "PNJ Liên Chiểu"
        d = distance_m(poi["lat"], poi["lon"], f["geometry"])
        if d <= MID_M:
            out.append((level, kind, d, i))
    return out


def _words(mine: list, theirs: list) -> tuple:
    """Words of the longest exactly-equal variant pair (for the conflict test)."""
    best: tuple = ()
    for a in mine:
        for b in theirs:
            if a[0] and set(a[0]) == set(b[0]) and len(a[0]) > len(best):
                best = a[0]
    return best


def accuse_candidates(poi: dict, strict: list, osm: dict) -> tuple:
    """Strict name matches anywhere in the extract (word index):
    (accusable ones as (level, kind, dist, idx, shared), all strict ones)."""
    pool = set()
    for ident, _, full in strict:
        keys = [w[0] for w in ident] or (["=" + " ".join(w[0] for w in full)] if full else [])
        if keys:
            pool |= min((osm["index"].get(k, set()) for k in keys), key=len)
    ident = max((s[0] for s in strict), key=len, default=[])
    good, every = [], []
    for i in pool:
        f = osm["places"][i]
        level, shared = strict_level(strict, f["strict"])
        if level < CONTAINS:
            continue
        kind = kind_check(poi["category"], f["fams"])
        if kind == "conflict":
            continue
        d = distance_m(poi["lat"], poi["lon"], f["geometry"])
        c = (level, kind, d, i, shared)
        every.append(c)
        if accusable(level, shared, kind, ident, far=d > MID_M):
            good.append(c)
    return good, every


def clusters(cands: list, osm: dict, poi: dict) -> list:
    """Group candidates whose shown points are within CLUSTER_M (one place
    mapped as a node and a building); returns the best candidate per group."""
    groups: list = []
    for c in sorted(cands, key=lambda c: (-c[0], -KIND_RANK[c[1]], c[2])):
        pt = rep_point(osm["places"][c[3]]["geometry"], poi["lat"], poi["lon"])
        for g in groups:
            if haversine_m(pt[0], pt[1], g[1][0], g[1][1]) <= CLUSTER_M:
                break
        else:
            groups.append((c, pt))
    return [g[0] for g in groups]


def rank(c: tuple) -> tuple:
    return (c[0], KIND_RANK[c[1]], -c[2])


def fmt_m(d: float) -> str:
    return f"{d / 1000:.1f} km" if d >= 1000 else f"{d:.0f} m"


def describe(f: dict) -> str:
    return f"'{f['names'][0]}' ({main_tag(f['tags']) or 'không có thẻ loại'})"


def check_poi(poi: dict, osm: dict, all_pois: list) -> dict:
    lat, lon = poi["lat"], poi["lon"]
    texts = poi_texts(poi)
    confirm = confirm_candidates(poi, variants(texts), osm)
    strict = [strict_form(t, osm["location"]) for t in poi_core_texts(poi)]
    accuse, every = accuse_candidates(poi, strict, osm)
    same_name = clusters(every, osm, poi)
    chain = len(same_name) >= CHAIN_MIN
    near_groups = clusters(confirm, osm, poi)
    flags, why = [], []
    best, tier, how, shared = None, "", "", ""
    ok = [c for c in confirm if c[2] <= OK_M]
    if ok:
        best, tier, how = max(ok, key=rank), "100m", "confirm"
    else:
        for limit, name in ((NEAR_M, "300m"), (MID_M, "1km"), (math.inf, "far")):
            ring = [c for c in accuse if c[2] <= limit]
            if ring:
                pick = max(ring, key=rank)
                best, tier, how, shared = pick[:4], name, "accuse", pick[4]
                break
    row = {"tier": tier, "osm_ref": "", "osm_name": "", "osm_kind": "", "name_match": "",
           "shared_words": shared, "kind_check": "", "dist_m": "", "osm_lat": "", "osm_lon": "",
           "places_1km": len(near_groups), "same_name_places": len(same_name)}
    if best:
        level, kind, d, i = best
        f = osm["places"][i]
        olat, olon = rep_point(f["geometry"], lat, lon)
        row.update(osm_ref=osm_ref(f["id"]), osm_name=f["names"][0], osm_kind=main_tag(f["tags"]),
                   name_match=(LEVEL_NAME[level] if how == "confirm" else
                               "strict_" + LEVEL_NAME[level]),
                   kind_check=kind, dist_m=round(d), osm_lat=round(olat, 7),
                   osm_lon=round(olon, 7), _fid=f["id"])
        if how == "confirm":
            verdict = "ok"
            far_better = [c for c in accuse if c[0] == EXACT and c[2] > NEAR_M and c[3] != i]
            if level < CONTAINS and far_better:
                flags.append("better_name_farther")
                g = osm["places"][max(far_better, key=rank)[3]]
                why.append(f"tên trùng hẳn {describe(g)} ở xa hơn")
        elif chain or "brand" in f["tags"] or "brand:wikidata" in f["tags"]:
            chain = True
            verdict = "ambiguous"
            flags.append("chain")
        elif tier == "far" and poi["category"] in BUSINESS:
            verdict = "ambiguous"     # one other shop of that name: a branch or a namesake
            flags.append("far_namesake")
            why.append("quán/khách sạn cùng tên ở xa thường là chi nhánh khác")
        else:
            verdict = "check" if d <= NEAR_M else "off"
        if kind == "conflict":
            flags.append("kind_conflict")
        if verdict != "ok" and len(near_groups) >= 2:
            flags.append("several_places_1km")
        why.insert(0, f"OSM {describe(f)} cách {fmt_m(d)}, tên {row['name_match']}")
        if chain:
            why.append(f"chuỗi/chi nhánh: {len(same_name)} nơi cùng tên trong OSM"
                       + (", OSM gắn thẻ brand" if "brand" in f["tags"] else ""))
    else:
        verdict = "no_osm"
        why.append("không thấy trong OSM")
        if confirm:
            h = min(confirm, key=lambda c: c[2])
            why.append(f"gần nhất có tên na ná {describe(osm['places'][h[3]])} "
                       f"cách {fmt_m(h[2])}")
    street, street_how = street_in_name(poi, osm["streets"])
    row["street"], row["street_dist_m"] = "", ""
    if street:
        sd = street_distance(lat, lon, osm["streets"][street])
        row["street"], row["street_dist_m"] = f"{street} ({street_how})", round(sd)
        if sd > STREET_FAR_M:
            flags.append("street_far")
            why.append(f"cách đường '{street}' ghi trong tên {fmt_m(sd)}")
    row["note_street"], row["note_street_dist_m"] = "", ""
    noted = streets_in_notes(poi, osm["streets"])
    if noted:
        nd, nk = min((street_distance(lat, lon, osm["streets"][k]), k) for k in noted)
        row["note_street"], row["note_street_dist_m"] = " | ".join(noted), round(nd)
        if nd > STREET_FAR_M:
            flags.append("note_street_far")
            why.append(f"cách đường '{nk}' trong ghi chú nguồn (giá/giờ) {fmt_m(nd)}")
    # tie-break with the POI's own address: Gyu Sachi's note says "54-56 Quang
    # Trung", the pin is 8 m from Quang Trung, OSM's Gyu Sachi is elsewhere
    stated = ([street] if street else []) + noted
    if stated and best and verdict in ("check", "off", "ambiguous"):
        pin_d = min(street_distance(lat, lon, osm["streets"][k]) for k in stated)
        osm_d = min(street_distance(row["osm_lat"], row["osm_lon"], osm["streets"][k])
                    for k in stated)
        if pin_d <= ON_STREET_M and osm_d > STREET_FAR_M:
            flags.append("address_backs_pin")
            why.append(f"địa chỉ của POI khớp ghim ({fmt_m(pin_d)} tới đường), "
                       f"không khớp đối tượng OSM ({fmt_m(osm_d)}): OSM là nơi khác/chi nhánh khác")
        elif osm_d <= ON_STREET_M and pin_d > STREET_FAR_M:
            flags.append("address_backs_osm")
            why.append(f"địa chỉ của POI khớp đối tượng OSM ({fmt_m(osm_d)} tới đường), "
                       f"không khớp ghim ({fmt_m(pin_d)})")
    rd = road_distance(lat, lon, osm["roads"])
    row["road_dist_m"] = round(rd) if rd < math.inf else ""
    if rd > ROAD_FAR_M:
        flags.append("far_from_road")
        why.append("cách đường xe máy gần nhất "
                   + (fmt_m(rd) if rd < math.inf else "hơn 1 km"))
    same = [q for q in all_pois if q is not poi and q["status"] != "excluded"
            and abs(q["lat"] - lat) < 1e-4 and abs(q["lon"] - lon) < 1e-4
            and haversine_m(lat, lon, q["lat"], q["lon"]) <= SAME_POINT_M
            and norm(q["name"]) != norm(poi["name"])]
    row["same_point_as"] = " | ".join(q["name"] for q in same)
    if same:
        # two hotels on one point: one pin is a guess; a tour put on its pier is not
        flags.append("same_point_same_kind" if any(q["category"] == poi["category"]
                                                   for q in same) else "same_point")
        why.append(f"trùng toạ độ với {len(same)} POI khác")
    pn = [(n, haversine_m(lat, lon, la, lo)) for n, la, lo in osm["place_nodes"]
          if abs(la - lat) < 0.001 and abs(lo - lon) < 0.001]
    pn = [x for x in pn if x[1] <= PLACE_NODE_M]
    row["near_place_node"] = min(pn, key=lambda x: x[1])[0] if pn else ""
    if pn:
        flags.append("on_place_node")
        why.append(f"nằm ngay tâm địa danh OSM '{row['near_place_node']}'")
    named_zone = next((z for w, z in AREA_WORDS.items()
                       if re.search(rf"\b{w}\b", norm(poi["name"]))), None)
    if named_zone and named_zone != poi["zone"]:
        flags.append("area_name_elsewhere")
        why.append(f"tên nói vùng {named_zone} nhưng điểm ở {poi['zone']}")
    row.update(verdict=verdict, flags=" ".join(flags), why="; ".join(why))
    row["review"] = review_priority(poi, row)
    return row


def review_priority(poi: dict, row: dict) -> str:
    """P1 very likely wrong; P2 worth a look; P3 not verifiable in OSM."""
    if poi["status"] == "excluded":
        return ""
    v, flags = row["verdict"], row["flags"].split()
    sd = max(row["street_dist_m"] or 0, row["note_street_dist_m"] or 0)
    if v == "ok":
        # OSM already confirms the place (a citadel 191 m deep behind "24 Trần Phú"):
        # only a clear street conflict is worth a look
        return "P2" if sd > STREET_BAD_M or "far_from_road" in flags \
            or "better_name_farther" in flags or "same_point_same_kind" in flags else ""
    # beyond 1 km on equal kind/place words alone ("Nhà thờ An Hòa"): could be a namesake;
    # a shop 300 m-1 km from a one-word namesake ("Hideout"): could be a move
    weak_off = (row["tier"] == "far" and row["shared_words"] == 0) or \
        (poi["category"] in BUSINESS and row["shared_words"] == 1)
    if "address_backs_pin" in flags:
        return ""
    if (v == "off" and not weak_off) or sd > STREET_BAD_M or "on_place_node" in flags \
            or "address_backs_osm" in flags:
        return "P1"
    if v in ("check", "off") or sd > STREET_FAR_M or "area_name_elsewhere" in flags \
            or "better_name_farther" in flags or "same_point" in flags \
            or "same_point_same_kind" in flags or "far_from_road" in flags \
            or (v == "ambiguous" and (poi["role"] == "attraction" or "far_namesake" in flags)):
        return "P2"
    if v == "no_osm" and poi["role"] == "attraction":
        return "P3"
    return ""


def links(poi: dict, row: dict) -> dict:
    lat, lon = round(poi["lat"], 6), round(poi["lon"], 6)
    out = {"map_point": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}",
           "map_osm": f"https://www.openstreetmap.org/{row['osm_ref']}" if row["osm_ref"] else "",
           "map_google": "", "map_both": ""}
    pid = (poi.get("ext_ids") or {}).get("google_place_id")
    if pid:
        out["map_google"] = f"https://www.google.com/maps/place/?q=place_id:{pid}"
    if row["osm_lat"] != "":
        out["map_both"] = ("https://www.openstreetmap.org/directions?route="
                           f"{lat}%2C{lon}%3B{round(row['osm_lat'], 6)}%2C{round(row['osm_lon'], 6)}")
    return out


COLUMNS = ["poi_id", "name", "status", "category", "zone", "role", "loc_source", "lat", "lon",
           "verdict", "review", "flags", "why", "tier", "osm_ref", "osm_name", "osm_kind",
           "name_match", "shared_words", "kind_check", "dist_m", "osm_lat", "osm_lon", "places_1km",
           "same_name_places", "street", "street_dist_m", "note_street", "note_street_dist_m",
           "road_dist_m", "same_point_as", "near_place_node",
           "prev_osm_link", "prev_link_same", "map_point", "map_osm", "map_google", "map_both"]


def ref_of_ext(ext: str) -> set:
    """ext_ids.osm ("node/1", "way/2", "osm:node/3") -> osmium ids it can be."""
    kind, num = ext.replace("osm:", "").split("/")
    num = int(num)
    return {"node": {f"n{num}"}, "way": {f"w{num}", f"a{2 * num}"},
            "relation": {f"a{2 * num + 1}"}}.get(kind, set())


def load_pois(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["pois"]


def run(pois: list, osm: dict) -> list:
    rows = []
    for poi in pois:
        src = poi["provenance"]["location"]["source"]
        if src not in CHECK_SOURCES:
            continue
        row = check_poi(poi, osm, pois)
        prev = (poi.get("ext_ids") or {}).get("osm") or ""
        fid = row.pop("_fid", "")
        row["prev_osm_link"] = prev
        row["prev_link_same"] = (fid in ref_of_ext(prev)) if prev else ""
        row.update(poi_id=poi["poi_id"], name=poi["name"], status=poi["status"],
                   category=poi["category"], zone=poi["zone"], role=poi["role"],
                   loc_source=src, lat=poi["lat"], lon=poi["lon"])
        row.update(links(poi, row))
        rows.append(row)
    return rows


def validate(pois: list, osm: dict) -> Counter:
    """Matcher check on POIs whose coordinates came FROM OSM: the best match
    should be their own object at ~0 m (names there are OSM's own, so this is
    an upper bound on recall, not a precision test)."""
    out = Counter()
    for poi in pois:
        ext = (poi.get("ext_ids") or {}).get("osm")
        if poi["provenance"]["location"]["source"] != "osm" or not ext or poi["status"] != "active":
            continue
        row = check_poi(poi, osm, pois)
        out["n"] += 1
        if row.get("_fid", "") in ref_of_ext(ext):
            out["own_object"] += 1
        else:
            out[row["verdict"] + ("_other_object" if row["osm_ref"] else "")] += 1
    return out


def write_csv(rows: list, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    order = {"P1": 0, "P2": 1, "P3": 2, "": 3}
    rows = sorted(rows, key=lambda r: (order[r["review"]], r["status"] != "active",
                                       -(r["dist_m"] if r["dist_m"] != "" else -1), r["poi_id"]))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})


def print_md(rows: list) -> None:
    """Markdown tables for the hand-written summary (active POIs only)."""
    act = [r for r in rows if r["status"] == "active"]
    verdicts = ["ok", "check", "off", "ambiguous", "no_osm"]
    for key in ("zone", "category"):
        tab = defaultdict(Counter)
        for r in act:
            tab[r[key]][r["verdict"]] += 1
            tab[r[key]][r["review"] or "-"] += 1
        print(f"\n| {key} | " + " | ".join(verdicts) + " | P1 | P2 | P3 | tổng |")
        print("|---" * (len(verdicts) + 5) + "|")
        for k in sorted(tab, key=lambda k: -sum(tab[k][v] for v in verdicts)):
            print(f"| {k} | " + " | ".join(str(tab[k][v]) for v in verdicts)
                  + f" | {tab[k]['P1']} | {tab[k]['P2']} | {tab[k]['P3']}"
                  + f" | {sum(tab[k][v] for v in verdicts)} |")
        tot = Counter(r["verdict"] for r in act)
        rev = Counter(r["review"] for r in act)
        print("| **tổng** | " + " | ".join(f"**{tot[v]}**" for v in verdicts)
              + f" | **{rev['P1']}** | **{rev['P2']}** | **{rev['P3']}** | **{len(act)}** |")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pois", default=DEFAULT_POIS)
    ap.add_argument("--pbf", required=True, help="OSM extract (.osm.pbf) covering the snapshot")
    ap.add_argument("--keep-osm", help="keep the osmium exports in this folder")
    ap.add_argument("--out", default=DEFAULT_CSV)
    ap.add_argument("--validate", action="store_true",
                    help="also match OSM-sourced POIs and report how often the own object wins")
    ap.add_argument("--print-md", action="store_true", help="print summary tables")
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = a.keep_osm or tmp
        os.makedirs(workdir, exist_ok=True)
        named, roads = export_osm(a.pbf, workdir)
        osm = load_osm(named)
        osm["roads"] = load_roads(roads)
    print(f"OSM: {len(osm['places'])} named places, {len(osm['streets'])} named streets, "
          f"{len(osm['location'])} street/area names, {len(osm['place_nodes'])} place nodes")
    pois = load_pois(a.pois)
    rows = run(pois, osm)
    write_csv(rows, a.out)
    act = [r for r in rows if r["status"] == "active"]
    print(f"checked {len(rows)} POIs ({len(act)} active) -> {a.out}")
    print("verdict (active):", dict(Counter(r["verdict"] for r in act).most_common()))
    print("review (active):", dict(Counter(r["review"] or "-" for r in act).most_common()))
    print("source x verdict (active):",
          dict(Counter((r["loc_source"], r["verdict"]) for r in act).most_common()))
    prev = [r for r in act if r["prev_osm_link"]]
    print(f"earlier osm_match link = this match: {sum(r['prev_link_same'] is True for r in prev)}"
          f"/{len(prev)}")
    if a.validate:
        print("validation on OSM-sourced active POIs:", dict(validate(pois, osm)))
    if a.print_md:
        print_md(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
