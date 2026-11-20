# Task for Codex — opening hours for 80 religious POIs (read pages only, do not guess)

Write ONE file: `reports/p0/links/religious_codex.json`. Do not edit other files. Do not commit.
Generic User-Agent `davel-trace-data/0.1`. **Put ALL network reads in as few commands as possible** (one Overpass query for all
OSM ids/nearby, then batched page fetches) so the user has few approval prompts.

Input: `reports/p0/links/religious_candidates.json` (80 pagodas/churches/temples in Đà Nẵng + Hội An, sorted by prize_prior).
Current hours are a category guess (08:00-11:00, 14:00-16:00) and are probably too narrow.

## Sources allowed (in this order)
1. OSM `opening_hours` tag: for `osm:node/...`/`osm:way/...` ids read the element; for others search Overpass for
   `amenity=place_of_worship` within 80 m with a matching name.
2. A web page that names THIS place and states its visiting hours (official site/fanpage text, Danang Fantasticity,
   vietnamtourism, local news, travel guide). Mass schedules for churches count only as "Mass times", not visiting hours.
3. NOT allowed: Google Maps / Google place data (policy cach_ly), AI answers, generic "chùa thường mở 6h-18h" statements.

## Output (one row per POI, same order)
[{"poi_id": "...", "name": "...", "hours": "06:00-18:00" | null, "closed_days": [] , "kind": "visiting|mass_only|unknown",
  "source": "osm|web|none", "evidence_url": "...", "quote": "exact sentence", "published_or_updated": "...", "note": "..."}]
Several windows: "05:00-11:30, 13:30-21:00". If sources conflict, give the NARROWER common window and say so in note.
null when nothing readable states it. Reply DONE when the file is written.
