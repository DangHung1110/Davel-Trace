# Task for Codex — clean popularity signal: travel-guide mentions (read pages only)

Write TWO files: `reports/p0/links/guide_pages_codex.json` (the pages you read) and
`reports/p0/links/guide_mentions_codex.json` (counts). Do not edit other files. Do not commit.
Generic User-Agent `davel-trace-data/0.1`. Batch network reads. NOT allowed: Google Maps/place data/ratings, AI answers.

Goal: for each of the 869 POIs in `reports/p0/links/popularity_pois.json`, count in how many independent
travel-guide / "best of" pages it is recommended. This replaces Google rating as a clean popularity prior.

## Pages (aim 30–50, Vietnamese + English, 2024–2026 preferred)
Mix of: city tourism portal (danangfantasticity.com, hoian tourism), big travel sites (vinpearl, vinwonders, mia.vn,
vietnambooking, traveloka/klook blog, nangtrip, Lonely Planet, Culture Trip, TimeOut, hiddenhoian, Foody "top" lists,
Michelin Guide Vietnam (Đà Nẵng/Hội An selections), Tripadvisor Travellers' Choice text pages if readable).
Cover: attractions, beaches, pagodas, markets, restaurants/street food, cafes, bars/nightlife, spas — for Đà Nẵng AND Hội An.
Record each page: {"url","title","published_or_updated","topic","zone"} in guide_pages_codex.json.

## Matching
A POI counts as mentioned on a page when the page names it (diacritic-insensitive; allow the core name, e.g. "Mộc Quán"
for "Mộc quán Seafood Đà Nẵng", "Bánh mì Phượng" for "Bánh Mì Phượng"), AND the context is the same city/zone.
Do not count a generic word ("chợ", "biển") as a match. Michelin selection = also set "michelin": true.

## Output guide_mentions_codex.json
[{"poi_id","name","mentions": int, "pages": [url,...], "michelin": bool}]  — include every POI (mentions 0 allowed).
Reply DONE when both files are written.
