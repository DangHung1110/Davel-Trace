# Task for Codex — category audit on a 68-POI random sample (read pages only, do not guess)

Write ONE file: `reports/p0/links/category_audit_codex.json`. Do not edit other files. Do not commit.
Generic User-Agent `davel-trace-data/0.1`. Batch network reads (one Overpass query for all points, then batched pages).
NOT allowed: Google Maps/place data, AI answers.

Input `reports/p0/links/category_sample.json`: 68 active POIs whose category was assigned by name rules.
Allowed categories (pick exactly one): beach, viewpoint, outdoor_landmark, religious, museum_indoor, day_market,
night_market, paid_attraction, restaurant, cafe, nightlife, wellness, lodging.
Meaning: paid_attraction = ticketed park/experience/tour/class; outdoor_landmark = free public place (park, bridge, square, statue);
day_market = daytime market/food court/souvenir shop; night_market = evening market/street; nightlife = bar/pub/club/karaoke/lounge;
wellness = spa/massage; cafe = coffee/tea/dessert shop; restaurant = meal place (incl. street food stall).

For each POI: read OSM tags of the same place (same name within 80 m: amenity/shop/tourism/leisure) and/or a page that names it.
Decide whether the current category is right.

Row (same order): {"poi_id","name","category_now","category_true": "...", "verdict": "ok|wrong|closed|unclear",
"source": "osm|web|name_only", "evidence_url", "quote_or_tags", "note"}
"closed" only when a page states it closed permanently. "unclear" when nothing readable settles it.
At the end add a summary object: {"summary": {"ok": n, "wrong": n, "closed": n, "unclear": n, "wrong_rate_of_decided": x}}
(as the LAST element of the array). Reply DONE when written.
