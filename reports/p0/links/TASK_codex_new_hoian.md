# Task for Codex — hours + price for new Hội An POIs (read pages only, do not guess)

Write ONE file: `reports/p0/links/new_hoian_codex.json`. Do not edit other files. Do not commit.
Generic User-Agent `davel-trace-data/0.1`. Batch network reads. NOT allowed: Google Maps/place data, AI answers, generic statements.

Input `reports/p0/links/new_hoian_candidates.json` (new Hội An POIs from OSM: pagodas, family chapels, Cao Đài temple, Protestant church,
Kazik memorial, 2 art galleries, spas, bars) whose hours are a category guess and/or price unknown.
For each: visiting/opening hours and the adult price (ticket for chapels/galleries if any; typical treatment price per person for spas;
typical drink price for bars) from a page that names THIS place (own site/fanpage text, Hội An tourism portal, travel guide, OSM tags).
Family chapels Trần / Nguyễn Tường: say whether they are in the Hội An old-town ticket list.

Row (same order): {"poi_id","name","hours": "08:00-17:00" | null, "closed_days": [], "typical_vnd": int|null, "min_vnd": int|null,
"max_vnd": int|null, "free_entry": bool|null, "in_old_town_ticket": bool|null, "evidence_url", "quote", "note"}
null when nothing readable states it. Reply DONE when written.
