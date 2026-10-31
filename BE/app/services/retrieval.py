"""POI retrieval/filter (T015 + T024, lane C). Hard filter + uncertainty.

Reads pois.json directly with json stdlib (STUB-NOTE: lane-A snapshot
loader T008 wires in at phase-PR — same schema, swap one line).

FR-013: unverified POIs are EXCLUDED from the main plan
(`candidates`); they are listed separately under `needs_verification`
("can xac minh"), must-visit flagged (validator decides per FR-031).
FR-024/FR-026: unverified fields (giờ mở cửa/rating/giá/tags) get
`uncertainty` labels and are never presented as fact.

Rules:
- avoid -> always excluded (reason).
- must_visit + verified -> candidates (violations flagged).
- must_visit + unverified -> needs_verification (flagged, NOT main plan).
- other unverified -> needs_verification (reason "chua xac minh").
- lodging/transport -> excluded unless must_visit (not a day activity).
- budget/hours filters apply to candidates as before.

Activities are a soft preference (FR-006/FR-022) and NEVER an exclusion
filter: dropping every non-matching POI also dropped the restaurants a day
needs, so "tắm biển" gave an infeasible (no lunch) or one-stop plan.
`activity_requirements` turns them into optimizer `required_any` groups
("at least one beach") that the planner may relax with a warning.

Activities match the canonical group `cat` (lane-A enum in pois.json; seed
POIs without `cat` fall back to canonical_category(type)), never the raw
SerpApi `type`. Activity text is NFC-normalised and matched whole-word,
longest phrase first; a matched phrase is consumed so its sub-words cannot
match again ("yêu cầu" never reads as "cầu"). Multi-word phrases also match
without diacritics ("tam bien").

A category alone is too wide for most wishes: a noodle shop is a restaurant but
not "hải sản", a statue is a landmark but not "chùa". `ACTIVITY_WORDS` narrows a
wish to the POIs whose name, type or tags say so, and a plan only counts as
meeting the wish when one of THOSE POIs is in it.

`plan_tier` (BE/tools/fix_poi_accuracy.py) keeps the places no traveller would look
for out of a default plan: `local` and `wish_only` POIs come up only when a wish
asks for them, `excluded` ones only as a must_visit.
"""

from __future__ import annotations

import re
import unicodedata

from BE.app.services import to_min
from BE.app.services.profile_filter import fold
from BE.common import effective_fee, load_json, party_size
from BE.ml.patm.estimate_duration import canonical_category

# Phrase -> canonical groups. An empty list marks a phrase that only
# blocks its sub-words from matching.
ACTIVITY_TYPE_MAP = {
    "biển": ["beach"], "bãi biển": ["beach"], "tắm biển": ["beach"], "tắm": ["beach"],
    "bơi": ["beach"], "lặn": ["beach"], "lướt sóng": ["beach"],
    "núi": ["nature"], "leo núi": ["nature"], "leo": ["nature"],
    "trekking": ["nature"], "rừng": ["nature"], "thác": ["nature"],
    "suối": ["nature"], "đèo": ["nature"], "hang động": ["nature"],
    "cắm trại": ["nature"], "thiên nhiên": ["nature"], "bán đảo": ["nature"],
    "ăn": ["restaurant"], "nhà hàng": ["restaurant"], "hải sản": ["restaurant"],
    "mì": ["restaurant"], "mì quảng": ["restaurant"], "mỳ quảng": ["restaurant"],
    "bún": ["restaurant"], "phở": ["restaurant"], "bánh xèo": ["restaurant"],
    "lẩu": ["restaurant"], "đồ nướng": ["restaurant"], "ăn chay": ["restaurant"],
    "ẩm thực": ["restaurant"], "buffet": ["restaurant"],
    "đặc sản": ["restaurant", "shop"],
    "quán": ["restaurant", "cafe", "bar"], "quán ăn": ["restaurant"],
    "quán cà phê": ["cafe"], "quán bar": ["bar"], "quán bia": ["bar"],
    "quán nhậu": ["bar"],
    "cà phê": ["cafe"], "cafe": ["cafe"], "coffee": ["cafe"],
    "trà sữa": ["cafe"], "uống trà": ["cafe"], "bánh ngọt": ["cafe"],
    "bar": ["bar"], "pub": ["bar"], "bia": ["bar"], "nhậu": ["bar"],
    "cocktail": ["bar"], "rượu": ["bar"], "karaoke": ["bar"], "club": ["bar"],
    "hộp đêm": ["bar"], "nhạc sống": ["bar"],
    "spa": ["spa"], "massage": ["spa"], "mát xa": ["spa"], "xông hơi": ["spa"],
    "gội đầu": ["spa"], "làm nail": ["spa"],
    "chợ": ["market"], "chợ đêm": ["market"], "mua sắm": ["market", "shop"],
    "shopping": ["market", "shop"], "quà": ["shop"], "lưu niệm": ["shop"],
    "siêu thị": ["shop", "market"], "trung tâm thương mại": ["market", "shop"],
    "văn hóa": ["museum"], "bảo tàng": ["museum"], "triển lãm": ["museum"],
    "nghệ thuật": ["museum"], "phòng trưng bày": ["museum"],
    "lịch sử": ["museum", "landmark", "temple"],
    "check-in": ["landmark", "viewpoint"], "cầu": ["landmark"], "chùa": ["temple"],
    "nhà thờ": ["temple"], "đền": ["temple"], "đình": ["temple"],
    "ngắm cảnh": ["landmark", "viewpoint"], "chụp ảnh": ["landmark", "viewpoint"],
    "sống ảo": ["landmark", "viewpoint"], "ngắm hoàng hôn": ["viewpoint", "beach"],
    "hoàng hôn": ["viewpoint", "beach"], "ngắm bình minh": ["beach", "viewpoint"],
    "bình minh": ["beach", "viewpoint"], "đài quan sát": ["viewpoint"],
    "di tích": ["landmark", "temple"], "tâm linh": ["temple"],
    "vui chơi": ["attraction"], "công viên giải trí": ["attraction"],
    "công viên nước": ["attraction"], "thủy cung": ["attraction"],
    "cáp treo": ["attraction"], "du thuyền": ["attraction"],
    "đi thuyền": ["attraction"], "thuyền thúng": ["attraction"],
    "nấu ăn": ["attraction"],
    "công viên": ["park"], "đi dạo": ["park"], "dạo bộ": ["park"],
    "picnic": ["park"],
    "yêu cầu": [], "nhu cầu": [], "gần biển": [], "view biển": [],
}
NON_ACTIVITY_CATS = {"lodging", "transport"}
PAID_CATS = {"restaurant", "cafe", "bar", "spa"}
_HILL_WORDS = ("núi", "bán đảo", "đỉnh", "đèo", "ngũ hành sơn")
# Wishes narrower than their category: words the POI's name, type or tags must hold
# (`_has_word`). A phrase not listed here takes the whole category.
ACTIVITY_WORDS = {
    "hải sản": ("hải sản", "seafood", "ốc", "cua biển", "tôm hùm", "ghẹ"),
    "mì": ("mì", "mỳ", "noodle"), "mì quảng": ("mì quảng", "mỳ quảng"),
    "mỳ quảng": ("mì quảng", "mỳ quảng"), "bún": ("bún",), "phở": ("phở",),
    "bánh xèo": ("bánh xèo",), "lẩu": ("lẩu", "hot pot", "hotpot"),
    "đồ nướng": ("nướng", "bbq", "yakiniku"), "ăn chay": ("chay", "vegan", "vegetarian"),
    "buffet": ("buffet",), "đặc sản": ("đặc sản", "speciality", "specialty"),
    "quà": ("quà", "lưu niệm", "souvenir", "handmade", "gift"),
    "lưu niệm": ("lưu niệm", "souvenir", "quà", "handmade", "gift"),
    "chợ đêm": ("chợ đêm", "night market"),
    "bảo tàng": ("bảo tàng", "museum"), "chùa": ("chùa", "thiền viện", "quốc tự", "pagoda", "tu viện"),
    "nhà thờ": ("nhà thờ", "giáo xứ", "church"), "đền": ("đền",), "đình": ("đình",),
    "cầu": ("cầu", "bridge"), "tâm linh": ("chùa", "thiền viện", "quốc tự", "pagoda", "đền"),
    "núi": _HILL_WORDS, "leo núi": _HILL_WORDS, "leo": _HILL_WORDS,
    "trekking": _HILL_WORDS + ("suối",),
    "thác": ("thác",), "suối": ("suối",), "đèo": ("đèo",), "rừng": ("rừng", "bán đảo"),
    "hang động": ("hang động", "cave", "ngũ hành sơn"), "cắm trại": ("cắm trại", "glamping", "camping"),
    "bán đảo": ("bán đảo", "sơn trà"),
    "công viên nước": ("công viên nước", "water park"), "cáp treo": ("bà nà", "cáp treo"),
    "du thuyền": ("du thuyền", "cruise"), "đi thuyền": ("thuyền",),
    "thuyền thúng": ("thúng",), "thủy cung": ("thủy cung", "aquarium"),
    "nấu ăn": ("nấu ăn", "cooking"), "lặn": ("lặn", "san hô", "diving"),
}
# Hiking also counts on a viewpoint or attraction that IS a hill climb; the caves
# of Ngũ Hành Sơn are inside that one attraction.
ACTIVITY_EXTRA_CATS = {"núi": ["viewpoint", "attraction"], "leo núi": ["viewpoint", "attraction"],
                       "leo": ["viewpoint", "attraction"], "trekking": ["viewpoint", "attraction"],
                       "hang động": ["attraction"]}
# Wishes that only mean something at an hour: the stop must start inside this window
# (minutes), or the wish is reported unmet. A sunset at nine in the morning is none.
_SUNSET, _SUNRISE = (16 * 60, 18 * 60), (5 * 60, 7 * 60)
ACTIVITY_START = {"ngắm hoàng hôn": _SUNSET, "hoàng hôn": _SUNSET,
                  "ngắm bình minh": _SUNRISE, "bình minh": _SUNRISE}
_WISH_TIERS = {"local", "wish_only"}


def load_pois_json(path: str) -> list[dict]:
    """Read a snapshot pois.json (T061c: shares BE.common.load_json)."""
    data = load_json(path)
    return data["pois"] if isinstance(data, dict) else data


def poi_category(p: dict) -> str:
    return p.get("cat") or canonical_category(p.get("type") or "")


def _overlaps(hours: list[str], ws: int, we: int) -> bool:
    for h in hours or []:
        for interval in h.split(","):
            if interval.count("-") != 1:
                # A stray single-time fragment is not an open interval; skip it as closed.
                continue
            o, c = (part.strip() for part in interval.split("-"))
            try:
                o, c = to_min(o), to_min(c)
            except ValueError:
                continue
            if o <= c and o < we and ws < c:
                return True
            if o > c and (ws < c or o < we):
                return True
    return not hours


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return unicodedata.normalize(
        "NFC", "".join(c for c in s if unicodedata.category(c) != "Mn")
    ).replace("đ", "d")


def _consume(text: str, phrase: str) -> tuple[bool, str]:
    pat = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    out, n = re.subn(pat, " | ", text)
    return n > 0, out


_PHRASES = sorted(ACTIVITY_TYPE_MAP, key=len, reverse=True)


def match_activity(text: str) -> set[str]:
    """One activity string -> canonical groups (empty set = not understood)."""
    rest = " ".join(unicodedata.normalize("NFC", text).lower().split())
    out: set[str] = set()
    for ph in _PHRASES:
        hit, rest = _consume(rest, ph)
        if hit:
            out.update(ACTIVITY_TYPE_MAP[ph])
    rest = _plain(rest)
    for ph in _PHRASES:
        if " " in ph:
            hit, rest = _consume(rest, _plain(ph))
            if hit:
                out.update(ACTIVITY_TYPE_MAP[ph])
    return out


def wanted_types(activities: list[str]) -> set[str]:
    out: set[str] = set()
    for a in activities or []:
        out.update(match_activity(a))
    return out


def _wish_rule(text: str) -> tuple[set[str], tuple[str, ...]]:
    """One activity -> (categories, folded words narrowing them; () = any POI)."""
    rest = " ".join(unicodedata.normalize("NFC", text).lower().split())
    cats: set[str] = set()
    words: list[str] = []
    for ph in _PHRASES:
        hit, rest = _consume(rest, ph)
        if hit and ACTIVITY_TYPE_MAP[ph]:
            cats.update(ACTIVITY_TYPE_MAP[ph])
            cats.update(ACTIVITY_EXTRA_CATS.get(ph, []))
            words.extend(ACTIVITY_WORDS.get(ph, ()))
    return cats or match_activity(text), tuple(words)


def _wish_start(text: str) -> list[int] | None:
    rest = " ".join(unicodedata.normalize("NFC", text).lower().split())
    for phrase, span in ACTIVITY_START.items():
        if _consume(rest, phrase)[0]:
            return list(span)
    return None


def _poi_words(poi: dict) -> tuple[str, str]:
    """Name, type and tags as spaced lower-case words: (accented, folded)."""
    parts = [str(poi.get("name") or ""), str(poi.get("type") or "")]
    parts += [str(t) for t in poi.get("tags") or []]
    text = unicodedata.normalize("NFC", " ".join(parts)).lower()
    spaced = " ".join(re.sub(r"[^\w/ ]+", " ", text).split())
    return f" {spaced} ", f" {fold(spaced)} "


def _has_word(word: str, accented: str, folded: str) -> bool:
    """One syllable must match with its accents: folded, "phố" reads as "phở" and
    "cửa hàng" as a crab. A phrase is long enough to match a name typed without them."""
    if " " in word:
        return f" {fold(word)} " in folded
    return f" {word} " in accented


def poi_fits_wish(poi: dict, text: str) -> bool:
    """Is this POI really what the activity asks for, not just the same category?"""
    cats, words = _wish_rule(text)
    if poi_category(poi) not in cats - NON_ACTIVITY_CATS:
        return False
    if not words:
        return True
    accented, folded = _poi_words(poi)
    return any(_has_word(word, accented, folded) for word in words)


def wish_ids(activities: list[str], pois: list[dict]) -> list[str]:
    """The POIs some activity of the trip really asks for."""
    return [p["poi_id"] for p in pois if any(poi_fits_wish(p, a) for a in activities or [])]


def uncertainty(p: dict) -> list[str]:
    """FR-024/FR-026 labels for unverified fields (never used as fact)."""
    labels = []
    if not p.get("opening_hours"):
        labels.append("gio mo cua chua xac minh")
    if p.get("rating") is None:
        labels.append("rating chua xac minh")
    if not p.get("tags"):
        labels.append("tags chua xac minh")
    # Spend unknown: a paid group with no price band, or a ticketed POI whose
    # ticket price never landed in `fee`.
    ticketed = (p.get("smart_tags") or {}).get("ticket") is True
    if ((poi_category(p) in PAID_CATS and p.get("price_level") is None)
            or (ticketed and not int(p.get("fee") or 0))):
        labels.append("gia chua xac minh")
    return labels


def retrieve(trip: dict, pois: list[dict]) -> dict:
    """Return {"candidates": [{poi_id, reasons[], uncertainty[]}],
    "needs_verification": [{poi_id, reasons[], uncertainty[], must_visit}],
    "excluded": [{poi_id, reason}], "unmatched_activities": [str]}."""
    ws, we = to_min(trip.get("start_time", "07:00")), to_min(trip.get("end_time", "18:00"))
    budget = int(trip.get("budget", 0))
    party = party_size(trip)
    must = set(trip.get("must_visit", []))
    avoid = set(trip.get("avoid", []))
    activities = trip.get("activities", []) or []
    types = wanted_types(activities)
    candidates, needs_verification, excluded = [], [], []
    for p in pois:
        pid = p.get("poi_id")
        if pid in avoid:
            excluded.append({"poi_id": pid, "reason": "avoid"})
            continue
        if not p.get("verified"):
            entry = {"poi_id": pid, "uncertainty": uncertainty(p) + ["poi chua xac minh"],
                     "must_visit": pid in must,
                     "reasons": ["must-visit (cho xac minh, ngoai main plan)"] if pid in must
                     else ["chua xac minh (FR-013)"]}
            needs_verification.append(entry)
            continue
        reasons: list[str] = []
        if pid in must:
            if not _overlaps(p.get("opening_hours", []), ws, we):
                reasons.append("must-visit (ngoai gio mo cua)")
            reasons.append("must-visit")
            candidates.append({"poi_id": pid, "reasons": reasons,
                               "uncertainty": uncertainty(p)})
            continue
        cat = poi_category(p)
        if cat in NON_ACTIVITY_CATS:
            excluded.append({"poi_id": pid, "reason": "khong phai hoat dong"})
            continue
        tier = p.get("plan_tier")
        if tier == "excluded":
            excluded.append({"poi_id": pid, "reason": p.get("plan_tier_reason") or "khong xep vao lich"})
            continue
        if tier in _WISH_TIERS and not any(poi_fits_wish(p, a) for a in activities):
            excluded.append({"poi_id": pid, "reason": "chi xep khi duoc yeu cau"})
            continue
        if (effective_fee(p) or 0) * party > budget:
            excluded.append({"poi_id": pid, "reason": "vuot ngan sach"})
            continue
        if not _overlaps(p.get("opening_hours", []), ws, we):
            excluded.append({"poi_id": pid, "reason": "dong cua trong khung gio"})
            continue
        reasons.append(f"khop hoat dong {cat}" if cat in types else f"loai {cat}")
        candidates.append({"poi_id": pid, "reasons": reasons,
                           "uncertainty": uncertainty(p)})
    return {"candidates": candidates, "needs_verification": needs_verification,
            "excluded": excluded,
            "unmatched_activities": [a for a in activities if not match_activity(a)]}


def activity_requirements(activities: list[str], pool: list[dict],
                          banned: list[dict] | None = None,
                          unaffordable: list[dict] | None = None,
                          horizon: tuple[int, int] | None = None
                          ) -> tuple[list[dict], list[dict]]:
    """Trip activities -> (`required_any` groups, per-activity report).

    One group per understood activity: "at least one of THESE POIs", the ones
    that really fit the wish, so a wish with no matching POI never costs a solver
    run. `banned` is what the day's profile took out of the pool and `unaffordable`
    what the budget did: a wish only they could meet is reported as such, not as
    missing data. Report statuses: "required" (group emitted; the planner later marks
    it met/relaxed), "blocked_by_profile", "over_budget", "no_verified_poi"
    (understood, nothing fits), "outside_trip_hours" (a sunrise on a day that starts
    at eight), "not_understood".
    """
    groups: list[dict] = []
    report: list[dict] = []
    for activity in activities or []:
        cats = sorted(match_activity(activity) - NON_ACTIVITY_CATS)
        if not cats:
            report.append({"activity": activity, "categories": [],
                           "status": "not_understood"})
            continue
        ids = [p["poi_id"] for p in pool if poi_fits_wish(p, activity)]
        if not ids:
            status = ("blocked_by_profile" if any(poi_fits_wish(p, activity) for p in banned or [])
                      else "over_budget" if any(poi_fits_wish(p, activity) for p in unaffordable or [])
                      else "no_verified_poi")
            report.append({"activity": activity, "categories": cats, "status": status})
            continue
        usable = sorted({poi_category(p) for p in pool if p["poi_id"] in set(ids)})
        start = _wish_start(activity)
        if start and horizon and (start[1] <= horizon[0] or start[0] >= horizon[1]):
            report.append({"activity": activity, "categories": cats, "status": "outside_trip_hours",
                           "start_between": start})
            continue
        timed = {"start_between": start} if start else {}
        report.append({"activity": activity, "categories": usable,
                       "status": "required", "poi_ids": ids, **timed})
        group = {"count": 1, "categories": usable, "poi_ids": ids, **timed}
        if group not in groups:
            groups.append(group)
    return groups, report
