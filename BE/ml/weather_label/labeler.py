"""Weather labeler indoor/outdoor + rain protection (T063, lane A).

Two layers live here:

* **v1 legacy rules** (`featurize`/`label`/`label_element`) kept API-compatible
  for the existing smoke tests/wiring.  They are the old blanket rule path.
* **v2 snapshot-POI classifier** (`classify_poi`) which is pure, deterministic
  and audit-safe.  It accepts an optional human I/O/B audit + optional OSM
  element/geometry evidence and returns auditable space/rain fields.

Additionally (T063b) `classify_poi` derives continuous exposure attributes
(`outdoor_exposure`, `sun_exposure`, `wind_exposure`, `rain_cover`) with the
precedence human audit > OSM evidence > canonical type default > unknown.  The
old categorical `space`/`rain_protection` fields stay for compatibility, but
the continuous fields are the signal PATM features consume.  Their 0..1 values
are coarse rule anchors, NOT calibrated measurements.

Confidence is a HEURISTIC, UNCALIBRATED rule strength -- NOT a probability and
NOT an accuracy claim.  The real eval (macro-F1 >= 0.95 on human I/O/B labels)
is still PENDING; no GBDT is trained or required by this module.

Design rules (OSM Wiki):
* Rain protection (R1/R2/none) is asserted from linked OSM evidence ONLY.
  The human audit, name keywords and canonical category decide ``space`` (and
  the legacy ``weather_sensitive`` semantics); they never assert rain.
* ``indoor=yes`` / ``location=indoor`` / ``enclosed=yes`` or a linked/containing
  *actual* building polygon -> R1 ``enclosed``.
* ``building=roof`` / ``covered=yes`` / a qualifying
  ``amenity=shelter|weather_shelter`` / explicit roof-awning-canopy tags
  (including ``weather_protection=roof|awning|canopy``) -> R2 ``sheltered``
  (never enclosed).
* Sun-only tags (shade, trees, parasol, ``shelter_type=sun_shelter``,
  sun shelter/pergola) are NOT rain protection, even alongside
  ``amenity=shelter``.
* A clear open feature can be ``none``; absent evidence is ``unknown``, not
  proof that there is no cover.
* A node-only OSM cache is not geometry, and ``type=way`` alone is not a
  polygon.  Actual vertices/containment or explicit linked-polygon metadata
  must be supplied; mere proximity is never enough.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SPACE_LABELS = ("indoor", "outdoor", "both", "unknown")
RAIN_LABELS = ("enclosed", "sheltered", "none", "unknown")

#: Heuristic tiers.  These are rule strengths, not calibrated probabilities.
CONF_AUDIT = 1.0
CONF_OSM_NAME = 0.8
CONF_OSM = 0.7
CONF_NAME = 0.6
CONF_CANONICAL = 0.4
CONF_CONFLICT = 0.3

# ---------------------------------------------------------------------------
# Continuous exposure attributes (T063b)
# ---------------------------------------------------------------------------
#: smart_tags fields replacing the dead low-variance space/rain labels as the
#: signal PATM consumes.  The floats are coarse 0 (sheltered/none) .. 1 (fully
#: exposed) ANCHORS, not measurements: no calibration claim is made.
EXPOSURE_FIELDS = ("outdoor_exposure", "sun_exposure", "wind_exposure",
                   "rain_cover")
RAIN_COVER_LABELS = ("enclosed", "covered", "mixed", "open", "unknown")

#: Canonical category -> (outdoor, sun, wind, rain_cover) coarse preset.
#: Mixed-use categories (attraction/landmark/market) stay intermediate: they
#: are never forced indoor or fully open.
TYPE_EXPOSURE = {
    "beach": (0.95, 0.95, 0.95, "open"),
    "nature": (0.9, 0.8, 0.75, "open"),
    "park": (0.85, 0.75, 0.6, "open"),
    "landmark": (0.6, 0.55, 0.5, "mixed"),
    "attraction": (0.55, 0.55, 0.45, "mixed"),
    "market": (0.65, 0.5, 0.45, "mixed"),
    "transport": (0.5, 0.5, 0.6, "mixed"),
    "museum": (0.05, 0.05, 0.05, "enclosed"),
    "restaurant": (0.15, 0.15, 0.15, "enclosed"),
    "cafe": (0.2, 0.2, 0.2, "enclosed"),
    "bar": (0.2, 0.15, 0.15, "enclosed"),
    "spa": (0.05, 0.05, 0.05, "enclosed"),
    "lodging": (0.1, 0.1, 0.1, "enclosed"),
    "shop": (0.05, 0.05, 0.05, "enclosed"),
}

#: Coarse presets for the three evidence tiers.  "unknown" keeps the neutral
#: 0.5 floats (a float cannot encode absence) and rain_cover="unknown".
_AUDIT_EXPOSURE = {
    "indoor": (0.05, 0.0, 0.0, "enclosed"),
    "both": (0.5, 0.4, 0.4, "mixed"),
    "outdoor": (0.95, 0.9, 0.95, "open"),
}
_OSM_SPACE_EXPOSURE = {
    "indoor": (0.1, 0.05, 0.05, "enclosed"),
    "both": (0.5, 0.45, 0.45, "mixed"),
    "outdoor": (0.9, 0.85, 0.85, "open"),
}
_OSM_RAIN_EXPOSURE = {
    "enclosed": (0.1, 0.05, 0.05, "enclosed"),
    "sheltered": (0.7, 0.35, 0.45, "covered"),
    "none": (0.9, 0.85, 0.85, "open"),
}
_OSM_RAIN_COVER = {"enclosed": "enclosed", "sheltered": "covered",
                   "none": "open"}
_NEUTRAL_EXPOSURE = (0.5, 0.5, 0.5, "unknown")


def _resolve_exposure(tier: tuple) -> dict:
    outdoor, sun, wind, rain = tier
    return {"outdoor_exposure": round(float(outdoor), 3),
            "sun_exposure": round(float(sun), 3),
            "wind_exposure": round(float(wind), 3),
            "rain_cover": rain}


def type_exposure(cat: str) -> dict:
    """Coarse exposure preset for a canonical category.

    Used as the ``type default`` tier by :func:`derive_exposure` and by PATM
    features when a POI has not been enriched yet.  Unknown categories return
    the neutral 0.5/``unknown`` preset.
    """
    preset = TYPE_EXPOSURE.get(str(cat or "").strip().lower())
    return _resolve_exposure(preset or _NEUTRAL_EXPOSURE)


def derive_exposure(*, audit_space: str | None = None,
                    osm_space: str | None = None,
                    osm_rain: str | None = None,
                    cat: str = "") -> dict:
    """Derive continuous exposure attributes with a strict precedence.

    ``human audit > OSM evidence > canonical type default > unknown``.

    * ``outdoor_exposure`` / ``sun_exposure`` / ``wind_exposure`` are floats in
      [0, 1]; ``unknown`` maps to the neutral 0.5 (a float cannot encode
      absence).
    * ``rain_cover`` is categorical: enclosed | covered | mixed | open |
      unknown.
    * Mixed-use categories (attraction/landmark/market) get intermediate
      values; they are never forced indoor.
    * ``rain_cover`` in {enclosed, covered} caps sun/wind exposure, because a
      roof blocks both.
    """
    source = "unknown"
    audit_space = str(audit_space or "").strip().lower()
    osm_space = str(osm_space or "").strip().lower()
    osm_rain = str(osm_rain or "").strip().lower()

    if audit_space in _AUDIT_EXPOSURE:
        base = _resolve_exposure(_AUDIT_EXPOSURE[audit_space])
        source = "audit"
    elif osm_space in _OSM_SPACE_EXPOSURE:
        base = _resolve_exposure(_OSM_SPACE_EXPOSURE[osm_space])
        source = "osm"
    elif osm_rain in _OSM_RAIN_EXPOSURE:
        base = _resolve_exposure(_OSM_RAIN_EXPOSURE[osm_rain])
        source = "osm"
    else:
        preset = TYPE_EXPOSURE.get(str(cat or "").strip().lower())
        if preset is None:
            base = _resolve_exposure(_NEUTRAL_EXPOSURE)
        else:
            base = _resolve_exposure(preset)
            source = "type"

    # OSM rain evidence sharpens rain_cover unless a human audit already spoke.
    if source != "audit" and osm_rain in _OSM_RAIN_COVER:
        base["rain_cover"] = _OSM_RAIN_COVER[osm_rain]
        source = "osm"

    if base["rain_cover"] == "enclosed":
        base["sun_exposure"] = min(base["sun_exposure"], 0.05)
        base["wind_exposure"] = min(base["wind_exposure"], 0.1)
    elif base["rain_cover"] == "covered":
        base["sun_exposure"] = min(base["sun_exposure"], 0.25)
        base["wind_exposure"] = min(base["wind_exposure"], 0.35)

    return {**base, "exposure_source": source}


_RAIN_PRIORITY = {"enclosed": 3, "sheltered": 2, "none": 1, "unknown": 0}
_SOURCE_PRIORITY = {"audit": 4, "osm": 3, "name": 2, "canonical": 1, "unknown": 0}

# ---------------------------------------------------------------------------
# v1 legacy rules (kept compatible; do not rely on these for audit-safe work)
# ---------------------------------------------------------------------------

OUTDOOR_TAGS = {
    "tourism": {"viewpoint", "attraction", "artwork", "camp_site", "picnic_site"},
    "leisure": {"park", "garden", "beach", "stadium", "playground", "water_park",
                "nature_reserve", "common"},
    "amenity": {"marketplace"},
    "historic": {"memorial", "monument", "ruins", "archaeological_site"},
}
INDOOR_TAGS = {
    "tourism": {"museum", "hotel", "hostel", "motel", "guest_house", "apartment",
                "information", "gallery", "aquarium"},
    "leisure": {"amusement_arcade", "fitness_centre", "sports_hall"},
    "amenity": {"cafe", "restaurant", "museum", "food_court", "internet_cafe",
                "place_of_worship", "shrine", "marketplace"},
    "historic": {"wayside_shrine"},
    "shop": {"mall", "coffee", "books", "department_store"},
}
OUTDOOR_WORDS = ("bien", "beach", "cong vien", "park", "cau", "bridge",
                 "cho ", "market", "nui", "de o", "dao")
INDOOR_WORDS = ("bao tang", "museum", "cafe", "ca phe", "nha hang",
                "restaurant", "chua", "nha tho", "khu vui choi trong nha")


def _norm(s: str) -> str:
    """Lowercase, strip Vietnamese accents and convert ``đ`` -> ``d``."""
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def fold_text(s: str) -> str:
    """Public alias of the accent-folding normalizer (name joins)."""
    return _norm(s)


def featurize(el: dict, dn_category: str = "") -> dict:
    """Feature dict for one OSM element (+ optional DN category)."""
    tags = el.get("tags", {}) if isinstance(el, dict) else {}
    name = _norm(tags.get("name", ""))
    return {
        "tourism": tags.get("tourism", ""),
        "leisure": tags.get("leisure", ""),
        "amenity": tags.get("amenity", ""),
        "historic": tags.get("historic", ""),
        "shop": tags.get("shop", ""),
        "has_building_polygon": bool(el.get("type") == "way" and
                                     ("building" in tags or el.get("nodes"))),
        "area_m2": 0.0,  # ways geometry later (documented gap)
        "dn_category": dn_category,
        "name_hit_outdoor": any(w in name for w in OUTDOOR_WORDS),
        "name_hit_indoor": any(w in name for w in INDOOR_WORDS),
    }


def label(feat: dict) -> dict:
    """Legacy deterministic rules -> {label, confidence (heuristic), rule}."""
    for key, values in OUTDOOR_TAGS.items():
        if feat.get(key) in values:
            return {"label": "outdoor", "confidence": 0.9,
                    "rule": f"tag {key}={feat[key]}"}
    for key, values in INDOOR_TAGS.items():
        if feat.get(key) in values:
            return {"label": "indoor", "confidence": 0.9,
                    "rule": f"tag {key}={feat[key]}"}
    if feat.get("name_hit_outdoor"):
        return {"label": "outdoor", "confidence": 0.7, "rule": "name-keyword"}
    if feat.get("name_hit_indoor"):
        return {"label": "indoor", "confidence": 0.7, "rule": "name-keyword"}
    return {"label": "indoor", "confidence": 0.5, "rule": "default-indoor"}


def label_element(el: dict, dn_category: str = "") -> dict:
    """Legacy single-element labeler (kept for v1 smoke/wiring)."""
    feat = featurize(el, dn_category)
    return {**label(feat), "features": feat}


def weather_evidence(poi_name: str, result: dict) -> list[str]:
    """Evidence strings for validator/explainer wiring (phase-PR)."""
    return [f"{poi_name}: {result['label']} ({result['rule']}, "
            f"conf {result['confidence']})"]


def train_gbdt(X, y, seed: int = 7):
    """Legacy GBDT hook.  NOT used by `classify_poi`; no training in this step."""
    import lightgbm as lgb
    import numpy as np
    dtr = lgb.Dataset(np.array(X, dtype=float), np.array(y, dtype=float))
    return lgb.train({"objective": "binary", "verbosity": -1, "seed": seed,
                      "min_data_in_leaf": 5, "num_leaves": 15},
                     dtr, num_boost_round=100)


# ---------------------------------------------------------------------------
# v2 snapshot-POI classifier
# ---------------------------------------------------------------------------

# Text hints.  Normalised (accent-free) values; multi-word hits are substrings,
# single-word hits require token boundaries (so "park" does not hit "parking").
_NAME_INDOOR = (
    "bao tang", "museum", "nha hang", "restaurant", "quan an", "cafe", "ca phe",
    "coffee", "bar", "pub", "khach san", "hotel", "resort", "homestay",
    "nha tho", "church", "chua", "pagoda", "temple", "mall",
    "trung tam thuong mai", "sieu thi", "supermarket", "rap chieu phim",
    "cinema", "thu vien", "library", "spa", "karaoke", "cua hang", "shop",
    "gallery", "aquarium", "nha hat",
)
_NAME_OUTDOOR = (
    "bai bien", "bai tam", "beach", "cong vien", "park", "nui", "mountain",
    "dao", "island", "thac", "waterfall", "quang truong", "square", "plaza",
    "cau", "bridge", "song", "river", "rung", "forest", "deo", "pass",
    "duong dao", "promenade", "ben tau", "hang dong", "cave", "memorial",
    "dai tuong niem", "tuong dai",
)
_NAME_SUN_ONLY = (
    "pergola", "gian hoa", "parasol", "sun shade", "sun shelter", "umbrella",
    "du che nang", "shade",
)
_NAME_AMBIGUOUS = (
    "diem tham quan", "khu du lich", "tham quan", "attraction", "landmark",
    "market", "cho dem", "cho dau moi",
)
#: Names that denote a compound with both indoor and outdoor visit space.
#: Checked before indoor/outdoor so a pagoda/church/beer garden is not forced
#: into a single space.
_NAME_BOTH = (
    "chua", "nha tho", "beer garden", "bia san vuon", "san vuon bia", "cho",
)

# Canonical snapshot categories (`poi["cat"]`).
_CAT_INDOOR = {"restaurant", "cafe", "bar", "spa", "lodging", "museum", "shop"}
_CAT_OUTDOOR = {"beach", "nature", "park"}
_CAT_AMBIGUOUS = {"landmark", "attraction", "market"}

# OSM tag categories.
_OSM_INDOOR = {
    "tourism": {"museum", "hotel", "hostel", "motel", "guest_house", "apartment",
                "information", "gallery", "aquarium"},
    "leisure": {"amusement_arcade", "fitness_centre", "sports_hall", "indoor_play"},
    "amenity": {"cafe", "restaurant", "food_court", "internet_cafe",
                "place_of_worship", "library", "cinema", "theatre", "bank",
                "pharmacy", "hospital", "school", "university", "kindergarten"},
    "historic": {"wayside_shrine"},
}
_OSM_OUTDOOR = {
    "tourism": {"viewpoint", "camp_site", "picnic_site", "zoo", "theme_park"},
    "leisure": {"park", "garden", "beach", "stadium", "playground", "water_park",
                "nature_reserve", "common"},
    "historic": {"memorial", "monument", "ruins", "archaeological_site"},
    "natural": {"beach", "peak", "waterfall", "spring", "cave_entrance"},
}
_OSM_AMBIGUOUS = {
    "tourism": {"attraction", "artwork"},
    "amenity": {"marketplace", "market"},
    "historic": {"landmark"},
    "natural": {"cave", "tree"},
}
_OSM_OPEN = {
    "tourism": {"viewpoint", "camp_site", "picnic_site"},
    "leisure": {"park", "garden", "beach", "playground", "nature_reserve", "common"},
    "natural": {"beach", "peak", "waterfall", "spring"},
    "historic": {"memorial", "monument", "ruins", "archaeological_site"},
}

_OSM_SHELTER_AMENITIES = {"shelter", "weather_shelter"}
_OSM_SUN_ONLY_TAGS = (
    ("shade", "yes"),
    ("natural", "tree"),
    ("man_made", "pergola"),
    ("leisure", "pergola"),
    ("pergola", "yes"),
    ("parasol", "yes"),
    ("sun_shelter", "yes"),
    ("shelter", "sun"),
    ("shelter_type", "sun_shelter"),
)


def _as_bool(value) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y"}


def _tokenize(text: str) -> list[tuple[str, str]]:
    """Vietnamese-aware tokens as (NFC lowercase raw, accent-folded).

    Keeping the raw token lets the matcher reject accent-only look-alikes such
    as ``Đào`` (address) vs ``đảo`` (island) or ``sống`` (fresh) vs ``sông``
    (river) that plain diacritic stripping would conflate.
    """
    raw_text = unicodedata.normalize("NFC", str(text or "").lower())
    return [(m.group(0), _norm(m.group(0)))
            for m in re.finditer(r"[^\W_]+", raw_text, re.UNICODE)]


#: For single-word keywords whose folded form is ambiguous in Vietnamese,
#: only these accented spellings may match.  Unaccented input still matches.
_ACCENT_GUARD = {
    "dao": {"đảo"},       # island, not Đào (address/person)
    "cau": {"cầu"},       # bridge, not cậu/cấu
    "song": {"sông"},     # river, not sống (fresh/live)
    "bien": {"biển"},     # sea, not biên (border)
    "nui": {"núi"},       # mountain, not nữa
    "chua": {"chùa"},     # pagoda, not chứa/chua (sour)
    "cho": {"chợ"},       # market, not cho (give)
    "thac": {"thác"},     # waterfall, not thách
    "suoi": {"suối"},     # stream, not suôi
    "deo": {"đèo"},       # pass, not dẻo
    "ho": {"hồ"},         # lake, not hô/hó
    "dinh": {"đình"},     # communal house
    "den": {"đền"},       # temple/shrine
}


def _accent_ok(raw: str, folded: str) -> bool:
    allowed = _ACCENT_GUARD.get(folded)
    if not allowed:
        return True
    return raw == folded or raw in allowed


def _has_kw(text: str, kw: str) -> bool:
    """Match a folded keyword against Vietnamese-aware word tokens.

    Multi-word keywords match a contiguous folded token sequence; single-word
    keywords additionally pass :func:`_accent_ok`.
    """
    kw_tokens = [t for t in _norm(kw).split() if t]
    if not kw_tokens:
        return False
    tokens = _tokenize(text)
    folded = [f for _, f in tokens]
    if len(kw_tokens) == 1:
        key = kw_tokens[0]
        return any(f == key and _accent_ok(raw, f) for raw, f in tokens)
    width = len(kw_tokens)
    return any(folded[i:i + width] == kw_tokens
               for i in range(len(folded) - width + 1))


def _hit(text: str, words) -> list[str]:
    return [w for w in words if _has_kw(text, w)]


def _tag_dict(el: dict) -> dict:
    tags = el.get("tags") or {}
    return tags if isinstance(tags, dict) else {}


def _poi_name(poi: dict) -> str:
    """Original (accent-preserving) name, used for Vietnamese-aware matching."""
    return str(poi.get("name") or poi.get("name_en") or "")


def _poi_anchor(poi: dict) -> tuple[float | None, float | None]:
    try:
        lat = float(poi["lat"])
        lon = float(poi["lon"])
    except (KeyError, TypeError, ValueError):
        return None, None
    return lat, lon


def _parse_audit(audit, poi: dict) -> tuple[str | None, str | None, str | None]:
    """Return (space, origin, invalid_text) from an explicit audit or io_label."""
    raw = audit
    origin = "audit"
    if isinstance(raw, dict):
        raw = (raw.get("label") or raw.get("space") or raw.get("io_label")
               or raw.get("io"))
    if raw is None:
        raw = poi.get("io_label")
        origin = "snapshot io_label" if raw is not None else None
    if raw is None:
        return None, None, None
    key = _norm(str(raw)).strip()
    mapping = {
        "i": "indoor", "indoor": "indoor",
        "o": "outdoor", "outdoor": "outdoor",
        "b": "both", "both": "both",
    }
    if key not in mapping:
        return None, origin, str(raw)
    return mapping[key], origin, None


def _iter_osm(osm):
    if osm is None:
        return []
    if isinstance(osm, (list, tuple)):
        out = []
        for item in osm:
            out.extend(_iter_osm(item))
        return out
    if isinstance(osm, dict):
        if isinstance(osm.get("elements"), (list, tuple)):
            out = []
            for item in osm["elements"]:
                out.extend(_iter_osm(item))
            return out
        return [osm]
    return []


def _split_wrapper(item: dict) -> tuple[dict, dict]:
    """Accept a raw Overpass element or a {element, name_linked, ...} wrapper."""
    if not isinstance(item, dict):
        return item, {}
    if isinstance(item.get("element"), dict):
        el = dict(item["element"])
        meta = {k: item[k] for k in ("name_linked", "point_in_polygon", "linked")
                if k in item}
        if "tags" in item and "tags" not in el:
            el["tags"] = item["tags"]
        if "geometry" in item and "geometry" not in el:
            el["geometry"] = item["geometry"]
        return el, meta
    meta = {k: item[k] for k in ("name_linked", "point_in_polygon", "linked")
            if k in item}
    return item, meta


def _geometry_points(el: dict) -> list[tuple[float, float]] | None:
    """Return polygon vertices as (lat, lon), or None for node/absent geometry."""
    if el.get("type") == "node":
        return None  # a node point is NOT polygon geometry
    geom = el.get("geometry")
    if geom is None:
        geom = el.get("coordinates")
    if isinstance(geom, dict) and isinstance(geom.get("coordinates"), (list, tuple)):
        geom = geom["coordinates"]
    # Unwrap a single GeoJSON polygon ring: [[[lon, lat], ...]].
    if (isinstance(geom, (list, tuple)) and len(geom) == 1
            and isinstance(geom[0], (list, tuple)) and geom[0]
            and isinstance(geom[0][0], (list, tuple))):
        geom = geom[0]
    if not isinstance(geom, (list, tuple)) or len(geom) < 3:
        return None
    points: list[tuple[float, float]] = []
    for point in geom:
        try:
            if isinstance(point, dict):
                points.append((float(point["lat"]), float(point["lon"])))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                a, b = float(point[0]), float(point[1])
                # GeoJSON-style [lon, lat] unless the second value is the only
                # valid latitude (common [lat, lon] input).
                if abs(a) <= 90 and abs(b) > 90:
                    points.append((a, b))
                else:
                    points.append((b, a))
            else:
                return None
        except (KeyError, TypeError, ValueError):
            return None
    return points


def _point_in_polygon(lat: float, lon: float,
                      polygon: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (
                lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _element_link(poi: dict, el: dict, meta: dict):
    """Return (linked, contains, polygon, reason)."""
    tags = _tag_dict(el)
    names = [tags.get("name"), tags.get("name:en"), tags.get("alt_name"),
             tags.get("official_name")]
    poi_names = {_norm(poi.get("name", "")), _norm(poi.get("name_en", ""))}
    poi_names.discard("")
    name_match = any(_norm(n) in poi_names for n in names if n)
    polygon = _geometry_points(el)
    lat, lon = _poi_anchor(poi)
    contains = bool(polygon and lat is not None and lon is not None
                    and _point_in_polygon(lat, lon, polygon))
    explicit = any(_as_bool(meta.get(k)) for k in
                   ("name_linked", "point_in_polygon", "linked"))
    linked = explicit or name_match or contains
    el_name = next((_norm(n) for n in names if n), "")
    if linked:
        return True, contains, polygon, "linked"
    if el_name and poi_names:
        return False, contains, polygon, "different name / no containment"
    if polygon is not None:
        # An anonymous polygon that does not contain the POI is a nearby
        # feature, not evidence for this POI ("no inference from proximity").
        return False, contains, polygon, "polygon does not contain POI"
    # A caller-supplied node/tag element with no name and no geometry is the
    # matched element; trust its direct tags, but never invent geometry.
    return True, contains, polygon, "anonymous caller-supplied element"


def _polygon_evidence(el: dict, meta: dict, polygon,
                      linked: bool) -> bool:
    """True only for actual polygon vertices or explicit linked metadata.

    ``type=way``/``type=relation`` on its own is NOT geometry: an OSM way may
    reference nodes that were never fetched.  Callers that resolved a polygon
    outside the element payload can say so explicitly with
    ``point_in_polygon``/``name_linked``.
    """
    if polygon is not None and linked:
        return True
    if el.get("type") in {"way", "relation"}:
        return (_as_bool(meta.get("point_in_polygon"))
                or _as_bool(meta.get("name_linked")))
    return False


def _candidate(label: str, source: str, conf: float, evidence: str,
               priority: int = 0) -> dict:
    return {"label": label, "source": source, "conf": conf,
            "evidence": evidence, "priority": priority}


def _scan_osm_space(poi: dict, el: dict, meta: dict):
    """Return (candidates, conflicts, notes)."""
    tags = _tag_dict(el)
    linked, contains, polygon, reason = _element_link(poi, el, meta)
    if not linked:
        return [], [], [f"unlinked OSM element ignored ({reason})"]

    osm_ref = f"{el.get('type', 'element')}/{el.get('id', '?')}"
    location = "polygon contains POI" if contains else "element"
    candidates: list[dict] = []
    conflicts: list[str] = []
    notes: list[str] = []

    indoor_explicit = (
        _as_bool(tags.get("indoor"))
        or str(tags.get("location", "")).lower() == "indoor"
        or _as_bool(tags.get("indoor_seating"))
    )
    outdoor_explicit = (
        _as_bool(tags.get("outdoor"))
        or str(tags.get("location", "")).lower() == "outdoor"
        or _as_bool(tags.get("outdoor_seating"))
    )

    building = str(tags.get("building", "")).lower()
    building_enclosed = bool(
        building and building not in {"no", "roof"}
        and _polygon_evidence(el, meta, polygon, linked)
    )
    shelter_amenity = str(tags.get("amenity", "")).lower() in _OSM_SHELTER_AMENITIES
    r2_shelter = (
        building == "roof"
        or _as_bool(tags.get("covered"))
        or _as_bool(tags.get("roof"))
        or _as_bool(tags.get("awning"))
        or _as_bool(tags.get("canopy"))
        or _as_bool(tags.get("shelter"))
        or shelter_amenity
        or str(tags.get("man_made", "")).lower() in {"canopy", "awning", "shelter"}
    )

    indoor_category = False
    for key, values in _OSM_INDOOR.items():
        if str(tags.get(key, "")).lower() in values:
            indoor_category = True
            break
    if tags.get("shop"):
        indoor_category = True
    if building == "roof" and not (indoor_explicit or building_enclosed):
        # A roof-only building is not an enclosed space even if a category tag
        # (cafe, museum, shop, ...) is present.  R2 cannot become R1.
        indoor_category = False

    outdoor_category = False
    for key, values in _OSM_OUTDOOR.items():
        if str(tags.get(key, "")).lower() in values:
            outdoor_category = True
            break

    ambiguous = []
    for key, values in _OSM_AMBIGUOUS.items():
        value = str(tags.get(key, "")).lower()
        if value in values:
            ambiguous.append(f"{key}={value}")

    if ambiguous:
        notes.append(f"ambiguous OSM tag(s) {', '.join(ambiguous)} -> no space inference")

    # Space inference.  R2 shelters are rain-only; they never establish indoor
    # and never create "both" from a partial roof.
    both_explicit = (
        (indoor_explicit and outdoor_explicit)
        or (indoor_explicit and (outdoor_explicit or outdoor_category))
        or (outdoor_explicit and (indoor_explicit or building_enclosed
                                  or indoor_category))
    )
    if both_explicit:
        candidates.append(_candidate(
            "both", "osm", CONF_OSM,
            f"OSM {osm_ref} explicit indoor+outdoor evidence ({location})",
            priority=4))
    else:
        if indoor_explicit:
            candidates.append(_candidate(
                "indoor", "osm", CONF_OSM,
                f"OSM {osm_ref} indoor tag ({location})", priority=3))
        if building_enclosed:
            candidates.append(_candidate(
                "indoor", "osm", CONF_OSM,
                f"OSM {osm_ref} building={building} enclosed polygon ({location})",
                priority=2))
        if indoor_category:
            candidates.append(_candidate(
                "indoor", "osm", CONF_OSM,
                f"OSM {osm_ref} indoor category tags", priority=1))
        if outdoor_explicit:
            candidates.append(_candidate(
                "outdoor", "osm", CONF_OSM,
                f"OSM {osm_ref} outdoor tag ({location})", priority=3))
        if outdoor_category:
            candidates.append(_candidate(
                "outdoor", "osm", CONF_OSM,
                f"OSM {osm_ref} outdoor category tags", priority=1))
        if r2_shelter and not (indoor_explicit or building_enclosed
                               or indoor_category or outdoor_explicit
                               or outdoor_category):
            # R2 is covered but open-sided, so when nothing else determines the
            # space it is outdoor (never enclosed, never "both").
            candidates.append(_candidate(
                "outdoor", "osm", CONF_OSM,
                f"OSM {osm_ref} R2 shelter is open-sided outdoor space",
                priority=0))

    # Internal OSM conflicts (e.g. museum + park without explicit both tags).
    labels = {c["label"] for c in candidates}
    if len(labels) > 1 and "both" not in labels:
        conflicts.append("osm space conflict: " +
                         ", ".join(sorted(labels)))
        top = max(c["priority"] for c in candidates)
        top_labels = {c["label"] for c in candidates if c["priority"] == top}
        if len(top_labels) == 1:
            winner = top_labels.pop()
            candidates = [c for c in candidates if c["label"] == winner]
        else:
            candidates = [_candidate(
                "unknown", "osm", CONF_CONFLICT,
                f"OSM {osm_ref} conflicting indoor/outdoor evidence", priority=0)]
    elif "both" in labels:
        candidates = [c for c in candidates if c["label"] == "both"]

    return candidates, conflicts, notes


def _sun_only_evidence(tags: dict) -> list[str]:
    """Sun-only tags: shade/protection from sun is NOT rain protection."""
    hits = []
    for key, value in _OSM_SUN_ONLY_TAGS:
        if str(tags.get(key, "")).lower() == value:
            hits.append(f"{key}={value}")
    return hits


def _scan_osm_rain(poi: dict, el: dict, meta: dict):
    """Return (candidates, notes) from linked OSM evidence only."""
    tags = _tag_dict(el)
    linked, contains, polygon, reason = _element_link(poi, el, meta)
    if not linked:
        return [], []

    osm_ref = f"{el.get('type', 'element')}/{el.get('id', '?')}"
    location = "polygon contains POI" if contains else "element"
    candidates: list[dict] = []
    notes: list[str] = []

    building = str(tags.get("building", "")).lower()
    indoor_value = str(tags.get("indoor", "")).lower()
    indoor = (_as_bool(indoor_value)
              or indoor_value == "room"
              or str(tags.get("location", "")).lower() == "indoor"
              or _as_bool(tags.get("enclosed")))
    building_enclosed = bool(
        building and building not in {"no", "roof"}
        and _polygon_evidence(el, meta, polygon, linked)
    )
    if indoor or building_enclosed:
        detail = ("explicit indoor/enclosed tag" if indoor
                  else f"building={building} linked polygon")
        candidates.append(_candidate(
            "enclosed", "osm", CONF_OSM,
            f"OSM {osm_ref} {detail} ({location})", priority=3))

    sun_only = _sun_only_evidence(tags)
    sun_name_hits = _hit(str(tags.get("name", "")), _NAME_SUN_ONLY)
    sun_only.extend(f"name={hit}" for hit in sun_name_hits)

    sheltered_notes = []
    if building == "roof":
        sheltered_notes.append("building=roof")
    if _as_bool(tags.get("covered")):
        sheltered_notes.append("covered=yes")
    if _as_bool(tags.get("roof")):
        sheltered_notes.append("roof=yes")
    if _as_bool(tags.get("awning")):
        sheltered_notes.append("awning=yes")
    if _as_bool(tags.get("canopy")):
        sheltered_notes.append("canopy=yes")
    if _as_bool(tags.get("shelter")):
        sheltered_notes.append("shelter=yes")
    weather_protection = str(tags.get("weather_protection", "")).lower()
    if weather_protection in {"roof", "awning", "canopy"}:
        sheltered_notes.append(f"weather_protection={weather_protection}")
    if str(tags.get("amenity", "")).lower() in _OSM_SHELTER_AMENITIES:
        # A sun shelter is not rain protection unless some explicit cover tag
        # (roof/covered/awning/canopy/...) is also present.
        if sun_only and not sheltered_notes:
            notes.append(
                f"sun-only evidence(s) {', '.join(sun_only)}: "
                f"amenity={tags.get('amenity')} ignored for rain protection")
        else:
            sheltered_notes.append(f"amenity={tags.get('amenity')}")
    if str(tags.get("man_made", "")).lower() in {"canopy", "awning", "shelter"}:
        sheltered_notes.append(f"man_made={tags.get('man_made')}")
    if sheltered_notes:
        candidates.append(_candidate(
            "sheltered", "osm", CONF_OSM,
            f"OSM {osm_ref} R2 shelter: {', '.join(sheltered_notes)} ({location})",
            priority=2))

    for key, values in _OSM_OPEN.items():
        if str(tags.get(key, "")).lower() in values:
            candidates.append(_candidate(
                "none", "osm", CONF_OSM,
                f"OSM {osm_ref} clear open {key}={tags.get(key)} ({location})",
                priority=1))
            break

    for item in sun_only:
        notes.append(f"sun-only tag {item} ignored for rain protection")

    return candidates, notes


def _analyse_osm(poi: dict, osm) -> dict:
    space_candidates: list[dict] = []
    rain_candidates: list[dict] = []
    conflicts: list[str] = []
    notes: list[str] = []

    for item in _iter_osm(osm):
        el, meta = _split_wrapper(item)
        if not isinstance(el, dict):
            notes.append("ignored non-dict OSM evidence")
            continue
        sc, cf, nt = _scan_osm_space(poi, el, meta)
        space_candidates.extend(sc)
        conflicts.extend(cf)
        notes.extend(nt)
        rc, rn = _scan_osm_rain(poi, el, meta)
        rain_candidates.extend(rc)
        notes.extend(rn)

    space = None
    if space_candidates:
        labels = {c["label"] for c in space_candidates}
        if "both" in labels:
            chosen = next(c for c in space_candidates if c["label"] == "both")
        elif len(labels) == 1:
            chosen = space_candidates[0]
        else:
            conflicts.append("osm space conflict: " + ", ".join(sorted(labels)))
            chosen = _candidate(
                "unknown", "osm", CONF_CONFLICT,
                "conflicting OSM space evidence", priority=0)
        space = {**chosen, "conflict": bool(conflicts)}

    return {
        "space": space,
        "rain_candidates": rain_candidates,
        "conflicts": conflicts,
        "notes": notes,
    }


def _analyse_name(poi: dict) -> dict:
    name = _poi_name(poi)
    indoor = _hit(name, _NAME_INDOOR)
    outdoor = _hit(name, _NAME_OUTDOOR)
    both = _hit(name, _NAME_BOTH)
    sun = _hit(name, _NAME_SUN_ONLY)
    ambiguous = _hit(name, _NAME_AMBIGUOUS)

    notes: list[str] = []
    if sun:
        notes.append(f"sun-only name keyword(s) {', '.join(sun)} ignored for rain")
    if ambiguous:
        notes.append(f"ambiguous name keyword(s) {', '.join(ambiguous)} ignored")

    space = None
    conf = CONF_NAME
    evidence: list[str] = []
    conflicts: list[str] = []

    if both:
        space = "both"
        evidence.append(f"name compound keyword(s) {', '.join(both)} -> both")
    elif indoor and outdoor:
        # A venue/establishment keyword names the visit space; an outdoor word
        # in a business name (address `Đào`, brand `Beach Hotel`, proper name
        # `Cầu Út`) is context, not a second space.  This is what used to turn
        # clear cafes/hotels into `unknown`.
        space = "indoor"
        evidence.append(
            f"name venue keyword(s) {', '.join(indoor)} beat descriptive "
            f"outdoor keyword(s) {', '.join(outdoor)} -> indoor")
    elif indoor:
        space = "indoor"
        evidence.append(f"name indoor keyword(s) {', '.join(indoor)}")
    elif outdoor:
        space = "outdoor"
        evidence.append(f"name outdoor keyword(s) {', '.join(outdoor)}")

    # Name keywords inform `space` only: a name can never assert rain
    # protection (R1/R2/none).  Rain needs linked OSM evidence.
    return {
        "space": space,
        "conf": conf,
        "evidence": evidence,
        "conflicts": conflicts,
        "rain": None,
        "notes": notes,
    }


def _canonical_hint(text: str) -> dict:
    return {
        "indoor": _hit(text, _NAME_INDOOR),
        "outdoor": _hit(text, _NAME_OUTDOOR),
        "both": _hit(text, _NAME_BOTH),
        "ambiguous": _hit(text, _NAME_AMBIGUOUS),
    }


def _analyse_canonical(poi: dict) -> dict:
    cat = _norm(poi.get("cat", "")).strip()
    parts = [poi.get("type", "")]
    tags = poi.get("tags", [])
    if isinstance(tags, list):
        parts.extend(str(t) for t in tags)
    elif isinstance(tags, dict):
        parts.extend(str(v) for v in tags.values())
    text = " | ".join(str(p) for p in parts if p)
    hint = _canonical_hint(text)

    space = "unknown"
    evidence = ""
    source_hint = ""

    if cat in _CAT_INDOOR:
        space = "indoor"
        source_hint = f"canonical cat={cat}"
    elif cat in _CAT_OUTDOOR:
        space = "outdoor"
        source_hint = f"canonical cat={cat}"
    elif cat in _CAT_AMBIGUOUS:
        # An otherwise-clear type may still resolve an ambiguous category
        # (e.g. cat=attraction + type=Bãi biển, cat=landmark + Tượng đài).
        if hint["both"]:
            space = "both"
            source_hint = f"canonical type/tags ({', '.join(hint['both'])})"
        elif hint["indoor"]:
            # A venue keyword (cafe/hotel/pagoda compound...) decides, even if
            # an outdoor word also appears in the type.
            space = "indoor"
            source_hint = f"canonical type/tags ({', '.join(hint['indoor'])})"
        elif hint["outdoor"]:
            space = "outdoor"
            source_hint = f"canonical type/tags ({', '.join(hint['outdoor'])})"
        else:
            space = "unknown"
            evidence = f"canonical cat={cat} is ambiguous -> unknown"
    elif hint["both"]:
        space = "both"
        source_hint = f"canonical type/tags ({', '.join(hint['both'])})"
    elif hint["indoor"] and not hint["outdoor"] and not hint["ambiguous"]:
        space = "indoor"
        source_hint = f"canonical type/tags ({', '.join(hint['indoor'])})"
    elif hint["outdoor"] and not hint["indoor"] and not hint["ambiguous"]:
        space = "outdoor"
        source_hint = f"canonical type/tags ({', '.join(hint['outdoor'])})"
    else:
        evidence = "canonical category/type absent or ambiguous -> unknown"

    if not evidence:
        evidence = f"{source_hint} -> {space} (heuristic default)"
    evidence += f" [conf {CONF_CANONICAL}, uncalibrated]"

    # Canonical categories inform `space` only: they never assert rain
    # protection.  Rain needs linked OSM evidence.
    return {"space": space, "rain": None, "evidence": evidence, "cat": cat}


def _pick_rain(space: str, audit_space: str | None,
               osm_rain: list[dict], notes: list[str]) -> dict:
    """Pick rain protection from linked OSM candidates ONLY.

    The audit, name keywords and canonical category cannot create a rain
    label; they only shape `space`.
    """
    candidates: list[dict] = list(osm_rain)

    # "Both" is not the same as enclosed/none: it needs a covered part.
    allowed = {
        "indoor": {"enclosed", "sheltered"},
        "outdoor": {"sheltered", "none", "unknown"},
        "both": {"sheltered", "unknown"},
        "unknown": {"enclosed", "sheltered", "none", "unknown"},
    }[space]
    if audit_space == "outdoor":
        allowed -= {"enclosed"}
    elif audit_space == "both":
        allowed &= {"sheltered", "unknown"}

    filtered = []
    for cand in candidates:
        if cand["label"] in allowed:
            filtered.append(cand)
        else:
            notes.append(
                f"rain evidence {cand['label']} from {cand['source']} ignored "
                f"(incompatible with space={space})")

    if not filtered:
        return {"label": "unknown", "source": "unknown",
                "conf": CONF_CANONICAL,
                "evidence": "no linked OSM rain-protection evidence -> unknown"}

    return max(filtered, key=lambda c: (c["conf"],
                                        _RAIN_PRIORITY.get(c["label"], 0),
                                        _SOURCE_PRIORITY.get(c["source"], 0)))


def classify_poi(poi: dict, audit=None, osm=None, *, human_label=None,
                 audit_label=None, osm_evidence=None) -> dict:
    """Classify one snapshot POI's space + rain protection.

    Parameters
    ----------
    poi:
        Snapshot POI dict (``name``, ``lat``/``lon``, ``cat``, ``type``,
        ``tags``, optional ``io_label``).  Pure: the input is not mutated.
    audit:
        Optional human I/O/B label (``"I"``/``"O"``/``"B"``, ``"indoor"``,
        ``"outdoor"``, ``"both"``, or a dict with ``label``/``space``/
        ``io_label``/``io``).  If omitted, ``poi["io_label"]`` is used.
        ``human_label``/``audit_label`` are accepted aliases.
    osm:
        Optional OSM element, wrapper ``{"element": ..., "name_linked": bool,
        "point_in_polygon": bool}``, or list of either.  Polygon geometry must
        be supplied; a node-only cache cannot prove containment.
        ``osm_evidence`` is an accepted alias.  If both are omitted, a POI's
        nested ``osm_evidence`` dict is used only when it contains an
        element/tags/geometry payload.

    Returns
    -------
    dict
        ``space``, ``space_source``, ``space_confidence``, ``space_evidence``,
        ``space_conflict``, ``rain_protection``, ``rain_protection_source``,
        ``rain_protection_confidence``, ``rain_protection_evidence``,
        ``weather_sensitive``, ``confidence_kind`` and the continuous
        exposure fields ``outdoor_exposure``, ``sun_exposure``,
        ``wind_exposure``, ``rain_cover`` plus ``exposure_source``.

    Confidence is HEURISTIC and UNCALIBRATED, not a probability.
    """
    if not isinstance(poi, dict):
        raise TypeError("poi must be a dict")
    if audit is None:
        audit = human_label if human_label is not None else audit_label
    if osm is None:
        osm = osm_evidence
    if osm is None and isinstance(poi.get("osm_evidence"), dict):
        candidate = poi["osm_evidence"]
        if any(k in candidate for k in
               ("element", "elements", "tags", "geometry", "coordinates")):
            osm = candidate

    space_conflict: list[str] = []
    space_evidence: list[str] = []
    rain_notes: list[str] = []

    audit_space, audit_origin, invalid_audit = _parse_audit(audit, poi)
    if invalid_audit is not None:
        space_evidence.append(f"ignored invalid audit label {invalid_audit!r}")

    osm_res = _analyse_osm(poi, osm)
    name_res = _analyse_name(poi)
    canon_res = _analyse_canonical(poi)
    space_conflict.extend(osm_res["conflicts"])
    rain_notes.extend(osm_res["notes"])
    rain_notes.extend(name_res["notes"])

    osm_space = osm_res["space"]
    name_space = name_res["space"]
    canon_space = canon_res["space"]

    if audit_space:
        space = audit_space
        source = "audit"
        conf = CONF_AUDIT
        space_evidence.append(
            f"{audit_origin or 'audit'}={audit_space} (human audit wins)")
        audit_tag = audit_origin or "audit"
        for other_label, other_source in ((osm_space, "osm"),
                                          (name_space, "name")):
            if not other_label or other_label == "unknown" \
                    or other_label == audit_space:
                continue
            if audit_space == "both" and other_label in ("indoor", "outdoor"):
                continue  # "both" includes either component
            space_conflict.append(
                f"{audit_tag}={audit_space} vs "
                f"{other_source}={other_label}")
        space_conflict.extend(name_res["conflicts"])
    elif osm_space:
        space = osm_space["label"]
        source = "osm"
        conf = CONF_CONFLICT if osm_space.get("conflict") else CONF_OSM
        space_evidence.append(osm_space["evidence"])
        if name_space in ("indoor", "outdoor", "both"):
            if name_space == space:
                conf = max(conf, CONF_OSM_NAME) if conf > CONF_CONFLICT else conf
                space_evidence.extend(name_res["evidence"])
            elif space == "both" and name_space in ("indoor", "outdoor"):
                # "both" legitimately includes either component.
                space_evidence.extend(name_res["evidence"])
            else:
                space_conflict.append(f"osm={space} vs name={name_space}")
                conf = CONF_CONFLICT
        elif name_space == "unknown" and name_res["conflicts"]:
            space_conflict.extend(name_res["conflicts"])
    elif name_space:
        space = name_space
        source = "name"
        conf = name_res["conf"]
        space_evidence.extend(name_res["evidence"])
        space_conflict.extend(name_res["conflicts"])
    else:
        space = canon_space
        source = "canonical"
        conf = CONF_CANONICAL
        space_evidence.append(canon_res["evidence"])

    if not space_evidence:
        space_evidence.append(canon_res["evidence"])

    # OSM + agreeing name confidence boost for non-audit, non-conflict space.
    if source == "osm" and name_space == space and conf > CONF_CONFLICT:
        conf = CONF_OSM_NAME

    # Rain protection -------------------------------------------------------
    # The audit, name and canonical category decide `space` only.  Rain must
    # come from linked OSM evidence; otherwise it stays `unknown`.
    rain = _pick_rain(
        space=space,
        audit_space=audit_space,
        osm_rain=osm_res["rain_candidates"],
        notes=rain_notes,
    )

    if not audit_space and space_conflict and rain["label"] != "unknown":
        # Preserved non-audit conflicts cap both space and rain at the conflict
        # tier.  Audits stay authoritative and their conflicts remain metadata.
        rain = {**rain, "conf": min(rain["conf"], CONF_CONFLICT)}

    rain_evidence = [rain["evidence"]]
    if rain["label"] == "unknown":
        rain_evidence.append("abstained: absent evidence is not proof of no cover")
    if audit_space:
        rain_evidence.append(
            f"audit {audit_space} does not encode rain protection")
    rain_evidence.extend(rain_notes)

    exposure = derive_exposure(
        audit_space=audit_space,
        osm_space=(osm_space or {}).get("label") if isinstance(osm_space, dict)
        else None,
        osm_rain=rain["label"] if rain["source"] == "osm" else None,
        cat=canon_res["cat"],
    )

    # Derived conservative weather sensitivity.
    if audit_space:
        weather_sensitive = audit_space != "indoor"
    else:
        weather_sensitive = not (space == "indoor" and conf >= 0.5)

    return {
        "space": space,
        "space_source": source,
        "space_confidence": round(float(conf), 3),
        "space_evidence": space_evidence,
        "space_conflict": space_conflict,
        "rain_protection": rain["label"],
        "rain_protection_source": rain["source"],
        "rain_protection_confidence": round(float(rain["conf"]), 3),
        "rain_protection_evidence": rain_evidence,
        "weather_sensitive": bool(weather_sensitive),
        "confidence_kind": "heuristic_uncalibrated",
        **exposure,
    }


# Alias with the "snapshot" wording used by later wiring specs.
classify_snapshot_poi = classify_poi
