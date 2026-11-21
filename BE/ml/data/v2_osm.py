"""v1-shaped record for a new OSM POI (danang-v2 build, `migrate_v2._base_from_osm`).

Kept from the retired `BE/ml/data/osm_add.py` (removed on main as a one-off
script): only the part the v2 build calls. Duration / intensity / smart tags
still come from the shared helpers (`BE.ml.patm.estimate_duration`,
`BE.ml.data.enrich_snapshot`, `BE.ml.data.enrich_tags`).
"""

from __future__ import annotations

import datetime
import re

from BE.ml.patm.estimate_duration import canonical_category, enrich_poi

# OSM tag -> Vietnamese raw type (feeds canonical_category downstream)
VI_TYPE = {
    "hotel": "Khách sạn", "motel": "Khách sạn", "resort": "Khu nghỉ dưỡng",
    "hostel": "Nhà nghỉ", "guest_house": "Nhà nghỉ",
    "viewpoint": "Điểm ngắm cảnh", "museum": "Bảo tàng", "gallery": "Phòng trưng bày",
    "attraction": "Điểm thu hút khách du lịch", "theme_park": "Công viên giải trí",
    "gift": "Cửa hàng quà lưu niệm", "souvenir": "Cửa hàng quà lưu niệm",
    "marketplace": "Chợ", "place_of_worship": "Cơ sở thờ tự",
    "church": "Nhà thờ", "pagoda": "Chùa",
    "beach": "Bãi biển", "peak": "Đỉnh núi", "cave_entrance": "Hang động",
    "waterfall": "Thác nước", "spring": "Suối", "memorial": "Đài tưởng niệm",
    "monument": "Tượng đài", "stadium": "Sân vận động", "park": "Công viên",
    "zoo": "Vườn thú",
}


def osm_hours_to_schema(raw: str) -> tuple[list[str], str]:
    """OSM opening_hours ('Mo-Fr 08:00-18:00; Sa 09:00-12:00') -> ['08:00-18:00', ...]
    (day info stays in the raw string). Unparseable -> ([], raw)."""
    times = re.findall(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", raw or "")
    seen = list(dict.fromkeys(f"{a}-{b}" for a, b in times))
    if seen and re.match(r"^[\w\s,;\-:+]+$", raw or ""):
        return seen, raw
    return [], raw


def to_poi(el, c, la, lo, name, tags) -> dict:
    from BE.ml.data.enrich_snapshot import INTENSITY_DEFAULT, WS_DEFAULT  # noqa
    from BE.ml.data.enrich_tags import tag_poi  # noqa
    oh, _raw = osm_hours_to_schema((tags or {}).get("opening_hours", ""))
    p = {"poi_id": f"osm:{el.get('type')}/{el.get('id')}", "name": name,
         "type": VI_TYPE.get(c, c), "lat": la, "lon": lo,
         "opening_hours": oh,
         "hours_source": "osm" if oh else "",
         "price_level": 2, "fee": 0, "rating": None,
         "tags": [VI_TYPE.get(c, c)], "source": "osm/overpass",
         "fetched_at": datetime.date.today().isoformat(), "verified": False}
    enrich_poi(p)
    canon = canonical_category(p["type"])
    p["intensity"] = INTENSITY_DEFAULT.get(canon, 2)
    p["intensity_source"] = "canonical_rule"
    p["weather_sensitive"] = WS_DEFAULT.get(canon, False)
    p["ws_source"] = "canonical_rule"
    p["io_label"] = None
    t, src = tag_poi(p)
    p["smart_tags"] = t
    p["smart_tag_source"] = src
    return p
