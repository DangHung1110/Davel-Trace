"""Hard profile pre-filter (onboarding contract): allergy / must_avoid / accessibility.

Runs BEFORE retrieval and ranking, so a violating POI never reaches the ranker
or the optimizer:

- `allergy[]`: best-effort substring match against the POI's tags / cuisine /
  category / type (never the name alone, never a crash on missing fields).
  An allergen group expands to Vietnamese + English synonyms ("seafood" ->
  "hải sản", "tôm", "cua", ...) so an English onboarding answer still hits
  Vietnamese snapshot tags.
- `must_avoid[]`: same matcher plus a small group table for concepts that are
  categories rather than words ("nightlife", "trek", "spa", "beach", ...).
  "trek"/"adventure" also drops high-effort POIs with no explicit tag.
- `accessibility[]`: mobility rules over intensity + category + stair keywords
  (`wheelchair`, `stroller`, `low_walking`, `no_stairs`).

Every drop is returned as `{"poi_id", "name", "rule", "detail"}` so the router
can surface it as an assumption-style warning instead of silently shrinking
the pool. Unknown keys / missing tags are ignored, never fatal.

Matching notes:
- Terms keep their diacritics when Vietnamese ("cá" must not match "cà phê");
  ASCII terms are matched against a folded copy of the text so "seafood"
  matches "Hải sản". Both use word boundaries.

Taste (soft, NOT a filter): `taste_match` says how much of the profile's
food_prefs a POI carries, and `taste_score` turns that into a signed unit in
[-1, 1] that the ranker and the optimizer add to their own score: +1 full
match, 0 neutral, -1 exclusive cuisine clash (a vegan-only kitchen for a BBQ
lover). Only food POIs (restaurant/cafe/market) can score, so a beach is never
punished for not serving seafood. A clash is a penalty, never a drop: the
allergy/must_avoid rules own the hard exclusions.
"""

from __future__ import annotations

import re
import unicodedata

# --- allergy groups (keys are folded/ASCII) --------------------------------
ALLERGEN_GROUPS: dict[str, tuple[str, ...]] = {
    # NOTE: no bare "cua" (crab) — folded it collides with "cửa hàng" (shop).
    # Only diacritic-bearing Vietnamese seafood words + unambiguous English.
    "seafood": ("hải sản", "seafood", "fish", "shellfish", "cá", "tôm",
                "mực", "ốc", "sò", "hến", "nghêu", "hàu"),
    "shellfish": ("shellfish", "tôm", "mực", "ốc", "sò", "hến",
                  "nghêu", "hàu", "hải sản"),
    "fish": ("fish", "cá", "hải sản"),
    "peanut": ("đậu phộng", "lạc", "peanut"),
    "nut": ("hạt", "hạt điều", "đậu phộng", "lạc", "peanut", "nut", "nuts"),
    "nuts": ("hạt", "hạt điều", "đậu phộng", "lạc", "peanut", "nut", "nuts"),
    "gluten": ("gluten", "bánh mì", "mì", "phở", "bún", "pizza", "pasta"),
    "pork": ("thịt heo", "thịt lợn", "heo", "lợn", "pork"),
    "beef": ("thịt bò", "bò", "beef", "bít tết", "steak"),
    "chicken": ("thịt gà", "gà", "chicken"),
    "spicy": ("cay", "ớt", "spicy", "chili"),
    "dairy": ("sữa", "phô mai", "bơ", "dairy", "milk", "cheese"),
}

# --- must_avoid groups (concepts without a literal tag) ---------------------
AVOID_GROUPS: dict[str, tuple[str, ...]] = {
    "nightlife": ("bar", "nightlife", "quán bar", "quán rượu", "karaoke",
                  "quán bia", "pub", "club"),
    "alcohol": ("rượu", "bia", "cocktail", "alcohol", "bar", "pub"),
    "trek": ("trek", "trekking", "hiking", "leo núi", "leo", "phiêu lưu",
             "mạo hiểm", "adventure"),
    "spa": ("spa", "massage", "mát xa"),
    "beach": ("biển", "beach", "bãi biển"),
    "market": ("chợ", "market"),
    "shopping": ("mua sắm", "shopping", "chợ", "market", "shop", "cửa hàng"),
    "crowd": ("đông", "ồn ào", "crowded", "crowd"),
}
# "trek"/"adventure" is also an effort class: high-intensity outdoor POIs are
# dropped even when the snapshot lacks a "leo núi" tag.
TREK_CATEGORIES = frozenset({"nature", "viewpoint"})
TREK_MIN_INTENSITY = 3

# --- accessibility rules ---------------------------------------------------
MOBILITY_RULES: dict[str, dict] = {
    "wheelchair": {"max_intensity": 1,
                   "exclude_categories": {"nature", "beach", "viewpoint"},
                   "keywords": ("bậc thang", "leo", "núi", "ghềnh", "đỉnh")},
    "stroller": {"max_intensity": 1,
                 "exclude_categories": {"nature", "beach", "viewpoint"},
                 "keywords": ("bậc thang", "leo", "núi", "ghềnh", "đỉnh")},
    "low_walking": {"max_intensity": 2,
                    "exclude_categories": {"nature", "viewpoint"},
                    "keywords": ("bậc thang", "leo", "ghềnh", "đỉnh")},
    "no_stairs": {"max_intensity": 2,
                  "exclude_categories": {"nature", "viewpoint"},
                  "keywords": ("bậc thang", "leo", "ghềnh", "đỉnh")},
}

RULE_LABELS = {
    "allergy": "di ung",
    "must_avoid": "muon tranh",
    "accessibility": "kha nang tiep can",
}


def fold(text: str) -> str:
    """Lowercase + strip Vietnamese diacritics (đ -> d kept manually)."""
    text = str(text or "").replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _words(*parts) -> str:
    """Flatten str/list fields into one lowercase haystack (missing-safe)."""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, (list, tuple, set)):
            chunks.extend(str(x) for x in part if x is not None)
    return " ".join(chunks).lower()


def haystack(poi: dict | None) -> tuple[str, str]:
    """(original lowercase, folded) text used for term matching."""
    poi = poi or {}
    text = _words(poi.get("tags"), poi.get("cuisine"), poi.get("type"),
                  poi.get("cat"), poi.get("ambience"),
                  (poi.get("smart_tags") or {}).get("party"))
    return text, fold(text)


def _pattern(term: str) -> re.Pattern | None:
    term = str(term or "").strip()
    if len(term) < 2:
        return None
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")


def _match_terms(terms, text: str, folded: str) -> str | None:
    """First term found in the haystack (word boundary), else None."""
    for term in terms:
        raw = str(term or "").strip().lower()
        if not raw:
            continue
        # Vietnamese terms carry diacritics: match the original text only so
        # "cá" never collides with "cà phê". ASCII terms match the folded copy.
        needle, source = (raw, text) if not raw.isascii() else (fold(raw), folded)
        pattern = _pattern(needle)
        if pattern is not None and pattern.search(source):
            return raw
    return None


def has_word(text: str, words) -> bool:
    """Whole-word `words` hit in an already-folded `text` (never substring:
    "bar" must not fire on "barbecue", "pub" on "public")."""
    for word in words:
        pattern = _pattern(fold(str(word or "")))
        if pattern is not None and pattern.search(text or ""):
            return True
    return False


def terms_for(term: str, groups: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Expand a user term through its group table (unknown term = itself)."""
    raw = str(term or "").strip()
    return groups.get(fold(raw), (raw,))


def matches(poi: dict, term: str, groups: dict[str, tuple[str, ...]] | None = None
            ) -> str | None:
    """Matched term (for the warning) or None. Never raises on bad POI data."""
    text, folded = haystack(poi)
    return _match_terms(terms_for(term, groups or {}), text, folded)


def taste_match(poi: dict, prefs: list[str] | None) -> tuple[float, list[str]]:
    """Share of food prefs present on the POI (+ the hits) for the taste bonus.

    Unlike the allergy filter this also reads the POI name: a vegan kitchen
    tagged only "Nhà hàng" still says "chay"/"vegan" in its name, and a taste
    bonus is a positive nudge (a false hit costs nothing, unlike an allergy).
    """
    poi = poi or {}
    text, folded = haystack(poi)
    name = str(poi.get("name") or "").lower()
    text, folded = f"{text} {name}".strip(), f"{folded} {fold(name)}".strip()
    hits: list[str] = []
    for pref in prefs or []:
        hit = _match_terms(terms_for(pref, {}), text, folded)
        if hit and hit not in hits:
            hits.append(hit)
    total = len([p for p in (prefs or []) if str(p).strip()])
    return (len(hits) / total if total else 0.0), hits


# --- cuisine classes: a taste hit is not the only taste signal --------------
# A POI can have NO term of the user's preference and still be a bad match:
# a vegan-only kitchen for a BBQ lover. ``CUISINE_CLASSES`` groups the
# vocabulary so both sides (POI text, profile food_prefs) can be reduced to a
# small set of classes, and ``CUISINE_CONFLICTS`` says which pairs are a real
# clash. The table is deliberately narrow: "seafood" vs "Vietnamese" is not a
# conflict (it is merely unproven), "vegan-only" vs "bbq/meat/seafood" is.
CUISINE_CLASSES: dict[str, tuple[str, ...]] = {
    "seafood": ("hải sản", "hai san", "seafood", "fish", "shellfish",
                "tôm", "cá", "mực", "ốc", "sò", "hến", "nghêu", "hàu"),
    "vegan": ("chay", "vegan", "vegetarian", "thuần chay", "thuan chay"),
    "bbq": ("bbq", "nướng", "nuong", "grill", "barbecue", "bít tết",
            "bit tet", "steak", "thịt nướng", "thit nuong"),
    "meat": ("thịt", "thit", "bò", "heo", "gà", "pork", "beef",
             "chicken", "steak"),
}
# POI class -> preference classes it contradicts (a *soft* mismatch, never a
# drop: the allergy/must_avoid filter owns hard exclusions).
CUISINE_CONFLICTS: dict[str, frozenset[str]] = {
    "vegan": frozenset({"bbq", "meat", "seafood"}),
    "bbq": frozenset({"vegan"}),
    "meat": frozenset({"vegan"}),
    "seafood": frozenset({"vegan"}),
}
# Additive taste unit is [-1, 1]: +1 = every pref found on the POI, -1 = the
# POI is an exclusive clash (vegan-only venue for a BBQ/seafood eater).
TASTE_MISMATCH = 1.0


def cuisine_classes(text: str) -> set[str]:
    """Cuisine classes present in a (raw, diacritics kept) text."""
    folded = fold(text)
    found: set[str] = set()
    for name, terms in CUISINE_CLASSES.items():
        if _match_terms(terms, str(text or "").lower(), folded):
            found.add(name)
    return found


def cuisine_terms(text: str) -> list[str]:
    """Cuisine words named in free text ("ăn hải sản" -> ["hải sản"]).

    Lets a food wish that arrived as an activity reach the taste bonus the
    same way a `food_prefs` entry does.
    """
    raw = str(text or "").lower()
    folded = fold(raw)
    found: list[str] = []
    for terms in CUISINE_CLASSES.values():
        hit = _match_terms(terms, raw, folded)
        if hit and hit not in found:
            found.append(hit)
    return found


def poi_cuisine(poi: dict) -> set[str]:
    """Cuisine classes of a POI (tags/cuisine/type/cat/ambience/name)."""
    poi = poi or {}
    text = _words(poi.get("tags"), poi.get("cuisine"), poi.get("type"),
                  poi.get("cat"), poi.get("ambience"), poi.get("name"))
    return cuisine_classes(text)


def taste_score(poi: dict, prefs: list[str] | None
                ) -> tuple[float, list[str], list[str]]:
    """Signed taste unit in [-1, 1] for the optimizer / ranker.

    (+1) every food pref is on the POI, (0) neutral / not a food POI / no
    prefs, (-1) an exclusive cuisine clash (vegan-only venue for a BBQ lover).
    Returns (unit, hits, clashes) so callers can explain the number.

    The half-step (+/-) is deliberate: a partial hit (1 of 2 prefs) outscores
    no hit without beating a full match, so the ranking stays continuous.
    """
    poi = poi or {}
    prefs = [str(p) for p in (prefs or []) if str(p).strip()]
    if not prefs or not is_food_poi(poi):
        return 0.0, [], []
    ratio, hits = taste_match(poi, prefs)
    poi_cls = poi_cuisine(poi)
    pref_cls = cuisine_classes(" ".join(prefs))
    # A clash only exists when the POI serves NOTHING the profile asked for
    # (a seafood-and-vegan profile must not flag a seafood kitchen as vegan-
    # exclusive). Overlap wins; exclusivity is what the table describes.
    if poi_cls & pref_cls:
        return round(ratio, 4), hits, []
    clashes = sorted(c for c in poi_cls
                     if pref_cls & CUISINE_CONFLICTS.get(c, frozenset()))
    if clashes:
        return -TASTE_MISMATCH, hits, clashes
    return round(ratio, 4), hits, []


def is_food_poi(poi: dict | None) -> bool:
    """Taste only applies to what you can eat (restaurant/cafe/market)."""
    poi = poi or {}
    cat = str(poi.get("cat") or poi.get("type") or "").strip().lower()
    return cat in ("restaurant", "cafe", "market")


def _allergy_drop(poi: dict, allergy: list[str]) -> dict | None:
    for term in allergy or []:
        hit = matches(poi, term, ALLERGEN_GROUPS)
        if hit:
            return {"rule": "allergy", "detail": f"di ung '{term}' (khop '{hit}')"}
    return None


def _avoid_drop(poi: dict, must_avoid: list[str]) -> dict | None:
    category = str(poi.get("cat") or poi.get("type") or "").strip().lower()
    for term in must_avoid or []:
        key = fold(term)
        # High-effort outdoor POIs count as trek/adventure even without a tag.
        if key in ("trek", "trekking", "hiking", "adventure") and (
                category in TREK_CATEGORIES
                or int(poi.get("intensity") or 0) >= TREK_MIN_INTENSITY):
            return {"rule": "must_avoid",
                    "detail": f"tranh '{term}' (loai {category or '?'})"}
        hit = matches(poi, term, AVOID_GROUPS)
        if hit:
            return {"rule": "must_avoid", "detail": f"tranh '{term}' (khop '{hit}')"}
    return None


def _accessibility_drop(poi: dict, accessibility: list[str]) -> dict | None:
    category = str(poi.get("cat") or poi.get("type") or "").strip().lower()
    intensity = int(poi.get("intensity") or 2)
    text, folded = haystack(poi)
    for raw in accessibility or []:
        rule = MOBILITY_RULES.get(fold(raw))
        if rule is None:
            continue
        if category in rule["exclude_categories"]:
            return {"rule": "accessibility",
                    "detail": f"'{raw}': loai {category} khong phu hop"}
        if intensity > rule["max_intensity"]:
            return {"rule": "accessibility",
                    "detail": f"'{raw}': cuong do {intensity} qua cao"}
        hit = _match_terms(rule["keywords"], text, folded)
        if hit:
            return {"rule": "accessibility",
                    "detail": f"'{raw}': co dau hieu '{hit}'"}
    return None


def drop_reason(poi: dict, profile: dict | None) -> dict | None:
    """First hard-profile violation for `poi`, or None to keep it."""
    profile = profile or {}
    return (_allergy_drop(poi, profile.get("allergy") or [])
            or _avoid_drop(poi, profile.get("must_avoid") or [])
            or _accessibility_drop(poi, profile.get("accessibility") or []))


def hard_filter(pois: list[dict], profile: dict | None) -> tuple[list[dict], list[dict]]:
    """(kept, drops) — drops carry poi_id/name/rule/detail for warnings."""
    profile = profile or {}
    if not any(profile.get(k) for k in ("allergy", "must_avoid", "accessibility")):
        return list(pois), []
    kept, drops = [], []
    for poi in pois:
        reason = drop_reason(poi, profile)
        if reason is None:
            kept.append(poi)
            continue
        drops.append({"poi_id": poi.get("poi_id"),
                      "name": poi.get("name") or "",
                      **reason})
    return kept, drops


def warning(drop: dict) -> str:
    """One assumption-style line for the plan's `warnings` list."""
    label = RULE_LABELS.get(drop.get("rule"), drop.get("rule", "profile"))
    name = drop.get("name") or drop.get("poi_id")
    return f"da loai {name} ({label}): {drop.get('detail', '')}"
