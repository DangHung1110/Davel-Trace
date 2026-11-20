# Task for Codex — Sơn Trà peninsula controlled-route scope (read pages only, do not guess)

Write ONE file: `reports/p0/links/sontra_route_codex.json`. Do not edit other files. Do not commit.
Generic User-Agent `davel-trace-data/0.1`. Quote exact sentences from pages you actually read.

## Background
Đà Nẵng controls vehicle access to the Sơn Trà peninsula roads: 07:30-18:30 (March–September), 07:30-17:30 (October–February).
Known sources: vietnamnet; Nhân Dân 15/09/2025 (see `BE/data/sources/agent_web_2026-11-19c.json`, Cây Đa note). Find the official
rule/announcement (UBND / Sở Du lịch / BQL bán đảo Sơn Trà) and extract the SCOPE:
which roads/sections are controlled (e.g. from which checkpoint / barrier, which roads: đường lên Đỉnh Bàn Cờ, Hải đăng, Chùa Linh Ứng?, Bãi Bụt, Bãi Rạng, Bãi Bắc, Ghềnh Bàng, Hoàng Sa / Yết Kiêu coastal road?), what is exempt (residents, hotel guests, Linh Ứng pilgrims?), and whether walking/cycling is also restricted.

## Classify
For each POI in `reports/p0/links/son_tra_candidates.json` (46 active POIs in the bbox) decide:
- `on_route`: only reachable through the controlled section → visit must fit the window.
- `off_route`: reachable without passing the controlled section (city side, Thọ Quang, Sơn Trà Marina, coastal Hoàng Sa road before the barrier, etc.).
- `unknown`: sources do not settle it.
Use road geometry (OSM/Nominatim/Overpass: barrier/checkpoint nodes, road names) + the scope text. Give a one-line reason per POI.

## Output
{"rule": {"scope_text": "...", "windows": {"mar_sep": "07:30-18:30", "oct_feb": "07:30-17:30"}, "exemptions": "...",
          "checkpoints": [{"name": "...", "lat": 0, "lon": 0, "source": "..."}], "sources": [{"url": "...", "quote": "...", "date": "..."}]},
 "pois": [{"poi_id": "...", "name": "...", "class": "on_route|off_route|unknown", "reason": "..."}]}
Reply DONE when the file is written.
