# Task for Codex — real per-person prices for 100 POIs (read pages only, do not guess)

Write ONE file: `reports/p0/links/prices_codex.json`. Do not edit other files. Do not commit.
Generic User-Agent `davel-trace-data/0.1`. Batch network reads into as few commands as possible.
NOT allowed: Google Maps/place data, AI answers, generic statements ("quán bình dân 30-50k").

Input `reports/p0/links/price_candidates.json` (100 POIs whose price tier is a category estimate:
43 restaurants, 41 day markets, 12 paid attractions/classes, 3 night markets, 1 landmark).

## What to find (one row per POI, same order)
- Restaurants / markets / night markets: what ONE adult typically spends for one meal/visit, from a page that names
  THIS place: menu with prices (own site, fanpage text, ShopeeFood/GrabFood menu page, Foody), or a review/guide
  that states prices ("tô mì 35.000đ", "giá 30-60k/món"). Give min/max/typical per person in VND.
  Markets: price of typical dishes/snacks sold there (not souvenirs); free entry.
- Paid attractions / classes: adult ticket or class price (VND; if USD, give USD as written + VND at 25,000 VND/USD and say so).
- Mandatory extras you see (parking, boat) -> put in note only.

Row: {"poi_id","name","typical_vnd": int|null,"min_vnd": int|null,"max_vnd": int|null,"free_entry": bool|null,
"currency_note": "...","evidence_url","quote": "exact sentence(s)","published_or_updated","note"}
null when nothing readable states it. Reply DONE when the file is written.
