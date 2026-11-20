# Task for Codex — 3 lookups (read pages only, do not guess). Do them in order; write each file as soon as it is done.

Do not edit other files. Do not commit. Generic User-Agent `davel-trace-data/0.1`.
Batch network reads (one Overpass query per part, then batched page fetches). NOT allowed: Google Maps/place data,
AI answers, generic statements ("spa thường mở 9h-22h"). Quote the exact sentence for every value.
Sources conflict -> narrower common window, say so in note. null when nothing readable states it.

## Part 1 — 13 cooking classes: `reports/p0/links/cooking_sessions_codex.json`
Input `reports/p0/links/cooking_candidates.json`. From the class's own site / booking page (Cookly, Klook, KKday, Viator,
TripAdvisor page text, own website): fixed class sessions (start-end), days not running, price per adult (VND or USD as written),
what is included (market tour, basket boat), booking URL, duration.
Row: {"poi_id","name","sessions": ["08:30-12:30","14:00-18:00"] | [], "closed_days": [], "duration_min": null,
"price_adult": "...", "booking_url": "...", "evidence_url": "...", "quote": "...", "note": "..."}

## Part 2 — outdoor landmarks + day markets (69): `reports/p0/links/outdoor_market_codex.json`
Input `reports/p0/links/outdoor_market_candidates.json`. OSM opening_hours first (element itself or same-name element within 80 m), then web.
Public open spaces (parks, squares, bridges) with no stated hours -> hours null, note "public, no hours stated".
Row: {"poi_id","name","hours": "05:00-11:00" | null, "closed_days": [], "source": "osm|web|none", "evidence_url", "quote", "note"}

## Part 3 — spa/wellness + nightlife (158): `reports/p0/links/spa_nightlife_codex.json`
Input `reports/p0/links/spa_nightlife_candidates.json`. OSM opening_hours first, then the venue's own website/fanpage text or a
booking page that names the venue. Same row format as Part 2. It is fine to leave many null — only sourced values.

Reply DONE after all 3 files are written.
