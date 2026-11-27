"""Pure rules for the `danang-v2` snapshot (P0 data clean-up).

Everything here is deterministic and stdlib-only so it can be unit-tested
and re-run offline. The migration script (`migrate_v2.py`) wires these
rules to the v1 snapshot; nothing in this module reads files.

Vocabularies (see TRAVELAGENT_CONTEXT.md, section 7):

- 12 trip categories + `lodging` (role `base`, never a candidate).
- roles: attraction, meal, rest, nightlife, wellness, base.
- 6 zones.
- hour archetypes (`ARCHETYPES`) = ESTIMATES that a human must review;
  every value derived from them carries `verified_by = "inferred"`.
- 4 price bands per person (VND): re < 50k, vua 50-150k, kha 150-400k,
  cao > 400k.  `LEGACY_BAND` maps them onto the 3-level band the current
  app reads (`smart_tags.price_band`: cheap <100k, medium <=500k, expensive).

Nothing here invents facts about a specific POI: a rule either reads the
POI's own fields or assigns a *category-level* estimate that is labelled
as such.
"""

from __future__ import annotations

import math
import re
import unicodedata

# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------


CITY_WORDS = re.compile(r"\b(tp|thanh pho|da nang|danang|hoi an|hoian|viet nam|vietnam|quang nam)\b")


def name_key(text: str | None) -> str:
    """fold() without city words: "La Bonne Café Đà Nẵng" vs "Làng Bích họa
    Đà Nẵng" must not look alike just because both end in the city name."""
    return re.sub(r"\s+", " ", CITY_WORDS.sub(" ", fold(text))).strip()


def fold(text: str | None) -> str:
    """Lower-case, strip Vietnamese diacritics, collapse spaces."""
    t = (text or "").replace("đ", "d").replace("Đ", "D")
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = re.sub(r"[^0-9a-zA-Z]+", " ", t).lower()
    return re.sub(r"\s+", " ", t).strip()


def raw_words(text: str | None) -> str:
    """Lower-case original (diacritics kept), punctuation -> spaces."""
    t = unicodedata.normalize("NFC", (text or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", t)).strip()


def _has(text: str, keys, raw: str | None = None) -> str | None:
    """First key found as a whole-word phrase. ASCII keys match the folded
    text; keys with diacritics match `raw` (lower-cased original)."""
    padded = f" {text} "
    rpad = f" {raw} " if raw is not None else None
    for k in keys:
        if k.startswith("="):
            if rpad is not None and f" {k[1:]} " in rpad:
                return k[1:]
        elif k.isascii():
            if f" {k} " in padded:
                return k
        elif rpad is not None and f" {unicodedata.normalize('NFC', k)} " in rpad:
            return k
    return None


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------
# category / role
# --------------------------------------------------------------------------

CATEGORIES = (
    "beach", "viewpoint", "outdoor_landmark", "religious", "museum_indoor",
    "day_market", "night_market", "restaurant", "cafe", "nightlife",
    "wellness", "paid_attraction",
)
ALL_CATEGORIES = CATEGORIES + ("lodging",)

ROLE_OF = {
    "beach": "attraction", "viewpoint": "attraction",
    "outdoor_landmark": "attraction", "religious": "attraction",
    "museum_indoor": "attraction", "day_market": "attraction",
    "night_market": "attraction", "paid_attraction": "attraction",
    "restaurant": "meal", "cafe": "rest", "nightlife": "nightlife",
    "wellness": "wellness", "lodging": "base",
}

# Places that are not trip destinations. Kept in the snapshot (nothing is
# deleted) with status=excluded + reason, and never offered as candidates.
EXCLUDE_TYPES = {
    "Quán bar tiếp viên nữ": "quán có tiếp viên (không phù hợp lịch trình chung)",
}
EXCLUDE_NAME_KEYS = ("clinic", "tham my vien", "nha khoa", "dental")
REVIEW_TYPES = {
    "Thẩm mỹ viện": "tiệm làm đẹp — có nên là điểm trong lịch trình?",
    "Dịch vụ cho thuê thiết bị karaoke": "loại Google là cho thuê thiết bị — kiểm tra lại",
}

# Name rules come first because names are a clean source (facts, not
# Google-authored content). Order matters: the first match wins. Keys with
# Vietnamese diacritics are matched on the lower-cased original (so "đình"
# != "đỉnh", "phở" != "phố"); plain-ASCII keys on the folded text.
NAME_RULES = (
    ("lodging", ("khach san", "hotel", "resort", "homestay", "hostel", "villa",
                 "nha nghi", "apartment", "can ho", "motel", "resorts", "hotels")),
    ("night_market", ("cho dem", "night market")),
    ("paid_attraction", ("cooking class", "cooking tour", "cooking", "workshop",
                         "lop hoc nau an", "vinwonders", "sun world",
                         "water park", "cong vien nuoc", "wonderland",
                         "cano", "du thuyen", "cruise", "thuyen thung",
                         "basket boat", "basketboat", "glamping",
                         "khu du lich sinh thai", "kdl sinh thai",
                         "khu vui choi", "trung tam giai tri", "cap treo",
                         "ho boi", "lan bien", "coffee class", "banh mi class")),
    ("museum_indoor", ("bao tang", "museum", "gallery", "phong trung bay",
                       "nha luu niem", "art in paradise")),
    ("wellness", ("spa", "massage", "mat xa", "foot", "xong hoi", "onsen")),
    ("cafe", ("ca phe", "cafe", "caphe", "coffee", "tra sua", "milk tea",
              "tea", "tiem tra", "roaster", "espresso")),
    ("nightlife", ("bar", "pub", "beer", "club", "karaoke", "lounge",
                   "rooftop", "the roof", "cocktail", "wine", "quán bia",
                   "bia hơi", "bia tươi", "nhậu")),
    ("day_market", ("chợ", "market", "dac san", "luu niem", "souvenir",
                    "sieu thi", "trung tam thuong mai", "mall")),
    ("restaurant", ("nha hang", "restaurant", "quan an", "hai san", "seafood",
                    "bistro", "eatery", "dining", "kitchen")),
    ("religious", ("chua", "nha tho", "giao xu", "đình", "đền", "miếu",
                   "thien vien", "bao thap", "thap xa loi", "tuong phat",
                   "quan the am", "lam ty ni vien", "=am", "dien tho",
                   "tinh vien", "tam linh", "tu duong", "pagoda", "temple",
                   "church", "cathedral")),
    ("beach", ("bai bien", "bai tam", "beach", "bai cat", "bãi đá", "bai sung co")),
    ("viewpoint", ("viewpoint", "view", "vong canh", "ngắm", "đèo", "đỉnh",
                   "mũi", "hai dang", "radar")),
    ("outdoor_landmark", ("cầu", "bridge", "cong vien", "park", "quang truong",
                          "tuong dai", "dai tuong niem", "memorial", "làng",
                          "village", "suoi", "thác", "waterfall", "hồ", "rừng",
                          "nui", "ban dao", "cay da", "phố", "khu pho",
                          "downtown", "di tich", "thành", "can cu", "ghenh",
                          "hòn", "vịnh", "đảo", "vườn", "garden", "duong hoa",
                          "sơn", "biển")),
    ("restaurant", ("quán", "bún", "phở", "mì", "mỳ", "bánh", "lẩu", "nướng",
                    "cơm", "ốc", "bbq", "buffet", "yakiniku", "izakaya", "sushi",
                    "pizza", "steak", "ăn vặt", "noodle", "banh mi")),
)

# Google `type` label -> category. Used as a SECOND opinion (and only to
# break ties); it is a Google-derived field and lives in quarantine.
TYPE_RULES = (
    ("lodging", ("Khách sạn", "Lưu trú", "Khu nghỉ dưỡng", "Nhà nghỉ")),
    ("night_market", ("Chợ đêm",)),
    ("paid_attraction", ("Công viên giải trí", "Công viên nước", "Sân chơi trong nhà",
                         "Trung tâm vui chơi", "Lớp học nấu ăn", "Đại lý du lịch bằng thuyền",
                         "Bến du thuyền", "Đảo du lịch", "Hồ bơi", "Khu cắm trại")),
    ("museum_indoor", ("Bảo tàng", "Phòng trưng bày")),
    ("wellness", ("Spa", "mát xa", "Bác sĩ trị liệu xoa bóp")),
    ("nightlife", ("Quán bar", "Quán bia", "Quán rượu", "Hộp đêm", "Bar thể thao")),
    ("cafe", ("Quán cà phê", "Cửa hàng trà")),
    ("restaurant", ("Nhà hàng", "Quán mì", "Quán ăn")),
    ("religious", ("Chùa", "Cơ sở thờ tự", "Nhà thờ", "Điện thờ")),
    ("beach", ("Bãi biển", "Câu lạc bộ bãi biển", "Nhà chòi trên bãi biển",
               "Sân bóng chuyền bãi biển")),
    ("day_market", ("Chợ", "Trung tâm mua sắm", "Cửa hàng", "Siêu thị")),
    ("viewpoint", ("Điểm ngắm cảnh", "Đỉnh núi", "Ridge")),
    ("outdoor_landmark", ("Cầu", "Công viên", "Vườn", "Tượng đài", "Đài tưởng niệm",
                          "Địa điểm lịch sử", "Di tích lịch sử", "Điểm mốc lịch sử",
                          "Suối", "Bán đảo", "Thắng cảnh")),
)

V1_CAT_FALLBACK = {
    "attraction": "outdoor_landmark", "landmark": "outdoor_landmark",
    "nature": "outdoor_landmark", "park": "outdoor_landmark",
    "viewpoint": "viewpoint", "beach": "beach", "museum": "museum_indoor",
    "market": "day_market", "restaurant": "restaurant", "cafe": "cafe",
    "bar": "nightlife", "spa": "wellness", "lodging": "lodging",
}

# Exact-name decisions for well-known places where keyword rules are
# ambiguous. Each entry is a reviewed judgement, recorded as evidence.
NAME_OVERRIDES = {
    "Ngũ Hành Sơn": "paid_attraction",           # Thủy Sơn có vé vào cổng
    "Hải Vân Quan": "paid_attraction",           # di tích có bán vé
    "Cù Lao Chàm": "paid_attraction",            # đi bằng tour cano
    "Sun World Bà Nà Hills": "paid_attraction",
    "Ba Na Hills": "paid_attraction",
    "Bến Du Thuyền Đà Nẵng": "paid_attraction",
    "Bến Du Thuyền Sông Hàn": "paid_attraction",
    "Fantasy Park": "paid_attraction",
    "Trung Tâm Giải Trí Helio": "paid_attraction",
    "Rừng Dừa Bảy Mẫu": "paid_attraction",
    "Dịch Vụ Thuyền Thúng Bến Dừa": "paid_attraction",
    "Phố đi bộ - chợ đêm Bạch Đằng Đà Nẵng": "night_market",
    "KHU PHỐ DU LỊCH AN THƯỢNG": "outdoor_landmark",
    "Fishing Village and Fleet": "outdoor_landmark",
    "Nhà thờ Tộc Hồ Thanh Khê": "religious",
    "Tượng Phật Đá Phan Sơn": "religious",
    "Mai Vang (Yellow Blossom) Bonsai Garden": "outdoor_landmark",
    "Nhà bia Chứng tích Núi Ghềnh": "outdoor_landmark",
    "Khu Căn cứ Cách mạng K20": "outdoor_landmark",
    "Thác Tóc Tiên": "outdoor_landmark",
    "Small waterfall": "outdoor_landmark",
    "Public beach": "beach",
    "Public Beach Access": "beach",
    "Hồ Bơi Thanh Khê": "paid_attraction",
    "Làng đá mỹ nghệ Non Nước": "outdoor_landmark",
    "Đèo Hải Vân": "viewpoint",
    "Ghềnh Bàng": "outdoor_landmark",
    "Bán đảo Sơn Trà": "outdoor_landmark",
    "Núi Sơn Trà": "viewpoint",
    "Đỉnh Bà Nà": "viewpoint",
    "Tú Chợ đêm": "restaurant",
}

# Status=review: kept and usable as in v1, but queued for a human decision.
REVIEW_NAMES = {
    "Đà Nẵng Food Tour": "không phải một địa điểm cố định (chương trình/tour)",
    "Ba Na Hills": "có thể trùng 'Sun World Bà Nà Hills'",
    "DA NANG DOWNTOWN": "chưa rõ là khu vui chơi có vé hay khu phố",
    "Đà Sơn tâm linh": "chưa định danh rõ",
    "Gần núi thần tài": "tên chung chung",
    "Public beach": "tên chung chung (OSM)",
    "Public Beach Access": "tên chung chung (OSM)",
    "Small waterfall": "tên chung chung (OSM)",
    "Khu Dừng Chân": "tên chung chung",
}
GENERIC_PEAK = re.compile(r"^nui [a-z ]{2,20}$")


def classify(name: str, gtype: str | None, v1_cat: str | None) -> tuple[str, list[str]]:
    """Return (category, evidence). Name first, Google type second, v1 last."""
    if name in NAME_OVERRIDES:
        return NAME_OVERRIDES[name], [f"override:{name}"]
    f, r = fold(name), raw_words(name)
    by_name = None
    for cat, keys in NAME_RULES:
        k = _has(f, keys, r)
        if k:
            by_name = (cat, f"name:{k}")
            break
    by_type = None
    for cat, keys in TYPE_RULES:
        if gtype and any(gtype.startswith(k) or k in gtype for k in keys):
            by_type = (cat, f"type:{gtype}")
            break
    if by_name and by_type and by_name[0] != by_type[0]:
        winner = _resolve(by_name[0], by_type[0])
        if winner == by_type[0]:
            return by_type[0], [by_type[1], by_name[1]]
        return by_name[0], [by_name[1], by_type[1]]
    if by_name:
        return by_name[0], [by_name[1]] + ([by_type[1]] if by_type else [])
    if by_type:
        return by_type[0], [by_type[1]]
    cat = V1_CAT_FALLBACK.get(v1_cat or "", "outdoor_landmark")
    return cat, [f"v1_cat:{v1_cat}"]


# When the name keyword and the Google type disagree. A business type
# (hotel, restaurant, bar...) beats a place-ish name word ("Beach",
# "Sơn Trà"); a specific name word (cooking class, bảo tàng, chùa) beats a
# vague type ("Điểm thu hút khách du lịch" never reaches here).
_BUSINESS = {"lodging", "restaurant", "cafe", "nightlife", "wellness"}
_PLACEISH = {"beach", "viewpoint", "outdoor_landmark", "day_market"}


def _resolve(name_cat: str, type_cat: str) -> str:
    if type_cat == "lodging":
        return "lodging"
    if name_cat in ("paid_attraction", "museum_indoor", "night_market", "lodging"):
        return name_cat
    if type_cat in _BUSINESS and name_cat in _PLACEISH:
        return type_cat
    if name_cat == "religious":
        return name_cat
    if type_cat == "nightlife" and name_cat in ("cafe", "wellness", "restaurant"):
        return type_cat
    if name_cat in ("cafe", "wellness", "beach", "nightlife"):
        return name_cat
    return type_cat


def classify_name_only(name: str) -> str | None:
    """Clean-source label (no Google field) used to measure rule agreement."""
    if name in NAME_OVERRIDES:
        return NAME_OVERRIDES[name]
    f, r = fold(name), raw_words(name)
    for cat, keys in NAME_RULES:
        if _has(f, keys, r):
            return cat
    return None


def exclusion_reason(name: str, gtype: str | None) -> str | None:
    if gtype in EXCLUDE_TYPES:
        return EXCLUDE_TYPES[gtype]
    f = fold(name)
    k = _has(f, EXCLUDE_NAME_KEYS)
    if k:
        return f"cơ sở y tế/thẩm mỹ ('{k}' trong tên)"
    return None


def review_reason(name: str, category: str, poi_id: str = "",
                  gtype: str | None = None) -> str | None:
    if name in REVIEW_NAMES:
        return REVIEW_NAMES[name]
    if gtype in REVIEW_TYPES:
        return REVIEW_TYPES[gtype]
    if (poi_id.startswith("osm:") and category in ("viewpoint", "outdoor_landmark")
            and GENERIC_PEAK.match(fold(name))):
        return "đỉnh núi OSM, chưa rõ có đường lên/điểm tham quan"
    return None


# --------------------------------------------------------------------------
# zones (6)
# --------------------------------------------------------------------------

ZONES = ("trung_tam", "son_tra_my_khe", "ngu_hanh_son", "hoi_an",
         "ba_na_tay", "hai_van_lien_chieu")

# Bounding box of the merged Đà Nẵng (incl. former Quảng Nam tourist area
# we cover). POIs outside fail the coordinate rule.
BBOX = {"lat_min": 15.20, "lat_max": 16.30, "lon_min": 107.60, "lon_max": 108.80}


def zone_of(lat: float, lon: float) -> str:
    """Coarse planning zone from coordinates (approximate boundaries).

    The Hàn river runs at lon ~108.225-108.232 in the centre; east bank =
    Sơn Trà / Mỹ Khê (north of lat 16.035) or Ngũ Hành Sơn (south).
    """
    if lat < 15.935 or lon > 108.40:
        return "hoi_an"
    if lon < 108.125 and lat < 16.075:
        return "ba_na_tay"
    if lat >= 16.065 and lon < 108.185:
        return "hai_van_lien_chieu"
    if lon >= 108.232:
        return "son_tra_my_khe" if lat >= 16.035 else "ngu_hanh_son"
    if lat < 15.985:
        return "ngu_hanh_son"
    return "trung_tam"


# --------------------------------------------------------------------------
# opening hours
# --------------------------------------------------------------------------

DAY = 1440


def _tm(s: str) -> int:
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def parse_span(span: str) -> tuple[int, int] | None:
    """'HH:MM-HH:MM' -> (open, close) with close > open (overnight adds 1440)."""
    m = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*", span or "")
    if not m:
        return None
    o, c = _tm(m.group(1)), _tm(m.group(2))
    if (o, c) in ((0, 1439), (0, 1440), (0, 0)):
        return (0, DAY)
    if c <= o:
        c += DAY
    return (o, c)


def parse_element(el: str) -> list[tuple[int, int]]:
    out = []
    for part in (el or "").split(","):
        sp = parse_span(part)
        if sp:
            out.append(sp)
    return merge(out)


def merge(spans):
    spans = sorted(spans)
    out = []
    for o, c in spans:
        if out and o <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], c))
        else:
            out.append((o, c))
    return out


def _canon(spans):
    """Fold spans to start in [0, 1440) and merge."""
    res = []
    for o, c in spans:
        if c - o >= DAY:
            return [(0, DAY)]
        k = (o // DAY) * DAY
        res.append((o - k, c - k))
    return merge(res)


def intersect(a, b):
    """Intersection of two span lists on a circular day."""
    if a == [(0, DAY)]:
        return list(b)
    if b == [(0, DAY)]:
        return list(a)
    out = []
    for o1, c1 in a:
        for shift in (-DAY, 0, DAY):
            for o2, c2 in b:
                lo, hi = max(o1, o2 + shift), min(c1, c2 + shift)
                if hi - lo >= 15:          # ignore slivers < 15 min
                    out.append((lo, hi))
    return _canon(out)


def intersect_all(elements: list[str]):
    """Spans valid on EVERY day variant listed in v1 (conservative)."""
    sets = [parse_element(e) for e in elements]
    sets = [s for s in sets if s]
    if not sets:
        return []
    acc = sets[0]
    for s in sets[1:]:
        acc = intersect(acc, s)
    return acc


def union_all(elements: list[str]):
    spans = []
    for e in elements:
        spans.extend(parse_element(e))
    return _canon(spans)


def fmt(spans) -> list[str]:
    """Span list -> app format (one string, comma-separated windows)."""
    if not spans:
        return []
    parts = []
    for o, c in spans:
        if (o, c) == (0, DAY):
            parts.append("00:00-23:59")
            continue
        cc = c if c < DAY else (c - DAY if c > DAY else DAY - 1)
        parts.append(f"{o // 60:02d}:{o % 60:02d}-{cc // 60:02d}:{cc % 60:02d}")
    return [", ".join(parts)]


def contains(outer, inner) -> bool:
    """True iff every inner span lies inside some outer span."""
    if outer == [(0, DAY)]:
        return True
    for o, c in inner:
        ok = False
        for shift in (-DAY, 0, DAY):
            if any(oo + shift <= o and c <= cc + shift for oo, cc in outer):
                ok = True
                break
        if not ok:
            return False
    return True


_OSM_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def parse_osm_hours(spec: str | None) -> dict | None:
    """Small subset of OSM `opening_hours`: '24/7', 'Mo-Su 10:00-22:00',
    'Mo-Fr 08:00-17:00; Sa 08:00-12:00', 'Tu-Su ...', 'Mo,We ...'.
    Returns {day: [spans]} for 7 days or None when the syntax is outside the
    subset (kept as raw text, never guessed)."""
    if not spec:
        return None
    s = spec.strip()
    # tolerate common OSM variants: public-holiday tokens and lower-case days
    s = re.sub(r"\s*,?\s*\bPH\b\s*,?\s*", " ", s).strip()
    s = re.sub(r"\b(mo|tu|we|th|fr|sa|su)\b", lambda m: m.group(1).capitalize(), s, flags=re.I)
    if s == "24/7":
        return {d: [(0, DAY)] for d in _OSM_DAYS}
    week = {d: [] for d in _OSM_DAYS}
    for rule in s.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        m = re.fullmatch(r"((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*[-,]\s*(?:Mo|Tu|We|Th|Fr|Sa|Su))*)?\s*(.+)", rule)
        if not m:
            return None
        days_s, times_s = m.group(1), m.group(2)
        if times_s.strip().lower() == "off":
            spans = []
        else:
            spans = []
            for t in times_s.split(","):
                sp = parse_span(t)
                if not sp:
                    return None
                spans.append(sp)
        days = _OSM_DAYS if not days_s else _expand_days(days_s)
        if days is None:
            return None
        for d in days:
            week[d] = merge(spans)
    return week


def _expand_days(s: str):
    out = []
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = [x.strip() for x in part.split("-")]
            ia, ib = _OSM_DAYS.index(a), _OSM_DAYS.index(b)
            idx = list(range(ia, ib + 1)) if ia <= ib else list(range(ia, 7)) + list(range(0, ib + 1))
            out.extend(_OSM_DAYS[i] for i in idx)
        elif part in _OSM_DAYS:
            out.append(part)
        else:
            return None
    return out


def open_days_intersection(week: dict):
    """(spans common to every OPEN day, closed days). Used when a place
    closes one day a week: the planner gets the open-day window and the
    closed days are recorded (day-of-week planning is a P1 item)."""
    closed = [d for d in _OSM_DAYS if not week.get(d)]
    acc = None
    for d in _OSM_DAYS:
        if week.get(d):
            acc = week[d] if acc is None else intersect(acc, week[d])
    return (acc or []), closed


def week_intersection(week: dict):
    acc = None
    for d in _OSM_DAYS:
        if not week.get(d):
            return []          # closed one day -> no every-day window
        acc = week[d] if acc is None else intersect(acc, week[d])
    return acc or []


# Archetype table = ESTIMATES (verified_by=inferred). `default` is a typical
# opening span, `safe` the window where most places of that kind are open;
# the solver may only place inferred-hours visits inside `safe`, labelled
# "nên kiểm tra giờ".
#
# Calibration 2026-11-18 (internal QA, aggregate only): share of POIs whose
# every-day Google hours (v1, quarantined) fully contain `safe`. The first
# hand-written table scored 0.50-0.79 for cafe/bar/spa/market, so the
# windows below were narrowed. Expect ~85-90% hits, never 100%: inferred
# hours are a fallback, not a fact.
CALIBRATION = {
    "cafe": 0.85, "bar": 0.90, "spa": 0.87, "nha_hang_lunch": 0.85,
    "nha_hang_dinner": 0.93, "an_toi": 0.92, "com_trua": 0.90, "bao_tang": 1.0,
    "cho_ngay": 0.88, "cua_hang": 0.90, "chua": 0.83,
}
ARCHETYPES = {
    "an_sang":   {"default": ["06:00-10:30"], "safe": ["06:30-09:30"]},
    "com_trua":  {"default": ["10:00-14:00"], "safe": ["11:00-13:00"]},
    "nha_hang":  {"default": ["10:00-22:00"], "safe": ["11:00-13:30", "17:30-20:30"]},
    "an_toi":    {"default": ["16:00-23:00"], "safe": ["17:30-21:30"]},
    "cafe":      {"default": ["06:30-22:00"], "safe": ["08:00-20:30"]},
    "bar":       {"default": ["17:00-02:00"], "safe": ["19:30-23:00"]},
    "spa":       {"default": ["09:00-22:00"], "safe": ["10:00-20:00"]},
    "cho_ngay":  {"default": ["05:00-18:00"], "safe": ["08:00-11:00"]},
    "cua_hang":  {"default": ["08:00-21:00"], "safe": ["09:00-19:00"]},
    "cho_dem":   {"default": ["17:00-23:00"], "safe": ["18:00-22:00"]},
    "chua":      {"default": ["06:00-18:00"], "safe": ["08:00-11:00", "14:00-16:00"]},
    "bao_tang":  {"default": ["08:00-17:00"], "safe": ["08:30-11:00", "14:00-16:30"]},
    "ngoai_troi_do_thi": {"default": ["00:00-23:59"], "safe": ["05:00-22:00"]},
    "ngoai_troi_tu_nhien": {"default": ["05:00-18:30"], "safe": ["06:00-17:30"]},
    "co_ve":     {"default": [], "safe": []},       # phải tra trang chính thức
    "luu_tru":   {"default": [], "safe": []},       # không phải điểm tham quan
}

BREAKFAST_KEYS = ("banh mi", "bun bo", "pho", "xoi", "banh canh", "chao", "banh cuon")
LUNCH_KEYS = ("com", "bun cha ca", "mi quang", "my quang", "quan mi", "banh xeo",
              "bun mam", "banh trang cuon")
DINNER_KEYS = ("oc", "lau", "nuong", "nhau", "bbq", "yakiniku", "izakaya", "beer", "bia")
NATURE_KEYS = ("nui", "suoi", "thac", "deo", "rung", "ban dao", "hon", "mui", "dinh",
               "hai dang", "radar", "waterfall", "ghenh", "ho hoa trung", "can cu", "vong canh")
GATED_SITE_KEYS = ("di tich", "thanh dien hai", "nha luu niem", "lang nghe",
                   "nha bia", "dinh lang")


def archetype_of(category: str, name: str, gtype: str | None = None) -> str:
    f = fold(name) + " " + fold(gtype)
    if category == "restaurant":
        if _has(f, DINNER_KEYS):
            return "an_toi"
        if _has(f, BREAKFAST_KEYS):
            return "an_sang"
        if _has(f, LUNCH_KEYS):
            return "com_trua"
        return "nha_hang"
    if category == "outdoor_landmark" or category in ("beach", "viewpoint"):
        if _has(f, GATED_SITE_KEYS):
            return "bao_tang"
        if category == "beach":
            return "ngoai_troi_do_thi"
        if _has(f, NATURE_KEYS) or category == "viewpoint":
            return "ngoai_troi_tu_nhien"
        return "ngoai_troi_do_thi"
    return {
        "cafe": "cafe", "nightlife": "bar", "wellness": "spa",
        "day_market": "cho_ngay" if _has(f, ("=chợ", "market")) or " chợ " in f" {raw_words(name)} " else "cua_hang",
        "night_market": "cho_dem",
        "religious": "chua", "museum_indoor": "bao_tang",
        "paid_attraction": "co_ve", "lodging": "luu_tru",
    }.get(category, "co_ve")


# u(t) profile id per archetype/category (curves are defined in P1).
TIME_PROFILE = {
    "beach": "sun_anchored_beach", "viewpoint": "sun_anchored_view",
    "outdoor_landmark": "outdoor_heat_sensitive", "religious": "morning_cool",
    "museum_indoor": "indoor_flat", "day_market": "morning_market",
    "night_market": "evening_peak", "restaurant": "meal_windows",
    "cafe": "flat_rest", "nightlife": "evening_peak", "wellness": "afternoon_rest",
    "paid_attraction": "open_hours_flat", "lodging": "lodging_rest",
}


# Weather exposure prior for POIs the v1 T063 labeler never saw (OSM / manual
# additions). Values are the modes of the labeled POIs of the same space and
# category (danang-v2.1, 2026-11-20); `exposure_source` marks them estimated.
EXPOSURE_BY_SPACE = {
    "indoor": {"outdoor_exposure": 0.1, "sun_exposure": 0.05, "wind_exposure": 0.1, "rain_cover": "enclosed"},
    "both": {"outdoor_exposure": 0.6, "sun_exposure": 0.48, "wind_exposure": 0.48, "rain_cover": "mixed"},
}
OUTDOOR_EXPOSURE = {"beach": 0.95, "viewpoint": 0.9}          # others 0.75
DEFAULT_SPACE = {"beach": "outdoor", "viewpoint": "outdoor", "outdoor_landmark": "outdoor",
                 "paid_attraction": "outdoor", "religious": "both", "night_market": "both"}


def exposure_prior(category: str, space: str | None) -> dict:
    """Exposure fields from space (else the category's usual space)."""
    if space not in ("indoor", "outdoor", "both"):
        space = DEFAULT_SPACE.get(category, "indoor")
    if space == "outdoor":
        x = OUTDOOR_EXPOSURE.get(category, 0.75)
        ex = {"outdoor_exposure": x, "sun_exposure": x, "wind_exposure": x, "rain_cover": "open"}
    else:
        ex = dict(EXPOSURE_BY_SPACE[space])
    return {**ex, "space": space, "indoor": space == "indoor",
            "exposure_source": "category_prior"}


# --------------------------------------------------------------------------
# prices
# --------------------------------------------------------------------------

BANDS = ("re", "vua", "kha", "cao")


def band_of(vnd: float | None) -> str | None:
    if vnd is None:
        return None
    if vnd < 50_000:
        return "re"
    if vnd < 150_000:
        return "vua"
    if vnd <= 400_000:
        return "kha"
    return "cao"


def legacy_band(vnd: float | None) -> str | None:
    """3-level band the current app reads (thresholds of BE/common.py)."""
    if vnd is None:
        return None
    if vnd < 100_000:
        return "cheap"
    if vnd <= 500_000:
        return "medium"
    return "expensive"


_NUM = r"(\d+(?:[.,]\d{3})*(?:[.,]\d+)?)"


def _to_vnd(num: str, unit: str | None) -> float:
    unit = (unit or "").lower().replace("\xa0", " ").strip()
    n = num.replace(" ", "")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", n):
        v = float(n.replace(".", "").replace(",", ""))
    else:
        v = float(n.replace(",", "."))
    if unit in ("k", "n", "nghìn", "ngàn", "n ₫", "n₫"):
        v *= 1000
    elif unit in ("tr", "triệu", "trieu", "m"):
        v *= 1_000_000
    return v


def parse_google_price(note: str | None) -> dict | None:
    """'~500.000đ (khoảng 200-800 N ₫)' -> {typical, min, max} VND."""
    if not note or note.startswith("user:"):
        return None
    t = note.replace("\xa0", " ")
    out = {}
    m = re.search(r"~\s*" + _NUM + r"\s*đ", t)
    if m:
        out["typical"] = _to_vnd(m.group(1), None)
    m = re.search(r"khoảng\s*" + _NUM + r"\s*-\s*" + _NUM + r"\s*(N\s*₫|₫)", t)
    if m:
        unit = "n" if m.group(3).startswith("N") else None
        lo, hi = _to_vnd(m.group(1), unit), _to_vnd(m.group(2), unit)
        if lo < 1000:          # Google's "₫1-200.000" bucket: no real floor
            lo = None
        out["min"], out["max"] = lo, hi
    return out or None


def parse_user_price(note: str | None) -> dict | None:
    """'user: Muối Biển 100-200k, ...' / 'từ 400k' / '150k-1200k' -> VND range."""
    if not note:
        return None
    t = note.replace("\xa0", " ")
    t = re.sub(r"^user:\s*", "", t)
    m = re.search(_NUM + r"\s*(k|tr|triệu)?\s*[-–]\s*" + _NUM + r"\s*(k|tr|triệu|đ)?", t)
    if m:
        u2 = m.group(4) if m.group(4) != "đ" else None
        u1 = m.group(2) or u2
        lo, hi = _to_vnd(m.group(1), u1), _to_vnd(m.group(3), u2)
        if hi < lo:
            hi = lo
        return {"min": lo, "max": hi}
    m = re.search(r"(từ|from)\s*" + _NUM + r"\s*(k|tr|triệu)", t)
    if m:
        return {"min": _to_vnd(m.group(2), m.group(3)), "max": None}
    m = re.search(_NUM + r"\s*(k|tr|triệu)\b", t)
    if m:
        v = _to_vnd(m.group(1), m.group(2))
        return {"min": v, "max": v}
    return None


def typical_of(rng: dict | None) -> float | None:
    if not rng:
        return None
    if rng.get("typical"):
        return rng["typical"]
    lo, hi = rng.get("min"), rng.get("max")
    if lo and hi:
        return (lo + hi) / 2
    return lo or hi


# Category-level price ESTIMATES (VND per person; verified_by=inferred).
CATEGORY_PRICE = {
    "cafe":        {"min": 25_000, "max": 70_000},
    "nightlife":   {"min": 80_000, "max": 300_000},
    "wellness":    {"min": 200_000, "max": 600_000},
    "day_market":  {"min": 20_000, "max": 150_000},
    "night_market": {"min": 30_000, "max": 150_000},
}
RESTAURANT_PRICE = {
    "an_sang": {"min": 20_000, "max": 50_000},
    "com_trua": {"min": 30_000, "max": 70_000},
    "an_toi": {"min": 100_000, "max": 300_000},
    "nha_hang": {"min": 100_000, "max": 350_000},
}
HIGH_END_KEYS = ("fine dining", "steak", "french", "phap", "italia", "nhat ban",
                 "japanese", "sushi", "cao cap", "hai san")
FREE_PUBLIC = ("beach", "religious", "viewpoint", "outdoor_landmark")


# --------------------------------------------------------------------------
# dwell (minutes on site, p25/p50/p75) - CATEGORY-LEVEL ESTIMATES
# --------------------------------------------------------------------------
# v1 `visit_min` came from a category rule that gave bridges, statues and
# viewpoints 3-4 h (outdoor_landmark median p50 = 200 min). These estimates
# replace it unless a user/human confirmed the v1 value. They are priors to
# be re-fitted from pilot logs (P3), never facts.

DWELL = {
    "beach": (45, 90, 150),
    "viewpoint": (15, 30, 50),
    "outdoor_urban": (10, 20, 40),          # cầu, tượng đài, quảng trường, phố
    "park": (20, 40, 70),
    "nature": (45, 90, 150),                # suối, thác, bán đảo, rừng
    "village": (30, 60, 90),                # làng nghề, làng chài
    "historic_site": (20, 40, 60),
    "religious": (15, 30, 50),
    "religious_major": (30, 60, 90),        # chùa lớn / quần thể hang động
    "museum": (45, 75, 110),
    "gallery": (20, 40, 60),
    "market": (30, 60, 90),
    "shop": (15, 30, 45),
    "night_market": (45, 75, 110),
    "breakfast": (20, 30, 45),
    "restaurant": (40, 60, 90),
    "cafe": (30, 50, 80),
    "nightlife": (60, 90, 150),
    "wellness": (60, 90, 120),
    "theme_park_big": (300, 360, 480),      # Bà Nà, VinWonders
    "water_park": (150, 210, 270),
    # Cù Lao Chàm: the stay ON the island. The crossing is a leg of its own now (cano
    # 20 + 10 min each way, danang-v2/transfers.json), so the old day trip (6/7/8 h)
    # less the two crossings. 5 h is what a traveller on the last boat out (09:00,
    # on the island 09:20) has until the last one back (14:30, off by 14:20); tours
    # spend 09:00-14:00 (Vietnam Booking) to 09:00-15:00 (MIA) there.
    "island_day_trip": (300, 360, 420),
    "cooking_class": (180, 210, 240),
    "boat_short": (40, 60, 90),             # thuyền thúng, du thuyền
    "eco_park": (120, 180, 240),
    "indoor_play": (60, 90, 120),
    "paid_site": (45, 75, 110),
    "lodging": (45, 60, 90),                # never scheduled (role=base)
    "old_town": (90, 150, 240),             # phố cổ Hội An (đi bộ)
    "heritage_site": (90, 120, 180),        # Mỹ Sơn
    "evening_show": (90, 120, 150),         # show Ký ức Hội An
}
BIG_PARK_KEYS = ("sun world", "vinwonders", "ba na hills")
MAJOR_RELIGIOUS = ("Chùa Linh Ứng - Bãi Bụt Sơn Trà", "Chùa Quán Thế Âm", "Động Âm Phủ",
                   "Huyen Khong Cave", "Động Tàng Chơn", "Quốc Tự Tam Thai",
                   "Chùa Linh Ứng - Bà Nà")


def dwell_kind(category: str, name: str, archetype: str) -> str:
    f = fold(name)
    if category == "paid_attraction":
        if "pho co" in f:
            return "old_town"
        if "my son" in f:
            return "heritage_site"
        if _has(f, ("ky uc hoi an", "an tuong hoi an", "memories")):
            return "evening_show"
        if _has(f, BIG_PARK_KEYS):
            return "theme_park_big"
        if _has(f, ("water park", "cong vien nuoc", "ho boi")):
            return "water_park"
        if "cu lao cham" in f:
            return "island_day_trip"
        if _has(f, ("cooking", "class", "workshop")):
            return "cooking_class"
        if _has(f, ("thuyen thung", "basket", "basketboat", "du thuyen", "cruise", "cano", "dua")):
            return "boat_short"
        if _has(f, ("sinh thai", "glamping", "suoi", "ben nam yen", "heritage")):
            return "eco_park"
        if _has(f, ("wonderland", "giai tri", "fantasy", "helio")):
            return "indoor_play"
        if "ngu hanh son" in f:
            return "religious_major"
        return "paid_site"
    if category == "outdoor_landmark":
        if _has(f, ("cong vien", "park", "vuon", "garden", "duong hoa")):
            return "park"
        if _has(f, ("lang", "village", "lang chai", "fishing")):
            return "village"
        if archetype == "bao_tang" or _has(f, ("di tich", "can cu", "thanh", "nha bia")):
            return "historic_site"
        if archetype == "ngoai_troi_tu_nhien":
            return "nature"
        return "outdoor_urban"
    if category == "religious":
        return "religious_major" if name in MAJOR_RELIGIOUS else "religious"
    if category == "museum_indoor":
        return "gallery" if _has(f, ("gallery", "studio", "phong trung bay")) else "museum"
    if category == "day_market":
        return "market" if archetype == "cho_ngay" else "shop"
    if category == "restaurant":
        return "breakfast" if archetype == "an_sang" else "restaurant"
    return {"beach": "beach", "viewpoint": "viewpoint", "night_market": "night_market",
            "cafe": "cafe", "nightlife": "nightlife", "wellness": "wellness",
            "lodging": "lodging"}.get(category, "paid_site")
