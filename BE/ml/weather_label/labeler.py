"""Weather labeler indoor/outdoor (T063-M4CODE, lane A). NO TICK (audit pending).

v1 = deterministic tag rules (this file, working now). GBDT/logistic
training hook `train_gbdt()` is implemented and runs when audit labels
exist; until then the rule path serves. Confidence is a HEURISTIC rule
strength — NOT calibrated, NO accuracy claim before the user I/O audit
(real eval bar: macro-F1 >= 0.95, PENDING).

Features per element: tag one-hots (tourism/leisure/amenity/historic/
shop), has_building_polygon (ways only; node-only OSM fetch -> False,
documented gap), area_m2 (ways later; 0.0 now), DN category, name
keywords (bien/cong vien/bao tang...).

STUB-NOTE (phase-PR): `weather_evidence()` output plugs into lane-B
validator weather gate (T018 extension) + lane-C explainer (T042) as
evidence strings — no cross-lane edits from here.
"""

from __future__ import annotations

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
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


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
    """Deterministic rules -> {label, confidence (heuristic), rule}."""
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
    feat = featurize(el, dn_category)
    return {**label(feat), "features": feat}


def weather_evidence(poi_name: str, result: dict) -> list[str]:
    """Evidence strings for validator/explainer wiring (phase-PR)."""
    return [f"{poi_name}: {result['label']} ({result['rule']}, "
            f"conf {result['confidence']})"]


def train_gbdt(X, y, seed: int = 7):
    """GBDT trainer for audit labels (runs when user I/O audit lands)."""
    import lightgbm as lgb
    import numpy as np
    dtr = lgb.Dataset(np.array(X, dtype=float), np.array(y, dtype=float))
    return lgb.train({"objective": "binary", "verbosity": -1, "seed": seed,
                      "min_data_in_leaf": 5, "num_leaves": 15},
                     dtr, num_boost_round=100)
