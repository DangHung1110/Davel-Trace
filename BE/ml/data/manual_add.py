"""Apply manual_pois.json sidecar into snapshot (lane A, idempotent).

Skips entries with skip=true or poi_id already present. Enriches duration/
intensity/ws/tags via the same rule functions as other sources.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None

from BE.ml.data.enrich_snapshot import INTENSITY_DEFAULT, WS_DEFAULT  # noqa: E402
from BE.ml.data.enrich_tags import tag_poi  # noqa: E402
from BE.ml.patm.estimate_duration import canonical_category, enrich_poi  # noqa: E402

BAND = [(100000, "cheap"), (500000, "medium"), (float("inf"), "expensive")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    path = os.path.join(args.snapshot, "pois.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(args.snapshot, "manual_pois.json"), encoding="utf-8") as f:
        manual = json.load(f)
    have = {p["poi_id"] for p in data["pois"]}
    added = 0
    for m in manual:
        if m.get("skip") or m["poi_id"] in have:
            continue
        p = {"poi_id": m["poi_id"], "name": m["name"], "type": m["type"],
             "lat": m["lat"], "lon": m["lon"],
             "opening_hours": m.get("opening_hours", []),
             "hours_source": m.get("hours_source", ""),
             "price_level": 2, "fee": 0, "rating": m.get("rating"),
             "tags": [m["type"]], "source": "manual+web",
             "fetched_at": datetime.date.today().isoformat(),
             "verified": False}
        enrich_poi(p)
        canon = canonical_category(p["type"])
        p["cat"] = m.get("cat", canon)
        p["intensity"] = INTENSITY_DEFAULT.get(canon, 2)
        p["intensity_source"] = "canonical_rule"
        p["weather_sensitive"] = WS_DEFAULT.get(canon, False)
        p["ws_source"] = "canonical_rule"
        p["io_label"] = None
        t, src = tag_poi(p)
        p["smart_tags"] = t
        p["smart_tag_source"] = m.get("smart_tag_source", src)
        if m.get("ticket") is not None:
            p["smart_tags"]["ticket"] = m["ticket"]
        if m.get("ticket_vnd") is not None:
            p["ticket_vnd"] = m["ticket_vnd"]
            p["smart_tags"]["price_band"] = next(
                b for lim, b in BAND if m["ticket_vnd"] < lim)
            p["smart_tags"]["ticket"] = True
        if m.get("ticket_note"):
            p["ticket_note"] = m["ticket_note"]
        if m.get("price_sources"):
            p["price_sources"] = m["price_sources"]
        if m.get("excursion"):
            p["excursion"] = True
            p["smart_tags"]["budget"] = ["full-day"]
        data["pois"].append(p)
        added += 1
    data["count"] = len(data["pois"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"added {added} -> total {len(data['pois'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
